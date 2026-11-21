import type {Profile,Story} from './types';
import {actionTime} from './action-time';
export function contribution(story:Pick<Story,'tags'|'primary_topic'>,value:number,reason='interest'){
 const tags=[...new Set(story.tags)],primary=tags.includes(story.primary_topic||'')?story.primary_topic:tags[0];
 return Object.fromEntries(tags.map(tag=>[tag,value&&reason==='interest'?value*(tags.length===1?1:tag===primary?.6:.4/(tags.length-1)):0]));
}
export function effectiveWeights(profile:Profile,signed=false){
 const learned=profile.learned_interests||{};
 return Object.fromEntries([...new Set([...Object.keys(profile.interests),...Object.keys(learned)])].map(tag=>[tag,Math.max(signed?-2:0,Math.min(5,(profile.interests[tag]||0)+Math.max(-2,Math.min(2,learned[tag]||0))))]));
}
export function applyLearning(profile:Profile,delta:Record<string,number>):Profile{
 const learned={...profile.learned_interests};
 for(const [tag,value] of Object.entries(delta))learned[tag]=Math.round(((learned[tag]||0)+value)*10000)/10000;
 const next={...profile,learned_interests:learned};return {...next,effective_interests:effectiveWeights(next)};
}
export function clearEditedLearning(before:Profile,after:Profile):Profile{
 const learned={...after.learned_interests};
 const times={...after.interest_edit_times};
 for(const tag of new Set([...Object.keys(before.interests),...Object.keys(after.interests)]))if(before.interests[tag]!==after.interests[tag]&&!after.interest_edits?.includes(tag))times[tag]=actionTime();
 for(const tag of new Set([...Object.keys(before.interests),...Object.keys(after.interests),...(after.interest_edits||[])]))if(before.interests[tag]!==after.interests[tag]||after.interest_edits?.includes(tag))delete learned[tag];
 const next={...after,interest_edit_times:times,learned_interests:learned};return {...next,effective_interests:effectiveWeights(next)};
}

export function mergeLearningSnapshot(incoming:Profile,latest:Profile):Profile{
 const learned={...latest.learned_interests},resets={...latest.interest_resets};
 for(const [tag,time] of Object.entries(incoming.interest_resets||{}))if(Date.parse(time)>(Date.parse(resets[tag]||'')||0)){resets[tag]=time;learned[tag]=incoming.learned_interests?.[tag]||0;}
 const next={...incoming,learned_interests:learned,interest_resets:resets};return {...next,effective_interests:effectiveWeights(next)};
}
