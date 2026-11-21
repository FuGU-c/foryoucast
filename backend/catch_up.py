"""Conservative, token-free catch-up matching over already prepared stories."""
import datetime as dt
import re
import unicodedata
from urllib.parse import urlsplit

STOP = set('a an the and or of to in on for at by with from as is are was were be been this that it its has have had not but report reports news latest new says said according about after before over under into across amid also their they company coverage supplied dataset story'.split())


def tokens(text):
 text=unicodedata.normalize('NFKC',text).casefold()
 return {word for word in re.findall(r'[^\W_]+',text) if (len(word)>2 or word.isnumeric()) and word not in STOP}


def snapshot(story):
 # Use one canonical language: added translations/images/source counts aren't developments.
 return {'id':story['id'],'title':story.get('titles',{}).get('en') or story.get('title',''),
         'summary':story.get('summaries',{}).get('en') or story.get('summary',''),
         'entities':story.get('entities',[]),'updated_at':story['updated_at'],
         'sources':[{key:source.get(key,'') for key in ('article_id','url','translation_key')} for source in story.get('sources',[])]}


def stamp(value):
 try:
  value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
  return value.replace(tzinfo=value.tzinfo or dt.timezone.utc).timestamp()
 except (ValueError,TypeError,AttributeError):return 0


def overlap(left,right):
 return len(left&right)/max(1,len(left|right))


def source_keys(story):
 result=set()
 for source in story.get('sources',[]):
  for key in ('article_id','translation_key'):
   if source.get(key):result.add((key,source[key]))
  url=source.get('url','')
  if url:
   parsed=urlsplit(url)
   # Ignore homepages, query/tracking parameters and URL fragments.
   if parsed.netloc and parsed.path.strip('/'):result.add(('url',parsed.netloc.casefold()+parsed.path.rstrip('/')))
 return result


def relationship(current,previous):
 if current['id']==previous['id']:return 3
 if source_keys(current)&source_keys(previous):return 2
 entities={value.casefold() for value in current.get('entities',[])}&{value.casefold() for value in previous.get('entities',[])}
 # Shared tags or a company name alone never establish the same event.
 if entities and overlap(tokens(current['title']),tokens(previous['title']))>=.3 and overlap(tokens(current['summary']),tokens(previous['summary']))>=.42:return 1
 return 0


def material_change(current,previous):
 old=tokens(previous['title']+' '+previous['summary'])
 new=tokens(current['title']+' '+current['summary'])
 added=new-old
 # Rewording, grammar fixes and one new adjective should not become breaking news.
 number_change={word for word in added if any(char.isdigit() for char in word)}
 return (len(added)>=4 and len(added)/max(1,len(new))>=.12) or bool(number_change and len(added)>=2)


def select_updates(items,known,baseline):
 """Known entries hold the content the listener actually saw/heard, not today's copy."""
 result=[]
 for story in items:
  current=snapshot(story)
  matches=[(relationship(current,entry['snapshot']),entry['snapshot']) for entry in known]
  matches=[match for match in matches if match[0]]
  if matches:
   strength=max(match[0] for match in matches)
   previous=[match[1] for match in matches if match[0]==strength]
   # Any already-consumed copy of this coverage prevents its repetition.
   if any(not material_change(current,old) for old in previous):continue
   latest=max(previous,key=lambda old:stamp(old['updated_at']))
   if stamp(current['updated_at'])<=stamp(latest['updated_at']):continue
   result.append({**story,'catch_up_kind':'development','catch_up_previous_id':latest['id'],
                  'catch_up_note':'New details in a story you read or listened to.'})
  elif baseline and stamp(story.get('published_at',story['updated_at']))>stamp(baseline):
   result.append({**story,'catch_up_kind':'new','catch_up_note':'Published since your last catch-up.'})
 # Follow-ups lead, relevance order from the normal feed breaks ties.
 return sorted(result,key=lambda item:item['catch_up_kind']!='development')[:8]
