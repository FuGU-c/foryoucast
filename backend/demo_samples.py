"""Install the six fixed, source-linked demo editions into the local DB.

This module is intentionally an explicit CLI utility. Importing it never
changes the database; the caller must run ``python -m backend.demo_samples
install`` after the audio manifest and files are ready.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import datetime as dt
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from .prepare import ROOT

DATA = ROOT / 'data'
DEFAULT_DB = DATA / 'liquid.db'
DEFAULT_SCRIPTS = ROOT / 'assets' / 'demo' / 'demo-scripts.json'
DEFAULT_MANIFEST = ROOT / 'assets' / 'demo' / 'demo-audio-manifest.json'
DEFAULT_BACKUPS = DATA / 'backups'
PROFILES = ('mila', 'jonas', 'alex', 'sam', 'free-demo', 'medium-demo')


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot read {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return value


def _number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _media_file(url: str, media_root: Path) -> Path:
    parts = urlsplit(url)
    path = unquote(parts.path)
    prefix = '/media/demo-samples/'
    if parts.scheme or parts.netloc or not path.startswith(prefix):
        raise ValueError('Demo audio URLs must use /media/demo-samples/<file>')
    root = media_root.resolve()
    resolved = (root / path.removeprefix('/media/')).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f'Demo audio file is missing or outside media/: {url}')
    return resolved


def validate_inputs(scripts_path: Path, manifest_path: Path, media_root: Path) -> tuple[dict, dict]:
    scripts = _read_json(scripts_path)
    manifest = _read_json(manifest_path)
    catalog = _read_json(DATA / 'catalog.json')
    stories = {item['id']: item for item in catalog.get('stories', [])}
    script_episodes = scripts.get('episodes')
    audio_episodes = manifest.get('episodes')
    if not isinstance(script_episodes, list) or not isinstance(audio_episodes, list):
        raise ValueError('Both JSON files must contain an episodes array')
    scripts_by_id = {item.get('profile_id'): item for item in script_episodes if isinstance(item, dict)}
    audio_by_id = {item.get('profile_id'): item for item in audio_episodes if isinstance(item, dict)}
    if (len(script_episodes) != len(PROFILES) or len(audio_episodes) != len(PROFILES)
            or len(scripts_by_id) != len(script_episodes) or len(audio_by_id) != len(audio_episodes)
            or set(scripts_by_id) != set(PROFILES) or set(audio_by_id) != set(PROFILES)):
        raise ValueError(f'Expected exactly these six sample profiles: {", ".join(PROFILES)}')

    for profile_id in PROFILES:
        script = scripts_by_id[profile_id]
        audio = audio_by_id[profile_id]
        chapters = script.get('chapters')
        timings = audio.get('chapters')
        if not isinstance(chapters, list) or not 4 <= len(chapters) <= 6:
            raise ValueError(f'{profile_id}: script must contain four to six chapters')
        if not isinstance(timings, list) or len(timings) != len(chapters):
            raise ValueError(f'{profile_id}: audio chapter timings must match the script')
        duration = _number(audio.get('duration_seconds'), f'{profile_id} duration_seconds')
        if duration <= 0:
            raise ValueError(f'{profile_id}: audio duration must be positive')
        _media_file(str(audio.get('url', '')), media_root)
        if audio.get('provider') not in {'elevenlabs', 'microsoft-sapi'}:
            raise ValueError(f'{profile_id}: unsupported demo audio provider')
        voices = audio.get('voice_ids', [])
        if not isinstance(voices, list) or any(not isinstance(v, str) or not v for v in voices):
            raise ValueError(f'{profile_id}: voice_ids must be an array of non-empty strings')
        previous_end = 0.0
        for chapter, timing in zip(chapters, timings, strict=True):
            if not isinstance(chapter, dict) or not isinstance(timing, dict):
                raise ValueError(f'{profile_id}: malformed chapter')
            if not chapter.get('story_id') or timing.get('story_id') != chapter['story_id']:
                raise ValueError(f'{profile_id}: manifest chapter order does not match the script')
            story = stories.get(chapter['story_id'])
            if not story or not story.get('curated'):
                raise ValueError(f'{profile_id}: script references a story outside the curated catalog')
            start = _number(timing.get('start_seconds'), f'{profile_id} chapter start_seconds')
            end = _number(timing.get('end_seconds'), f'{profile_id} chapter end_seconds')
            if start < previous_end or end <= start or end > duration + 0.05:
                raise ValueError(f'{profile_id}: invalid or overlapping chapter timing')
            if not chapter.get('claim_source_ids') or not isinstance(chapter.get('sources'), list):
                raise ValueError(f'{profile_id}/{chapter['story_id']}: source evidence is missing')
            expected_ids = list(story.get('claim_source_ids', []))
            expected_sources = [source for source in story['sources'] if source['article_id'] in expected_ids]
            if chapter['claim_source_ids'] != expected_ids or chapter['sources'] != expected_sources:
                raise ValueError(f'{profile_id}/{chapter['story_id']}: source metadata differs from the catalog')
            source_ids = {source.get('article_id') for source in chapter['sources']}
            if not set(chapter['claim_source_ids']) <= source_ids:
                raise ValueError(f'{profile_id}/{chapter['story_id']}: claim source is not in sources')
            for turn in chapter.get('turns', []):
                if turn.get('speaker') not in {'maya', 'leo'} or not turn.get('text'):
                    raise ValueError(f'{profile_id}/{chapter['story_id']}: malformed dialogue turn')
                if not set(turn.get('source_ids', [])) <= set(chapter['claim_source_ids']):
                    raise ValueError(f'{profile_id}/{chapter['story_id']}: turn references an unknown claim source')
            previous_end = end
    return scripts_by_id, audio_by_id


def backup_database(db_path: Path, backup_dir: Path) -> Path:
    if not db_path.is_file():
        raise FileNotFoundError(f'Database does not exist: {db_path}')
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = backup_dir / f'liquid-before-demo-samples-{stamp}.sqlite3'
    suffix = 1
    while target.exists():
        target = backup_dir / f'liquid-before-demo-samples-{stamp}-{suffix}.sqlite3'
        suffix += 1
    source = sqlite3.connect(db_path, timeout=30)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def _profile(profile_id: str) -> dict:
    presets = {
        'mila': ('Mila', 'Dutch investor', 'nl', 'investor', 'balanced',
                 {'markets': 4, 'technology': 3, 'economy': 2, 'energy': 1},
                 'MN', 'coral', 'Europe, technology and the companies shaping tomorrow.', 'premium', True),
        'jonas': ('Jonas', 'German investor', 'de', 'investor', 'detailed',
                  {'markets': 4, 'economy': 3, 'energy': 3, 'technology': 1},
                  'JK', 'sage', 'Fundamentals, the economy and a wider view of the markets.', 'premium', True),
        'alex': ('Alex', 'FX trader', 'en', 'trader', 'detailed',
                 {'forex': 5, 'economy': 5, 'energy': 2, 'markets': 1},
                 'AC', 'lavender', 'Currencies, central banks and the signals behind the moves.', 'premium', True),
        'sam': ('Sam', 'General-news listener', 'en', 'general', 'simple',
                {'world': 4, 'money': 4, 'technology': 2, 'culture': 3},
                'SR', 'sand', 'The bigger picture, without the financial jargon.', 'premium', True),
        'free-demo': ('Free user', 'General-news listener', 'en', 'general', 'simple',
                      {'world': 4, 'money': 4, 'technology': 2, 'culture': 3},
                      'FU', 'slate', 'A simple daily briefing across the biggest stories.', 'free', False),
        'medium-demo': ('Medium user', 'Tech and investor', 'en', 'tech', 'balanced',
                        {'markets': 3, 'technology': 4, 'money': 2, 'economy': 2, 'energy': 1},
                        'MU', 'blue', 'Technology, markets and the forces shaping the next quarter.', 'plus', True),
    }
    name, role, language, goal, depth, interests, initials, color, bio, plan, translation = presets[profile_id]
    return {
        'id': profile_id, 'name': name, 'role': role, 'language': language,
        'news_languages': [language] + (['en'] if language != 'en' else []),
        'goal': goal, 'goals': ['tech', 'investor'] if profile_id == 'medium-demo' else [goal], 'depth': depth, 'interests': interests,
        'initials': initials, 'color': color, 'bio': bio, 'plan': plan,
        'tts_provider': 'device', 'device_voices': {}, 'elevenlabs_voices': {},
        'translate_news': translation, 'ai_settings': {'provider': 'demo', 'personalization_model': '', 'summary_model': '', 'script_model': ''},
        'duration': 5, 'wake_time': '07:30', 'timezone': 'Europe/Brussels',
        'scheduled': False, 'onboarded': True, 'last_listened_at': '2026-11-17T07:30:00+00:00',
        'custom_interests': '', 'symbols': [], 'feedback_count': 0,
    }


def _new_profile() -> dict:
    return {
        'demo_reset_id':now(), 'id': 'new', 'name': 'New listener', 'role': 'Unidentified', 'language': 'en',
        'news_languages': ['en'], 'goal': 'general', 'goals': [], 'goal_tags': [],
        'depth': 'simple', 'interests': {}, 'initials': '+', 'color': 'ink',
        'bio': 'A fresh start. Make this little corner of the world yours.',
        'plan': 'free', 'tts_provider': 'device', 'device_voices': {},
        'elevenlabs_voices': {}, 'translate_news': False,
        'ai_settings': {'provider': 'demo', 'personalization_model': '', 'summary_model': '', 'script_model': ''},
        'duration': 5, 'wake_time': '07:30', 'timezone': 'Europe/Brussels',
        'scheduled': False, 'onboarded': False, 'last_listened_at': None,
        'custom_interests': '', 'symbols': [], 'feedback_count': 0,
    }


def _edition(profile_id: str, script: dict, manifest: dict) -> dict:
    timestamp = now()
    provider = manifest['provider']
    provider_key = 'elevenlabs' if provider == 'elevenlabs' else 'device'
    chapters = []
    for chapter, timing in zip(script['chapters'], manifest['chapters'], strict=True):
        turns = chapter['turns']
        content = '\n'.join(f"{turn['speaker'].title()}: {turn['text']}" for turn in turns)
        start = float(timing['start_seconds'])
        end = float(timing['end_seconds'])
        cache_key = hashlib.sha256(json.dumps({
            'profile_id': profile_id, 'story_id': chapter['story_id'],
            'language': script['language'], 'turns': turns,
            'claim_source_ids': chapter['claim_source_ids'],
        }, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        chapters.append({
            'story_id': chapter['story_id'], 'title': chapter['title'], 'text': content,
            'turns': turns, 'summary': chapter['summary'], 'tags': chapter['tags'],
            'sources': chapter['sources'], 'claim_source_ids': chapter['claim_source_ids'],
            'cache_key': cache_key, 'estimated_seconds': end - start,
            'start_seconds': start, 'end_seconds': end, 'audio': None,
            'attribution_source_id': chapter['claim_source_ids'][0],
            'translated_from_languages': list(dict.fromkeys(
                source['language'] for source in chapter['sources']
                if source['article_id'] in chapter['claim_source_ids'] and source['language'] != script['language']
            )),
            'translated_by_ai': script['language'] not in {
                source['language'] for source in chapter['sources']
                if source['article_id'] in chapter['claim_source_ids']
            },
        })
    duration = float(manifest['duration_seconds'])
    return {
        'id': f'sample-{profile_id}-v1', 'profile_id': profile_id,
        'title': script['title'], 'language': script['language'],
        'depth': _profile(profile_id)['depth'], 'created_at': timestamp,
        'briefing_date': dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo('Europe/Brussels')).date().isoformat(),
        'news_date': script['coverage_date'], 'replay_day': script['coverage_date'],
        'coverage_date': script['coverage_date'], 'target_seconds': script['target_seconds'],
        'estimated_seconds': duration, 'timing_basis': 'measured',
        'status': 'ready', 'demo_sample': True,
        'episode_audio': {'url': manifest['url'], 'duration_seconds': duration, 'timing_basis': 'measured'},
        'chapters': chapters, 'audio_mode': 'elevenlabs' if provider_key == 'elevenlabs' else 'basic-audio',
        'tts_provider': provider_key, 'voice_ids': manifest.get('voice_ids', []),
        'catalog_version': json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))['version'],
        'translation_mode': 'reviewed-demo-summaries',
    }


def apply_demo_plan_defaults(db_path: Path = DEFAULT_DB) -> None:
    """One-time requested plan update, without resetting listener preferences."""
    with closing(sqlite3.connect(db_path, timeout=30)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS demo_seed_migrations(id TEXT PRIMARY KEY)')
        if db.execute('SELECT 1 FROM demo_seed_migrations WHERE id=?', ('horizon-personas-v1',)).fetchone():
            return
        for pid in ('mila', 'jonas', 'alex', 'sam'):
            db.execute("UPDATE profiles SET data=json_set(data,'$.plan','premium') WHERE id=?", (pid,))
        db.execute('INSERT INTO demo_seed_migrations VALUES (?)', ('horizon-personas-v1',))


def ensure_demo_samples(db_path: Path = DEFAULT_DB) -> int:
    """Seed missing sample accounts once; preserve preferences and removed audio.

    An existing edition (including summary-only) is a tombstone for reseeding.
    New listener and all personal history are deliberately left alone.
    """
    apply_demo_plan_defaults(db_path)
    with closing(sqlite3.connect(db_path, timeout=30)) as db:
        if all(db.execute('SELECT 1 FROM editions WHERE id=?', (f'sample-{pid}-v1',)).fetchone() for pid in PROFILES):
            return 0
    scripts, audio = validate_inputs(DEFAULT_SCRIPTS, DEFAULT_MANIFEST, ROOT / 'media')
    from .server import normalized_profile
    inserted = 0
    with closing(sqlite3.connect(db_path, timeout=30)) as db, db:
        for pid in PROFILES:
            eid = f'sample-{pid}-v1'
            if db.execute('SELECT 1 FROM editions WHERE id=?', (eid,)).fetchone():
                continue
            has_personal_edition = bool(db.execute('SELECT 1 FROM editions WHERE profile_id=?', (pid,)).fetchone())
            preset = normalized_profile(_profile(pid))
            if audio[pid]['provider'] == 'elevenlabs':
                preset['tts_provider'] = 'elevenlabs'
            raw = db.execute('SELECT data FROM profiles WHERE id=?', (pid,)).fetchone()
            existing = json.loads(raw[0]) if raw else {}
            # Only replace the untouched bootstrap defaults. Never reset feedback,
            # listening history, or a profile that has already been personalized.
            untouched = not has_personal_edition and not existing.get('demo_reset_id') and not existing.get('feedback_count')
            untouched = untouched and not any(db.execute(f'SELECT 1 FROM {table} WHERE profile_id=? LIMIT 1', (pid,)).fetchone() for table in ('feedback', 'listens', 'story_views'))
            untouched = untouched and not any(key in existing for key in ('interest_resets', 'updated_at', 'preference_revision'))
            untouched = untouched and all(existing.get(key, preset.get(key)) == preset.get(key) for key in ('name', 'language', 'depth', 'interests', 'goal', 'duration', 'wake_time', 'scheduled', 'custom_interests', 'symbols'))
            untouched = untouched and existing.get('plan', 'free') == 'free' and existing.get('tts_provider', 'device') == 'device'
            untouched = untouched and not any(existing.get(key) for key in ('device_voices', 'elevenlabs_voices', 'translate_news'))
            if not raw or untouched:
                # Upgrade only the bootstrap plan defaults on an existing row;
                # retain every other field, including newly introduced settings.
                seeded = {**existing, 'plan': preset['plan'], 'tts_provider': preset['tts_provider'], 'translate_news': preset['translate_news']} if raw else preset
                db.execute('INSERT INTO profiles VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (pid, json.dumps(seeded, ensure_ascii=False)))
            edition = _edition(pid, scripts[pid], audio[pid])
            edition['profile_snapshot'] = preset
            db.execute('INSERT INTO editions VALUES (?,?,?,?)', (eid, pid, json.dumps(edition, ensure_ascii=False), edition['created_at']))
            inserted += 1
    return inserted


def install_demo_samples(
    db_path: Path = DEFAULT_DB,
    scripts_path: Path = DEFAULT_SCRIPTS,
    manifest_path: Path = DEFAULT_MANIFEST,
    backup_dir: Path = DEFAULT_BACKUPS,
    media_root: Path = ROOT / 'media',
) -> Path:
    """Validate, back up, then install the six episodes and reset demo state."""
    db_path, scripts_path, manifest_path = Path(db_path), Path(scripts_path), Path(manifest_path)
    backup_dir, media_root = Path(backup_dir), Path(media_root)
    scripts_by_id, audio_by_id = validate_inputs(scripts_path, manifest_path, media_root)
    for profile_id in PROFILES:
        _media_file(audio_by_id[profile_id]['url'], media_root)
    backup = backup_database(db_path, backup_dir)
    from .server import normalized_profile
    timestamp = now()
    db = sqlite3.connect(db_path, timeout=30)
    try:
        with db:
            db.execute('PRAGMA foreign_keys=ON')
            existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            needed = {'profiles', 'editions', 'feedback', 'listens', 'jobs', 'story_views', 'deliveries', 'provider_keys'}
            if not needed <= existing:
                raise RuntimeError(f'Database schema is incomplete: {sorted(needed-existing)}')
            # Reset only the built-in unidentified placeholder. Other accounts are
            # retained even if present in the local database.
            for table in ('editions', 'feedback', 'listens', 'jobs', 'story_views', 'deliveries', 'provider_keys'):
                db.execute(f'DELETE FROM {table} WHERE profile_id=?', ('new',))
            for table in ('cloud_jobs', 'cloud_outbox', 'cloud_snapshots', 'saved_stories'):
                if table in existing:db.execute(f'DELETE FROM {table} WHERE profile_id=?', ('new',))
            db.execute('INSERT INTO profiles(id,data) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                       ('new', json.dumps(_new_profile(), ensure_ascii=False)))
            for profile_id in PROFILES:
                # Sample feedback and its learned-interest signal are reset so
                # these sample accounts always demonstrate their intended presets.
                db.execute('DELETE FROM feedback WHERE profile_id=?', (profile_id,))
                db.execute('UPDATE profiles SET data=json_set(data,\'$.feedback_count\',0) WHERE id=?', (profile_id,))
                preset=normalized_profile(_profile(profile_id));preset['demo_reset_id']=timestamp
                if audio_by_id[profile_id]['provider']=='elevenlabs' and preset['plan']!='free':preset['tts_provider']='elevenlabs'
                edition = _edition(profile_id, scripts_by_id[profile_id], audio_by_id[profile_id])
                edition['profile_snapshot']=json.loads(json.dumps(preset))
                edition['created_at'] = timestamp
                db.execute('INSERT INTO profiles(id,data) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',
                           (profile_id, json.dumps(preset, ensure_ascii=False)))
                db.execute('INSERT INTO editions(id,profile_id,data,created_at) VALUES (?,?,?,?) '
                           'ON CONFLICT(id) DO UPDATE SET profile_id=excluded.profile_id,data=excluded.data,created_at=excluded.created_at',
                           (edition['id'], profile_id, json.dumps(edition, ensure_ascii=False), timestamp))
    finally:
        db.close()
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Install the six fixed Liquid Briefing sample editions.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    install = subparsers.add_parser('install', help='back up the local database, then install the samples')
    install.add_argument('--db', type=Path, default=DEFAULT_DB)
    install.add_argument('--scripts', type=Path, default=DEFAULT_SCRIPTS)
    install.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    install.add_argument('--backup-dir', type=Path, default=DEFAULT_BACKUPS)
    install.add_argument('--media-root', type=Path, default=ROOT / 'media')
    args = parser.parse_args(argv)
    try:
        backup = install_demo_samples(args.db, args.scripts, args.manifest, args.backup_dir, args.media_root)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f'Demo sample installation failed: {exc}', file=sys.stderr)
        return 1
    print(f'Installed six demo editions. Database backup: {backup}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
