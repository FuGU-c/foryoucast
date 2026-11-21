import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import server
from .import_news import append_batch


class IncomingTests(unittest.TestCase):
    def test_new_reporting_refreshes_visible_feed_and_prompt_once(self):
        with tempfile.TemporaryDirectory(dir=server.DB.parent) as folder:
            root=Path(folder)
            catalog=root/'catalog.json'
            catalog.write_bytes(server.CATALOG_PATH.read_bytes())
            db=root/'test.db'
            with patch.multiple(server, DB=db, CATALOG_PATH=catalog, CATALOG_MTIME=0,
                                CATALOG=server.CATALOG, STORIES=server.STORIES, NOW=server.NOW):
                server.init()
                server.save_profile({**server.profile('mila'),'plan':'plus'})
                initial=server.bootstrap()
                date=(server.NOW+dt.timedelta(minutes=10)).isoformat()
                batch=root/'new.jsonl'
                base={'date':date,'translation_group_id':'fixture-event','event_id':'fixture-event',
                      'publication':{'name':'Example News'},'company_tickers':['ACME'],
                      'provider_categories':['Space exploration','Trending']}
                english={**base,'$id':'fixture-en','headline':'Acme expands its research program',
                         'language':'en','permalink':'https://example.com/en/research'}
                german={**base,'$id':'fixture-de','headline':'Acme erweitert sein Forschungsprogramm',
                        'language':'de','permalink':'https://example.com/de/forschung'}
                batch.write_text('\n'.join(map(json.dumps,[english,german])),encoding='utf-8')
                self.assertEqual(append_batch(batch,catalog),2)
                self.assertEqual(append_batch(batch,catalog),0)
                updated=server.bootstrap()
                self.assertNotEqual(initial['catalog_version'],updated['catalog_version'])
                self.assertEqual(updated['latest_news_at'],date)
                feed=server.feed('mila',limit=100)
                group=next(story for story in feed['stories'] if 'ticker-acme' in story['tags'])
                self.assertEqual({source['language'] for source in group['sources']},{'en','de'})
                self.assertEqual(len({source['translation_key'] for source in group['sources']}),1)
                suggestion=next(topic for topic in feed['suggestions'] if topic['id']=='ticker-acme')
                self.assertEqual(suggestion['example'],english['headline'])
                self.assertEqual(suggestion['count'],1)
                self.assertIn('section-space-exploration',group['tags'])
                self.assertNotIn('section-trending',group['tags'])
                self.assertIn('Space exploration',[topic['label'] for topic in updated['topics']])
                self.assertTrue(all(chapter['story_id']!=group['id'] for chapter in server.compose('mila')['chapters']))
