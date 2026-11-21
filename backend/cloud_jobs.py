"""Durable briefing production and advisory cloud radar, independent of FastAPI.

The server module is passed as ``service`` so the worker and HTTP handlers use
the same canonical profiles, ranking, quotas and database without import cycles.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import uuid

from fastapi import HTTPException

from . import audio_production, cloud_client

ACTIVE = ('queued', 'writing', 'checking', 'audio', 'waiting_retry')
MAX_ATTEMPTS = 3


class _AudioRemoved(Exception):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _later(service, seconds):
    return (dt.datetime.fromisoformat(service.now()) + dt.timedelta(seconds=seconds)).isoformat()


def init_tables(service):
    with service.conn() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS cloud_jobs(
          id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,state TEXT NOT NULL,
          stage TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,edition_id TEXT NOT NULL,
          payload TEXT NOT NULL,error TEXT,attempt INTEGER NOT NULL DEFAULT 0,
          next_run TEXT NOT NULL,uncertain INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS cloud_jobs_active_profile ON cloud_jobs(profile_id)
          WHERE state IN ('queued','writing','checking','audio','waiting_retry');
        CREATE TABLE IF NOT EXISTS cloud_outbox(
          profile_id TEXT PRIMARY KEY,revision TEXT NOT NULL,payload TEXT NOT NULL,
          state TEXT NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,next_run TEXT NOT NULL,
          error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cloud_snapshots(
          profile_id TEXT PRIMARY KEY,revision TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cloud_chapter_cache(
          cache_key TEXT PRIMARY KEY,script TEXT,audio TEXT,updated_at TEXT NOT NULL);
        ''')


def _public(row):
    payload = json.loads(row['payload'])
    return {'job_id': row['id'], 'profile_id': row['profile_id'], 'state': row['state'],
            'stage': row['stage'], 'progress': row['progress'], 'edition_id': row['edition_id'],
            'error': row['error'], 'can_retry': row['state'] == 'failed' and not row['uncertain'],
            'natural_pending': bool(payload.get('natural_pending')),
            'uncertain': bool(row['uncertain']), 'created_at': row['created_at'],
            'updated_at': row['updated_at'], 'next_run': row['next_run'] if row['state'] == 'waiting_retry' else None}


def list_jobs(service, pid):
    service.profile(pid)
    with service.conn() as db:
        return [_public(row) for row in db.execute(
            'SELECT * FROM cloud_jobs WHERE profile_id=? ORDER BY created_at DESC LIMIT 30', (pid,))]


def get_job(service, pid, job_id):
    service.profile(pid)
    with service.conn() as db:
        row = db.execute('SELECT * FROM cloud_jobs WHERE id=? AND profile_id=?', (job_id, pid)).fetchone()
    if not row:
        raise HTTPException(404, 'Preparation job not found')
    return _public(row)


def _active(db, pid):
    return db.execute("SELECT * FROM cloud_jobs WHERE profile_id=? AND state IN ('queued','writing','checking','audio','waiting_retry') ORDER BY created_at LIMIT 1", (pid,)).fetchone()


def _select_stories(stories, count, profile):
    remaining = [copy.deepcopy(story) for story in stories if story.get('curated')]
    if profile['plan'] == 'free':
        remaining = [story for story in remaining if any(
            source.get('language') == profile['language'] and source.get('article_id') in story.get('claim_source_ids', [])
            for source in story.get('sources', []))]
    selected, previous = [], set()
    while remaining and len(selected) < count:
        candidates = remaining[:4]
        winner = max(candidates, key=lambda story: float(story.get('score', 0)) + .8 * bool(previous.intersection(story.get('tags', []))))
        remaining.remove(winner)
        selected.append(winner)
        previous = set(winner.get('tags', []))
    return selected


def _voices(service, profile):
    try:
        available = json.loads((Path(service.ROOT) / 'public' / 'voice-samples.json').read_text(encoding='utf-8'))
        pool = [voice['id'] for voice in available if voice.get('language') == profile['language']]
    except (OSError, ValueError, KeyError, TypeError):
        pool = []
    preferred = profile.get('elevenlabs_voices', {}).get(profile['language'], [])
    return list(dict.fromkeys([voice for voice in preferred if voice in pool] + pool))[:2]


def _evidence(service, story):
    result = []
    sources = {source['article_id']: source for source in story.get('sources', [])}
    for identifier in story.get('claim_source_ids', []):
        original = service.read_article(identifier)
        metadata = sources.get(identifier, {})
        if not isinstance(original, dict) or not isinstance(original.get('paragraphs'), list):
            continue
        paragraphs = [paragraph for paragraph in original['paragraphs'] if isinstance(paragraph, str) and paragraph.strip()]
        if not paragraphs:
            continue
        result.append({'article_id': identifier, 'outlet': metadata.get('outlet') or original.get('outlet', ''),
                       'title': original.get('title') or metadata.get('headline', ''),
                       'language': original.get('language') or metadata.get('language'),
                       'url': metadata.get('url') or original.get('url'), 'paragraphs': paragraphs})
    return result


def queue_briefing(service, pid, day=None):
    profile = copy.deepcopy(service.profile(pid))
    init_tables(service)
    with service.conn() as db:
        existing = _active(db, pid)
        if existing:
            return _public(existing)
    service.refresh_catalog()
    if day is not None and day not in service.briefing_dates():
        raise HTTPException(422, 'Choose a date available in this news sample.')
    as_of = dt.datetime.combine(dt.date.fromisoformat(day), dt.time.max, tzinfo=dt.timezone.utc) if day else None
    profile['duration'] = min(max(1, int(profile.get('duration', 5))), {'free': 7, 'plus': 15, 'premium': 40}.get(profile['plan'], 7))
    count = min(12, max(1, round(profile['duration'] / 1.2)))
    stories = _select_stories(service.ranked(pid, for_podcast=True, as_of=as_of), count, profile)
    if not stories:
        raise HTTPException(409, 'No source reports match this podcast language and date.')
    config = cloud_client.connection(service.ROOT)
    voices = _voices(service, profile)
    natural = profile['plan'] != 'free' and profile.get('tts_provider') == 'elevenlabs'
    identifier = 'cloud-' + uuid.uuid4().hex[:16]
    edition_id = 'edition-' + uuid.uuid4().hex[:16]
    timestamp = service.now()
    # All chapter metadata and original evidence are frozen before the job runs.
    profile['selected_voice_ids'] = voices
    chapters = [service.chapter(story, profile) for story in stories]
    for chapter in chapters:
        chapter['audio'] = None
    payload = {'profile': profile, 'stories': stories, 'evidence': [_evidence(service, story) for story in stories],
               'chapters': chapters, 'catalog': {'version': service.CATALOG.get('version'),
                   'replay_day': service.CATALOG.get('replay_day'), 'as_of': service.CATALOG.get('as_of')},
               'ai_enabled': bool(config.get('ai_ready')), 'natural_enabled': natural and bool(config.get('audio_ready')),
               'natural_requested': natural, 'voice_ids': voices, 'request_ids': [],
               'max_words': profile['duration'] * 135, 'target_words': max(40, profile['duration'] * 135 // len(stories)),
               'natural_pending': False, 'paid_inflight': None}
    edition = {'id': edition_id, 'profile_id': pid, 'title': {
        'en': 'Your morning, in perspective', 'nl': 'Je ochtend, in perspectief', 'de': 'Dein Morgen, mit Perspektive'
    }.get(profile['language'], 'Your daily briefing'), 'language': profile['language'], 'depth': profile['depth'],
        'created_at': timestamp, 'replay_day': service.CATALOG.get('replay_day', day),
        'news_date': day or str(service.CATALOG.get('as_of', timestamp))[:10], 'chapters': chapters,
        'estimated_seconds': 0, 'status': 'pending', 'audio_mode': 'preparing', 'episode_audio': None,
        'catalog_version': service.CATALOG.get('version'), 'tts_provider': 'device',
        'requested_tts_provider': profile.get('tts_provider', 'device'),
        'natural_reserved': bool(payload['natural_enabled']), 'voice_ids': voices,
        'requested_duration_minutes': profile['duration'], 'job_id': identifier,
        'profile_snapshot': copy.deepcopy(profile)}
    if hasattr(service, 'normalized_edition'):
        edition = service.normalized_edition(edition)
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = _active(db, pid)
        if existing:
            return _public(existing)
        usage = service.daily_usage(profile, db)
        if not usage['can_create']:
            raise HTTPException(429, 'Your daily Free briefing is ready. Replay it or explore another plan.')
        if profile['plan'] == 'plus' and not usage.get('natural_remaining'):
            payload['natural_enabled'] = payload['natural_requested'] = False
            edition['natural_reserved'] = False
        if payload['natural_enabled'] and len(voices) != 2:
            payload['natural_enabled'] = False
            edition['natural_reserved'] = False
            edition['audio_note'] = 'Two natural voices are not configured for this language; preparing Basic audio.'
        db.execute('INSERT INTO editions(id,profile_id,data,created_at) VALUES (?,?,?,?)',
                   (edition_id, pid, _json(edition), timestamp))
        db.execute('''INSERT INTO cloud_jobs(id,profile_id,state,stage,progress,edition_id,payload,error,
                   attempt,next_run,uncertain,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (identifier, pid, 'queued', 'Queued for preparation', 0, edition_id, _json(payload), None,
                    0, timestamp, 0, timestamp, timestamp))
        row = db.execute('SELECT * FROM cloud_jobs WHERE id=?', (identifier,)).fetchone()
    return _public(row)


def retry_job(service, pid, job_id):
    current = service.profile(pid)
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM cloud_jobs WHERE id=? AND profile_id=?', (job_id, pid)).fetchone()
        if not row:
            raise HTTPException(404, 'Preparation job not found')
        if row['uncertain']:
            raise HTTPException(409, 'The voice request may already have been charged. Check its n8n execution before starting another request.')
        if row['state'] in ACTIVE:
            return _public(row)
        if row['state'] != 'failed':
            raise HTTPException(409, 'This preparation job is already complete.')
        if _active(db, pid):
            raise HTTPException(409, 'Another briefing is already being prepared.')
        usage = service.daily_usage(current, db)
        if not usage['can_create']:
            raise HTTPException(429, 'Your daily briefing allowance is already reserved.')
        payload = json.loads(row['payload'])
        payload.pop('uncertain_audio', None)
        payload['paid_inflight'] = None
        payload['natural_pending'] = False
        payload['natural_attempt'] = 0
        if current['plan'] == 'free' or (current['plan'] == 'plus' and not usage.get('natural_remaining')):
            payload['natural_enabled'] = False
        edition_row = db.execute('SELECT data FROM editions WHERE id=?', (row['edition_id'],)).fetchone()
        if edition_row:
            edition = json.loads(edition_row['data'])
            edition.update({'status': 'pending', 'natural_reserved': bool(payload['natural_enabled'])})
            db.execute('UPDATE editions SET data=? WHERE id=?', (_json(edition), row['edition_id']))
        db.execute("UPDATE cloud_jobs SET state='queued',stage='Queued to resume saved work',progress=0,error=NULL,attempt=0,next_run=?,payload=?,updated_at=? WHERE id=?",
                   (service.now(), _json(payload), service.now(), job_id))
        return _public(db.execute('SELECT * FROM cloud_jobs WHERE id=?', (job_id,)).fetchone())


def _save(service, job, *, state=None, stage=None, progress=None, error=None, edition=None,
          next_run=None, uncertain=None):
    if state is not None:
        job['state'] = state
    if stage is not None:
        job['stage'] = stage
    if progress is not None:
        job['progress'] = max(0, min(100, int(progress)))
    if next_run is not None:
        job['next_run'] = next_run
    if uncertain is not None:
        job['uncertain'] = int(bool(uncertain))
    job['error'] = error
    with service.conn() as db:
        current = db.execute('SELECT data FROM editions WHERE id=?', (job['edition_id'],)).fetchone()
        if current:
            saved = json.loads(current['data'])
            if saved.get('audio_mode') == 'summary-only' or saved.get('audio_removed_at'):
                raise _AudioRemoved()
        db.execute('UPDATE cloud_jobs SET state=?,stage=?,progress=?,payload=?,error=?,attempt=?,next_run=?,uncertain=?,updated_at=? WHERE id=?',
                   (job['state'], job['stage'], job['progress'], _json(job['payload']), error,
                    job['attempt'], job['next_run'], job['uncertain'], service.now(), job['id']))
        if edition is not None:
            db.execute('UPDATE editions SET data=? WHERE id=? AND profile_id=?',
                       (_json(edition), job['edition_id'], job['profile_id']))


def _load_edition(service, job):
    with service.conn() as db:
        row = db.execute('SELECT data FROM editions WHERE id=?', (job['edition_id'],)).fetchone()
    if not row:
        raise ValueError('The reserved edition no longer exists')
    return json.loads(row['data'])


def _ensure_audio_wanted(service, job):
    edition = _load_edition(service, job)
    if edition.get('audio_mode') == 'summary-only' or edition.get('audio_removed_at'):
        raise _AudioRemoved()


def _finish_removed(service, job):
    payload = job['payload']
    payload['natural_pending'] = False
    payload['audio_cancelled'] = True
    spent = bool(payload.get('paid_inflight') or payload.get('uncertain_audio')
                 or any(chapter.get('natural_audio') for chapter in payload['chapters']))
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT data FROM editions WHERE id=?', (job['edition_id'],)).fetchone()
        if row:
            edition = json.loads(row['data'])
            edition.update({'natural_pending': False, 'natural_reserved': spent})
            db.execute('UPDATE editions SET data=? WHERE id=?', (_json(edition), job['edition_id']))
        db.execute("UPDATE cloud_jobs SET state='ready',stage='Audio removed; summary kept',progress=100,payload=?,error=NULL,updated_at=? WHERE id=?",
                   (_json(payload), service.now(), job['id']))


def cancel_edition_audio(service, pid, edition_id):
    """Call after committing a summary-only deletion, including waiting jobs."""
    with service.conn() as db:
        rows = db.execute('SELECT * FROM cloud_jobs WHERE profile_id=? AND edition_id=?', (pid, edition_id)).fetchall()
    for row in rows:
        job = dict(row)
        job['payload'] = json.loads(job['payload'])
        try:
            _ensure_audio_wanted(service, job)
        except _AudioRemoved:
            _finish_removed(service, job)


def _shared_story(story):
    return {field:story.get(field) for field in ('id','updated_at','title','titles','summary','summaries','claim_source_ids','sources')}


def _script_key(payload, index):
    shared_story=_shared_story(payload['stories'][index])
    return _hash({'version': 2, 'story': shared_story, 'evidence': payload['evidence'][index],
                  'language': payload['profile']['language'], 'depth': payload['profile']['depth'],
                  'writer_model': 'gpt-6-luna' if payload['profile']['plan']=='free' else 'gpt-6.1-sol',
                  'review_model': 'gpt-6.1-sol',
                  'target_words': payload['target_words'], 'ai': payload['ai_enabled'],
                  'previous_title': payload['stories'][index - 1].get('title') if index else None,
                  'next_title': payload['stories'][index + 1].get('title') if index + 1 < len(payload['stories']) else None})


def _offline_script(story, profile):
    language = profile['language']
    summary = story.get('summaries', {}).get(language)
    if not story.get('curated') or not isinstance(summary, str) or not summary.strip():
        raise ValueError('A reviewed summary is not available in the requested language')
    identifiers = story.get('claim_source_ids', [])
    supporting = [source for source in story['sources'] if source['article_id'] in identifiers]
    if not supporting or not identifiers:
        raise ValueError('The reviewed story has no approved supporting source')
    outlet = supporting[0]['outlet']
    introduction = {'en': f'According to {outlet}, here is the story.',
                    'nl': f'Volgens {outlet} is dit het verhaal.',
                    'de': f'Laut {outlet} ist dies die aktuelle Meldung.'}[language]
    sentences = re.split(r'(?<=[.!?])\s+', summary.strip())
    split = max(1, len(sentences) // 2)
    first, second = ' '.join(sentences[:split]), ' '.join(sentences[split:])
    if not second:
        first, second = '', summary.strip()
    return {'turns': [
        {'speaker': 'maya', 'text': introduction + (' ' + first if first else ''), 'source_ids': list(identifiers)},
        {'speaker': 'leo', 'text': second, 'source_ids': list(identifiers)}],
        'script_origin': 'reviewed-curated-summary',
        'evidence_review': {'passed': True, 'method': 'manual-curated-summary', 'ai_reviewed': False}}


def _validate_script(result, story, max_words):
    if not isinstance(result, dict):
        raise ValueError('The script workflow returned no chapter')
    review = result.get('evidence_review')
    if not isinstance(review, dict) or review.get('passed') is not True:
        raise ValueError('The script did not pass its evidence review')
    turns = result.get('turns')
    if not isinstance(turns, list) or not 2 <= len(turns) <= 30:
        raise ValueError('The script needs source-linked Maya and Leo dialogue')
    allowed = set(story.get('claim_source_ids', []))
    used, speakers, words = set(), set(), []
    for turn in turns:
        if not isinstance(turn, dict) or turn.get('speaker') not in {'maya', 'leo'} or not isinstance(turn.get('text'), str) or not turn['text'].strip():
            raise ValueError('The script contains an invalid approved turn')
        identifiers = turn.get('source_ids')
        if not isinstance(identifiers, list) or any(not isinstance(identifier, str) for identifier in identifiers) or not set(identifiers).issubset(allowed):
            raise ValueError('The script references a source outside the approved story')
        used.update(identifiers)
        speakers.add(turn['speaker'])
        words.append(turn['text'])
    text = ' '.join(words)
    if speakers != {'maya', 'leo'} or not used:
        raise ValueError('The script must include both hosts and its supporting source')
    if len(text.split()) > max_words:
        raise ValueError('The script exceeds the chapter word budget; no text was cut')
    outlets = [source.get('outlet', '') for source in story['sources'] if source['article_id'] in allowed]
    if not any(outlet and outlet.casefold() in text.casefold() for outlet in outlets):
        raise ValueError('The script must speak the name of a supporting outlet')
    return copy.deepcopy(result)


def _make_script(service, job, index):
    payload = job['payload']
    story = payload['stories'][index]
    key = _script_key(payload, index)
    with service.conn() as db:
        cached = db.execute('SELECT script FROM cloud_chapter_cache WHERE cache_key=?', (key,)).fetchone()
    if cached and cached['script']:
        result = _validate_script(json.loads(cached['script']), story, payload['target_words'])
    else:
        evidence_ids = {item['article_id'] for item in payload['evidence'][index]}
        if payload['ai_enabled'] and set(story['claim_source_ids']).issubset(evidence_ids):
            request = {'language': payload['profile']['language'], 'depth': payload['profile']['depth'],
                       'target_words': max(1, int(payload['target_words'] * .85)), 'plan': payload['profile']['plan'],
                       'story': _shared_story(story), 'evidence': payload['evidence'][index],
                       'previous_title': payload['stories'][index - 1].get('title') if index else None,
                       'next_title': payload['stories'][index + 1].get('title') if index + 1 < len(payload['stories']) else None,
                       'is_first': index == 0, 'is_last': index == len(payload['stories']) - 1}
            response = cloud_client.invoke('script', request, root=service.ROOT,
                                           request_id=f"{job['id']}-script-{index}")
            result = _validate_script(response.get('chapter'), story, payload['target_words'])
            result['script_origin'] = 'n8n-ai-script-evidence-reviewed'
            if response.get('usage'):
                result['usage'] = response['usage']
        else:
            result = _validate_script(_offline_script(story, payload['profile']), story, payload['target_words'])
        with service.conn() as db:
            db.execute('INSERT INTO cloud_chapter_cache(cache_key,script,updated_at) VALUES (?,?,?) ON CONFLICT(cache_key) DO UPDATE SET script=excluded.script,updated_at=excluded.updated_at',
                       (key, _json(result), service.now()))
    chapter = payload['chapters'][index]
    chapter.update({field: result[field] for field in ('turns', 'script_origin', 'evidence_review')})
    chapter['text'] = ' '.join(turn['text'] for turn in chapter['turns'])
    if isinstance(result.get('title'), str) and result['title'].strip() and len(result['title']) <= 180:
        chapter['title'] = result['title'].strip()
    chapter['cache_key'] = _hash({'script_key': key, 'turns': chapter['turns'], 'voices': payload['voice_ids']})
    chapter['script_ready'] = True


def _valid_audio(value, media_root):
    if not isinstance(value, dict):
        return False
    try:
        audio_production._media_file(value.get('url'), Path(media_root).resolve())
        return True
    except (OSError, ValueError):
        return False


def _audio_key(payload, chapter, provider):
    return _hash({'version': 2, 'provider': provider, 'model': 'eleven_v3' if provider=='elevenlabs' else 'windows-sapi', 'language': payload['profile']['language'],
                  'turns': chapter['turns'], 'voices': payload['voice_ids'] if provider == 'elevenlabs' else []})


def _cached_audio(service, key):
    with service.conn() as db:
        row = db.execute('SELECT audio FROM cloud_chapter_cache WHERE cache_key=?', (key,)).fetchone()
    if row and row['audio']:
        value = json.loads(row['audio'])
        if _valid_audio(value, Path(service.ROOT) / 'media'):
            return value
    return None


def _cache_audio(service, key, value):
    with service.conn() as db:
        db.execute('INSERT INTO cloud_chapter_cache(cache_key,audio,updated_at) VALUES (?,?,?) ON CONFLICT(cache_key) DO UPDATE SET audio=excluded.audio,updated_at=excluded.updated_at',
                   (key, _json(value), service.now()))
        db.execute('INSERT INTO audio_cache(cache_key,data,created_at) VALUES (?,?,?) ON CONFLICT(cache_key) DO UPDATE SET data=excluded.data',
                   (key, _json(value), service.now()))


def _basic_chapters(service, job):
    payload = job['payload']
    media = Path(service.ROOT) / 'media'
    for index, chapter in enumerate(payload['chapters']):
        _ensure_audio_wanted(service, job)
        if _valid_audio(chapter.get('natural_audio'), media):
            chapter['audio'] = chapter['natural_audio']
            continue
        if not _valid_audio(chapter.get('basic_audio'), media):
            key = _audio_key(payload, chapter, 'microsoft-sapi')
            value = _cached_audio(service, key)
            if value is None:
                _save(service, job, state='audio', stage=f'Recording Basic chapter {index + 1} of {len(payload["chapters"])}', progress=55 + index / len(payload['chapters']) * 35)
                value = audio_production.render_basic_chapter(chapter, payload['profile']['language'], media, key)
                _cache_audio(service, key, value)
            chapter['basic_audio'] = value
            _save(service, job)
        chapter['audio'] = chapter['basic_audio']


def _publish(service, job, *, pending=False, warning=None, uncertain=False):
    _ensure_audio_wanted(service, job)
    payload = job['payload']
    edition = _load_edition(service, job)
    edition['chapters'] = copy.deepcopy(payload['chapters'])
    for chapter in edition['chapters']:
        chapter.pop('basic_audio', None)
        chapter.pop('natural_audio', None)
        chapter.pop('script_ready', None)
    edition = audio_production.combine_episode(edition, Path(service.ROOT) / 'media')
    # A mixed episode has already used natural narration and still consumes its
    # daily natural allowance even if the remaining chapters use Basic voices.
    natural = any(chapter['audio'].get('provider') == 'elevenlabs' for chapter in edition['chapters'])
    edition.update({'status': 'ready', 'tts_provider': 'elevenlabs' if natural else 'device',
                    'natural_pending': pending, 'natural_reserved': pending or uncertain,
                    'script_origin': 'n8n-ai-script-evidence-reviewed' if all(
                        chapter.get('script_origin') == 'n8n-ai-script-evidence-reviewed' for chapter in edition['chapters'])
                    else 'reviewed-curated-summary', 'natural_uncertain': uncertain})
    if warning:
        edition['audio_note'] = warning
    else:
        edition.pop('audio_note', None)
    payload['natural_pending'] = pending
    _save(service, job, edition=edition)
    return edition


def _natural_chapters(service, job):
    payload = job['payload']
    media = Path(service.ROOT) / 'media'
    for index, chapter in enumerate(payload['chapters']):
        _ensure_audio_wanted(service, job)
        if _valid_audio(chapter.get('natural_audio'), media):
            chapter['audio'] = chapter['natural_audio']
            continue
        key = _audio_key(payload, chapter, 'elevenlabs')
        value = _cached_audio(service, key)
        if value is None:
            request_id = f"{job['id']}-audio-{index}-{payload.get('natural_attempt', 0)}"
            # A process crash after this commit is ambiguous: never resend audio.
            payload['paid_inflight'] = {'chapter_index': index, 'request_id': request_id}
            _save(service, job, state='audio', stage=f'Recording natural chapter {index + 1} of {len(payload["chapters"])}', progress=55 + index / len(payload['chapters']) * 35)
            try:
                response = cloud_client.invoke('audio', {'language': payload['profile']['language'],
                    'turns': chapter['turns'], 'voice_ids': payload['voice_ids'],
                    'previous_request_ids': payload['request_ids'][-3:]}, root=service.ROOT,
                    request_id=request_id, timeout=180)
                _ensure_audio_wanted(service, job)
                value = audio_production.persist_natural_chapter(chapter, response, media, key)
                expected = set(payload['voice_ids'])
                if set(value.get('voice_ids', [])) != expected:
                    raise ValueError('Natural audio returned voices outside the frozen selection')
                _cache_audio(service, key, value)
                if isinstance(response.get('request_id'), str) and response['request_id']:
                    payload['request_ids'].append(response['request_id'])
            except _AudioRemoved:
                raise
            except cloud_client.CloudError as exc:
                if exc.uncertain:
                    payload['uncertain_audio'] = True
                elif not exc.uncertain:
                    payload['paid_inflight'] = None
                _save(service, job)
                raise
            except Exception as exc:
                # Audio existed but validation/storage failed; another paid take
                # is unsafe until the workflow execution has been inspected.
                payload['uncertain_audio'] = True
                _save(service, job)
                raise cloud_client.CloudError(str(exc), uncertain=True) from exc
            payload['paid_inflight'] = None
        chapter['natural_audio'] = value
        chapter['audio'] = value
        _save(service, job)


def _fail(service, job, message, *, uncertain=False):
    try:
        edition = _load_edition(service, job)
    except ValueError:
        _save(service, job, state='failed', stage='Preparation failed',
              error=str(message)[:500], uncertain=uncertain)
        return
    if not edition.get('episode_audio'):
        edition['status'] = 'pending' if uncertain else 'failed'
    edition['natural_reserved'] = bool(uncertain)
    edition['natural_pending'] = False
    job['payload']['natural_pending'] = False
    _save(service, job, state='failed', stage='Needs attention' if uncertain else 'Preparation failed',
          error=str(message)[:500], uncertain=uncertain, edition=edition)


def process_one(service):
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM cloud_jobs WHERE state IN ('queued','waiting_retry') AND next_run<=? ORDER BY created_at LIMIT 1", (service.now(),)).fetchone()
        if not row:
            return False
        job = dict(row)
        job['payload'] = json.loads(job['payload'])
        job['attempt'] += 1
        db.execute("UPDATE cloud_jobs SET state='writing',stage='Resuming saved preparation',attempt=?,updated_at=? WHERE id=?",
                   (job['attempt'], service.now(), job['id']))
    payload = job['payload']
    try:
        _ensure_audio_wanted(service, job)
        for index, chapter in enumerate(payload['chapters']):
            if chapter.get('script_ready'):
                continue
            _save(service, job, state='writing', stage=f'Writing chapter {index + 1} of {len(payload["chapters"])}', progress=5 + index / len(payload['chapters']) * 35)
            _make_script(service, job, index)
            _save(service, job, state='checking', stage=f'Checking sources for chapter {index + 1}', progress=10 + (index + 1) / len(payload['chapters']) * 35)
        if sum(len(chapter['text'].split()) for chapter in payload['chapters']) > payload['max_words']:
            raise ValueError('The complete script exceeds its word budget; no approved words were cut')
        if payload.get('uncertain_audio') or payload.get('paid_inflight'):
            _basic_chapters(service, job)
            _publish(service, job, warning='Basic audio is ready. The natural request may have been charged; check its n8n execution before another request.', uncertain=True)
            _fail(service, job, 'The natural request has an uncertain outcome; automatic paid retry is disabled.', uncertain=True)
            return True
        if payload['natural_enabled']:
            try:
                _natural_chapters(service, job)
            except cloud_client.CloudError as exc:
                _basic_chapters(service, job)
                if exc.uncertain:
                    _publish(service, job, warning='Basic audio is ready. Check the natural request in n8n before another paid attempt.', uncertain=True)
                    _fail(service, job, exc, uncertain=True)
                elif exc.retryable:
                    payload['natural_attempt'] = payload.get('natural_attempt', 0) + 1
                    pending = payload['natural_attempt'] < MAX_ATTEMPTS
                    _publish(service, job, pending=pending, warning='Basic audio is ready while the natural voice service is busy.' if pending else 'Basic audio is ready. The natural voice service remained busy after three attempts.')
                    if pending:
                        _save(service, job, state='waiting_retry', stage='Basic audio ready; natural voices queued', progress=90,
                              error=str(exc)[:500], next_run=_later(service, min(180, max(10, exc.retry_after))))
                    else:
                        _save(service, job, state='ready', stage='Basic audio ready', progress=100, error=str(exc)[:500])
                else:
                    _publish(service, job, warning='Basic audio is ready. ' + str(exc)[:300])
                    _save(service, job, state='ready', stage='Basic audio ready', progress=100, error=str(exc)[:500])
                return True
        else:
            _basic_chapters(service, job)
        _save(service, job, state='audio', stage='Combining the recorded briefing', progress=95)
        _publish(service, job)
        _save(service, job, state='ready', stage='Your briefing is ready', progress=100)
    except _AudioRemoved:
        _finish_removed(service, job)
    except cloud_client.CloudError as exc:
        if exc.retryable and not exc.uncertain and job['attempt'] < MAX_ATTEMPTS:
            _save(service, job, state='waiting_retry', stage='Waiting to resume saved preparation', error=str(exc)[:500],
                  next_run=_later(service, min(180, max(10, exc.retry_after))))
        else:
            _fail(service, job, exc, uncertain=exc.uncertain or bool(payload.get('paid_inflight')))
    except Exception as exc:
        _fail(service, job, exc, uncertain=bool(payload.get('paid_inflight')))
    return True


def recover(service):
    """Resume safe stages; mark in-flight paid audio for Basic-only recovery."""
    init_tables(service)
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        for row in db.execute("SELECT * FROM cloud_jobs WHERE state IN ('writing','checking','audio')").fetchall():
            payload = json.loads(row['payload'])
            if payload.get('paid_inflight'):
                payload['uncertain_audio'] = True
            db.execute("UPDATE cloud_jobs SET state='queued',stage='Recovering saved work',payload=?,next_run=?,updated_at=? WHERE id=?",
                       (_json(payload), service.now(), service.now(), row['id']))
        db.execute("UPDATE cloud_outbox SET state='queued',next_run=?,updated_at=? WHERE state='running'", (service.now(), service.now()))


def _radar_context(service, pid, db):
    row = db.execute('SELECT data FROM profiles WHERE id=?', (pid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Listener not found')
    profile = json.loads(row['data'])
    feedback = [dict(item) for item in db.execute('SELECT story_id,value,reason,created_at FROM feedback WHERE profile_id=? ORDER BY story_id', (pid,))]
    revision = _hash({'profile': profile, 'feedback': feedback, 'catalog_version': service.CATALOG.get('version')})
    stories = [{key: story.get(key) for key in ('id', 'title', 'titles', 'summary', 'tags', 'primary_topic', 'updated_at')}
               for story in service.CATALOG['stories'] if story.get('curated')]
    return revision, {'operation': 'rank', 'profile': profile, 'feedback': feedback, 'stories': stories, 'revision': revision}


def enqueue_radar(service, pid):
    init_tables(service)
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        revision, payload = _radar_context(service, pid, db)
        db.execute('''INSERT INTO cloud_outbox(profile_id,revision,payload,state,attempt,next_run,error,created_at,updated_at)
          VALUES (?,?,?,'queued',0,?,NULL,?,?) ON CONFLICT(profile_id) DO UPDATE SET
          revision=excluded.revision,payload=excluded.payload,state='queued',attempt=0,next_run=excluded.next_run,
          error=NULL,updated_at=excluded.updated_at WHERE cloud_outbox.revision!=excluded.revision OR cloud_outbox.state='failed' ''',
                   (pid, revision, _json(payload), service.now(), service.now(), service.now()))
        state = db.execute('SELECT state FROM cloud_outbox WHERE profile_id=?', (pid,)).fetchone()['state']
    return {'profile_id': pid, 'revision': revision, 'state': state}


def get_snapshot(service, pid):
    with service.conn() as db:
        revision, _ = _radar_context(service, pid, db)
        row = db.execute('SELECT * FROM cloud_snapshots WHERE profile_id=? AND revision=?', (pid, revision)).fetchone()
    return {'revision': row['revision'], 'data': json.loads(row['data']), 'created_at': row['created_at']} if row else None


def process_outbox(service):
    if not cloud_client.connection(service.ROOT).get('verified_at'):
        return False
    with service.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM cloud_outbox WHERE state IN ('queued','waiting_retry') AND next_run<=? ORDER BY updated_at LIMIT 1", (service.now(),)).fetchone()
        if not row:
            return False
        item = dict(row)
        db.execute("UPDATE cloud_outbox SET state='running',attempt=attempt+1,updated_at=? WHERE profile_id=? AND revision=?",
                   (service.now(), item['profile_id'], item['revision']))
    try:
        result = cloud_client.invoke('radar', json.loads(item['payload']), root=service.ROOT,
                                     request_id='radar-' + item['revision'])
        if len(_json(result)) > 150_000:
            raise ValueError('The radar response is too large')
        with service.conn() as db:
            db.execute('BEGIN IMMEDIATE')
            revision, payload = _radar_context(service, item['profile_id'], db)
            if revision == item['revision']:
                db.execute('INSERT INTO cloud_snapshots VALUES (?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET revision=excluded.revision,data=excluded.data,created_at=excluded.created_at',
                           (item['profile_id'], revision, _json(result), service.now()))
                db.execute("UPDATE cloud_outbox SET state='ready',error=NULL,updated_at=? WHERE profile_id=? AND revision=?",
                           (service.now(), item['profile_id'], revision))
            else:
                db.execute("UPDATE cloud_outbox SET revision=?,payload=?,state='queued',attempt=0,next_run=?,error=NULL,updated_at=? WHERE profile_id=? AND revision=?",
                           (revision, _json(payload), service.now(), service.now(), item['profile_id'], item['revision']))
    except Exception as exc:
        retry = isinstance(exc, cloud_client.CloudError) and exc.retryable and item['attempt'] + 1 < MAX_ATTEMPTS
        with service.conn() as db:
            db.execute('UPDATE cloud_outbox SET state=?,error=?,next_run=?,updated_at=? WHERE profile_id=? AND revision=?',
                       ('waiting_retry' if retry else 'failed', str(exc)[:500],
                        _later(service, min(180, max(10, getattr(exc, 'retry_after', 30)))),
                        service.now(), item['profile_id'], item['revision']))
    return True
