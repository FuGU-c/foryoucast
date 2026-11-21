import {useRef,useState} from 'react';
import type {Memory,Profile,Story} from './types';
import {actionTime} from './action-time';
import {applyLearning,contribution} from './feedback-learning';
type Change={storyId:string;value:number;reason:string;version:number;occurredAt?:string;tags:string[];primary_topic?:string};
type Result={memory:Memory;profile?:Profile;vote?:{value:number;reason:string;created_at:string}};
type Options={write:(profile:string,change:Change)=>Promise<Result>;accept:(profile:string,result:Result)=>void;failed:()=>void};
/** Serialize votes, preserve the current card, and preview reversible topic learning. */
export function useVoteSync(options:Options){
 const [states,setStates]=useState<Record<string,Change>>({}),[revision,setRevision]=useState(0);
 const live=useRef(states),confirmed=useRef(new Map<string,Change>()),pending=useRef(new Map<string,Map<string,Change>>());
 const running=useRef(new Set<string>()),version=useRef(0),helpers=useRef(options);helpers.current=options;
 const key=(profile:string,story:string)=>profile+':'+story;
 function publish(id:string,value:Change){live.current={...live.current,[id]:value};setStates(live.current);setRevision(value=>value+1);}
 async function flush(profile:string){
  if(running.current.has(profile))return;running.current.add(profile);
  const queue=pending.current.get(profile)!;
  try{while(queue.size){
   const change=queue.values().next().value!,id=key(profile,change.storyId);
   try{
    const result=await helpers.current.write(profile,change);const accepted=result.vote?{...change,value:result.vote.value,reason:result.vote.reason,occurredAt:result.vote.created_at}:change;confirmed.current.set(id,accepted);if(live.current[id]===change)publish(id,accepted);helpers.current.accept(profile,result);setRevision(value=>value+1);
   }catch{if(queue.get(change.storyId)===change){publish(id,confirmed.current.get(id)!);helpers.current.failed();}}
   if(queue.get(change.storyId)===change)queue.delete(change.storyId);
  }}finally{running.current.delete(profile);}
 }
 function vote(profile:string,story:Story,value:number,reason='interest'){
  const id=key(profile,story.id),before=live.current[id]?.value??story.vote;
  if(!confirmed.current.has(id))confirmed.current.set(id,{storyId:story.id,value:story.vote,reason:story.feedback_reason||'interest',version:0,occurredAt:story.feedback_at,tags:story.tags,primary_topic:story.primary_topic});
  const next=reason==='interest'&&before===value?0:value;
  const change={storyId:story.id,value:next,reason,version:++version.current,occurredAt:actionTime(),tags:story.tags,primary_topic:story.primary_topic};publish(id,change);
  let queue=pending.current.get(profile);if(!queue){queue=new Map();pending.current.set(profile,queue);}queue.set(story.id,change);void flush(profile);
 }
 function decorate(profile:string,story:Story):Story{const value=states[key(profile,story.id)];return !value?story:{...story,vote:value.value,feedback_reason:value.reason};}
 function withLearning(profile:Profile):Profile{
  const delta:Record<string,number>={};
  for(const [id,current] of Object.entries(live.current)){
   if(!id.startsWith(profile.id+':'))continue;const saved=confirmed.current.get(id);if(!saved||saved===current)continue;
   const before=contribution(saved,saved.value,saved.reason),after=contribution(current,current.value,current.reason);
   for(const tag of new Set([...Object.keys(before),...Object.keys(after)])){
    const cutoff=Math.max(Date.parse(profile.interest_resets?.[tag]||'')||0,Date.parse(profile.interest_edit_times?.[tag]||'')||0);
    const beforeEligible=!cutoff||!!saved.occurredAt&&Date.parse(saved.occurredAt)>cutoff;
    const afterEligible=!cutoff||!!current.occurredAt&&Date.parse(current.occurredAt)>cutoff;
    delta[tag]=(delta[tag]||0)+(afterEligible?after[tag]||0:0)-(beforeEligible?before[tag]||0:0);
   }
  }
  return Object.values(delta).some(value=>Math.abs(value)>.00001)?applyLearning(profile,delta):profile;
 }
 return {vote,decorate,withLearning,revision};
}
