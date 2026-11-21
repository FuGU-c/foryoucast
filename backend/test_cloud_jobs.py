"""Durable queue, quota, recovery and stale-radar tests without cloud calls."""
import contextlib
import copy
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from . import cloud_jobs as jobs
from .cloud_client import CloudError


class CloudJobsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'public').mkdir()
        (self.root / 'media').mkdir()
        (self.root / 'public' / 'voice-samples.json').write_text(json.dumps([
            {'id': 'voice-a', 'language': 'en'}, {'id': 'voice-b', 'language': 'en'}]), encoding='utf-8')
        self.database = self.root / 'test.db'
        self.clock = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
        self.p = {'id': 'listener', 'plan': 'premium', 'language': 'en', 'depth': 'balanced',
                  'duration': 5, 'tts_provider': 'device', 'interests': {'technology': 3},
                  'news_languages': ['en'], 'elevenlabs_voices': {}, 'timezone': 'UTC'}
        self.stories = [self.story(index) for index in range(1, 10)]
        self.svc = SimpleNamespace(ROOT=self.root, conn=self.connection, now=lambda: self.clock.isoformat(),
            profile=self.profile, refresh_catalog=lambda: None, briefing_dates=lambda: ['2026-11-20'],
            ranked=lambda *args, **kwargs: copy.deepcopy(self.stories), chapter=self.chapter,
            read_article=lambda identifier: {'paragraphs': ['An original report, including its qualifications.'], 'outlet': 'Evidence Daily'},
            CATALOG={'version': 'test-1', 'replay_day': '2026-11-20', 'as_of': self.clock.isoformat(), 'stories': self.stories},
            daily_usage=self.daily_usage)
        with self.connection() as db:
            db.executescript('''CREATE TABLE profiles(id TEXT PRIMARY KEY,data TEXT);
              CREATE TABLE feedback(profile_id TEXT,story_id TEXT,value INTEGER,reason TEXT,created_at TEXT);
              CREATE TABLE editions(id TEXT PRIMARY KEY,profile_id TEXT,data TEXT,created_at TEXT);
              CREATE TABLE audio_cache(cache_key TEXT PRIMARY KEY,data TEXT,created_at TEXT);''')
            db.execute('INSERT INTO profiles VALUES (?,?)', (self.p['id'], json.dumps(self.p)))
        jobs.init_tables(self.svc)
        self.config = {'ai_ready': False, 'audio_ready': False, 'verified_at': None}
        self.patches = [
            patch.object(jobs.cloud_client, 'connection', side_effect=lambda *args: self.config),
            patch.object(jobs.audio_production, 'render_basic_chapter', side_effect=self.render_basic),
            patch.object(jobs.audio_production, 'persist_natural_chapter', side_effect=self.persist_natural),
            patch.object(jobs.audio_production, 'combine_episode', side_effect=self.combine),
        ]
        self.mocks = [patcher.start() for patcher in self.patches]

    def tearDown(self):
        for patcher in self.patches:
            patcher.stop()
        self.temporary.cleanup()

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def story(self, index):
        text = f'Evidence Daily reports development {index}. This remains uncertain and is not a guarantee.'
        return {'id': f'story-{index}', 'title': f'Headline {index}', 'titles': {'en': f'Headline {index}'},
                'summary': text, 'summaries': {'en': text}, 'curated': True,
                'updated_at': self.clock.isoformat(), 'score': 20-index, 'tags': ['technology'],
                'claim_source_ids': [f'article-{index}'],
                'sources': [{'article_id': f'article-{index}', 'outlet': 'Evidence Daily', 'language': 'en',
                             'url': f'https://example.com/{index}'}]}

    def profile(self, pid):
        with self.connection() as db:
            row = db.execute('SELECT data FROM profiles WHERE id=?', (pid,)).fetchone()
        if not row:
            raise HTTPException(404, 'Listener not found')
        return json.loads(row['data'])

    def save_profile(self):
        with self.connection() as db:
            db.execute('UPDATE profiles SET data=? WHERE id=?', (json.dumps(self.p), self.p['id']))

    def chapter(self, story, profile):
        return {'story_id': story['id'], 'title': story['title'], 'text': 'Old short text.',
                'cache_key': story['id'], 'sources': copy.deepcopy(story['sources']),
                'claim_source_ids': list(story['claim_source_ids']), 'estimated_seconds': 10, 'audio': None}

    def daily_usage(self, profile, db):
        editions = [json.loads(row['data']) for row in db.execute('SELECT data FROM editions WHERE profile_id=?', (profile['id'],))]
        counted = [edition for edition in editions if edition.get('status') != 'failed']
        natural = sum(edition.get('natural_reserved') or edition.get('tts_provider') == 'elevenlabs' for edition in counted)
        return {'can_create': profile['plan'] != 'free' or not counted, 'natural_remaining': max(0, 1-natural)}

    def render_basic(self, chapter, language, media, key):
        path = Path(media) / ('basic-' + key + '.mp3')
        path.write_bytes(b'ID3mock-basic')
        return {'url': '/media/' + path.name, 'duration_seconds': 8, 'provider': 'microsoft-sapi', 'voice_ids': ['installed']}

    def persist_natural(self, chapter, result, media, key):
        path = Path(media) / ('natural-' + key + '.mp3')
        path.write_bytes(b'ID3mock-natural')
        return {'url': '/media/' + path.name, 'duration_seconds': 10, 'provider': 'elevenlabs', 'voice_ids': ['voice-a', 'voice-b']}

    def combine(self, edition, media):
        edition = copy.deepcopy(edition)
        end = 0
        providers = set()
        for chapter in edition['chapters']:
            chapter['start_seconds'] = end
            end += chapter['audio']['duration_seconds']
            chapter['end_seconds'] = end
            providers.add(chapter['audio']['provider'])
        mode = 'elevenlabs' if providers == {'elevenlabs'} else 'basic-audio' if providers == {'microsoft-sapi'} else 'mixed-audio'
        edition.update({'episode_audio': {'url': '/media/episode.mp3', 'duration_seconds': end, 'timing_basis': 'measured'},
                        'duration_seconds': end, 'estimated_seconds': end, 'audio_mode': mode})
        return edition

    def edition(self, job):
        with self.connection() as db:
            return json.loads(db.execute('SELECT data FROM editions WHERE id=?', (job['edition_id'],)).fetchone()['data'])

    def payload(self, job):
        with self.connection() as db:
            return json.loads(db.execute('SELECT payload FROM cloud_jobs WHERE id=?', (job['job_id'],)).fetchone()['payload'])

    def advance(self, seconds=200):
        self.clock += dt.timedelta(seconds=seconds)

    def natural(self):
        self.p.update({'plan': 'plus', 'tts_provider': 'elevenlabs'})
        self.save_profile()
        self.config['audio_ready'] = True

    def script_response(self, payload):
        identifier = payload['story']['claim_source_ids'][0]
        return {'ok': True, 'chapter': {'turns': [
            {'speaker': 'maya', 'text': 'According to Evidence Daily, the report describes a development.', 'source_ids': [identifier]},
            {'speaker': 'leo', 'text': 'The report says that the outcome is still uncertain.', 'source_ids': [identifier]}],
            'evidence_review': {'passed': True}}, 'usage': {'total_tokens': 20}}

    def test_double_tap_reserves_one_pending_edition_and_free_gates(self):
        self.p['plan'] = 'free'
        self.save_profile()
        first = jobs.queue_briefing(self.svc, 'listener')
        second = jobs.queue_briefing(self.svc, 'listener')
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertEqual(len(jobs.list_jobs(self.svc, 'listener')), 1)
        self.assertEqual(self.edition(first)['status'], 'pending')
        self.assertTrue(jobs.process_one(self.svc))
        self.assertEqual(jobs.get_job(self.svc, 'listener', first['job_id'])['state'], 'ready')
        with self.assertRaises(HTTPException) as error:
            jobs.queue_briefing(self.svc, 'listener')
        self.assertEqual(error.exception.status_code, 429)

    def test_rate_limited_writer_uses_reviewed_summaries_and_finishes_creation(self):
        self.config['ai_ready'] = True
        # Supply valid frozen evidence so this test reaches the cloud writer.
        with patch.object(jobs, '_evidence', side_effect=lambda service, story: [{'article_id': story['claim_source_ids'][0], 'paragraphs': ['Source evidence.']}]):
            queued = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke', side_effect=CloudError('Rate limited', retryable=True)) as invoke:
            self.assertTrue(jobs.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(jobs.get_job(self.svc, 'listener', queued['job_id'])['state'], 'ready')
        self.assertEqual(self.edition(queued)['script_origin'], 'reviewed-curated-summary')
        self.assertIn('reviewed source summaries', self.edition(queued)['audio_note'])

    def test_missing_system_voice_uses_only_matching_bundled_summaries(self):
        folder=self.root/'assets/demo';folder.mkdir(parents=True)
        media=self.root/'media/story-summaries';media.mkdir()
        reference={};audio={}
        for story in self.stories:
            sid=story['id']
            reference[sid]={'summaries':story['summaries'],'claim_source_ids':story['claim_source_ids']}
            (media/f'{sid}-en.mp3').write_bytes(b'ID3included-basic')
            audio[sid]={'en':{'url':f'/media/story-summaries/{sid}-en.mp3','provider':'microsoft-sapi','duration_seconds':8}}
        (folder/'summary-content.json').write_text(json.dumps(reference))
        (folder/'demo-story-audio.json').write_text(json.dumps({'stories':audio}))
        queued=jobs.queue_briefing(self.svc,'listener')
        with patch.object(jobs.audio_production,'render_basic_chapter',side_effect=RuntimeError('No installed Dutch voice')):
            self.assertTrue(jobs.process_one(self.svc))
        self.assertEqual(jobs.get_job(self.svc,'listener',queued['job_id'])['state'],'ready')
        self.assertIn('no installed system voice',self.edition(queued)['audio_note'])
        payload=self.payload(queued)
        payload['stories'][0]['summaries']['en']='This is a different development.'
        self.assertIsNone(jobs._portable_summary(self.svc,payload,0))

    def test_basic_generation_freezes_preferences_evidence_and_keeps_qualifications(self):
        queued = jobs.queue_briefing(self.svc, 'listener')
        payload = self.payload(queued)
        self.assertEqual(len(payload['stories']), 4)
        self.assertEqual(payload['evidence'][0][0]['paragraphs'], ['An original report, including its qualifications.'])
        self.p['depth'] = 'simple'
        self.p['language'] = 'de'
        self.save_profile()
        self.stories[0]['summaries']['en'] = 'Changed after queueing.'
        with patch.object(jobs.cloud_client, 'invoke') as invoke:
            self.assertTrue(jobs.process_one(self.svc))
            invoke.assert_not_called()
        self.assertFalse(jobs.process_one(self.svc))
        edition = self.edition(queued)
        self.assertEqual(edition['status'], 'ready')
        self.assertEqual(edition['language'], 'en')
        self.assertEqual(edition['depth'], 'balanced')
        self.assertEqual(edition['audio_mode'], 'basic-audio')
        self.assertEqual(edition['estimated_seconds'], 32)
        self.assertNotEqual(edition['estimated_seconds'], 300)
        self.assertEqual(edition['script_origin'], 'reviewed-curated-summary')
        self.assertIn('uncertain and is not a guarantee.', edition['chapters'][0]['text'])
        self.assertNotIn('Changed after queueing.', edition['chapters'][0]['text'])
        self.assertEqual(self.mocks[1].call_count, 4)

    def test_free_never_requests_natural_and_excludes_other_original_languages(self):
        self.p.update({'plan': 'free', 'tts_provider': 'elevenlabs', 'language': 'en'})
        self.save_profile()
        for story in self.stories:
            story['sources'][0]['language'] = 'de'
        with self.assertRaises(HTTPException) as error:
            jobs.queue_briefing(self.svc, 'listener')
        self.assertEqual(error.exception.status_code, 409)
        self.stories[0]['sources'][0]['language'] = 'en'
        job = jobs.queue_briefing(self.svc, 'listener')
        self.assertEqual(len(self.payload(job)['stories']), 1)
        self.assertFalse(self.payload(job)['natural_enabled'])
        self.assertFalse(self.edition(job)['natural_reserved'])

    def test_failed_job_releases_free_quota_and_retry_does_not_double_reserve(self):
        self.p['plan'] = 'free'
        self.save_profile()
        queued = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.audio_production, 'render_basic_chapter', side_effect=RuntimeError('No local voice')):
            jobs.process_one(self.svc)
        failed = jobs.get_job(self.svc, 'listener', queued['job_id'])
        self.assertEqual(failed['state'], 'failed')
        self.assertTrue(failed['can_retry'])
        self.assertEqual(self.edition(queued)['status'], 'failed')
        retried = jobs.retry_job(self.svc, 'listener', queued['job_id'])
        self.assertEqual(retried['job_id'], queued['job_id'])
        self.assertEqual(jobs.queue_briefing(self.svc, 'listener')['job_id'], queued['job_id'])
        jobs.process_one(self.svc)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM editions').fetchone()[0], 1)

    def test_old_failed_job_cannot_bypass_a_new_free_reservation(self):
        self.p['plan'] = 'free'
        self.save_profile()
        old = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.audio_production, 'render_basic_chapter', side_effect=RuntimeError('No voice')):
            jobs.process_one(self.svc)
        new = jobs.queue_briefing(self.svc, 'listener')
        with self.assertRaises(HTTPException):
            jobs.retry_job(self.svc, 'listener', old['job_id'])
        self.assertEqual(jobs.queue_briefing(self.svc, 'listener')['job_id'], new['job_id'])

    def test_ai_script_uses_original_frozen_evidence_and_strict_source_review(self):
        self.config['ai_ready'] = True
        queued = jobs.queue_briefing(self.svc, 'listener')
        requests = []
        def invoke(kind, payload, **kwargs):
            self.assertEqual(kind, 'script')
            requests.append(copy.deepcopy(payload))
            return self.script_response(payload)
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke):
            jobs.process_one(self.svc)
        self.assertEqual(len(requests), 4)
        self.assertTrue(requests[0]['is_first'])
        self.assertTrue(requests[-1]['is_last'])
        self.assertEqual(requests[0]['evidence'][0]['article_id'], 'article-1')
        self.assertEqual(requests[0]['target_words'], int(self.payload(queued)['target_words'] * .85))
        self.assertEqual(self.edition(queued)['script_origin'], 'n8n-ai-script-evidence-reviewed')
        for mutation in ['source', 'review', 'outlet', 'budget']:
            response = self.script_response(requests[0])['chapter']
            if mutation == 'source':
                response['turns'][0]['source_ids'] = ['not-approved']
            elif mutation == 'review':
                response['evidence_review']['passed'] = False
            elif mutation == 'outlet':
                response['turns'][0]['text'] = 'An unnamed source has a development.'
            else:
                response['turns'][0]['text'] += ' words' * 200
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                jobs._validate_script(response, requests[0]['story'], requests[0]['target_words'])

    def test_completed_scripts_and_audio_are_reused_across_jobs(self):
        self.config['ai_ready'] = True
        with patch.object(jobs.cloud_client, 'invoke', side_effect=lambda kind, payload, **kwargs: self.script_response(payload)) as invoke:
            first = jobs.queue_briefing(self.svc, 'listener')
            jobs.process_one(self.svc)
            second = jobs.queue_briefing(self.svc, 'listener')
            jobs.process_one(self.svc)
        self.assertEqual(invoke.call_count, 4)
        self.assertEqual(self.mocks[1].call_count, 4)
        self.assertNotEqual(first['edition_id'], second['edition_id'])

    def test_provider_queue_publishes_basic_and_bounded_retry_upgrades_same_edition(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        self.assertTrue(self.edition(queued)['natural_reserved'])
        calls = []
        def invoke(kind, payload, **kwargs):
            self.assertEqual(kind, 'audio')
            calls.append(payload)
            if len(calls) == 1:
                raise CloudError('busy', retryable=True, retry_after=10)
            return {'ok': True, 'request_id': str(len(calls))}
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke):
            jobs.process_one(self.svc)
            waiting = jobs.get_job(self.svc, 'listener', queued['job_id'])
            self.assertEqual(waiting['state'], 'waiting_retry')
            basic = self.edition(queued)
            self.assertEqual(basic['audio_mode'], 'basic-audio')
            self.assertTrue(basic['natural_pending'])
            self.assertTrue(basic['natural_reserved'])
            self.assertFalse(jobs.process_one(self.svc))
            self.advance()
            jobs.process_one(self.svc)
        ready = jobs.get_job(self.svc, 'listener', queued['job_id'])
        self.assertEqual(ready['state'], 'ready')
        upgraded = self.edition(queued)
        self.assertEqual(upgraded['audio_mode'], 'elevenlabs')
        self.assertFalse(upgraded['natural_pending'])
        self.assertFalse(upgraded['natural_reserved'])
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[-1]['previous_request_ids'], ['2', '3', '4'])
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM editions').fetchone()[0], 1)

    def test_known_queue_stops_after_three_attempts_with_basic_still_ready(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke', side_effect=CloudError('busy', retryable=True)) as invoke:
            for _ in range(3):
                jobs.process_one(self.svc)
                self.advance()
            self.assertFalse(jobs.process_one(self.svc))
        self.assertEqual(invoke.call_count, 3)
        self.assertEqual(jobs.get_job(self.svc, 'listener', queued['job_id'])['state'], 'ready')
        self.assertEqual(self.edition(queued)['status'], 'ready')
        self.assertFalse(self.edition(queued)['natural_pending'])
        self.assertFalse(self.edition(queued)['natural_reserved'])

    def test_ambiguous_audio_is_never_retried_and_holds_natural_allowance(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke', side_effect=CloudError('timeout after send', uncertain=True)) as invoke:
            jobs.process_one(self.svc)
            self.advance()
            self.assertFalse(jobs.process_one(self.svc))
        self.assertEqual(invoke.call_count, 1)
        failed = jobs.get_job(self.svc, 'listener', queued['job_id'])
        self.assertEqual(failed['state'], 'failed')
        self.assertFalse(failed['can_retry'])
        self.assertTrue(failed['uncertain'])
        edition = self.edition(queued)
        self.assertEqual(edition['status'], 'ready')
        self.assertEqual(edition['audio_mode'], 'basic-audio')
        self.assertTrue(edition['natural_reserved'])
        with self.assertRaises(HTTPException):
            jobs.retry_job(self.svc, 'listener', queued['job_id'])
        second = jobs.queue_briefing(self.svc, 'listener')
        self.assertFalse(self.payload(second)['natural_enabled'])

    def test_partly_natural_episode_keeps_its_natural_allowance_after_queue_exhaustion(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        calls = []
        def invoke(kind, payload, **kwargs):
            calls.append(payload)
            if len(calls) == 1:
                return {'ok': True}
            raise CloudError('remaining voices busy', retryable=True)
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke):
            for _ in range(3):
                jobs.process_one(self.svc)
                self.advance()
        edition = self.edition(queued)
        self.assertEqual(edition['audio_mode'], 'mixed-audio')
        self.assertEqual(edition['tts_provider'], 'elevenlabs')
        self.assertFalse(edition['natural_pending'])
        next_job = jobs.queue_briefing(self.svc, 'listener')
        self.assertFalse(self.payload(next_job)['natural_enabled'])

    def test_recovery_never_resends_inflight_paid_audio(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        payload = self.payload(queued)
        payload['paid_inflight'] = {'chapter_index': 0, 'request_id': 'sent-before-crash'}
        with self.connection() as db:
            db.execute("UPDATE cloud_jobs SET state='audio',payload=? WHERE id=?", (json.dumps(payload), queued['job_id']))
        jobs.recover(self.svc)
        with patch.object(jobs.cloud_client, 'invoke') as invoke:
            jobs.process_one(self.svc)
            invoke.assert_not_called()
        self.assertFalse(jobs.get_job(self.svc, 'listener', queued['job_id'])['can_retry'])
        self.assertEqual(self.edition(queued)['audio_mode'], 'basic-audio')

    def remove_audio(self, queued):
        edition = self.edition(queued)
        edition.update({'audio_mode': 'summary-only', 'audio_removed_at': self.svc.now(), 'episode_audio': None})
        for chapter in edition['chapters']:
            chapter['audio'] = None
        with self.connection() as db:
            db.execute('UPDATE editions SET data=? WHERE id=?', (json.dumps(edition), queued['edition_id']))

    def test_summary_only_deletion_cancels_waiting_natural_retry(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke', side_effect=CloudError('busy', retryable=True)):
            jobs.process_one(self.svc)
        self.remove_audio(queued)
        jobs.cancel_edition_audio(self.svc, 'listener', queued['edition_id'])
        self.advance()
        with patch.object(jobs.cloud_client, 'invoke') as invoke:
            self.assertFalse(jobs.process_one(self.svc))
            invoke.assert_not_called()
        edition = self.edition(queued)
        self.assertEqual(edition['audio_mode'], 'summary-only')
        self.assertIsNone(edition['episode_audio'])
        self.assertFalse(edition['natural_pending'])
        self.assertFalse(edition['natural_reserved'])
        self.assertEqual(jobs.get_job(self.svc, 'listener', queued['job_id'])['state'], 'ready')

    def test_summary_only_deletion_during_paid_request_never_restores_audio_or_sends_next(self):
        self.natural()
        queued = jobs.queue_briefing(self.svc, 'listener')
        def invoke(kind, payload, **kwargs):
            self.remove_audio(queued)
            return {'ok': True}
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke) as invoke:
            jobs.process_one(self.svc)
        self.assertEqual(invoke.call_count, 1)
        self.mocks[2].assert_not_called()
        edition = self.edition(queued)
        self.assertEqual(edition['audio_mode'], 'summary-only')
        self.assertIsNone(edition['episode_audio'])
        self.assertTrue(edition['natural_reserved'])

    def test_radar_stale_response_cannot_overwrite_current_preferences_or_snapshot(self):
        self.config['ai_ready'] = True
        self.config['verified_at'] = self.svc.now()
        first = jobs.enqueue_radar(self.svc, 'listener')
        def invoke(kind, payload, **kwargs):
            self.assertEqual(kind, 'radar')
            self.p['interests']['technology'] = 5
            self.save_profile()
            return {'ok': True, 'ranked_story_ids': ['story-2'], 'memory': {'note': 'old revision'}}
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke):
            self.assertTrue(jobs.process_outbox(self.svc))
        self.assertIsNone(jobs.get_snapshot(self.svc, 'listener'))
        self.assertEqual(self.profile('listener')['interests']['technology'], 5)
        with self.connection() as db:
            queued = dict(db.execute('SELECT * FROM cloud_outbox').fetchone())
        self.assertEqual(queued['state'], 'queued')
        self.assertNotEqual(queued['revision'], first['revision'])
        with patch.object(jobs.cloud_client, 'invoke', return_value={'ok': True, 'ranked_story_ids': ['story-3']}):
            jobs.process_outbox(self.svc)
        snapshot = jobs.get_snapshot(self.svc, 'listener')
        self.assertEqual(snapshot['data']['ranked_story_ids'], ['story-3'])
        self.assertFalse(jobs.process_outbox(self.svc))

    def test_feedback_revision_upsert_retains_latest_change_during_radar_call(self):
        self.config['ai_ready'] = True
        self.config['verified_at'] = self.svc.now()
        old = jobs.enqueue_radar(self.svc, 'listener')
        def invoke(kind, payload, **kwargs):
            with self.connection() as db:
                db.execute('INSERT INTO feedback VALUES (?,?,?,?,?)', ('listener', 'story-1', -1, 'interest', self.svc.now()))
            jobs.enqueue_radar(self.svc, 'listener')
            return {'ok': True, 'memory': {'note': 'stale'}}
        with patch.object(jobs.cloud_client, 'invoke', side_effect=invoke):
            jobs.process_outbox(self.svc)
        self.assertIsNone(jobs.get_snapshot(self.svc, 'listener'))
        with self.connection() as db:
            current = dict(db.execute('SELECT * FROM cloud_outbox').fetchone())
        self.assertEqual(current['state'], 'queued')
        self.assertNotEqual(current['revision'], old['revision'])
        self.assertEqual(json.loads(current['payload'])['feedback'][0]['value'], -1)

    def test_radar_remains_durable_when_ai_is_disconnected_and_failure_is_bounded(self):
        jobs.enqueue_radar(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke') as invoke:
            self.assertFalse(jobs.process_outbox(self.svc))
            invoke.assert_not_called()
        self.config['ai_ready'] = True
        self.config['verified_at'] = self.svc.now()
        with patch.object(jobs.cloud_client, 'invoke', side_effect=CloudError('busy', retryable=True)) as invoke:
            for _ in range(3):
                self.assertTrue(jobs.process_outbox(self.svc))
                self.advance()
            self.assertFalse(jobs.process_outbox(self.svc))
        self.assertEqual(invoke.call_count, 3)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT state FROM cloud_outbox').fetchone()[0], 'failed')

    def test_radar_works_without_ai_and_catalog_change_invalidates_snapshot(self):
        self.config.update({'ai_ready': False, 'verified_at': self.svc.now()})
        jobs.enqueue_radar(self.svc, 'listener')
        with patch.object(jobs.cloud_client, 'invoke', return_value={'ok': True, 'ranked_story_ids': ['story-1']}):
            self.assertTrue(jobs.process_outbox(self.svc))
        self.assertIsNotNone(jobs.get_snapshot(self.svc, 'listener'))
        self.svc.CATALOG['version'] = 'new-news-version'
        self.assertIsNone(jobs.get_snapshot(self.svc, 'listener'))


class SharedChapterCacheTests(unittest.TestCase):
    def payload(self):
        return {'profile':{'id':'one','plan':'plus','language':'en','depth':'balanced'},
                'stories':[{'id':'event','title':'A checked report','updated_at':'v1','summary':'Sourced facts','sources':[],'claim_source_ids':['source'],'score':3,'vote':0,'reason':'Because you follow technology'}],
                'evidence':[[]],'target_words':100,'ai_enabled':True}

    def test_listener_scores_and_names_do_not_prevent_shared_chapter_reuse(self):
        first=self.payload();second=copy.deepcopy(first)
        second['profile'].update(id='two',name='Another listener',plan='premium')
        second['stories'][0].update(score=99,vote=1,reason='From your watchlist')
        self.assertEqual(jobs._script_key(first,0),jobs._script_key(second,0))
        self.assertNotIn('reason',jobs._shared_story(second['stories'][0]))

    def test_changed_facts_or_writer_model_produce_distinct_cache_keys(self):
        first=self.payload();changed=copy.deepcopy(first)
        changed['stories'][0]['summary']='A new development'
        self.assertNotEqual(jobs._script_key(first,0),jobs._script_key(changed,0))
        changed=copy.deepcopy(first);changed['profile']['plan']='free'
        self.assertNotEqual(jobs._script_key(first,0),jobs._script_key(changed,0))


if __name__ == '__main__':
    unittest.main()
