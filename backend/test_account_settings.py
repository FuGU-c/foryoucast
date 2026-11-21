"""Plan preferences, translation selection and local credential privacy."""
import copy
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from . import server
from .key_vault import unprotect

class AccountSettingsTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
  self.db=patch.object(server,'DB',Path(self.folder.name)/'test.db');self.db.start();server.init()
 def tearDown(self):
  self.db.stop();self.folder.cleanup()
 def update(self,pid='sam',**changes):
  return server.update_profile(pid,server.Preferences.model_validate({**server.profile(pid),**changes}))
 def test_free_plan_and_downgrade_keep_preferences_but_disable_premium_processing(self):
  p=self.update(plan='plus',tts_provider='elevenlabs',translate_news=True,device_voices={'en':['Microsoft A','Microsoft B']})
  self.assertEqual(p['tts_provider'],'elevenlabs')
  p=self.update(plan='free')
  self.assertEqual(p['tts_provider'],'device');self.assertFalse(p['translate_news'])
  self.assertEqual(p['device_voices']['en'],['Microsoft A','Microsoft B'])
 def test_voices_survive_reload_but_personal_models_are_retired(self):
  self.update(device_voices={'en':['Voice A'],'de':['Stimme B']},ai_settings={'provider':'openai','summary_model':'example-summary-model'})
  p=server.profile('sam');body={key:value for key,value in p.items() if key not in ['device_voices','ai_settings','plan']}
  server.update_profile('sam',server.Preferences.model_validate(body))
  p=server.profile('sam');self.assertEqual(p['device_voices']['de'],['Stimme B']);self.assertEqual(p['ai_settings']['provider'],'demo');self.assertEqual(p['ai_settings']['summary_model'],'')
  with self.assertRaises(ValidationError):server.Preferences.model_validate({**p,'device_voices':{'en':['A','A']}})
  with self.assertRaises(ValidationError):server.Preferences.model_validate({**p,'device_voices':{'en':['A','B','C']}})
 def test_personal_model_key_connections_are_retired_for_every_plan(self):
  for plan in ['free','plus','premium']:
   self.update(plan=plan)
   with self.assertRaises(HTTPException) as error:server.save_provider_key('sam','openai',server.ProviderKey(api_key='not-a-real-test-key'))
   self.assertEqual(error.exception.status_code,410)
   self.assertEqual(json.loads(server.provider_key_status('sam').body)['configured'],[])
 def test_legacy_key_can_still_be_removed_without_decrypting_it(self):
  with server.conn() as c:c.execute('INSERT INTO provider_keys VALUES (?,?,?)',('sam','openai',b'old-encrypted-value'))
  server.delete_provider_key('sam','openai')
  self.assertEqual(json.loads(server.provider_key_status('sam').body)['configured'],[])
  with self.assertRaises(ValidationError):server.ProviderKey(api_key=' '*15)
 def test_credential_validation_does_not_echo_rejected_secret_input(self):
  marker='rejected-secret-marker'
  request=Request({'type':'http','path':'/api/profiles/sam/provider-keys/openai','headers':[],'query_string':b'','scheme':'http','server':('test',80)})
  error=RequestValidationError([{'loc':['body','api_key'],'msg':'Invalid key','type':'value_error','input':marker}])
  response=asyncio.run(server.safe_validation_error(request,error))
  self.assertEqual(response.status_code,422);self.assertNotIn(marker,response.body.decode())
 def test_plus_can_include_reviewed_translation_without_changing_source_ids(self):
  story=copy.deepcopy(next(story for story in server.CATALOG['stories'] if story['curated']))
  story['id']='translation-fixture';story['sources']=[{**story['sources'][0],'article_id':'german-original','language':'de'}];story['claim_source_ids']=['german-original'];story['summaries']['en']='Reviewed English translation of this story.'
  self.update(language='en',news_languages=['en'])
  with patch.object(server,'CATALOG',{**server.CATALOG,'stories':[story]}),patch.object(server,'refresh_catalog'):
   self.assertEqual(server.ranked('sam',for_podcast=True),[])
   self.update(plan='plus',translate_news=False);self.assertEqual(server.ranked('sam',for_podcast=True),[])
   self.update(translate_news=True)
   included=server.ranked('sam',for_podcast=True)
   self.assertEqual(len(included),1);self.assertEqual(included[0]['claim_source_ids'],['german-original'])
   self.assertEqual(included[0]['sources'][0]['language'],'de')
   self.assertEqual(server.ranked('sam'),[],'Podcast translation must not change Discover language filters')
 def test_elevenlabs_random_pair_is_language_matched_and_changes_cache_key(self):
  self.update(plan='plus',tts_provider='elevenlabs')
  e=server.compose('sam');self.assertEqual(len(e['voice_ids']),2);self.assertEqual(len(set(e['voice_ids'])),2)
  available={voice['id'] for voice in json.loads((server.ROOT/'public/voice-samples.json').read_text()) if voice['language']=='en'}
  self.assertTrue(set(e['voice_ids']).issubset(available))
  a,b=list(available)[:2]
  p=server.profile('sam');story=server.ranked('sam')[0]
  first=server.chapter(story,{**p,'selected_voice_ids':[a,b]});second=server.chapter(story,{**p,'selected_voice_ids':[b,a]})
  self.assertNotEqual(first['cache_key'],second['cache_key'])

 def test_plan_durations_are_clamped_and_premium_supports_forty_minutes(self):
  for plan,limit in [('free',7),('plus',15),('premium',40)]:
   saved=self.update(plan=plan,duration=40)
   self.assertEqual(saved['duration'],limit)
 def test_free_daily_generation_limit_is_atomic_and_audio_removal_does_not_reset_it(self):
  from concurrent.futures import ThreadPoolExecutor
  def attempt():
   try:return server.compose('sam')['id']
   except HTTPException as error:return error.status_code
  with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(lambda _:attempt(),range(2)))
  self.assertEqual(sum(isinstance(value,str) for value in outcomes),1)
  self.assertIn(429,outcomes)
  edition_id=next(value for value in outcomes if isinstance(value,str));server.remove_edition_audio('sam',edition_id)
  self.assertFalse(server.daily_usage(server.profile('sam'))['can_create'])
 def test_flow_has_one_natural_edition_then_unlimited_basic(self):
  self.update(plan='plus',tts_provider='elevenlabs',duration=15)
  editions=[server.compose('sam') for _ in range(3)]
  self.assertEqual([edition['tts_provider'] for edition in editions],['elevenlabs','device','device'])
  self.assertTrue(all(edition['estimated_seconds']<=900 for edition in editions))
  self.assertEqual(server.daily_usage(server.profile('sam'))['natural_remaining'],0)
 def test_horizon_does_not_limit_natural_editions(self):
  self.update(plan='premium',tts_provider='elevenlabs',duration=40)
  self.assertTrue(all(server.compose('sam')['tts_provider']=='elevenlabs' for _ in range(3)))
 def test_free_summaries_keep_original_language_without_translated_variants(self):
  story=copy.deepcopy(next(story for story in server.CATALOG['stories'] if story['curated']))
  story['sources']=[{**story['sources'][0],'language':'de','article_id':'original-de'}];story['claim_source_ids']=['original-de']
  story['summaries']={'de':'Deutsches Original.','en':'English translation.'}
  free=server.localized_story(story,'en',['de'],allow_translation=False)
  self.assertEqual(free['summary_language'],'de');self.assertEqual(free['summary'],'Deutsches Original.')
  self.assertNotIn('en',free['summaries']);self.assertFalse(free['ai_translated'])
  paid=server.localized_story(story,'en',['de'],allow_translation=True)
  self.assertTrue(paid['ai_translated']);self.assertEqual(paid['summary_language'],'en')
