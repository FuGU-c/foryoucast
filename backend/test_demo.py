"""Service behavior checks against an isolated SQLite database.

Run from the project root: python -m unittest backend.test_demo -v
The licensed catalog must already have been prepared with backend.prepare.
No paid APIs or external article URLs are contacted by these tests. Route
handlers and their Pydantic request models are called synchronously because
the sandbox's Windows asyncio socketpair cannot establish loopback sockets.
Browser/API transport tests are separate from these service-level checks.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.parse import urlencode, urlparse
from fastapi import HTTPException
from pydantic import ValidationError

from . import server as service


def request(method, path, payload=None, query=None, headers=None):
    """Thin synchronous adapter; intentionally does not test ASGI transport."""
    query = query or {}
    try:
        if method == 'GET' and path == '/api/bootstrap':
            value = service.bootstrap()
        elif method == 'GET' and (match := re.fullmatch(r'/api/feed/([^/]+)', path)):
            value = service.feed(match[1], topic=query.get('topic', ''), q=query.get('q', ''),
                                 all_items=query.get('all_items', False), limit=query.get('limit', 50))
        elif method == 'PUT' and (match := re.fullmatch(r'/api/profiles/([^/]+)', path)):
            value = service.update_profile(match[1], service.Preferences.model_validate(payload))
        elif method == 'POST' and (match := re.fullmatch(r'/api/profiles/([^/]+)/feedback', path)):
            value = service.feedback(match[1], service.Vote.model_validate(payload))
        elif method == 'POST' and (match := re.fullmatch(r'/api/profiles/([^/]+)/listens', path)):
            value = service.listen(match[1], service.Listen.model_validate(payload))
        elif method == 'POST' and (match := re.fullmatch(r'/api/profiles/([^/]+)/editions', path)):
            value = service.create_edition(match[1])
        elif method == 'GET' and (match := re.fullmatch(r'/api/editions/([^/]+)/export', path)):
            value = service.export_edition(match[1], query.get('kind', 'report'))
        elif method == 'GET' and path == '/api/integrations/due':
            value = service.due(x_workflow_key=(headers or {}).get('x-workflow-key'))
        elif method == 'POST' and path == '/api/integrations/prepare':
            value = service.prepare_article(payload, x_workflow_key=(headers or {}).get('x-workflow-key'))
        else:
            raise AssertionError('Synchronous test adapter does not implement ' + method + ' ' + path)
        if hasattr(value, 'body'):
            return value.status_code, value.body, {k.encode(): v.encode() for k, v in value.headers.items()}
        return 200, value, {}
    except HTTPException as error:
        return error.status_code, {'detail': error.detail}, {}
    except ValidationError:
        return 422, {'detail': 'Pydantic rejected request'}, {}


class LiquidDemoTests(unittest.TestCase):
    def setUp(self):
        self.cloud_config = patch.object(service.cloud_client, 'connection', return_value={})
        self.cloud_config.start()
        self.original_db = service.DB
        self.temp = tempfile.TemporaryDirectory(prefix='liquid-test-', ignore_cleanup_errors=True)
        service.DB = Path(self.temp.name) / 'test.db'
        service.init()

    def tearDown(self):
        self.cloud_config.stop()
        service.DB = self.original_db
        self.temp.cleanup()

    def get(self, path, **query):
        status, value, _ = request('GET', path, query=query)
        self.assertEqual(status, 200, value)
        return value

    def post(self, path, body=None):
        status, value, _ = request('POST', path, body)
        self.assertEqual(status, 200, value)
        return value

    def test_seven_profiles_and_unconfigured_integrations(self):
        bootstrap = self.get('/api/bootstrap')
        profiles = {p['id']: p for p in bootstrap['profiles']}
        self.assertEqual(set(profiles), {'mila', 'jonas', 'alex', 'sam', 'new', 'free-demo', 'medium-demo'})
        self.assertEqual(profiles['mila']['language'], 'nl')
        self.assertEqual(profiles['jonas']['language'], 'de')
        self.assertEqual(profiles['alex']['goal'], 'trader')
        self.assertEqual(profiles['sam']['goal'], 'general')
        self.assertFalse(profiles['new']['onboarded'])
        self.assertFalse(bootstrap['integrations']['elevenlabs'])
        self.assertFalse(bootstrap['integrations']['n8n'])

    def test_catalog_retains_all_articles_and_languages(self):
        sources = {s['article_id']: s for story in service.CATALOG['stories'] for s in story['sources']}
        self.assertEqual(len(sources), 1740)
        self.assertEqual(sum(s['language'] == 'de' for s in sources.values()), 120)
        self.assertEqual(sum(s['language'] == 'nl' for s in sources.values()), 120)
        self.assertEqual(sum(s['language'] == 'en' for s in sources.values()), 1500)
        self.assertEqual(service.CATALOG['stats']['translation_links'], 238)
        for story in service.CATALOG['stories']:
            self.assertTrue(story['tags'])
            self.assertTrue(set(story['tags']) <= {topic['id'] for topic in service.CATALOG['topics']})
            self.assertTrue(set(story['claim_source_ids']) <= {s['article_id'] for s in story['sources']})
            for source in story['sources']:
                parsed = urlparse(source['url'])
                self.assertIn(parsed.scheme, {'http', 'https'})
                self.assertTrue(parsed.netloc)

    def test_personas_change_story_selection(self):
        trader = self.get('/api/feed/alex')['stories'][:6]
        general = self.get('/api/feed/sam')['stories'][:6]
        self.assertNotEqual([s['id'] for s in trader], [s['id'] for s in general])
        self.assertNotEqual({s['id'] for s in trader}, {s['id'] for s in general})
        self.assertGreaterEqual(sum('economy' in s['tags'] or 'forex' in s['tags'] for s in trader), 2)
        self.assertGreaterEqual(sum(bool(set(s['tags']) & {'world', 'money', 'culture'}) for s in general), 2)

    def test_localized_titles_scripts_and_cache_keys(self):
        nl = {s['id']: s for s in self.get('/api/feed/mila')['stories']}
        de = {s['id']: s for s in self.get('/api/feed/jonas')['stories']}
        sid = next(s for s in nl if s in de)
        self.assertNotEqual(nl[sid]['title'], de[sid]['title'])
        nc = service.chapter(nl[sid], service.profile('mila'))
        dc = service.chapter(de[sid], service.profile('jonas'))
        self.assertTrue(nc['text'].startswith('Volgens '))
        self.assertTrue(dc['text'].startswith('Laut '))
        self.assertNotEqual(nc['cache_key'], dc['cache_key'])
        self.assertTrue(nc['claim_source_ids'])

    def test_native_sources_prioritized_without_losing_other_languages(self):
        for pid, language in [('mila', 'nl'), ('jonas', 'de')]:
            stories = self.get('/api/feed/' + pid)['stories']
            translated = [s for s in stories if any(x['language'] == language for x in s['sources'])]
            self.assertTrue(translated)
            for story in translated:
                self.assertEqual(story['sources'][0]['language'], language)
                self.assertTrue(any(x['language'] == 'en' for x in story['sources']))

    def test_votes_are_idempotent_reversible_and_preserve_explicit_settings(self):
        pid = 'sam'; original = service.profile(pid)
        story = self.get('/api/feed/' + pid)['stories'][3]
        sid = story['id']; score = story['score']
        route = '/api/profiles/' + pid + '/feedback'
        vote = {'story_id': sid, 'value': 1, 'reason': 'interest'}
        self.post(route, vote); self.post(route, vote)
        up = next(s for s in self.get('/api/feed/' + pid)['stories'] if s['id'] == sid)
        self.assertGreater(up['score'], score)
        self.assertEqual(service.profile(pid)['feedback_count'], 1)
        self.post(route, {**vote, 'value': -1})
        down = next(s for s in self.get('/api/feed/' + pid)['stories'] if s['id'] == sid)
        self.assertLess(down['score'], score)
        self.post(route, {**vote, 'value': 0})
        undo = next(s for s in self.get('/api/feed/' + pid)['stories'] if s['id'] == sid)
        self.assertEqual(undo['score'], score)
        self.assertEqual(service.profile(pid)['feedback_count'], 0)
        for key in ['language', 'goal', 'depth', 'duration', 'interests']:
            self.assertEqual(service.profile(pid)[key], original[key])

    def test_repetition_feedback_does_not_reduce_other_topic_scores(self):
        before = {s['id']: s for s in self.get('/api/feed/mila')['stories']}
        story = next(s for s in before.values() if len(s['tags']) > 1)
        self.post('/api/profiles/mila/feedback', {'story_id': story['id'], 'value': -1, 'reason': 'repetition'})
        after = {s['id']: s for s in self.get('/api/feed/mila')['stories']}
        self.assertLess(after[story['id']]['score'], before[story['id']]['score'])
        for sid in before:
            if sid != story['id']:
                self.assertEqual(after[sid]['score'], before[sid]['score'])

    def test_new_listener_onboarding_persists(self):
        user = service.profile('new')
        payload = {**user, 'name': 'Test Listener', 'language': 'de', 'goal': 'trader',
                   'interests': {'forex': 5, 'economy': 4}, 'depth': 'detailed',
                   'wake_time': '06:45', 'plan':'plus', 'duration': 10, 'scheduled': True}
        status, saved, _ = request('PUT', '/api/profiles/new', payload)
        self.assertEqual(status, 200, saved)
        self.assertFalse(saved['onboarded'])
        status, saved, _ = request('PUT', '/api/profiles/new', {**payload,'onboarded':True})
        self.assertEqual(status, 200, saved)
        self.assertTrue(saved['onboarded'])
        reloaded = next(p for p in self.get('/api/bootstrap')['profiles'] if p['id'] == 'new')
        for key in ['name', 'language', 'goal', 'interests', 'depth', 'wake_time', 'duration', 'scheduled']:
            self.assertEqual(reloaded[key], payload[key])

    def test_duration_changes_chapters_and_length(self):
        result = []
        for duration in [1, 3, 7, 10]:
            p = service.profile('sam'); p['plan']='premium'; p['duration'] = duration; service.save_profile(p)
            e = self.post('/api/profiles/sam/editions')
            result.append((len(e['chapters']), e['estimated_seconds']))
            self.assertLessEqual(e['estimated_seconds'], duration * 60)
            self.assertTrue(all(ch['claim_source_ids'] for ch in e['chapters']))
        self.assertLess(result[0][0], result[1][0])
        self.assertLessEqual(result[1][0], result[2][0])
        self.assertLess(result[0][1], result[1][1])

    def test_detailed_goals_watchlist_and_multiple_tags(self):
        p = service.profile('new')
        saved = service.update_profile('new', service.Preferences(
            name=p['name'], goals=['investor', 'tech'], goal_tags=['earnings', 'chips'],
            interests={'earnings': 4, 'chips': 5}, symbols=['NVDA', 'NVDA'], duration=7,
        ))
        self.assertEqual(saved['goals'], ['investor', 'tech'])
        self.assertEqual(saved['symbols'], ['NVDA'])
        f = service.feed('new', topics='earnings,chips', limit=50)
        self.assertTrue(f['stories'])
        self.assertEqual(len({story['id'] for story in f['stories']}), len(f['stories']))
        self.assertTrue(any('earnings' in story['tags'] and 'chips' in story['tags'] for story in f['stories']))
        self.assertTrue(any('NVDA' in story['reason'] for story in f['stories']))
        self.assertTrue(all(tag['id'] not in saved['interests'] for tag in f['suggestions']))

    def test_feedback_memory_separates_dislikes_from_repetition(self):
        stories = self.get('/api/feed/mila')['stories']
        service.feedback('mila', service.Vote(story_id=stories[0]['id'], value=1))
        service.feedback('mila', service.Vote(story_id=stories[1]['id'], value=-1, reason='repetition'))
        memory = service.memory(service.profile('mila'))
        self.assertTrue(memory['liked_topics'])
        self.assertFalse(memory['disliked_topics'])
        service.feedback('mila', service.Vote(story_id=stories[1]['id'], value=-1))
        self.assertTrue(service.memory(service.profile('mila'))['disliked_topics'])

    def test_exports_are_separate_and_cite_claim_sources(self):
        listener=service.profile('mila'); listener['plan']='plus'; service.save_profile(listener)
        e = self.post('/api/profiles/mila/editions')
        exports = {}
        for kind in ['report', 'script']:
            status, body, headers = request('GET', '/api/editions/' + e['id'] + '/export', query={'kind': kind})
            self.assertEqual(status, 200)
            text = body.decode()
            self.assertIn(b'attachment;', headers[b'content-disposition'])
            self.assertIn(kind.encode(), headers[b'content-disposition'])
            self.assertIn('Dataset replay:', text)
            for ch in e['chapters']:
                self.assertIn(ch['summary'] if kind=='report' else ch['text'], text)
                for sid in ch['claim_source_ids']:
                    self.assertIn(sid, text)
            exports[kind] = text
        self.assertGreaterEqual(len(exports['report']), len(exports['script']))

    def test_listening_history_changes_since_last_listened(self):
        before = self.get('/api/feed/mila')
        self.assertTrue(before['since'])
        sid = before['since'][0]['id']
        self.post('/api/profiles/mila/listens', {'story_id': sid, 'seconds': 12, 'completed': False})
        after = self.get('/api/feed/mila')
        self.assertIn(sid, after['listening'])
        self.assertEqual(after['listening'][sid]['seconds'], 12)
        self.assertFalse(after['since'])
        self.assertIsNone(service.profile('new')['last_listened_at'])

    def test_invalid_inputs_are_rejected(self):
        original = service.profile('sam')
        for patch in [{'wake_time': '25:99'}, {'timezone': 'Not/AZone'}, {'language': 'xx'},
                      {'interests': {'nonexistent-topic': 3}}, {'duration': 99}]:
            status, _, _ = request('PUT', '/api/profiles/sam', {**original, **patch})
            self.assertEqual(status, 422, patch)
        self.assertEqual(request('GET', '/api/feed/missing')[0], 404)
        self.assertEqual(request('POST', '/api/profiles/sam/feedback', {'story_id': 'missing', 'value': 1})[0], 404)
        self.assertEqual(request('POST', '/api/profiles/sam/feedback', {'story_id': 'story-1', 'value': 8})[0], 422)
        limit_schema = next(p['schema'] for p in service.app.openapi()['paths']['/api/feed/{pid}']['get']['parameters'] if p['name'] == 'limit')
        self.assertEqual(limit_schema['maximum'], 150)

    def test_live_workflow_endpoints_are_disabled_without_secret(self):
        previous = os.environ.pop('WORKFLOW_SECRET', None)
        try:
            self.assertEqual(request('GET', '/api/integrations/due')[0], 503)
            self.assertEqual(request('POST', '/api/integrations/prepare', {})[0], 503)
        finally:
            if previous is not None:
                os.environ['WORKFLOW_SECRET'] = previous


if __name__ == '__main__':
    unittest.main()
