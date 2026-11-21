import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from . import server


class HistoryLibraryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.root=Path(self.temp.name)
  (self.root/'media').mkdir()
  self.patches=patch.multiple(server,DB=self.root/'test.db',ROOT=self.root)
  self.patches.start();server.init()
  # These tests exercise history and audio lifecycle; generation allowances have separate coverage.
  for listener in server.profiles():server.save_profile({**listener,'plan':'premium'})

 def tearDown(self):
  self.patches.stop();self.temp.cleanup()

 def test_views_are_profile_scoped_searchable_and_do_not_imply_likes(self):
  story=server.ranked('mila')[0]
  before=server.memory(server.profile('mila'))
  server.view_story('mila',server.StoryView(story_id=story['id']))
  source=story['sources'][0]
  server.view_story('mila',server.StoryView(article_id=source['article_id']))
  entries=server.history('mila')['entries']
  self.assertEqual(len(entries),1)
  self.assertEqual(entries[0]['view_count'],2)
  self.assertEqual(entries[0]['article_id'],source['article_id'])
  self.assertEqual(server.history('sam')['total'],0)
  self.assertEqual(server.history('mila',q=source['outlet'])['matches'],1)
  self.assertEqual(server.history('mila',q='nonexistent topic 9z')['matches'],0)
  self.assertEqual(server.history('mila',period='today')['matches'],1)
  self.assertEqual(server.memory(server.profile('mila')),before)
  self.assertEqual(server.history('mila',feedback='liked')['matches'],0)
  server.feedback('mila',server.Vote(story_id=story['id'],value=1))
  self.assertEqual(server.history('mila',feedback='liked')['matches'],1)
  self.assertEqual(server.history('mila',feedback='disliked')['matches'],0)
  server.feedback('mila',server.Vote(story_id=story['id'],value=-1))
  self.assertEqual(server.history('mila',feedback='disliked')['matches'],1)

 def test_views_validate_sources_and_recent_period(self):
  story=server.ranked('mila')[0]
  with self.assertRaises(HTTPException):server.view_story('mila',server.StoryView(story_id=story['id'],article_id='wrong-source'))
  with self.assertRaises(HTTPException):server.view_story('mila',server.StoryView(story_id='missing'))
  server.view_story('mila',server.StoryView(story_id=story['id']))
  with server.conn() as connection:
   old=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=10)).isoformat()
   connection.execute('UPDATE story_views SET last_viewed_at=?',(old,))
  self.assertEqual(server.history('mila',period='week')['matches'],0)
  self.assertEqual(server.history('mila')['matches'],1)

 def test_day_editions_use_no_future_reports_and_preserve_existing_snapshots(self):
  dates=server.briefing_dates()
  self.assertGreater(len(dates),1)
  old=server.create_edition('sam',day=dates[-1])
  self.assertEqual(old['news_date'],dates[-1])
  self.assertEqual(old['briefing_date'],dt.datetime.fromisoformat(old['created_at']).astimezone(server.ZoneInfo('Europe/Brussels')).date().isoformat())
  for chapter in old['chapters']:
   self.assertTrue(chapter['summary'])
   self.assertTrue(all(source['date'][:10]<=dates[-1] for source in chapter['sources']))
  recent=server.create_edition('sam',day=dates[0])
  self.assertGreaterEqual(len(recent['chapters']),len(old['chapters']))
  self.assertEqual(next(edition for edition in server.editions('sam') if edition['id']==old['id']),old)
  with self.assertRaises(HTTPException):server.create_edition('sam',day='2026-01-01')

 def test_new_briefing_uses_today_even_when_latest_sample_is_yesterday(self):
  with patch.object(server,'now',return_value='2026-11-20T08:00:00+00:00'):
   edition=server.create_edition('sam')
  self.assertEqual(edition['briefing_date'],'2026-11-20')
  self.assertEqual(edition['news_date'],server.CATALOG['as_of'][:10])
  self.assertEqual(edition['news_date'],'2026-11-19')
  exported=server.export_edition(edition['id']).body.decode()
  self.assertIn('Briefing date: 2026-11-20',exported)
  self.assertIn('Dataset replay: 2026-11-19',exported)

 def test_legacy_dates_are_corrected_without_changing_saved_content(self):
  with patch.object(server,'now',return_value='2026-11-19T23:30:00+00:00'):
   edition=server.compose('sam')
  self.assertEqual(edition['briefing_date'],'2026-11-20')
  legacy={**edition,'briefing_date':'2026-11-19'}
  del legacy['news_date']
  with server.conn() as connection:
   connection.execute('UPDATE editions SET data=? WHERE id=?',(json.dumps(legacy),legacy['id']))
  saved=server.editions('sam')[0]
  self.assertEqual(saved['briefing_date'],'2026-11-20')
  self.assertEqual(saved['news_date'],'2026-11-19')
  self.assertEqual(saved['created_at'],legacy['created_at'])
  self.assertEqual(saved['chapters'],legacy['chapters'])

 def attach_audio(self,edition,key='a'*64):
  path=self.root/'media'/(key+'.mp3');path.write_bytes(b'demo audio bytes')
  audio={'url':'/media/'+key+'.mp3','alignment':{}}
  edition['chapters'][0]['cache_key']=key
  edition['chapters'][0]['audio']=audio
  edition['audio_mode']='elevenlabs'
  with server.conn() as connection:
   connection.execute('UPDATE editions SET data=? WHERE id=?',(json.dumps(edition),edition['id']))
   connection.execute('INSERT OR REPLACE INTO audio_cache VALUES (?,?,?)',(key,json.dumps(audio),server.now()))
  return path

 def test_removing_audio_keeps_summaries_sources_and_frees_unshared_files(self):
  edition=server.compose('sam')
  path=self.attach_audio(edition)
  expected=[(chapter['summary'],chapter['sources']) for chapter in edition['chapters']]
  result=server.remove_edition_audio('sam',edition['id'])
  self.assertGreater(result['reclaimed_bytes'],0)
  self.assertFalse(path.exists())
  saved=result['edition']
  self.assertEqual(saved['audio_mode'],'summary-only')
  self.assertTrue(all(chapter['audio'] is None for chapter in saved['chapters']))
  self.assertEqual([(chapter['summary'],chapter['sources']) for chapter in saved['chapters']],expected)
  self.assertEqual(server.remove_edition_audio('sam',edition['id'])['reclaimed_bytes'],0)
  self.assertIn(edition['chapters'][0]['summary'],server.export_edition(edition['id']).body.decode())
  with server.conn() as connection:self.assertEqual(connection.execute('SELECT COUNT(*) FROM audio_cache').fetchone()[0],0)

 def test_shared_audio_is_kept_until_last_edition_releases_it(self):
  first=server.compose('sam');second=server.compose('mila')
  path=self.attach_audio(first);self.attach_audio(second)
  result=server.remove_edition_audio('sam',first['id'])
  self.assertEqual(result['reclaimed_bytes'],0)
  self.assertGreater(result['shared_bytes'],0)
  self.assertTrue(path.is_file())
  self.assertIsNotNone(server.editions('mila')[0]['chapters'][0]['audio'])
  server.remove_edition_audio('mila',second['id'])
  self.assertFalse(path.exists())

 def test_preview_removal_has_no_fake_savings_and_profiles_are_isolated(self):
  edition=server.compose('sam')
  with self.assertRaises(HTTPException):server.remove_edition_audio('mila',edition['id'])
  result=server.remove_edition_audio('sam',edition['id'])
  self.assertEqual(result['reclaimed_bytes'],0)
  self.assertEqual(result['edition']['audio_mode'],'summary-only')
