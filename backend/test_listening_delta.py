import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import server


class ListeningDeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.locations=patch.multiple(server,ROOT=root,DB=root/'test.db')
        self.locations.start();server.init()
        profile=server.profile('sam')
        profile.update(plan='premium',language='en',news_languages=['en','nl','de'],translate_news=True)
        server.save_profile(profile)
        self.story=server.ranked('sam',for_podcast=True)[0]

    def tearDown(self):
        self.locations.stop();self.temp.cleanup()

    def test_completed_unchanged_story_is_not_regenerated_but_can_be_read(self):
        server.listen('sam',server.Listen(story_id=self.story['id'],seconds=60,completed=True))
        self.assertNotIn(self.story['id'],[item['id'] for item in server.ranked('sam',for_podcast=True)])
        self.assertIn(self.story['id'],[item['id'] for item in server.ranked('sam')])
        updated=copy.deepcopy(server.CATALOG)
        for item in updated['stories']:
            if item['id']==self.story['id']:
                item['updated_at']=(dt.datetime.fromisoformat(item['updated_at'])+dt.timedelta(seconds=1)).isoformat()
        with patch.object(server,'CATALOG',updated):
            self.assertIn(self.story['id'],[item['id'] for item in server.ranked('sam',for_podcast=True)])

    def test_partial_listen_does_not_hide_a_story(self):
        server.listen('sam',server.Listen(story_id=self.story['id'],seconds=10,completed=False))
        self.assertIn(self.story['id'],[item['id'] for item in server.ranked('sam',for_podcast=True)])
