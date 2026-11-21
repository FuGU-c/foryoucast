import {actionTime} from './action-time';
import {effectiveWeights} from './feedback-learning';
import type {Goal, GoalId, NewsLanguage, Profile, Story} from './types';

export type ProfileChange = (current:Profile)=>Profile;

export function toggleGoal(current:Profile, id:GoalId, goals:Goal[]):Profile {
 const next=current.goals.includes(id)?current.goals.filter(goal=>goal!==id):[...current.goals,id];
 const suggested=new Set(goals.filter(goal=>next.includes(goal.id)).flatMap(goal=>goal.tags));
 const interests={...current.interests};
 const autoTags=new Set(current.goal_tags);
 for(const id of autoTags)if(!suggested.has(id)){delete interests[id];autoTags.delete(id);}
 for(const id of suggested)if(interests[id]===undefined){interests[id]=3;autoTags.add(id);}
 return {...current,goals:next,goal:next[0]||'general',interests,goal_tags:[...autoTags]};
}

export function updateTag(current:Profile,id:string,weight:number):Profile {
 return {...current,interest_edit_times:{...current.interest_edit_times,[id]:actionTime()},interest_edits:[...new Set([...(current.interest_edits||[]),id])],interests:{...current.interests,[id]:weight},goal_tags:current.goal_tags.filter(tag=>tag!==id)};
}

export function preferenceKey(profile:Profile){
 const canonicalize=(value:unknown):unknown=>{
  if(Array.isArray(value))return value.map(canonicalize);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).sort(([left],[right])=>left<right?-1:left>right?1:0).map(([key,item])=>[key,canonicalize(item)]));
  return value;
 };
 return JSON.stringify(canonicalize([profile.goals,profile.interests,profile.language,profile.news_languages,profile.depth,profile.duration,profile.symbols,profile.custom_interests,profile.plan,profile.tts_provider,profile.device_voices,profile.elevenlabs_voices,profile.translate_news,profile.ai_settings]));
}

export function previewStories(items:Story[], profile:Profile):Story[] {
 const byNewest=Math.max(...items.map(item=>Date.parse(item.updated_at)));
 const scored=items.flatMap(story=>{
  const available=profile.news_languages.filter(lang=>story.sources.some(source=>source.language===lang));
  if(!available.length)return [];
  const display=available.includes(profile.language)?profile.language:available[0];
  const localizedSources=[...story.sources].sort((a,b)=>Number(b.language===display)-Number(a.language===display));
  const titleSource=localizedSources[0];
  const search=story.sources.map(source=>source.headline||'').join(' ')+' '+story.entities.join(' ');
  const aliases:Record<string,string>={NVDA:'Nvidia',INTC:'Intel',MSFT:'Microsoft',AAPL:'Apple',HD:'Home Depot',CRM:'Salesforce',GOOG:'Google'};
  const watchlist=profile.symbols.filter(symbol=>search.includes(symbol)||(aliases[symbol]&&search.toLowerCase().includes(aliases[symbol].toLowerCase())));
  const custom=profile.custom_interests.toLowerCase().split(/\W+/).filter(term=>term.length>3);
  const weights=effectiveWeights(profile,true);
  const strongestTag=[...story.tags].sort((a,b)=>(weights[b]||0)-(weights[a]||0))[0];
  const age=(byNewest-Date.parse(story.updated_at))/86400000;
  const score=story.tags.reduce((value,tag)=>value+(weights[tag]||0),0)/Math.max(1,story.tags.length**.35)
   +(weights[story.primary_topic||'']||0)*.8+Math.max(0,3-age*.35)+(story.sources.length>1?1:0)
   +2*story.vote+Math.min(5,watchlist.length*3)+Math.min(2,custom.filter(term=>search.toLowerCase().includes(term)).length*.6)
   +(profile.goals.includes('trader')&&story.tags.includes('forex')?2:0)
   +(profile.goals.includes('general')&&story.tags.some(tag=>['world','money','culture'].includes(tag))?2:0);
  const originalLanguages=new Set(story.sources.filter(source=>story.claim_source_ids.includes(source.article_id)).map(source=>source.language));
  const canTranslate=profile.plan==='plus'||profile.plan==='premium';
  const summaryLanguage=canTranslate||originalLanguages.has(profile.language)?profile.language:([...originalLanguages].find(lang=>available.includes(lang))||[...originalLanguages][0]||display);
  const allowedSummaries=canTranslate?story.summaries:Object.fromEntries(Object.entries(story.summaries||{}).filter(([language])=>originalLanguages.has(language as NewsLanguage)));
  return [{...story,summaries:allowedSummaries,ai_translated:canTranslate&&!originalLanguages.has(summaryLanguage),score,title:!canTranslate?(titleSource.headline||story.title):display===profile.language?story.titles?.[display]||titleSource.headline||story.title:titleSource.headline||story.title,
   title_language:display,summary:allowedSummaries?.[summaryLanguage]||story.sources.find(source=>source.language===summaryLanguage)?.snippet||'',summary_language:summaryLanguage,
   sources:localizedSources,news_languages_available:available,selected_language_sources:localizedSources.filter(source=>available.includes(source.language)),
   preferred_sources:localizedSources.filter(source=>source.language===display),source_language_note:undefined,
   reason:watchlist.length?'From your watchlist: '+watchlist.join(', '):strongestTag&&weights[strongestTag]>0?'Matches your current interests.':'A different perspective for your day'}];
 });
 const chosen:Story[]=[];
 const counts:Record<string,number>={};
 while(scored.length){
  scored.sort((a,b)=>score(b)-score(a)||a.id.localeCompare(b.id));
  const item=scored.shift()!;
  chosen.push(item);
  for(const tag of item.tags)counts[tag]=(counts[tag]||0)+1;
 }
 function score(story:Story&{score:number}){
  return story.score-story.tags.reduce((penalty,tag)=>penalty+(counts[tag]||0)*.8,0);
 }
 return chosen;
}

export function nextNewsLanguages(language:NewsLanguage, selected:NewsLanguage[]){
 const results=selected.includes(language)?selected.filter(item=>item!==language):[...selected,language];
 return results.length?results:selected;
}
