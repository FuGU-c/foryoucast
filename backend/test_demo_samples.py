"""Focused DB/audio lifecycle checks for the six fixed demo samples."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import demo_samples, server


class DemoSampleInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='liquid-samples-')
        self.root = Path(self.temp.name)
        self.db = self.root / 'liquid.db'
        self.media = self.root / 'media'
        (self.media / 'demo-samples').mkdir(parents=True)
        self.scripts_path = demo_samples.DEFAULT_SCRIPTS
        self.manifest_path = self.root / 'demo-audio-manifest.json'
        self.backups = self.root / 'backups'
        self.server_patches = patch.multiple(server, DB=self.db, ROOT=self.root)
        self.server_patches.start()
        server.init()
        scripts = json.loads(self.scripts_path.read_text(encoding='utf-8'))
        manifest = {'episodes': []}
        for script in scripts['episodes']:
            profile_id = script['profile_id']
            audio_path = self.media / 'demo-samples' / f'{profile_id}.mp3'
            audio_path.write_bytes(f'dummy audio {profile_id}'.encode())
            chapter_timings = []
            for index, chapter in enumerate(script['chapters']):
                chapter_timings.append({
                    'story_id': chapter['story_id'],
                    'start_seconds': index * 60,
                    'end_seconds': (index + 1) * 60,
                })
            manifest['episodes'].append({
                'profile_id': profile_id,
                'url': f'/media/demo-samples/{profile_id}.mp3',
                'duration_seconds': len(script['chapters']) * 60,
                'chapters': chapter_timings,
                'provider': 'microsoft-sapi' if profile_id in {'mila', 'sam'} else 'elevenlabs',
                'voice_ids': ['test-voice-a', 'test-voice-b'] if profile_id in {'jonas', 'alex'} else [],
            })
        self.manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

    def tearDown(self):
        self.server_patches.stop()
        self.temp.cleanup()

    def install(self):
        return demo_samples.install_demo_samples(
            self.db, self.scripts_path, self.manifest_path, self.backups, self.media,
        )

    def test_install_backs_up_resets_builtin_placeholder_and_keeps_other_profiles(self):
        with server.conn() as db:
            db.execute('INSERT INTO profiles(id,data) VALUES (?,?)', ('hidden', json.dumps({'id': 'hidden', 'name': 'Hidden account'})))
            db.execute('UPDATE profiles SET data=json_set(data,\'$.onboarded\',1) WHERE id=?', ('new',))
            db.execute('INSERT INTO editions VALUES (?,?,?,?)', ('old-new', 'new', json.dumps({'id': 'old-new', 'profile_id': 'new', 'chapters': []}), server.now()))
            db.execute('INSERT INTO feedback VALUES (?,?,?,?,?)', ('new', 'story-1', 1, 'interest', server.now()))
            db.execute('INSERT INTO listens VALUES (?,?,?,?,?,?)', ('new', 'story-1', 'v1', 20, 1, server.now()))
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)', ('old-job', 'new', 'ready', '{}', '{}', None, server.now(), server.now()))
            db.execute('INSERT INTO story_views VALUES (?,?,?,?,?,1)', ('new', 'story-1', None, server.now(), server.now()))
            db.execute('INSERT INTO deliveries VALUES (?,?,?)', ('new', '2026-11-20', 'old-job'))
            db.execute('INSERT INTO provider_keys VALUES (?,?,?)', ('new', 'openai', b'encrypted-test-value'))

        backup = self.install()
        self.assertTrue(backup.is_file())
        old = sqlite3.connect(backup)
        try:
            old_new = json.loads(old.execute('SELECT data FROM profiles WHERE id=?', ('new',)).fetchone()[0])
            self.assertEqual(old_new['name'], 'New listener')
            self.assertEqual(old.execute('SELECT COUNT(*) FROM editions WHERE profile_id=?', ('new',)).fetchone()[0], 1)
        finally:
            old.close()

        with server.conn() as db:
            self.assertIsNotNone(db.execute('SELECT data FROM profiles WHERE id=?', ('hidden',)).fetchone())
            new_profile = json.loads(db.execute('SELECT data FROM profiles WHERE id=?', ('new',)).fetchone()[0])
            self.assertEqual((new_profile['name'], new_profile['role'], new_profile['initials']), ('New listener', 'Unidentified', '+'))
            self.assertFalse(new_profile['onboarded'])
            self.assertEqual(new_profile['plan'], 'free')
            for table in ('editions', 'feedback', 'listens', 'jobs', 'story_views', 'deliveries', 'provider_keys'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table} WHERE profile_id=?', ('new',)).fetchone()[0], 0)

        profiles = {profile['id']: profile for profile in server.profiles()}
        self.assertEqual(set(profiles), {'mila', 'jonas', 'alex', 'sam', 'free-demo', 'medium-demo', 'new'})
        self.assertEqual(len(profiles), 7)
        self.assertEqual((profiles['mila']['role'], profiles['mila']['language'], profiles['mila']['plan']), ('Dutch investor', 'nl', 'premium'))
        self.assertEqual((profiles['jonas']['role'], profiles['jonas']['language'], profiles['jonas']['plan']), ('German investor', 'de', 'premium'))
        self.assertEqual((profiles['alex']['role'], profiles['alex']['goal'], profiles['alex']['plan']), ('FX trader', 'trader', 'premium'))
        self.assertEqual((profiles['sam']['role'], profiles['sam']['goal'], profiles['sam']['plan']), ('General-news listener', 'general', 'premium'))
        self.assertEqual((profiles['free-demo']['name'], profiles['free-demo']['language'], profiles['free-demo']['goal'], profiles['free-demo']['depth'], profiles['free-demo']['plan']), ('Free user', 'en', 'general', 'simple', 'free'))
        self.assertEqual((profiles['medium-demo']['name'], profiles['medium-demo']['goal'], profiles['medium-demo']['goals'], profiles['medium-demo']['plan']), ('Medium user', 'tech', ['tech', 'investor'], 'plus'))
        self.assertEqual({tag:profiles['medium-demo']['interests'][tag] for tag in ['markets','technology','money','economy','energy']}, {'markets': 3, 'technology': 4, 'money': 2, 'economy': 2, 'energy': 1})

        for profile_id in demo_samples.PROFILES:
            edition = server.editions(profile_id)[0]
            self.assertEqual(edition['id'], f'sample-{profile_id}-v1')
            self.assertTrue(edition['demo_sample'])
            self.assertEqual(edition['timing_basis'], 'measured')
            self.assertEqual(edition['episode_audio']['timing_basis'], 'measured')
            self.assertTrue(edition['chapters'][0]['turns'])
            self.assertGreater(edition['chapters'][0]['end_seconds'], edition['chapters'][0]['start_seconds'])
            self.assertEqual(len(server.editions(profile_id)), 1)
        for profile_id in ('mila', 'sam', 'new'):
            usage = server.daily_usage(server.profile(profile_id))
            self.assertEqual(usage['created'], 0)
            self.assertTrue(usage['can_create'])

    def test_removing_episode_audio_unlinks_unshared_sample_but_keeps_chapters(self):
        self.install()
        edition = server.editions('mila')[0]
        original = [(chapter['summary'], chapter['sources']) for chapter in edition['chapters']]
        media_path = self.media / 'demo-samples' / 'mila.mp3'
        result = server.remove_edition_audio('mila', edition['id'])
        self.assertGreater(result['reclaimed_bytes'], 0)
        self.assertFalse(media_path.exists())
        saved = result['edition']
        self.assertIsNone(saved['episode_audio'])
        self.assertEqual(saved['audio_mode'], 'summary-only')
        self.assertEqual([(chapter['summary'], chapter['sources']) for chapter in saved['chapters']], original)
        self.assertTrue(all(chapter['audio'] is None for chapter in saved['chapters']))

    def test_removing_episode_audio_keeps_a_shared_sample_file(self):
        self.install()
        edition = server.editions('mila')[0]
        shared_copy = {**edition, 'id': 'shared-copy', 'profile_id': 'sam'}
        with server.conn() as db:
            db.execute('INSERT INTO editions VALUES (?,?,?,?)',
                       ('shared-copy', 'sam', json.dumps(shared_copy), server.now()))
        media_path = self.media / 'demo-samples' / 'mila.mp3'
        result = server.remove_edition_audio('mila', edition['id'])
        self.assertTrue(media_path.exists())
        self.assertGreater(result['shared_bytes'], 0)
        self.assertIsNone(result['edition']['episode_audio'])

    def test_validation_failure_does_not_back_up_or_change_db(self):
        original = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        original['episodes'][0]['chapters'][0]['story_id'] = 'unknown-story'
        self.manifest_path.write_text(json.dumps(original), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse(self.backups.exists())
        self.assertEqual(server.profile('new')['name'], 'New listener')

    def test_portable_seed_is_once_only_and_preserves_custom_settings(self):
        custom = server.profile('mila')
        custom['interests'] = {'culture': 5}
        custom['wake_time'] = '10:15'
        server.save_profile(custom)
        with patch.multiple(demo_samples, ROOT=self.root, DEFAULT_SCRIPTS=self.scripts_path, DEFAULT_MANIFEST=self.manifest_path):
            self.assertEqual(demo_samples.ensure_demo_samples(self.db), 6)
            self.assertEqual(demo_samples.ensure_demo_samples(self.db), 0)
            self.assertEqual(server.profile('mila')['wake_time'], '10:15')
            self.assertEqual(server.profile('mila')['interests']['culture'], 5)
            self.assertFalse(server.profile('new')['onboarded'])
            self.assertEqual(server.editions('new'), [])
            server.remove_edition_audio('mila', 'sample-mila-v1')
            # Summary-only is an explicit choice; startup must not undo it.
            self.assertEqual(demo_samples.ensure_demo_samples(self.db), 0)
            self.assertIsNone(server.editions('mila')[0]['episode_audio'])

    def test_portable_seed_keeps_personal_edition_and_adds_missing_sample(self):
        with server.conn() as db:
            db.execute('INSERT INTO editions VALUES (?,?,?,?)', ('my-edition', 'mila', json.dumps({'id':'my-edition','profile_id':'mila','chapters':[]}), server.now()))
        with patch.multiple(demo_samples, ROOT=self.root, DEFAULT_SCRIPTS=self.scripts_path, DEFAULT_MANIFEST=self.manifest_path):
            self.assertEqual(demo_samples.ensure_demo_samples(self.db), 6)
        with server.conn() as db:
            self.assertEqual({row[0] for row in db.execute('SELECT id FROM editions WHERE profile_id=?', ('mila',))}, {'my-edition','sample-mila-v1'})

    def test_horizon_defaults_migrate_once_and_leave_free_medium_alone(self):
        with server.conn() as db:
            db.execute("UPDATE profiles SET data=json_set(data,'$.plan','plus') WHERE id='mila'")
        demo_samples.apply_demo_plan_defaults(self.db)
        for pid in ('mila','jonas','alex','sam'):
            self.assertEqual(server.profile(pid)['plan'],'premium')
        self.assertEqual(server.profile('free-demo')['plan'],'free')
        p=server.profile('mila');p['plan']='free';server.save_profile(p)
        demo_samples.apply_demo_plan_defaults(self.db)
        self.assertEqual(server.profile('mila')['plan'],'free')


if __name__ == '__main__':
    unittest.main()
