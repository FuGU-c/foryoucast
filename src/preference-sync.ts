import {useEffect,useRef,useState} from 'react';
import type {Profile} from './types';
import type {ProfileChange} from './live-preferences';
import {effectiveWeights} from './feedback-learning';

const key='seranews-pending-preferences-v1';
type Pending = Record<string,Profile|undefined>;
function restore():Pending {
 try{
  const value=JSON.parse(localStorage.getItem(key)||'{}');
  return value&&typeof value==='object'&&!Array.isArray(value)?value:{};
 }
 catch{return {};}
}

export function usePreferenceSync(write:(profile:Profile)=>Promise<Profile>, accept:(profile:Profile)=>Promise<void>){
 const [pending,setPending]=useState<Pending>(restore);
 const [errors,setErrors]=useState<Record<string,string|undefined>>({});
 const staged=useRef(pending);
 const timers=useRef(new Map<string,ReturnType<typeof setTimeout>>());
 const writes=useRef(new Map<string,Promise<boolean>>());
 const helpers=useRef({write,accept});
 helpers.current={write,accept};

 function publish(){
  const next={...staged.current};
  setPending(next);
  try{localStorage.setItem(key,JSON.stringify(next));}catch{/* The tab still retains the current edits. */}
 }

 function flush(id:string):Promise<boolean>{
  clearTimeout(timers.current.get(id));
  timers.current.delete(id);
  const inFlight=writes.current.get(id);
  if(inFlight)return inFlight;
  if(!staged.current[id])return Promise.resolve(true);
  const job=(async()=>{
   let snapshot:Profile|undefined;
   try{
    while((snapshot=staged.current[id])){
     const saved=await helpers.current.write(snapshot);
     if(staged.current[id]!==snapshot)continue;
     await helpers.current.accept(saved);
     if(staged.current[id]!==snapshot)continue;
     delete staged.current[id];
     setErrors(previous=>({...previous,[id]:undefined}));
     publish();
    }
    return true;
   }catch{
    setErrors(previous=>({...previous,[id]:'Changes are on this device. Retry when the server is available.'}));
    return false;
   }finally{
    writes.current.delete(id);
   }
  })();
  writes.current.set(id,job);
  return job;
 }

 function edit(profile:Profile,change:ProfileChange){
  const before=staged.current[profile.id]||profile;
  const next=change(before);
  if(next===before)return;
  staged.current[profile.id]=next;
  setErrors(previous=>({...previous,[profile.id]:undefined}));
  publish();
  clearTimeout(timers.current.get(profile.id));
  timers.current.set(profile.id,setTimeout(()=>void flush(profile.id),180));
 }

 useEffect(()=>{
  function retryPending(){for(const id of Object.keys(staged.current))void flush(id);}
  window.addEventListener('online',retryPending);
  return ()=>window.removeEventListener('online',retryPending);
 },[]);

 function mergeLearning(saved:Profile){
  const current=staged.current[saved.id];if(!current)return;
  const learned={...saved.learned_interests};
  for(const tag of new Set([...Object.keys(current.interests),...Object.keys(saved.interests)]))if(current.interests[tag]!==saved.interests[tag]||(Date.parse(current.interest_edit_times?.[tag]||'')||0)>(Date.parse(saved.interest_resets?.[tag]||'')||0))delete learned[tag];
  const next={...current,learned_interests:learned};staged.current[saved.id]={...next,effective_interests:effectiveWeights(next)};publish();
 }
 function dropPending(id:string){clearTimeout(timers.current.get(id));timers.current.delete(id);delete staged.current[id];publish();}
 return {pending,errors,flush,edit,mergeLearning,dropPending};
}
