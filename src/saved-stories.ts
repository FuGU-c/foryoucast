import type {Story} from './types';

export type SavedStoryRecord = {story:Story;saved_at:string};

const cacheKey=(profileId:string)=>`liquid-briefing:saved:${profileId}`;

export function readSavedStoryCache(profileId:string):SavedStoryRecord[]{
 try{
  const parsed=JSON.parse(localStorage.getItem(cacheKey(profileId))||'[]');
  if(!Array.isArray(parsed))return [];
  return parsed.filter((item):item is SavedStoryRecord=>!!item&&typeof item==='object'&&!!item.story&&typeof item.story.id==='string');
 }catch{return [];}
}

export function writeSavedStoryCache(profileId:string,records:SavedStoryRecord[]):void{
 try{localStorage.setItem(cacheKey(profileId),JSON.stringify(records));}catch{}
}

export function savedRecordsFromStories(stories:Story[]):SavedStoryRecord[]{
 const now=new Date().toISOString();
 return stories.filter(story=>story&&typeof story.id==='string').map(story=>({
  story:{...story,saved:true},
  saved_at:story.saved_at||now,
 }));
}

export function filterSavedRecords(records:SavedStoryRecord[],query:string,period:string,now=new Date()):SavedStoryRecord[]{
 const needle=query.trim().toLocaleLowerCase();
 const cutoff=now.getTime()-7*24*60*60*1000;
 const today=now.toLocaleDateString('en-CA',{timeZone:'Europe/Brussels'});
 return records.filter(({story,saved_at})=>{
  if(needle){
   const haystack=[story.title,story.summary,...story.tags,...story.sources.flatMap(source=>[source.outlet,source.headline||'',source.snippet||''])].join(' ').toLocaleLowerCase();
   if(!haystack.includes(needle))return false;
  }
  if(period==='today')return new Date(saved_at).toLocaleDateString('en-CA',{timeZone:'Europe/Brussels'})===today;
  if(period==='week')return Date.parse(saved_at)>=cutoff;
  return true;
 });
}
