import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import server
from .feedback_learning import contribution,effective_weights

class FeedbackLearningTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.db=patch.object(server,'DB',Path(self.folder.name)/'learning.db');self.db.start();server.init()
  self.story=next(story for story in server.CATALOG['stories'] if story['curated'] and len(story['tags'])>1)
  self.primary=self.story.get('primary_topic') or self.story['tags'][0]
  self.base={tag:2 for tag in self.story['tags']}
  with patch.object(server,'now',return_value='2026-01-01T00:00:00+00:00'):
   server.update_profile('sam',server.Preferences.model_validate({**server.profile('sam'),'interests':self.base}))
 def tearDown(self):self.db.stop();self.folder.cleanup()
 def vote(self,value,reason='interest'):
  return server.feedback('sam',server.Vote(story_id=self.story['id'],value=value,reason=reason))
 def test_primary_has_greater_influence_and_total_vote_budget_is_one(self):
  delta=contribution(self.story,1)
  self.assertAlmostEqual(sum(delta.values()),1)
  self.assertGreater(delta[self.primary],max(value for tag,value in delta.items() if tag!=self.primary))
 def test_votes_change_visible_balance_and_reverse_without_drift(self):
  a=self.vote(1)['profile'];self.assertAlmostEqual(a['effective_interests'][self.primary],2.6)
  self.assertEqual(self.vote(1)['profile']['effective_interests'],a['effective_interests'])
  b=self.vote(-1)['profile'];self.assertAlmostEqual(b['effective_interests'][self.primary],1.4)
  c=self.vote(0)['profile'];self.assertEqual(c['effective_interests'],self.base)
  self.assertEqual(c['interests'],self.base,'Implicit learning overwrote explicit settings')
 def test_manual_override_is_immediate_and_stale_retry_does_not_undo_it(self):
  before='2026-11-20T10:00:00+00:00';after='2026-11-20T10:01:00+00:00'
  with patch.object(server,'now',return_value=before):self.vote(1)
  with patch.object(server,'now',return_value=after):
   updated=server.update_profile('sam',server.Preferences.model_validate({**server.profile('sam'),'interests':{**self.base,self.primary:0},'interest_edits':[self.primary]}))
  self.assertEqual(updated['effective_interests'][self.primary],0)
  with patch.object(server,'now',return_value='2026-11-20T10:02:00+00:00'):self.vote(1)
  self.assertEqual(server.profile('sam')['effective_interests'][self.primary],0,'An identical vote retry overrode a newer manual choice')
  with patch.object(server,'now',return_value='2026-11-20T10:03:00+00:00'):
   self.vote(0);fresh=self.vote(1)['profile']
  self.assertAlmostEqual(fresh['effective_interests'][self.primary],.6)
 def test_non_interest_reasons_do_not_penalize_the_whole_topic(self):
  self.vote(1);result=self.vote(-1,'technical')['profile']
  self.assertEqual(result['effective_interests'],self.base)
 def test_newer_same_vote_after_reset_relearns_and_retry_is_idempotent(self):
  before='2026-11-20T10:00:00+00:00';reset='2026-11-20T10:01:00+00:00';renewed='2026-11-20T10:02:00+00:00'
  with patch.object(server,'now',return_value=before):
   server.feedback('sam',server.Vote(story_id=self.story['id'],value=1,occurred_at=before))
  with patch.object(server,'now',return_value=reset):
   server.update_profile('sam',server.Preferences.model_validate({**server.profile('sam'),'interests':{**self.base,self.primary:0},'interest_edits':[self.primary]}))
  with patch.object(server,'now',return_value=renewed):
   action=server.Vote(story_id=self.story['id'],value=1,occurred_at=renewed)
   result=server.feedback('sam',action);retry=server.feedback('sam',action)
  self.assertAlmostEqual(result['profile']['effective_interests'][self.primary],.6)
  self.assertEqual(result['vote'],retry['vote'])
  self.assertEqual(result['vote']['created_at'],'2026-11-20T10:02:00.000000+00:00')
 def test_stale_vote_response_contains_authoritative_persisted_vote(self):
  newest='2026-11-20T10:02:00+00:00';older='2026-11-20T10:01:00+00:00'
  with patch.object(server,'now',return_value=newest):
   saved=server.feedback('sam',server.Vote(story_id=self.story['id'],value=1,occurred_at=newest))
   stale=server.feedback('sam',server.Vote(story_id=self.story['id'],value=-1,reason='technical',occurred_at=older))
  self.assertEqual(stale['vote'],saved['vote'])
  self.assertEqual(stale['vote']['value'],1)
  self.assertEqual(stale['vote']['reason'],'interest')
 def test_feed_includes_persisted_feedback_time_and_reason(self):
  original=server.feed('sam',limit=150)
  story=next(item for item in original['stories'] if any(x['id']==item['id'] for x in original['preview_stories']))
  saved=server.feedback('sam',server.Vote(story_id=story['id'],value=-1,reason='technical'))['vote']
  result=server.feed('sam',limit=150)
  for items in (result['stories'],result['preview_stories']):
   item=next(x for x in items if x['id']==story['id'])
   self.assertEqual(item['feedback_at'],saved['created_at'])
   self.assertEqual(item['feedback_reason'],'technical')
 def test_delayed_manual_edit_cannot_move_reset_backward(self):
  newer='2026-11-20T10:02:00+00:00';older='2026-11-20T10:01:00+00:00'
  with patch.object(server,'now',return_value=newer):
   newer_edit={**server.profile('sam'),'interest_edits':[self.primary],'interest_edit_times':{self.primary:newer}}
   server.update_profile('sam',server.Preferences.model_validate(newer_edit))
   older_edit={**server.profile('sam'),'interest_edits':[self.primary],'interest_edit_times':{self.primary:older}}
   result=server.update_profile('sam',server.Preferences.model_validate(older_edit))
  self.assertEqual(result['interest_resets'][self.primary],'2026-11-20T10:02:00.000000+00:00')
 def test_learning_is_profile_scoped_and_not_stored_as_manual_preferences(self):
  self.vote(1)
  self.assertEqual(server.profile('mila')['learned_interests'],{})
  with server.conn() as c:data=json.loads(c.execute('SELECT data FROM profiles WHERE id=?',('sam',)).fetchone()[0])
  self.assertNotIn('learned_interests',data);self.assertNotIn('effective_interests',data)
 def test_influence_is_bounded_even_when_raw_vote_count_grows(self):
  self.assertEqual(effective_weights({'x':2},{'x':200})['x'],4)
  self.assertEqual(effective_weights({'x':2},{'x':-200})['x'],0)
  self.assertEqual(effective_weights({}, {'x':-200},signed=True)['x'],-2)
