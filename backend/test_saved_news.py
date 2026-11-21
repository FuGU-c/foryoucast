"""Saved stories persist independently of reading and preference feedback."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from . import server


class SavedNewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = patch.multiple(server, DB=root/'test.db', ROOT=root)
        self.patches.start()
        self.clock = patch.object(server, 'now', return_value='2026-11-21T12:00:00+00:00')
        self.clock.start()
        server.init()
        self.story = next(story for story in server.STORIES.values() if story['curated'])

    def tearDown(self):
        self.clock.stop()
        self.patches.stop()
        self.temp.cleanup()

    def save(self, value=True, timestamp=None, pid='mila'):
        return server.save_story(pid, self.story['id'], server.SavedStoryChange(saved=value, occurred_at=timestamp))

    def test_save_is_idempotent_persisted_and_profile_scoped(self):
        first = self.save()
        self.assertEqual(first, self.save())
        server.init()
        self.assertEqual(server.saved_news('mila', q='', period='all')['stories'][0]['id'], self.story['id'])
        self.assertEqual(server.saved_news('jonas', q='', period='all')['total'], 0)

    def test_late_save_cannot_undo_newer_unsave(self):
        self.save(True, '2026-11-21T09:00:00+00:00')
        self.save(False, '2026-11-21T09:02:00+00:00')
        self.assertFalse(self.save(True, '2026-11-21T09:01:00+00:00')['saved'])
        self.assertFalse(server.saved_news('mila', q='', period='all')['stories'])
        self.assertTrue(self.save(True, '2026-11-21T09:03:00+00:00')['saved'])

    def test_saved_search_matches_sources_and_tags(self):
        self.save()
        for term in [self.story['tags'][0], self.story['sources'][0]['outlet']]:
            self.assertEqual(server.saved_news('mila', q=term, period='all')['matches'], 1)
        self.assertEqual(server.saved_news('mila', q='no-such-report-1234', period='all')['matches'], 0)

    def test_saved_dates_filter_and_saving_does_not_signal_liking(self):
        self.save(True, '2026-11-10T09:00:00+00:00')
        self.assertEqual(server.saved_news('mila', q='', period='today')['matches'], 0)
        self.assertEqual(server.saved_news('mila', q='', period='week')['matches'], 0)
        with server.conn() as db:
            for table in ('feedback', 'listens', 'editions', 'story_views'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_unknown_story_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            server.save_story('mila', 'missing', server.SavedStoryChange(saved=True))
        self.assertEqual(error.exception.status_code, 404)
