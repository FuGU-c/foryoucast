from __future__ import annotations
import base64, datetime as dt, hashlib, json, math, os, re, secrets, sqlite3, sys, uuid
from pathlib import Path
from typing import Literal
from functools import lru_cache
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from .feedback_learning import learned_weights, effective_weights
from .prepare import ROOT, TOPICS, TOPIC_LABELS
from .news_topics import story_topics
from .article_store import read_article
from . import cloud_client, cloud_jobs, catch_up

DB = ROOT/'data'/'liquid.db'
CATALOG_PATH = ROOT/'data'/'catalog.json'
CATALOG_MTIME = CATALOG_PATH.stat().st_mtime_ns

def read_catalog():
 catalog=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
 topics={topic['id']:topic for topic in catalog['topics']}
 for story in catalog['stories']:
  if not story['curated']:continue
  headline=story['title']+' '+next((src.get('headline','') for src in story['sources'] if src['article_id'] in story['claim_source_ids']),'')
  matched=story_topics(headline)
  for topic in matched:topics[topic['id']]=topic
  story['tags']=list(dict.fromkeys(story['tags']+[topic['id'] for topic in matched]))
 catalog['topics']=list(topics.values())
 return catalog

CATALOG = read_catalog()
STORIES = {s['id']:s for s in CATALOG['stories']}
NOW = dt.datetime.fromisoformat(CATALOG['as_of'])

GOALS = [
 {'id':'general','label':'Catch up on the big stories','tags':['world','diplomacy','elections','culture','outages']},
 {'id':'investor','label':'Follow companies and investments','tags':['markets','earnings','funds','deals','technology']},
 {'id':'trader','label':'Track currencies and central banks','tags':['forex','fx-pairs','economy','rates','inflation','trade']},
 {'id':'tech','label':'Keep up with technology','tags':['technology','ai','chips','outages','deals']},
 {'id':'practical','label':'Find useful news for everyday money','tags':['money','consumer','banking','inflation','energy']},
]
Goal = Literal['general','investor','trader','tech','practical']
VISIBLE_PROFILE_IDS = frozenset({'mila','jonas','alex','sam','free-demo','medium-demo','new'})

def refresh_catalog():
 global CATALOG, CATALOG_MTIME, STORIES, NOW
 try:
  revision=CATALOG_PATH.stat().st_mtime_ns
  if revision==CATALOG_MTIME:return
  published=read_catalog()
  index={story['id']:story for story in published['stories']}
  as_of=dt.datetime.fromisoformat(published['as_of'])
 except (OSError,ValueError,KeyError):
  return
 CATALOG, STORIES, NOW, CATALOG_MTIME=published,index,as_of,revision

class ClosingConnection(sqlite3.Connection):
 def __exit__(self,exc_type,exc_value,traceback):
  try:return super().__exit__(exc_type,exc_value,traceback)
  finally:self.close()

def conn():
 c=sqlite3.connect(DB,timeout=20,factory=ClosingConnection);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def action_time(value=None):
 current=dt.datetime.fromisoformat(now())
 try:stamp=dt.datetime.fromisoformat(value.replace('Z','+00:00')) if value else current
 except (ValueError,AttributeError):raise HTTPException(422,'Invalid action time')
 if stamp.tzinfo is None:raise HTTPException(422,'Action time needs a timezone')
 if stamp>current+dt.timedelta(seconds=60):stamp=current
 return stamp.astimezone(dt.timezone.utc).isoformat(timespec='microseconds')

def default_news_languages(language):return [language]+(['en'] if language!='en' else [])
def normalized_profile(p):
 # Schema-on-read migration preserves existing demo accounts and feedback.
 result=dict(p)
 current=result.get('news_languages')
 result['news_languages']=list(dict.fromkeys(v for v in current if v in ['en','nl','de'])) if isinstance(current,list) else []
 if not result['news_languages']:result['news_languages']=default_news_languages(result.get('language','en'))
 result.setdefault('goals',[result.get('goal','general')] if result.get('onboarded') else [])
 if 'goal_tags' not in result:
  result['interests']=dict(result.get('interests',{}))
  result['goal_tags']=[]
  for goal in GOALS:
   if goal['id'] not in result['goals']:continue
   for tag in goal['tags']:
    if tag not in result['interests']:
     result['interests'][tag]=3
     result['goal_tags'].append(tag)
 result.setdefault('symbols',[])
 result.setdefault('plan','free')
 result.setdefault('tts_provider','device')
 result.setdefault('device_voices',{})
 result.setdefault('elevenlabs_voices',{})
 result.setdefault('translate_news',False)
 result['ai_settings']={'provider':'demo','personalization_model':'','summary_model':'','script_model':''}
 result['duration']=min(result.get('duration',5),{'free':7,'plus':15,'premium':40}.get(result['plan'],7))
 if result['plan']=='free':result['tts_provider']='device';result['translate_news']=False
 return result
def with_learning(p):
 with conn() as c:rows=c.execute('SELECT story_id,value,reason,created_at FROM feedback WHERE profile_id=?',(p['id'],)).fetchall()
 learned=learned_weights(rows,STORIES,p.get('interest_resets',{}))
 return {**p,'learned_interests':learned,'effective_interests':effective_weights(p['interests'],learned)}

def save_profile(p):
 p=normalized_profile(p)
 p.pop('learned_interests',None);p.pop('effective_interests',None);p.pop('interest_edits',None);p.pop('interest_edit_times',None)
 with conn() as c:
  c.execute('INSERT INTO profiles VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(p['id'],json.dumps(p)))
def profile(pid):
 with conn() as c: row=c.execute('SELECT data FROM profiles WHERE id=?',(pid,)).fetchone()
 if not row: raise HTTPException(404,'Listener not found')
 return with_learning(normalized_profile(json.loads(row[0])))
def profiles():
 with conn() as c: raw=[normalized_profile(json.loads(r[0])) for r in c.execute('SELECT data FROM profiles WHERE id IN (?,?,?,?,?,?,?) ORDER BY rowid',tuple(VISIBLE_PROFILE_IDS))]
 raw.sort(key=lambda p:('mila','jonas','alex','sam','free-demo','medium-demo','new').index(p['id']))
 return [with_learning(p) for p in raw]

def init():
 DB.parent.mkdir(exist_ok=True)
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,data TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS feedback(profile_id TEXT,story_id TEXT,value INTEGER,reason TEXT,created_at TEXT,PRIMARY KEY(profile_id,story_id));
  CREATE TABLE IF NOT EXISTS listens(profile_id TEXT,story_id TEXT,story_version TEXT,seconds REAL,completed INTEGER,listened_at TEXT,PRIMARY KEY(profile_id,story_id));
  CREATE TABLE IF NOT EXISTS editions(id TEXT PRIMARY KEY,profile_id TEXT,data TEXT,created_at TEXT);
  CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,profile_id TEXT,state TEXT,payload TEXT,result TEXT,error TEXT,created_at TEXT,updated_at TEXT);
  CREATE TABLE IF NOT EXISTS audio_cache(cache_key TEXT PRIMARY KEY,data TEXT,created_at TEXT);
  CREATE TABLE IF NOT EXISTS provider_keys(profile_id TEXT,provider TEXT,ciphertext BLOB NOT NULL,PRIMARY KEY(profile_id,provider));
  CREATE TABLE IF NOT EXISTS story_views(profile_id TEXT,story_id TEXT,article_id TEXT,first_viewed_at TEXT,last_viewed_at TEXT,view_count INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(profile_id,story_id));
  CREATE TABLE IF NOT EXISTS story_exposures(profile_id TEXT,story_id TEXT,snapshot TEXT NOT NULL,catalog_at TEXT NOT NULL,seen_at TEXT NOT NULL,PRIMARY KEY(profile_id,story_id));
  CREATE TABLE IF NOT EXISTS deliveries(profile_id TEXT,day TEXT,job_id TEXT,PRIMARY KEY(profile_id,day));
  CREATE TABLE IF NOT EXISTS saved_stories(profile_id TEXT,story_id TEXT,saved INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(profile_id,story_id));''')
 cloud_jobs.init_tables(sys.modules[__name__])
 if profiles(): return
 seeds=[
  ('mila','Mila','Dutch investor','nl','investor','balanced',{'markets':4,'technology':3,'economy':2,'energy':1},'MN','coral','Europe, technology and the companies shaping tomorrow.'),
  ('jonas','Jonas','German investor','de','investor','detailed',{'markets':4,'economy':3,'energy':3,'technology':1},'JK','sage','Fundamentals, the economy and a wider view of the markets.'),
  ('alex','Alex','FX trader','en','trader','detailed',{'forex':5,'economy':5,'energy':2,'markets':1},'AC','lavender','Currencies, central banks and the signals behind the moves.'),
  ('sam','Sam','General-news listener','en','general','simple',{'world':4,'money':4,'technology':2,'culture':3},'SR','sand','The bigger picture, without the financial jargon.'),
  ('free-demo','Free user','General-news listener','en','general','simple',{'world':4,'money':4,'technology':2,'culture':3},'FU','slate','A simple daily briefing across the biggest stories.'),
  ('medium-demo','Medium user','Tech and investor','en','tech','balanced',{'markets':3,'technology':4,'money':2,'economy':2,'energy':1},'MU','blue','Technology, markets and the forces shaping the next quarter.'),
  ('new','New listener','Unidentified','en','general','simple',{},'+','ink','A fresh start. Make this little corner of the world yours.'),
 ]
 for pid,name,role,lang,goal,depth,interests,initials,color,bio in seeds:
  profile_data={'id':pid,'name':name,'role':role,'language':lang,'goal':goal,'goals':['tech','investor'] if pid=='medium-demo' else [] if pid=='new' else [goal],'depth':depth,'interests':interests,'initials':initials,'color':color,'bio':bio,'duration':5,'wake_time':'07:30','timezone':'Europe/Brussels','scheduled':False,'onboarded':pid!='new','last_listened_at':'2026-11-17T07:30:00+00:00' if pid!='new' else None,'custom_interests':'','feedback_count':0}
  if pid in ('mila','jonas','alex','sam'):
   profile_data.update({'plan':'premium','tts_provider':'elevenlabs','translate_news':True})
  save_profile(profile_data)

init()
# The private team checkout includes fixed samples, never a personal database.
# Missing files leave the rest of the app available with a clear server message.
if (ROOT/'assets'/'demo'/'demo-scripts.json').is_file():
 try:
  from .demo_samples import ensure_demo_samples
  ensure_demo_samples(DB)
 except (OSError,ValueError,sqlite3.Error) as error:
  print(f'Demo audio not installed: {error}',file=sys.stderr)
app=FastAPI(title='Seranews',version='0.1.0')

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request,error):
 # Pydantic's default error includes rejected inputs; credentials must not echo.
 if '/provider-keys/' in request.url.path:
  return JSONResponse({'detail':'Enter a provider key of 12–512 characters, without spaces.'},status_code=422,headers={'Cache-Control':'no-store'})
 return await request_validation_exception_handler(request,error)

class AISettings(BaseModel):
 provider:Literal['demo','openai','anthropic','google']='demo'
 personalization_model:str=Field(default='',max_length=100,pattern=r'^[\w./:-]*$')
 summary_model:str=Field(default='',max_length=100,pattern=r'^[\w./:-]*$')
 script_model:str=Field(default='',max_length=100,pattern=r'^[\w./:-]*$')

class Preferences(BaseModel):
 plan:Literal['free','plus','premium']='free'
 tts_provider:Literal['device','elevenlabs']='device'
 device_voices:dict[Literal['en','nl','de'],list[str]]=Field(default_factory=dict,max_length=3)
 elevenlabs_voices:dict[Literal['en','nl','de'],list[str]]=Field(default_factory=dict,max_length=3)
 translate_news:bool=False
 ai_settings:AISettings=Field(default_factory=AISettings)
 name:str=Field(min_length=1,max_length=40)
 language:Literal['en','nl','de']='en'
 news_languages:list[Literal['en','nl','de']]=Field(default_factory=list,min_length=1,max_length=3)
 goal:Goal='general'
 goals:list[Goal]=Field(default_factory=list,max_length=5)
 goal_tags:list[str]=Field(default_factory=list,max_length=100)
 depth:Literal['simple','balanced','detailed']='balanced'
 interests:dict[str,float]=Field(default_factory=dict,max_length=100)
 interest_edits:list[str]=Field(default_factory=list,max_length=100)
 interest_edit_times:dict[str,str]=Field(default_factory=dict,max_length=100)
 duration:int=Field(default=5,ge=1,le=40,strict=True)
 wake_time:str='07:30'
 timezone:str='Europe/Brussels'
 scheduled:bool=False
 custom_interests:str=Field(default='',max_length=500)
 symbols:list[str]=Field(default_factory=list,max_length=50)
 onboarded:bool|None=None
 @field_validator('device_voices','elevenlabs_voices')
 @classmethod
 def check_voices(cls,value):
  if any(len(ids)>2 or len(set(ids))!=len(ids) or any(not voice or len(voice)>256 for voice in ids) for ids in value.values()):raise ValueError('Choose up to two distinct voices per language')
  return value
 @field_validator('symbols')
 @classmethod
 def validate_symbols(cls,values):
  if any(not re.fullmatch(r'[A-Z][A-Z0-9]{0,7}(?:[.-][A-Z0-9]{1,5})?',symbol) for symbol in values):
   raise ValueError('Invalid stock symbol')
  return list(dict.fromkeys(values))
 @model_validator(mode='after')
 def default_source_languages(self):
  if 'news_languages' not in self.model_fields_set:self.news_languages=default_news_languages(self.language)
  return self
 @field_validator('news_languages')
 @classmethod
 def check_source_languages(cls,v):
  if len(v)!=len(set(v)):raise ValueError('Choose each news language only once')
  return v
 @field_validator('wake_time')
 @classmethod
 def check_time(cls,v):
  if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',v): raise ValueError('Use HH:MM')
  return v
 @field_validator('timezone')
 @classmethod
 def check_zone(cls,v):
  try: ZoneInfo(v)
  except Exception: raise ValueError('Unknown timezone')
  return v
 @field_validator('interests')
 @classmethod
 def check_topics(cls,v):
  known=TOPIC_LABELS.keys() | {topic['id'] for topic in CATALOG['topics']}
  if any(k not in known or not math.isfinite(n) or n<0 or n>5 for k,n in v.items()): raise ValueError('Invalid interest')
  return v

def votes(pid):
 with conn() as c: return {r['story_id']:{'value':r['value'],'reason':r['reason'],'created_at':r['created_at']} for r in c.execute('SELECT * FROM feedback WHERE profile_id=?',(pid,))}

@lru_cache(maxsize=1)
def _spoken_catalog(path,mtime):
 return json.loads(Path(path).read_text(encoding='utf-8'))['stories']

def spoken_summary(story_id,language):
 path=ROOT/'data'/'demo-story-audio.json'
 if not path.is_file():path=ROOT/'assets'/'demo'/'demo-story-audio.json'
 try:
  entry=_spoken_catalog(str(path),path.stat().st_mtime_ns).get(story_id,{}).get(language)
  if entry and entry.get('language')==language and entry.get('provider')=='microsoft-sapi' and str(entry.get('url','')).startswith('/media/story-summaries/'):return entry
 except (OSError,ValueError,KeyError):pass
 return None

def localized_story(story,language,news_languages=None,allow_translation=True):
 """Localize presentation while preserving the exact claim-evidence mapping.

 A source in the preferred language can be related/translated coverage; its
 presence does not silently make it evidence for the editorial summary.
 """
 item=dict(story)
 selected=list(dict.fromkeys(news_languages or default_news_languages(language)))
 available={s['language'] for s in story['sources']}
 selected_available=[lang for lang in selected if lang in available]
 display_language=language if language in selected_available else next(iter(selected_available),None)
 # Keep every original article. Selected languages come first, with a source
 # matching the narration language leading only when the user selected it.
 source_priority=([display_language] if display_language else [])+[lang for lang in selected if lang!=display_language]
 sources=sorted(story['sources'],key=lambda s:source_priority.index(s['language']) if s['language'] in source_priority else len(source_priority))
 preferred=[s for s in sources if s['language']==display_language]
 selected_sources=[s for s in sources if s['language'] in selected]
 item['sources']=sources
 item['requested_language']=language
 item['news_languages']=selected
 item['news_languages_available']=selected_available
 item['selected_language_sources']=selected_sources
 item['preferred_sources']=preferred
 item['source_language_available']=language in selected_available
 item['available_source_languages']=sorted(available)
 titles=story.get('titles',{})
 primary=next(iter(preferred),sources[0])
 if display_language==language and language in titles:
  item['title']=titles[language]
 else:
  item['title']=primary.get('headline') or titles.get(display_language,story['title'])
 item['title_language']=display_language or ('en' if 'en' in titles else next(iter(titles),sources[0]['language']))
 item['presentation_source_id']=primary['article_id']
 summaries=story.get('summaries',{})
 support_languages={src['language'] for src in sources if src['article_id'] in story.get('claim_source_ids',[])}
 if not allow_translation:
  item['title']=primary.get('headline') or story['title'];item['title_language']=primary['language']
  item['titles']={src['language']:src['headline'] for src in sources if src.get('headline')}
  summaries={lang:text for lang,text in summaries.items() if lang in support_languages}
  item['summaries']=summaries
  native=next((lang for lang in [language,display_language,*selected,*sorted(support_languages)] if lang in summaries),None)
  item['summary']=summaries.get(native) or primary.get('snippet') or primary.get('headline','')
  item['summary_language']=native or primary['language']
 elif language in summaries:
  item['summary']=summaries[language];item['summary_language']=language
 elif not story.get('curated'):
  item['summary']={
   'en':'Additional source coverage. Open the original report for the complete story.',
   'nl':'Aanvullende berichtgeving. Open het oorspronkelijke artikel voor het volledige verhaal.',
   'de':'Ergänzende Berichterstattung. Den vollständigen Beitrag finden Sie im Originalbericht.',
  }[language]
  item['summary_language']=language
 else:
  item['summary']=story['summary'];item['summary_language']='en'
 language_names={
  'en':{'en':'English','nl':'Dutch','de':'German'},
  'nl':{'en':'Engels','nl':'Nederlands','de':'Duits'},
  'de':{'en':'Englisch','nl':'Niederländisch','de':'Deutsch'},
 }[language]
 source_label=', '.join(language_names[lang] for lang in sorted(available))
 support_languages={s['language'] for s in sources if s['article_id'] in story.get('claim_source_ids',[])}
 translated=bool(story.get('curated') and support_languages and item['summary_language'] not in support_languages)
 item['ai_translated']=translated
 summary_note={
  'en':f"{'Translated summary' if translated else 'Summary'} in {language_names[item['summary_language']]}. Original source articles keep their own language.",
  'nl':f"{'Vertaalde samenvatting' if translated else 'Samenvatting'} in het {language_names[item['summary_language']]}. Bronartikelen behouden hun oorspronkelijke taal.",
  'de':f"{'Übersetzte Zusammenfassung' if translated else 'Zusammenfassung'} auf {language_names[item['summary_language']]}. Quellartikel behalten ihre Originalsprache.",
 }[language]
 original_note={'en':'Original reporting','nl':'Oorspronkelijke berichtgeving','de':'Originalberichte'}[language]
 unavailable_note={
  'en':' No original source is available in your selected news languages.',
  'nl':' Er is geen oorspronkelijke bron beschikbaar in de geselecteerde nieuwstalen.',
  'de':' In den ausgewählten Nachrichtensprachen ist kein Originalbericht verfügbar.',
 }[language] if not selected_available else ''
 item['source_language_note']=f'{original_note}: {source_label}. {summary_note}{unavailable_note}'
 # Copy the list so downstream code cannot accidentally reassign evidence on
 # the shared catalog when it changes source ordering for a listener.
 item['claim_source_ids']=list(story.get('claim_source_ids',[]))
 if allow_translation:
  narration=spoken_summary(story['id'],item['summary_language'])
  if narration:item['spoken_summary']=narration
 return item

def ranked(pid,all_items=False,include_incoming=False,as_of=None,for_podcast=False):
 refresh_catalog()
 p=profile(pid);feedback=votes(pid);weights=effective_weights(p['interests'],p['learned_interests'],signed=True)
 heard={}
 if for_podcast:
  with conn() as c:heard={row['story_id']:row['story_version'] for row in c.execute('SELECT story_id,story_version FROM listens WHERE profile_id=? AND completed=1',(pid,))}
 symbols=set(p['symbols'])
 entity_aliases={'NVDA':'Nvidia','INTC':'Intel','MSFT':'Microsoft','AAPL':'Apple','HD':'Home Depot','CRM':'Salesforce','AMZN':'Amazon','TSLA':'Tesla','META':'Meta','GOOG':'Google','GOOGL':'Alphabet','BTC':'Bitcoin'}
 custom_terms=set(re.findall(r'[^\W\d_]{4,}',p.get('custom_interests','').casefold()))-{'follow','about','please','stories','updates','every','would'}
 labels={topic['id']:topic['label'] for topic in CATALOG['topics']}
 items=[]
 for s in CATALOG['stories']:
  if for_podcast and heard.get(s['id'],'')>=s['updated_at']:continue
  if not all_items and not s['curated'] and not (include_incoming and s.get('fresh_import')):continue
  if as_of is not None:
   sources=[source for source in s['sources'] if dt.datetime.fromisoformat(source['date'])<=as_of]
   if not sources or not set(s.get('claim_source_ids',[])).issubset({source['article_id'] for source in sources}):continue
   s={**s,'sources':sources}
  translated_for_podcast=for_podcast and p['plan']!='free' and p['translate_news'] and s['curated'] and bool(s.get('summaries',{}).get(p['language']))
  if not translated_for_podcast and not any(source['language'] in p['news_languages'] for source in s['sources']):continue
  if for_podcast and p['plan']=='free' and not any(src['language']==p['language'] and src['article_id'] in s.get('claim_source_ids',[]) for src in s['sources']):continue
  published=dt.datetime.fromisoformat(s['updated_at'])
  if as_of is not None and published>as_of:continue
  age=max(0,((as_of or NOW)-published).total_seconds()/86400)
  if not all_items and age>7:continue
  affinity=sum(weights.get(t,0) for t in s['tags'])/max(1,len(s['tags'])**.35)
  affinity+=weights.get(s.get('primary_topic'),0)*.8
  score=affinity+max(0,3-age*.35)+(1 if len(s['sources'])>1 else 0)
  if s['curated']:score+=2
  score+=feedback.get(s['id'],{}).get('value',0)*2
  if 'trader' in p['goals'] and 'forex' in s['tags']:score+=2
  if 'general' in p['goals'] and any(t in s['tags'] for t in ['world','money','culture']):score+=2
  searchable=' '.join([s['title'],*(src.get('headline','') for src in s['sources'])])
  symbol_matches=[sym for sym in sorted(symbols) if re.search(r'(?<!\w)'+re.escape(sym)+r'(?!\w)',searchable)
                  or (sym in entity_aliases and re.search(r'\b'+re.escape(entity_aliases[sym])+r'\b',searchable,re.I))]
  score+=min(5,3*len(symbol_matches))
  score+=min(2,len(custom_terms.intersection(re.findall(r'[^\W\d_]{4,}',searchable.casefold())))*.6)
  item=localized_story(s,p['language'],p['news_languages'],allow_translation=p['plan']!='free');item['score']=round(score,3);item['vote']=feedback.get(s['id'],{}).get('value',0);item['feedback_reason']=feedback.get(s['id'],{}).get('reason','interest');item['feedback_at']=feedback.get(s['id'],{}).get('created_at')
  matched=sorted(s['tags'],key=lambda t:weights.get(t,0),reverse=True)
  item['reason']=('From your watchlist: '+', '.join(symbol_matches)) if symbol_matches else ('Because you follow '+labels.get(matched[0],matched[0]).lower() if matched and weights.get(matched[0],0)>0 else 'A different perspective for your day')
  items.append(item)
 items.sort(key=lambda s:(-s['score'],s['id']))
 if not all_items and as_of is None and not for_podcast and cloud_client.connection(ROOT).get('verified_at'):
  snapshot=cloud_jobs.get_snapshot(sys.modules[__name__],pid)
  if snapshot:
   order={identifier:index for index,identifier in enumerate(snapshot['data'].get('story_ids',[]))}
   items.sort(key=lambda story:(order.get(story['id'],len(order)),-story['score'],story['id']))
 # Re-rank for variety: at most two of the same primary topic in the first six.
 chosen=[];remaining=list(items);used=collections_counter()
 while remaining:
  winner=max(remaining,key=lambda s:s['score']-sum(used[t]*.8 for t in s['tags']))
  chosen.append(winner);remaining.remove(winner)
  for t in winner['tags']:used[t]+=1
  if len(chosen)>=24 and all_items: chosen.extend(remaining);break
 return chosen

def collections_counter():
 from collections import Counter
 return Counter()

def memory(p):
 f=votes(p['id'])
 labels={topic['id']:topic['label'] for topic in CATALOG['topics']}
 def summarize(direction):
  stories=[STORIES[key] for key,vote in f.items() if key in STORIES and vote['value']==direction and vote['reason']=='interest']
  counts=collections_counter()
  for story in stories:
   tags=[tag for tag in story['tags'] if tag not in TOPICS] or story['tags']
   counts.update(tags[:3])
  return [labels.get(key,key) for key,_ in counts.most_common(3)], [story['titles'].get(p['language'],story['title']) for story in stories[-3:]]
 liked,ups=summarize(1)
 disliked,downs=summarize(-1)
 return {'explicit':[labels.get(k,k) for k,v in p['interests'].items() if v>0],
         'more':ups,'less':downs,'liked_topics':liked,'disliked_topics':disliked,
         'note':'Feedback helps rank future briefings.'}

def tag_suggestions(p):
 from collections import Counter
 counts=Counter()
 latest={}
 examples={}
 for story in CATALOG['stories']:
  age=(NOW-dt.datetime.fromisoformat(story['updated_at'])).total_seconds()/86400
  if age>4 or not any(src['language'] in p['news_languages'] for src in story['sources']):continue
  for tag in story['tags']:
   counts[tag]+=1
   if story['updated_at']>latest.get(tag,''):
    latest[tag]=story['updated_at']
    examples[tag]=next((source.get('headline') for source in story['sources'] if source['language'] in p['news_languages'] and source.get('headline')),story['title'])
 return [{
  **topic,'count':counts[topic['id']],'latest':latest[topic['id']],'example':examples[topic['id']]
 } for topic in sorted(CATALOG['topics'],key=lambda t:(latest.get(t['id'],''),bool(t.get('dynamic')),counts[t['id']]),reverse=True)
 if topic.get('parent') and counts[topic['id']]>0 and not p['effective_interests'].get(topic['id']) and p['learned_interests'].get(topic['id'],0)>=0][:6]

def chapter(s,p):
 lang=p['language']
 # Sources have been reordered for convenient native-language access. Spoken
 # attribution must still name the report that actually supports the summary.
 support_ids=s.get('claim_source_ids',[])
 supporting=[src for src in s['sources'] if src['article_id'] in support_ids]
 attribution_source=next((src for src in supporting if src['article_id']==next(iter(support_ids),None)),None)
 if attribution_source is None:attribution_source=next(iter(supporting),s['sources'][0])
 outlet=attribution_source['outlet']
 attribution={'en':f'According to {outlet}, here is the story.','nl':f'Volgens {outlet} is dit het verhaal.','de':f'Laut {outlet} ist dies die aktuelle Meldung.'}[lang]
 text=s['summaries'].get(lang,s['summary'])
 if p['depth']=='simple':text=' '.join(re.split(r'(?<=[.!?])\s+',text)[:2])
 if p['depth']=='detailed':
  text+=' '+{'en':'You can open the linked report in the app to see its reporting and attribution.','nl':'Open het gekoppelde artikel in de app voor de oorspronkelijke berichtgeving en bronvermelding.','de':'Den verlinkten Originalbericht mit Quellenangaben finden Sie in der App.'}[lang]
 script=attribution+' '+text
 cache_key=hashlib.sha256(json.dumps({'story':s['id'],'version':s['updated_at'],'language':lang,'depth':p['depth'],'script':script,'voice':os.getenv('ELEVENLABS_VOICE_ID','preview'),'voices':p.get('selected_voice_ids',[]),'provider':p.get('tts_provider','device'),'model':os.getenv('ELEVENLABS_MODEL_ID','eleven_multilingual_v2')},sort_keys=True).encode()).hexdigest()
 with conn() as c:cached=c.execute('SELECT data FROM audio_cache WHERE cache_key=?',(cache_key,)).fetchone()
 return {'story_snapshot':catch_up.snapshot(s),'story_id':s['id'],'title':s.get('titles',{}).get(lang,s['title']),'text':script,'language':lang,'news_languages':p.get('news_languages',default_news_languages(lang)),'sources':s['sources'],'claim_source_ids':list(s['claim_source_ids']),'attribution_source_id':attribution_source['article_id'],'source_language_available':s.get('source_language_available',any(src['language']==lang for src in s['sources'])),'news_languages_available':s.get('news_languages_available',[]),'selected_language_sources':s.get('selected_language_sources',[]),'source_language_note':s.get('source_language_note',''),'cache_key':cache_key,'estimated_seconds':round(len(script.split())/2.35),'audio':json.loads(cached[0]) if cached else None}

def briefing_dates():
 return sorted({story['updated_at'][:10] for story in CATALOG['stories'] if story['curated']},reverse=True)

def normalized_edition(edition):
 """Keep the edition's creation day separate from its source coverage date."""
 result=dict(edition)
 result.setdefault('news_date',edition.get('briefing_date') or edition['replay_day'][:10])
 result['briefing_date']=dt.datetime.fromisoformat(edition['created_at']).astimezone(ZoneInfo('Europe/Brussels')).date().isoformat()
 return result

def daily_usage(p,connection=None):
 today=dt.datetime.fromisoformat(now()).astimezone(ZoneInfo(p['timezone'])).date()
 if connection is None:
  with conn() as c:rows=c.execute('SELECT data,created_at FROM editions WHERE profile_id=?',(p['id'],)).fetchall()
 else:rows=connection.execute('SELECT data,created_at FROM editions WHERE profile_id=?',(p['id'],)).fetchall()
 todays=[]
 for row in rows:
  if dt.datetime.fromisoformat(row['created_at']).astimezone(ZoneInfo(p['timezone'])).date()!=today:continue
  edition=json.loads(row['data'])
  if not edition.get('demo_sample') and edition.get('status') not in ('failed','cancelled'):todays.append(edition)
 natural=sum(bool(e.get('natural_reserved')) or e.get('tts_provider')=='elevenlabs' or e.get('audio_mode')=='elevenlabs' for e in todays)
 return {'day':today.isoformat(),'created':len(todays),'natural_created':natural,'can_create':p['plan']!='free' or not todays,'natural_remaining':max(0,1-natural) if p['plan']=='plus' else (0 if p['plan']=='free' else None)}

def compose(pid,day=None):
 refresh_catalog()
 if day is not None and day not in briefing_dates():raise HTTPException(422,'Choose a date available in this news sample.')
 as_of=dt.datetime.combine(dt.date.fromisoformat(day),dt.time.max,tzinfo=dt.timezone.utc) if day else None
 p=profile(pid);usage=daily_usage(p)
 if not usage['can_create']:raise HTTPException(429,'Your daily Free briefing is ready. Replay it or explore another plan.')
 if p['plan']=='plus' and not usage['natural_remaining']:p['tts_provider']='device'
 stories=ranked(pid,as_of=as_of,for_podcast=True);duration=p['duration']*60
 voice_ids=p['device_voices'].get(p['language'],[])
 if p['tts_provider']=='elevenlabs' and p['plan']!='free':
  available=[v['id'] for v in json.loads((ROOT/'public'/'voice-samples.json').read_text(encoding='utf-8')) if v['language']==p['language']]
  voice_ids=[voice for voice in p['elevenlabs_voices'].get(p['language'],[]) if voice in available]
  pool=[voice for voice in available if voice not in voice_ids];secrets.SystemRandom().shuffle(pool)
  voice_ids=(voice_ids+pool)[:2]
 p['selected_voice_ids']=voice_ids
 chapters=[];elapsed=0;previous=None
 while stories:
  # Keep relevance dominant while preferring a related next topic among close results.
  candidates=stories[:4]
  story=max(candidates,key=lambda s:s['score']+.8*bool(previous and set(s['tags']).intersection(previous)))
  stories.remove(story)
  ch=chapter(story,p)
  if p['tts_provider']=='device':ch['audio']=None
  ch['translated_from_languages']=list(dict.fromkeys(source['language'] for source in ch['sources'] if source['article_id'] in ch['claim_source_ids'] and source['language']!=p['language']))
  ch['translated_by_ai']=p['language'] not in {source['language'] for source in ch['sources'] if source['article_id'] in ch['claim_source_ids']}
  ch['summary']=story['summaries'].get(p['language'],story['summary'])
  ch['tags']=list(story['tags'])
  if elapsed+ch['estimated_seconds']>duration:continue
  chapters.append(ch);elapsed+=ch['estimated_seconds'];previous=[story['primary_topic']] if story.get('primary_topic') else story['tags']
 if not chapters:raise HTTPException(409,'No original-language reports match this podcast language. Try another language or explore a plan with AI translations.')
 eid='edition-'+uuid.uuid4().hex[:12]
 edition={'id':eid,'profile_id':pid,'title':{'en':'Your morning, in perspective','nl':'Je ochtend, in perspectief','de':'Dein Morgen, mit Perspektive'}[p['language']],'language':p['language'],'depth':p['depth'],'created_at':now(),'replay_day':CATALOG['replay_day'],'chapters':chapters,'estimated_seconds':elapsed,'status':'ready','audio_mode':'elevenlabs' if chapters and all(ch['audio'] for ch in chapters) else 'browser-preview','catalog_version':CATALOG['version']}
 edition['news_date']=day or CATALOG['as_of'][:10]
 edition['tts_provider']=p['tts_provider'];edition['voice_ids']=voice_ids
 edition['translation_mode']='reviewed-demo-summaries' if p['plan']!='free' and p['translate_news'] else 'selected-article-languages'
 edition=normalized_edition(edition)
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  fresh=daily_usage(p,c)
  if not fresh['can_create']:raise HTTPException(429,'Your daily Free briefing is already prepared. You can replay it anytime.')
  if p['plan']=='plus' and edition['tts_provider']=='elevenlabs' and not fresh['natural_remaining']:
   edition['tts_provider']='device';edition['voice_ids']=p['device_voices'].get(p['language'],[]);edition['audio_mode']='browser-preview'
   for ch in edition['chapters']:
    ch['audio']=None;ch['cache_key']=hashlib.sha256((ch['cache_key']+'device-fallback').encode()).hexdigest()
  c.execute('INSERT INTO editions VALUES (?,?,?,?)',(eid,pid,json.dumps(edition),now()))
 return edition

@app.get('/api/bootstrap')
def bootstrap():
 refresh_catalog()
 return {'profiles':profiles(),'usage':{p['id']:daily_usage(p) for p in profiles()},'topics':CATALOG['topics'],'goals':GOALS,'stats':CATALOG['stats'],'replay_day':CATALOG['replay_day'],'latest_news_at':CATALOG['as_of'],'catalog_version':CATALOG['version'],'briefing_dates':briefing_dates(),'integrations':cloud_client.capabilities(ROOT)}

@app.get('/api/articles/{article_id}')
def article(article_id:str):
 body=read_article(article_id)
 if body is None:raise HTTPException(404,'The full article is unavailable in the local dataset.')
 return JSONResponse(body,headers={'Cache-Control':'private, no-store'})

@app.get('/api/feed/{pid}')
def feed(pid:str,topic:str='',q:str='',all_items:bool=False,limit:int=Query(50,ge=1,le=150),topics:str='',languages:str=''):
 items=ranked(pid,all_items,include_incoming=True)
 topic_filters=set(filter(None,[topic,*topics.split(',')]))
 language_filters=set(filter(None,languages.split(',')))
 if topic_filters:
  items=[story for story in items if topic_filters.intersection(story['tags'])]
 if language_filters:
  items=[story for story in items if language_filters.intersection(story['news_languages_available'])]
 if q:
  query=q.casefold()
  items=[story for story in items if query in ' '.join([
   story['title'],story['summary'],*story['tags'],
   *(source.get('headline','') for source in story['selected_language_sources']),
  ]).casefold()]
 p=profile(pid)
 with conn() as c:hist={r['story_id']:dict(r) for r in c.execute('SELECT * FROM listens WHERE profile_id=?',(pid,))}
 known,baseline=catch_up_history(pid,p,hist)
 changed=catch_up.select_updates(items,known,baseline)
 result={'stories':items[:limit],'total':len(items),'since':changed,'since_baseline':baseline,'memory':memory(p),'listening':hist,'suggestions':tag_suggestions(p)}
 if not all_items and not topic_filters and not language_filters and not q:
  # A small unfiltered pool lets the phone react before the preference write returns.
  feedback=votes(pid)
  result['preview_stories']=[
   {**localized_story(s,p['language'],p['news_languages'],allow_translation=p['plan']!='free'),
    'vote':feedback.get(s['id'],{}).get('value',0),'feedback_reason':feedback.get(s['id'],{}).get('reason','interest'),'feedback_at':feedback.get(s['id'],{}).get('created_at'),'reason':''}
   for s in CATALOG['stories'] if (s['curated'] or s.get('fresh_import')) and (NOW-dt.datetime.fromisoformat(s['updated_at'])).days<7
  ]
 return result

@app.put('/api/profiles/{pid}')
def update_profile(pid:str,body:Preferences):
 p=profile(pid);changes=body.model_dump()
 for key in ['plan','tts_provider','device_voices','elevenlabs_voices','translate_news','ai_settings']:
  if key not in body.model_fields_set:changes[key]=p[key]
 changes['duration']=min(changes['duration'],{'free':7,'plus':15,'premium':40}[changes['plan']])
 changes['ai_settings']={'provider':'demo','personalization_model':'','summary_model':'','script_model':''}
 if changes['plan']=='free':changes['tts_provider']='device';changes['translate_news']=False
 if 'news_languages' not in body.model_fields_set:changes['news_languages']=p['news_languages']
 if 'goals' not in body.model_fields_set:changes['goals']=[body.goal]
 changes['goals']=list(dict.fromkeys(changes['goals']))
 changes['goal_tags']=[key for key in dict.fromkeys(changes['goal_tags']) if changes['interests'].get(key,0)>0]
 if changes['goals']:changes['goal']=changes['goals'][0]
 changes['onboarded']=True if body.onboarded is None else body.onboarded
 touched=set(changes.pop('interest_edits',[]))
 if touched-({topic['id'] for topic in CATALOG['topics']}|TOPIC_LABELS.keys()):raise HTTPException(422,'Unknown topic')
 resets=dict(p.get('interest_resets',{}));cutoff=action_time();edit_times=changes.pop('interest_edit_times',{})
 for tag in p['interests'].keys()|changes['interests'].keys()|touched:
  if p['interests'].get(tag)!=changes['interests'].get(tag) or tag in touched:
   incoming=action_time(edit_times[tag]) if tag in edit_times else cutoff
   resets[tag]=max(resets.get(tag,''),incoming)
 p.update(changes);p['interest_resets']=resets
 save_profile(p)
 if cloud_client.connection(ROOT).get('verified_at'):cloud_jobs.enqueue_radar(sys.modules[__name__],pid)
 return profile(pid)

class ProviderKey(BaseModel):
 api_key:SecretStr=Field(min_length=12,max_length=512)
 @field_validator('api_key')
 @classmethod
 def clean_key(cls,value):
  key=value.get_secret_value().strip()
  if len(key)<12 or any(char.isspace() for char in key):raise ValueError('Enter a valid provider key without spaces')
  return SecretStr(key)

def key_provider(provider):
 if provider not in ['openai','anthropic','google']:raise HTTPException(422,'Choose a supported AI provider.')

@app.get('/api/profiles/{pid}/provider-keys')
def provider_key_status(pid:str):
 profile(pid)
 with conn() as c:configured=[row[0] for row in c.execute('SELECT provider FROM provider_keys WHERE profile_id=?',(pid,))]
 return JSONResponse({'configured':configured,'generation_connected':False},headers={'Cache-Control':'no-store'})

@app.put('/api/profiles/{pid}/provider-keys/{provider}')
def save_provider_key(pid:str,provider:str,body:ProviderKey):
 profile(pid);key_provider(provider)
 raise HTTPException(410,'Personal model connections have been retired. Seranews manages AI processing for every plan.')

@app.delete('/api/profiles/{pid}/provider-keys/{provider}')
def delete_provider_key(pid:str,provider:str):
 profile(pid);key_provider(provider)
 with conn() as c:c.execute('DELETE FROM provider_keys WHERE profile_id=? AND provider=?',(pid,provider))
 return {'removed':True}

class Vote(BaseModel):
 story_id:str
 value:Literal[-1,0,1]
 reason:Literal['interest','repetition','technical','basic']='interest'
 occurred_at:str|None=Field(default=None,max_length=40)

@app.post('/api/profiles/{pid}/feedback')
def feedback(pid:str,body:Vote):
 profile(pid)
 if body.story_id not in STORIES:raise HTTPException(404,'Story not found')
 with conn() as c:
  c.execute('''INSERT INTO feedback VALUES (?,?,?,?,?) ON CONFLICT(profile_id,story_id) DO UPDATE SET
   value=excluded.value,reason=excluded.reason,created_at=excluded.created_at
   WHERE (excluded.created_at>feedback.created_at AND (? OR feedback.value!=excluded.value OR feedback.reason!=excluded.reason))
      OR (excluded.created_at=feedback.created_at AND NOT ? AND (feedback.value!=excluded.value OR feedback.reason!=excluded.reason))''',
   (pid,body.story_id,body.value,body.reason,action_time(body.occurred_at),body.occurred_at is not None,body.occurred_at is not None))
  vote=dict(c.execute('SELECT value,reason,created_at FROM feedback WHERE profile_id=? AND story_id=?',(pid,body.story_id)).fetchone())
  count=c.execute('SELECT COUNT(*) FROM feedback WHERE profile_id=? AND value!=0',(pid,)).fetchone()[0]
  c.execute("UPDATE profiles SET data=json_set(data,'$.feedback_count',?) WHERE id=?",(count,pid))
 updated=profile(pid)
 if cloud_client.connection(ROOT).get('verified_at'):cloud_jobs.enqueue_radar(sys.modules[__name__],pid)
 return {'ok':True,'memory':memory(updated),'profile':updated,'vote':vote}

class Listen(BaseModel):
 story_id:str
 seconds:float=Field(ge=0,le=86400)
 completed:bool=False
 edition_id:str|None=Field(default=None,max_length=180)

def remember_exposure(c,pid,story):
 snapshot=catch_up.snapshot(story)
 previous=c.execute('SELECT snapshot FROM story_exposures WHERE profile_id=? AND story_id=?',(pid,story['id'])).fetchone()
 if previous and catch_up.stamp(json.loads(previous[0])['updated_at'])>catch_up.stamp(snapshot['updated_at']):return
 c.execute('''INSERT INTO story_exposures VALUES (?,?,?,?,?)
  ON CONFLICT(profile_id,story_id) DO UPDATE SET snapshot=excluded.snapshot,catalog_at=excluded.catalog_at,seen_at=excluded.seen_at''',
  (pid,story['id'],json.dumps(snapshot),CATALOG['as_of'],now()))

def catch_up_history(pid,p,hist):
 with conn() as c:
  rows=c.execute('SELECT * FROM story_exposures WHERE profile_id=? ORDER BY seen_at DESC LIMIT 500',(pid,)).fetchall()
  views=c.execute('SELECT story_id FROM story_views WHERE profile_id=? ORDER BY last_viewed_at DESC LIMIT 500',(pid,)).fetchall()
 known=[{'snapshot':json.loads(row['snapshot'])} for row in rows]
 seen={entry['snapshot']['id'] for entry in known}
 # Older demos lack content snapshots. Retain known IDs conservatively; tracking
 # exact content changes starts with the next read/listen, without inventing history.
 for sid in dict.fromkeys([*hist,*(row['story_id'] for row in views)]):
  if sid not in seen and sid in STORIES:
   old=catch_up.snapshot(STORIES[sid])
   if sid in hist and catch_up.stamp(hist[sid]['story_version'])<catch_up.stamp(old['updated_at']):
    old.update(title='',summary='',updated_at=hist[sid]['story_version'])
   known.append({'snapshot':old})
 baseline=rows[0]['catalog_at'] if rows else p.get('last_listened_at')
 return known,baseline

@app.post('/api/profiles/{pid}/listens')
def listen(pid:str,body:Listen):
 profile(pid);s=STORIES.get(body.story_id)
 if not s:raise HTTPException(404,'Story not found')
 with conn() as c:
  heard=s
  capture=True
  if body.edition_id:
   row=c.execute('SELECT data FROM editions WHERE id=? AND profile_id=?',(body.edition_id,pid)).fetchone()
   if not row:raise HTTPException(404,'Briefing not found for this listener')
   edition=json.loads(row[0]);segment=next((item for item in edition.get('chapters',[]) if item['story_id']==s['id']),None)
   if not segment:raise HTTPException(422,'Story is not in this briefing')
   if segment.get('story_snapshot'):heard=segment['story_snapshot']
   elif edition.get('catalog_version')!=CATALOG.get('version'):
    capture=False;heard={**s,'updated_at':min((source['date'] for source in segment.get('sources',[]) if source.get('date')),default=s['published_at'])}
  c.execute('''INSERT INTO listens VALUES (?,?,?,?,?,?)
   ON CONFLICT(profile_id,story_id) DO UPDATE SET
     seconds=CASE WHEN listens.story_version=excluded.story_version THEN MAX(listens.seconds,excluded.seconds) ELSE excluded.seconds END,
     completed=CASE WHEN listens.story_version=excluded.story_version THEN MAX(listens.completed,excluded.completed) ELSE excluded.completed END,
     story_version=excluded.story_version, listened_at=excluded.listened_at''',
   (pid,s['id'],heard['updated_at'],body.seconds,int(body.completed),now()))
  if capture and (body.seconds>=3 or body.completed):remember_exposure(c,pid,heard)
  # Use the replay clock without replacing concurrently edited preferences.
  c.execute("UPDATE profiles SET data=json_set(data,'$.last_listened_at',?) WHERE id=?",(CATALOG['as_of'],pid))
 return {'ok':True}

@app.get('/api/profiles/{pid}/editions')
def editions(pid:str):
 profile(pid)
 with conn() as c:items=[normalized_edition(json.loads(r[0])) for r in c.execute('SELECT data FROM editions WHERE profile_id=? ORDER BY created_at DESC LIMIT 200',(pid,))]
 return [item for item in items if item.get('status','ready')=='ready']

class BriefingRequest(BaseModel):
 day:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$')

@app.post('/api/profiles/{pid}/briefings')
def prepare_briefing(pid:str,body:BriefingRequest):
 return cloud_jobs.queue_briefing(sys.modules[__name__],pid,body.day)

@app.get('/api/profiles/{pid}/briefings')
def briefing_jobs(pid:str):
 return {'jobs':cloud_jobs.list_jobs(sys.modules[__name__],pid)}

@app.get('/api/profiles/{pid}/briefings/{job_id}')
def briefing_job(pid:str,job_id:str):
 return cloud_jobs.get_job(sys.modules[__name__],pid,job_id)

@app.post('/api/profiles/{pid}/briefings/{job_id}/retry')
def retry_briefing(pid:str,job_id:str):
 return cloud_jobs.retry_job(sys.modules[__name__],pid,job_id)

@app.post('/api/profiles/{pid}/editions')
def create_edition(pid:str,day:str|None=None):return compose(pid,day)

class StoryView(BaseModel):
 story_id:str|None=Field(default=None,max_length=180)
 article_id:str|None=Field(default=None,max_length=180)

@app.post('/api/profiles/{pid}/views')
def view_story(pid:str,body:StoryView):
 profile(pid);refresh_catalog()
 story=STORIES.get(body.story_id) if body.story_id else next((item for item in STORIES.values() if any(source['article_id']==body.article_id for source in item['sources'])),None)
 if not story:raise HTTPException(404,'Story not found')
 if body.article_id and not any(source['article_id']==body.article_id for source in story['sources']):raise HTTPException(422,'This source does not belong to the story.')
 timestamp=now()
 with conn() as c:
  c.execute('''INSERT INTO story_views VALUES (?,?,?,?,?,1)
   ON CONFLICT(profile_id,story_id) DO UPDATE SET
    article_id=COALESCE(excluded.article_id,story_views.article_id),
    last_viewed_at=excluded.last_viewed_at,view_count=story_views.view_count+1''',
   (pid,story['id'],body.article_id,timestamp,timestamp))
  remember_exposure(c,pid,story)
 return {'ok':True,'story_id':story['id'],'last_viewed_at':timestamp}

@app.get('/api/profiles/{pid}/history')
def history(pid:str,q:str='',period:Literal['all','today','week']='all',feedback:Literal['all','liked','disliked']='all',limit:int=100):
 p=profile(pid);refresh_catalog();entries=[];f=votes(pid)
 local_now=dt.datetime.now(ZoneInfo(p['timezone']))
 labels={topic['id']:topic['label'] for topic in CATALOG['topics']}
 with conn() as c:rows=c.execute('SELECT * FROM story_views WHERE profile_id=? ORDER BY last_viewed_at DESC,story_id',(pid,)).fetchall()
 for row in rows:
  story=STORIES.get(row['story_id'])
  if not story:continue
  seen=dt.datetime.fromisoformat(row['last_viewed_at']).astimezone(local_now.tzinfo)
  if period=='today' and seen.date()!=local_now.date():continue
  if period=='week' and seen<local_now-dt.timedelta(days=7):continue
  value=f.get(story['id'],{}).get('value',0)
  if feedback=='liked' and value!=1 or feedback=='disliked' and value!=-1:continue
  searchable=' '.join([story['title'],story['summary'],*story.get('titles',{}).values(),*story.get('summaries',{}).values(),
    *(source.get('headline','')+' '+source['outlet'] for source in story['sources']),*(labels.get(tag,tag) for tag in story['tags'])])
  if q.strip().casefold() not in searchable.casefold():continue
  item=localized_story(story,p['language'],p['news_languages'],allow_translation=p['plan']!='free');item['vote']=value;item['feedback_reason']=f.get(story['id'],{}).get('reason','interest');item['feedback_at']=f.get(story['id'],{}).get('created_at');item['reason']='Recently viewed by you'
  entries.append({'story':item,'article_id':row['article_id'],'first_viewed_at':row['first_viewed_at'],'last_viewed_at':row['last_viewed_at'],'view_count':row['view_count']})
 return {'entries':entries[:max(1,min(200,limit))],'total':len(rows),'matches':len(entries)}

class SavedStoryChange(BaseModel):
 saved:bool
 occurred_at:str|None=Field(default=None,max_length=40)

@app.put('/api/profiles/{pid}/saved/{story_id}')
def save_story(pid:str,story_id:str,body:SavedStoryChange):
 profile(pid)
 if story_id not in STORIES:raise HTTPException(404,'Story not found')
 timestamp=action_time(body.occurred_at)
 with conn() as c:
  c.execute('''INSERT INTO saved_stories VALUES (?,?,?,?,?)
   ON CONFLICT(profile_id,story_id) DO UPDATE SET
    saved=excluded.saved,
    created_at=CASE WHEN saved_stories.saved=0 AND excluded.saved=1 THEN excluded.created_at ELSE saved_stories.created_at END,
    updated_at=excluded.updated_at
   WHERE excluded.updated_at>=saved_stories.updated_at''',(pid,story_id,int(body.saved),timestamp,timestamp))
  row=c.execute('SELECT * FROM saved_stories WHERE profile_id=? AND story_id=?',(pid,story_id)).fetchone()
 return {'story_id':story_id,'saved':bool(row['saved']),'saved_at':row['created_at'] if row['saved'] else None,'updated_at':row['updated_at']}

@app.get('/api/profiles/{pid}/saved')
def saved_news(pid:str,q:str=Query(default='',max_length=200),period:Literal['all','today','week']='all'):
 p=profile(pid);refresh_catalog();items=[]
 local_now=dt.datetime.fromisoformat(now()).astimezone(ZoneInfo(p['timezone']))
 with conn() as c:rows=c.execute('SELECT story_id,created_at FROM saved_stories WHERE profile_id=? AND saved=1 ORDER BY created_at DESC,story_id',(pid,)).fetchall()
 for row in rows:
  original=STORIES.get(row['story_id'])
  if not original:continue
  timestamp=dt.datetime.fromisoformat(row['created_at']).astimezone(local_now.tzinfo)
  if period=='today' and timestamp.date()!=local_now.date():continue
  if period=='week' and timestamp<local_now-dt.timedelta(days=7):continue
  story=localized_story(original,p['language'],p['news_languages'],allow_translation=p['plan']!='free')
  searchable=' '.join([story['title'],story['summary'],*story.get('tags',[]),*(source.get('outlet','')+' '+source.get('headline','') for source in story['sources'])]).casefold()
  if q.strip().casefold() not in searchable:continue
  items.append({**story,'saved':True,'saved_at':row['created_at']})
 return {'stories':items,'total':len(rows),'matches':len(items)}

@app.delete('/api/profiles/{pid}/editions/{eid}/audio')
def remove_edition_audio(pid:str,eid:str):
 profile(pid)
 freed=shared=unreclaimed=0;deleted_paths=set()
 with conn() as c:
  row=c.execute('SELECT data FROM editions WHERE id=? AND profile_id=?',(eid,pid)).fetchone()
  if not row:raise HTTPException(404,'Edition not found')
  edition=normalized_edition(json.loads(row[0]))
  keys={chapter['cache_key'] for chapter in edition['chapters'] if chapter.get('audio') and re.fullmatch(r'[a-f0-9]{64}',chapter.get('cache_key',''))}
  referenced=set()
  for other in c.execute('SELECT data FROM editions WHERE id!=?',(eid,)):
   referenced.update(chapter['cache_key'] for chapter in json.loads(other[0])['chapters'] if chapter.get('audio'))
  media=(ROOT/'media').resolve()
  for key in keys:
   path=(media/(key+'.mp3')).resolve()
   if not path.is_relative_to(media):continue
   size=path.stat().st_size if path.is_file() else 0
   if key in referenced:shared+=size;continue
   try:path.unlink(missing_ok=True)
   except OSError:unreclaimed+=size;continue
   freed+=size;deleted_paths.add(path)
   c.execute('DELETE FROM audio_cache WHERE cache_key=?',(key,))
  episode_audio=edition.get('episode_audio')
  episode_url=episode_audio.get('url') if isinstance(episode_audio,dict) else None
  if episode_url and episode_url.startswith(('/media/demo-samples/','/media/episodes/')):
   other_urls=set()
   for other in c.execute('SELECT data FROM editions WHERE id!=?',(eid,)):
    other_audio=json.loads(other[0]).get('episode_audio')
    if isinstance(other_audio,dict) and other_audio.get('url'):other_urls.add(other_audio['url'])
   media=(ROOT/'media').resolve();path=(media/episode_url.removeprefix('/media/')).resolve()
   if path.is_relative_to(media):
    if episode_url in other_urls:
     try:shared+=path.stat().st_size
     except OSError:pass
    else:
     size=path.stat().st_size if path.is_file() else 0
     try:path.unlink(missing_ok=True)
     except OSError:unreclaimed+=size
     else:
      if path not in deleted_paths:freed+=size
    edition['episode_audio']=None
  for chapter in edition['chapters']:
   chapter['audio']=None
   if 'summary' not in chapter:
    chapter['summary']=chapter['text']
  edition['audio_mode']='summary-only';edition['audio_removed_at']=now()
  c.execute('UPDATE editions SET data=? WHERE id=?',(json.dumps(edition),eid))
 if hasattr(cloud_jobs,'cancel_edition_audio'):cloud_jobs.cancel_edition_audio(sys.modules[__name__],pid,eid)
 return {'edition':edition,'reclaimed_bytes':freed,'shared_bytes':shared,'unreclaimed_bytes':unreclaimed}

@app.get('/api/editions/{eid}/export')
def export_edition(eid:str,kind:Literal['report','script']='report'):
 with conn() as c:row=c.execute('SELECT data FROM editions WHERE id=?',(eid,)).fetchone()
 if not row:raise HTTPException(404,'Edition not found')
 e=normalized_edition(json.loads(row[0]));lines=[f"# {e['title']}",f"Briefing date: {e['briefing_date']}",f"Dataset replay: {e['news_date']}",f"Created: {e['created_at']}",'Synthetic voice; informational reporting.']
 for ch in e['chapters']:
  lines+=['',f"## {ch['title']}"]
  if kind=='script' and ch.get('turns'):
   lines.extend(f"**{turn['speaker'].title()}** — {turn['text']}" for turn in ch['turns'])
  else:lines.append(ch.get('summary',ch['text']) if kind=='report' else ch['text'])
  for s in ch['sources']:
   if kind=='report' or s['article_id'] in ch['claim_source_ids']:lines.append(f"- {s['outlet']}: {s['url']} [article {s['article_id']}]")
 return Response('\n'.join(lines),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="liquid-{kind}-{eid}.md"'})

@app.get('/api/desk')
def desk():
 with conn() as c:
  jobs=[dict(r) for r in c.execute('SELECT id,profile_id,state,error,created_at FROM jobs ORDER BY created_at DESC LIMIT 10')]
  cache=c.execute('SELECT COUNT(*) FROM audio_cache').fetchone()[0]
  editions_count=c.execute('SELECT COUNT(*) FROM editions').fetchone()[0]
 return {'stats':CATALOG['stats'],'version':CATALOG['version'],'jobs':jobs,'cached_chapters':cache,'editions':editions_count,'cost':{'actual_external_spend_usd':0,'full_dataset_articles':1740,'ten_times_articles':17400,'note':'Offline preparation and browser speech use no model or ElevenLabs API calls. Live API and hosting costs are not yet measured.'},'pipeline':[{'label':'Import six feeds','status':'done'},{'label':'Tag every article','status':'done'},{'label':'Link translated coverage','status':'done'},{'label':'Source-linked demo summaries','status':'done'},{'label':'Personalize and compose','status':'done'},{'label':'ElevenLabs / n8n Cloud','status':'pending'}]}

# These endpoints are deliberately disabled without a server-side secret.
# Live workflow setup is deferred until the demo has been reviewed.
def integration_auth(key):
 expected=os.getenv('WORKFLOW_SECRET','')
 if not expected:raise HTTPException(503,'Cloud integration is not configured')
 if not key or not secrets.compare_digest(key,expected):raise HTTPException(401,'Invalid workflow credential')

@app.post('/api/integrations/prepare')
def prepare_article(body:dict,x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key)
 # Live ingestion must use the reviewed extraction worker. No silent mock.
 raise HTTPException(501,'Live source extraction is not enabled in this demo')

@app.get('/api/integrations/due')
def due(x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key)
 return due_profiles()

def due_profiles():
 result=[]
 for p in profiles():
  if not p['scheduled'] or not p['onboarded']:continue
  local=dt.datetime.now(ZoneInfo(p['timezone']));target=dt.datetime.combine(local.date(),dt.time.fromisoformat(p['wake_time']),tzinfo=local.tzinfo)
  if target<local:target=dt.datetime.combine(local.date()+dt.timedelta(days=1),dt.time.fromisoformat(p['wake_time']),tzinfo=local.tzinfo)
  day=target.date().isoformat()
  if 0 <= (target-local).total_seconds() <= 1800:
   with conn() as c:exists=c.execute('SELECT 1 FROM deliveries WHERE profile_id=? AND day=?',(p['id'],day)).fetchone()
   if not exists:result.append({'profile_id':p['id'],'day':day})
 return result

class ScheduleClaim(BaseModel):
 profile_id:str=Field(min_length=1,max_length=80)
 day:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')

@app.post('/api/integrations/schedule/claim')
def workflow_schedule_claim(body:ScheduleClaim,x_workflow_key:str|None=Header(default=None)):
 """Reserve a due listener/day atomically before any paid audio calls."""
 integration_auth(x_workflow_key)
 p=profile(body.profile_id)
 local=dt.datetime.now(ZoneInfo(p['timezone']))
 target=dt.datetime.combine(local.date(),dt.time.fromisoformat(p['wake_time']),tzinfo=local.tzinfo)
 if target<local:target=dt.datetime.combine(local.date()+dt.timedelta(days=1),dt.time.fromisoformat(p['wake_time']),tzinfo=local.tzinfo)
 eligible=(p['scheduled'] and p['onboarded'] and body.day==target.date().isoformat() and 0 <= (target-local).total_seconds() <= 1800)
 token='cloud-reserved-'+uuid.uuid4().hex
 claimed=False
 if eligible:
  with conn() as c:
   result=c.execute('INSERT OR IGNORE INTO deliveries VALUES (?,?,?)',(body.profile_id,body.day,token))
   claimed=result.rowcount==1
 return {'claimed':claimed,'profile_id':body.profile_id,'day':body.day,'claim_token':token if claimed else None}

class ScheduleRelease(ScheduleClaim):
 claim_token:str=Field(pattern=r'^cloud-reserved-[a-f0-9]{32}$')

@app.post('/api/integrations/schedule/release')
def workflow_schedule_release(body:ScheduleRelease,x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key)
 with conn() as c:
  result=c.execute('DELETE FROM deliveries WHERE profile_id=? AND day=? AND job_id=?',(body.profile_id,body.day,body.claim_token))
 return {'released':result.rowcount==1}

@app.post('/api/integrations/editions/{pid}')
def workflow_compose(pid:str,x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key);return compose(pid)

class AudioResult(BaseModel):
 cache_key:str=Field(pattern=r'^[a-f0-9]{64}$')
 audio_base64:str=Field(max_length=40_000_000)
 alignment:dict

@app.post('/api/integrations/audio')
def workflow_audio(body:AudioResult,x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key)
 try:audio=base64.b64decode(body.audio_base64,validate=True)
 except Exception:raise HTTPException(422,'Invalid audio encoding')
 path=ROOT/'media'/(body.cache_key+'.mp3');path.write_bytes(audio)
 data={'url':'/media/'+path.name,'alignment':body.alignment,'provider':'elevenlabs'}
 with conn() as c:c.execute('INSERT OR REPLACE INTO audio_cache VALUES (?,?,?)',(body.cache_key,json.dumps(data),now()))
 return {'ok':True,'url':data['url']}

@app.post('/api/integrations/editions/{eid}/ready')
def workflow_ready(eid:str,x_workflow_key:str|None=Header(default=None)):
 integration_auth(x_workflow_key)
 with conn() as c:
  row=c.execute('SELECT data FROM editions WHERE id=?',(eid,)).fetchone()
  if not row:raise HTTPException(404,'Edition not found')
  e=normalized_edition(json.loads(row[0]))
  if e.get('audio_mode')=='summary-only':raise HTTPException(409,'The listener removed this edition’s audio. Create a new edition.')
  for ch in e['chapters']:
   cached=c.execute('SELECT data FROM audio_cache WHERE cache_key=?',(ch['cache_key'],)).fetchone()
   if not cached:raise HTTPException(409,'An audio chapter is missing')
   ch['audio']=json.loads(cached[0])
  e['audio_mode']='elevenlabs';e['status']='ready'
  c.execute('UPDATE editions SET data=? WHERE id=?',(json.dumps(e),eid))
  p=profile(e['profile_id']);day=dt.datetime.now(ZoneInfo(p['timezone'])).date().isoformat()
  c.execute('INSERT OR REPLACE INTO deliveries VALUES (?,?,?)',(p['id'],day,eid))
 return e

app.mount('/media',StaticFiles(directory=str(ROOT/'media')),name='media')
if (ROOT/'dist'/'assets').exists():app.mount('/assets',StaticFiles(directory=str(ROOT/'dist'/'assets')),name='assets')

@app.get('/{path:path}')
def spa(path:str):
 if path.startswith('api/'):raise HTTPException(404,'Unknown API endpoint')
 candidate=(ROOT/'dist'/path).resolve()
 if candidate.is_relative_to((ROOT/'dist').resolve()) and candidate.is_file():return FileResponse(candidate)
 index=ROOT/'dist'/'index.html'
 if not index.exists():return JSONResponse({'message':'Build the frontend first with npm run build.'},status_code=503)
 return FileResponse(index)

