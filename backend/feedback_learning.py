"""Deterministic, reversible topic learning from the latest vote per story."""
def contribution(story,value,reason='interest'):
 if not value or reason!='interest':return {}
 tags=list(dict.fromkeys(story.get('tags',[])))
 if not tags:return {}
 primary=story.get('primary_topic')
 if primary not in tags:primary=tags[0]
 return {tag:value*(1 if len(tags)==1 else .6 if tag==primary else .4/(len(tags)-1)) for tag in tags}

def learned_weights(rows,stories,resets=None):
 totals={};resets=resets or {}
 for row in rows:
  story=stories.get(row['story_id'])
  if not story:continue
  for tag,delta in contribution(story,row['value'],row['reason']).items():
   if row['created_at']<=resets.get(tag,''):continue
   totals[tag]=totals.get(tag,0)+delta
 return {tag:round(value,4) for tag,value in totals.items() if abs(value)>.00001}

def effective_weights(manual,learned,signed=False):
 return {tag:round(max(-2 if signed else 0,min(5,manual.get(tag,0)+max(-2,min(2,learned.get(tag,0))))),4) for tag in manual.keys()|learned.keys()}
