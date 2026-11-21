import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import catch_up, server


def story(sid='one',**changes):
 return {'id':sid,'title':'Nvidia quarterly earnings beat investor forecasts',
         'summary':'Nvidia reported quarterly revenue of 40 billion dollars as demand for data centre chips accelerated. Investors await management guidance for the coming quarter.',
         'entities':['Nvidia'],'sources':[{'article_id':'report-1','url':'https://news.example/nvidia-earnings','translation_key':'earnings-1'}],
         'published_at':'2026-11-18T10:00:00Z','updated_at':'2026-11-18T10:00:00Z','tags':['markets','technology'],**changes}


class CatchUpMatchingTests(unittest.TestCase):
 def setUp(self):self.old=story();self.known=[{'snapshot':catch_up.snapshot(self.old)}]
 def updates(self,*items):return catch_up.select_updates(items,self.known,'2026-11-18T12:00:00Z')
 def test_seen_story_and_newer_timestamp_alone_do_not_repeat(self):
  self.assertFalse(self.updates(self.old,story(updated_at='2026-11-19T12:00:00Z')))
 def test_added_source_translation_tags_and_image_are_not_developments(self):
  new=copy.deepcopy(self.old);new['updated_at']='2026-11-19T12:00:00Z'
  new['sources'].append({'article_id':'german-copy'});new['tags'].append('ai');new['summaries']={'de':'Neu übersetzt'};new['image_url']='new.jpg'
  self.assertFalse(self.updates(new))
 def test_different_id_syndication_is_not_new_news(self):
  self.assertFalse(self.updates(story('copy',published_at='2026-11-19T12:00:00Z',updated_at='2026-11-19T12:00:00Z')))
 def test_actual_new_details_link_to_history(self):
  new=story(updated_at='2026-11-19T12:00:00Z',summary=self.old['summary']+' Management raised its outlook and announced a factory expansion in Arizona.')
  update=self.updates(new)[0]
  self.assertEqual(update['catch_up_kind'],'development');self.assertEqual(update['catch_up_previous_id'],'one')
 def test_new_number_with_context_counts(self):
  new=story(updated_at='2026-11-19T12:00:00Z',summary=self.old['summary'].replace('40 billion','45 billion').replace('reported quarterly','revised quarterly'))
  self.assertEqual(self.updates(new)[0]['catch_up_kind'],'development')
 def test_entity_and_event_similarity_detect_new_followup_id(self):
  new=story('follow-up',sources=[{'article_id':'independent-new-report'}],updated_at='2026-11-19T12:00:00Z',summary=self.old['summary']+' Management raised its outlook and announced a factory expansion in Arizona.')
  self.assertEqual(self.updates(new)[0]['catch_up_kind'],'development')
 def test_same_company_and_tags_alone_do_not_link_different_events(self):
  new=story('leadership',sources=[{'article_id':'ceo-report'}],title='Nvidia appoints a new chief executive',summary='The board has selected a successor following a lengthy leadership review.',published_at='2026-11-19T12:00:00Z')
  self.assertEqual(self.updates(new)[0]['catch_up_kind'],'new')
 def test_old_unrelated_story_is_not_promoted_by_new_metadata(self):
  new=story('oil',sources=[],title='Oil output changes',summary='Producers discuss supply cuts.',entities=['OPEC'],updated_at='2026-11-19T12:00:00Z')
  self.assertFalse(self.updates(new))
 def test_reading_latest_copy_suppresses_older_duplicate(self):
  self.known.append({'snapshot':catch_up.snapshot(story('latest',updated_at='2026-11-20T12:00:00Z'))})
  self.assertFalse(self.updates(story('duplicate',updated_at='2026-11-19T12:00:00Z')))
 def test_new_listener_without_history_gets_no_invented_catchup(self):
  self.assertFalse(catch_up.select_updates([story()],[],None))


class CatchUpHistoryTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.db=patch.object(server,'DB',Path(self.folder.name)/'catch-up.db');self.db.start();server.init()
  self.item=next(item for item in server.CATALOG['stories'] if item['curated'])
 def tearDown(self):self.db.stop();self.folder.cleanup()
 def test_views_and_listens_capture_profile_scoped_content_snapshots(self):
  server.view_story('sam',server.StoryView(story_id=self.item['id']))
  known,baseline=server.catch_up_history('sam',server.profile('sam'),{})
  self.assertEqual(known[0]['snapshot']['summary'],catch_up.snapshot(self.item)['summary'])
  self.assertEqual(baseline,server.CATALOG['as_of'])
  self.assertEqual(server.catch_up_history('new',server.profile('new'),{})[0],[])
  server.listen('mila',server.Listen(story_id=self.item['id'],seconds=12))
  self.assertEqual(len(server.catch_up_history('mila',server.profile('mila'),{})[0]),1)
 def test_stored_content_survives_catalog_updates_and_drives_feed(self):
  server.view_story('sam',server.StoryView(story_id=self.item['id']))
  updated=copy.deepcopy(self.item)
  updated['summary']+=' The board confirmed a new factory expansion in Arizona following regulatory approval.'
  updated['summaries']={**updated.get('summaries',{}),'en':updated['summary']}
  updated['updated_at']='2026-11-22T10:00:00Z'
  with patch.object(server,'ranked',return_value=[updated]):
   results=server.feed('sam',limit=50)['since']
  self.assertEqual(len(results),1);self.assertEqual(results[0]['catch_up_kind'],'development')
 def test_replaying_an_old_episode_does_not_mark_latest_news_as_heard(self):
  old=catch_up.snapshot(self.item);old.update(summary='The company awaited a board decision.',updated_at='2026-11-01T00:00:00Z')
  edition={'id':'old-edition','chapters':[{'story_id':self.item['id'],'story_snapshot':old}]}
  with server.conn() as c:c.execute('INSERT INTO editions VALUES (?,?,?,?)',('old-edition','sam',json.dumps(edition),server.now()))
  server.listen('sam',server.Listen(story_id=self.item['id'],seconds=12,edition_id='old-edition'))
  known,_=server.catch_up_history('sam',server.profile('sam'),{})
  self.assertEqual(known[0]['snapshot']['summary'],old['summary'])
  server.view_story('sam',server.StoryView(story_id=self.item['id']))
  server.listen('sam',server.Listen(story_id=self.item['id'],seconds=15,edition_id='old-edition'))
  known,_=server.catch_up_history('sam',server.profile('sam'),{})
  self.assertEqual(known[0]['snapshot']['updated_at'],self.item['updated_at'])


if __name__=='__main__':unittest.main()
