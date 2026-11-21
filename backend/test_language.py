"""Language/provenance regression tests; no network or paid API calls."""
import copy
import json
import tempfile
import unittest
import datetime as dt
from pathlib import Path
from unittest.mock import patch
from . import server


class LanguageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.db_patch=patch.object(server,'DB',Path(self.tmp.name)/'test.db')
  self.db_patch.start();server.init()
  self.story={
   'id':'test-story','title':'An English title',
   'titles':{'en':'An English title','nl':'Een Nederlandse titel','de':'Ein deutscher Titel'},
   'summary':'English summary. The evidence is English.',
   'summaries':{'en':'English summary. The evidence is English.','nl':'Een Nederlandse samenvatting. Het bewijs is Engelstalig.','de':'Eine deutsche Zusammenfassung. Der Beleg ist englisch.'},
   'sources':[
    {'article_id':'en-support','outlet':'Supporting publisher','url':'https://example.com/en','language':'en','date':'2026-11-18T10:00:00+00:00'},
    {'article_id':'nl-related','outlet':'Dutch related publisher','url':'https://example.com/nl','language':'nl','date':'2026-11-18T10:05:00+00:00'},
    {'article_id':'de-related','outlet':'German related publisher','url':'https://example.com/de','language':'de','date':'2026-11-18T10:06:00+00:00'},
   ],
   'claim_source_ids':['en-support'],'updated_at':'2026-11-18T10:06:00+00:00','curated':True,'tags':['technology'],
  }

 def tearDown(self):
  self.db_patch.stop();self.tmp.cleanup()

 def test_native_sources_are_first_without_rewriting_evidence(self):
  original=copy.deepcopy(self.story)
  for language,source_id in [('nl','nl-related'),('de','de-related'),('en','en-support')]:
   item=server.localized_story(self.story,language)
   self.assertEqual(item['sources'][0]['article_id'],source_id)
   self.assertEqual(item['title'],self.story['titles'][language])
   self.assertEqual(item['summary'],self.story['summaries'][language])
   self.assertEqual(item['claim_source_ids'],['en-support'])
   self.assertTrue(item['source_language_available'])
  self.assertEqual(self.story,original)

 def test_missing_native_report_is_disclosed(self):
  self.story['sources']=self.story['sources'][:1]
  item=server.localized_story(self.story,'nl')
  self.assertFalse(item['source_language_available'])
  self.assertEqual(item['preferred_sources'][0]['language'],'en')
  self.assertEqual(item['available_source_languages'],['en'])
  self.assertIn('Vertaalde samenvatting',item['source_language_note'])
  self.assertEqual(item['summary_language'],'nl')

 def test_multiselect_feed_and_independent_narration(self):
  server.update_profile('jonas',server.Preferences(name='Jonas',language='de',news_languages=['de','en'],goal='investor',plan='plus'))
  stories=server.feed('jonas',languages='de,en',limit=50)['stories']
  bilingual=next(story for story in stories if set(story['news_languages_available'])=={'de','en'})
  self.assertEqual({src['language'] for src in bilingual['selected_language_sources']},{'de','en'})
  self.assertTrue(all(src.get('headline') for src in bilingual['selected_language_sources']))
  self.assertTrue(any(story['news_languages_available']==['en'] for story in stories))
  self.assertTrue(all(ch['language']=='de' for ch in server.compose('jonas')['chapters']))

  server.update_profile('jonas',server.Preferences(name='Jonas',language='de',news_languages=['de'],goal='investor'))
  german=server.feed('jonas',limit=50)['stories']
  self.assertTrue(german)
  self.assertTrue(all(story['news_languages_available']==['de'] for story in german))
  self.assertTrue(any(src['language']=='en' for story in german for src in story['sources']))
  self.assertEqual(server.feed('jonas',languages='en',limit=50)['stories'],[])

 def test_spoken_attribution_uses_supporting_source(self):
  p=server.profile('mila')
  item=server.localized_story(self.story,p['language'])
  ch=server.chapter(item,p)
  self.assertTrue(ch['text'].startswith('Volgens Supporting publisher'))
  self.assertNotIn('Volgens Dutch related publisher',ch['text'])
  self.assertIn('Nederlandse samenvatting',ch['text'])
  self.assertEqual(ch['attribution_source_id'],'en-support')
  self.assertEqual(ch['sources'][0]['language'],'nl')
  self.assertEqual(ch['claim_source_ids'],['en-support'])

 def test_chapter_cache_varies_with_language_depth_and_model(self):
  p=server.profile('mila');s=server.localized_story(self.story,'nl')
  first=server.chapter(s,p)
  other=dict(p,language='de')
  self.assertNotEqual(first['cache_key'],server.chapter(server.localized_story(self.story,'de'),other)['cache_key'])
  self.assertNotEqual(first['cache_key'],server.chapter(s,dict(p,depth='detailed'))['cache_key'])
  with patch.dict(server.os.environ,{'ELEVENLABS_MODEL_ID':'different-model'}):
   self.assertNotEqual(first['cache_key'],server.chapter(s,p)['cache_key'])

 def test_real_catalog_retains_language_variants(self):
  items=server.ranked('mila')
  native=[s for s in items if s['source_language_available']]
  self.assertTrue(native)
  self.assertTrue(all(s['sources'][0]['language']=='nl' for s in native))
  for item in items:
   self.assertTrue(set(item['claim_source_ids']).issubset({s['article_id'] for s in item['sources']}))

 def test_feedback_does_not_change_explicit_language_or_topics(self):
  before=server.profile('mila')
  story=next(s for s in server.CATALOG['stories'] if s['curated'])
  server.feedback('mila',server.Vote(story_id=story['id'],value=1))
  after=server.profile('mila')
  self.assertEqual(before['interests'],after['interests'])
  self.assertEqual(before['language'],after['language'])
  self.assertEqual(after['feedback_count'],1)

 def test_connections_close_after_transaction(self):
  with server.conn() as c:c.execute('SELECT 1')
  with self.assertRaises(server.sqlite3.ProgrammingError):c.execute('SELECT 1')

 def test_native_only_headline_has_honest_language(self):
  self.story['titles']={'de':'Ein deutscher Titel'}
  self.story['title']='Ein deutscher Titel'
  self.story['sources']=[self.story['sources'][2]]
  item=server.localized_story(self.story,'en')
  self.assertEqual(item['title_language'],'de')
  self.assertFalse(item['source_language_available'])
  self.assertEqual(item['available_source_languages'],['de'])

 def test_schedule_reservation_is_idempotent_and_token_scoped(self):
  p=server.profile('mila')
  local=dt.datetime.now(server.ZoneInfo(p['timezone']))
  target=local+dt.timedelta(minutes=5)
  if target.date()!=local.date():self.skipTest('Schedule test crosses local midnight')
  p.update(scheduled=True,wake_time=target.strftime('%H:%M'));server.save_profile(p)
  body=server.ScheduleClaim(profile_id='mila',day=local.date().isoformat())
  with patch.dict(server.os.environ,{'WORKFLOW_SECRET':'unit-test-only'}):
   first=server.workflow_schedule_claim(body,'unit-test-only')
   second=server.workflow_schedule_claim(body,'unit-test-only')
   self.assertTrue(first['claimed']);self.assertFalse(second['claimed'])
   bad=server.ScheduleRelease(**body.model_dump(),claim_token='cloud-reserved-'+'0'*32)
   self.assertFalse(server.workflow_schedule_release(bad,'unit-test-only')['released'])
   good=server.ScheduleRelease(**body.model_dump(),claim_token=first['claim_token'])
   self.assertTrue(server.workflow_schedule_release(good,'unit-test-only')['released'])
   self.assertTrue(server.workflow_schedule_claim(body,'unit-test-only')['claimed'])


if __name__=='__main__':unittest.main()
