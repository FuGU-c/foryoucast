import {useEffect,useRef,useState} from 'react';
export type SleepSetting={kind:'off'}|{kind:'minutes';deadline:number}|{kind:'end';editionId:string|null};

export function useSleepTimer(onExpire:()=>void){
 const [setting,setSetting]=useState<SleepSetting>({kind:'off'});
 const [now,setNow]=useState(Date.now());
 const live=useRef(setting),callback=useRef(onExpire);
 callback.current=onExpire;
 function update(value:SleepSetting){live.current=value;setSetting(value);setNow(Date.now());}
 function clear(){update({kind:'off'});}
 useEffect(()=>{
  if(setting.kind!=='minutes')return;
  function check(){
   const value=live.current;
   const time=Date.now();setNow(time);
   if(value.kind==='minutes'&&time>=value.deadline){live.current={kind:'off'};setSetting({kind:'off'});callback.current();}
  }
  const timeout=setTimeout(check,Math.max(0,setting.deadline-Date.now()));
  const interval=setInterval(check,1000);
  document.addEventListener('visibilitychange',check);
  return ()=>{clearTimeout(timeout);clearInterval(interval);document.removeEventListener('visibilitychange',check);};
 },[setting]);
 return {
  setting,clear,
  minutes:(minutes:number)=>{if(Number.isFinite(minutes)&&minutes>=1&&minutes<=180)update({kind:'minutes',deadline:Date.now()+minutes*60000});},
  end:(editionId:string|null)=>update({kind:'end',editionId}),
  bindEdition:(id:string)=>{const value=live.current;if(value.kind==='end'){if(value.editionId===null)update({kind:'end',editionId:id});else if(value.editionId!==id)clear();}},
  finishEdition:(id:string)=>{const value=live.current;if(value.kind==='end'&&value.editionId===id){clear();return true;}return false;},
  remainingSeconds:setting.kind==='minutes'?Math.max(0,Math.ceil((setting.deadline-now)/1000)):0,
 };
}
export type SleepTimer=ReturnType<typeof useSleepTimer>;
