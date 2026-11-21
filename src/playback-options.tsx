import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Check,Gauge,Headphones,Moon,X} from 'lucide-react';
import type {SleepTimer} from './sleep-timer';
import './playback-options.css';
export const playbackSpeeds=[.75,1,1.25,1.5,1.75,2];

export function PlaybackOptions({speed,onSpeed,sleep,editionId}:{speed:number;onSpeed:(speed:number)=>void;sleep:SleepTimer;editionId:string|null}){
 const [panel,setPanel]=useState<'speed'|'sleep'|null>(null);
 const [custom,setCustom]=useState('20');
 const sheet=useRef<HTMLElement>(null);
 const sleepText=sleep.setting.kind==='end'?'End of podcast':sleep.setting.kind==='minutes'?`${Math.floor(sleep.remainingSeconds/60)}:${String(sleep.remainingSeconds%60).padStart(2,'0')}`:'Sleep timer';
 useEffect(()=>{
  if(!panel)return;
  const before=document.activeElement as HTMLElement|null;
  sheet.current?.focus({preventScroll:true});
  return ()=>{if(before?.isConnected)before.focus({preventScroll:true});};
 },[panel]);
 return <>
  <div className="playback-options-bar"><button aria-label="Playback speed" aria-haspopup="dialog" onClick={()=>setPanel('speed')}><Gauge size={16}/><span>{speed}×</span></button>
   <button aria-label="Sleep timer" aria-haspopup="dialog" className={sleep.setting.kind!=='off'?'timer-active':''} onClick={()=>setPanel('sleep')}><Moon size={16}/><span>{sleepText}</span></button></div>
  {panel&&createPortal(<div className="listening-options-backdrop" onClick={()=>setPanel(null)}><section ref={sheet} role="dialog" aria-modal="true" tabIndex={-1} aria-label={panel==='speed'?'Playback speed':'Sleep timer'} className="listening-options-sheet" onClick={event=>event.stopPropagation()} onKeyDown={event=>{
   if(event.key==='Escape'){event.stopPropagation();setPanel(null);}
   if(event.key==='Tab'){
    const nodes=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input')],first=nodes[0],last=nodes.at(-1);
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===sheet.current)){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
   }
  }}>
   <header><div><span>YOUR LISTENING PACE</span><h2>{panel==='speed'?'Make it your tempo.':'Drift off, we’ll pause.'}</h2></div><button aria-label="Close playback options" onClick={()=>setPanel(null)}><X size={19}/></button></header>
   {panel==='speed'?<><p>Change speed instantly. Your place stays the same.</p><div className="speed-options">{playbackSpeeds.map(rate=><button key={rate} aria-pressed={speed===rate} onClick={()=>{onSpeed(rate);setPanel(null);}}><b>{rate}×</b><span>{rate<1?'A little slower':rate===1?'Original pace':rate===2?'Twice as fast':'A little quicker'}</span>{speed===rate&&<Check size={14}/>}</button>)}</div><p className="listening-options-note">Briefing length estimates are shown at 1× speed.</p></>:<>
    <p>Pause playback after a set time, or at the end of this whole podcast.</p>
    <div className="sleep-minute-options">{[5,10,15,30,45,60].map(minutes=><button key={minutes} onClick={()=>{sleep.minutes(minutes);setPanel(null);}}>{minutes} min</button>)}</div>
    <form className="custom-sleep-time" onSubmit={event=>{event.preventDefault();const value=Number(custom);if(value>=1&&value<=180){sleep.minutes(value);setPanel(null);}}}><label>Custom minutes<input aria-label="Custom sleep minutes" type="number" min="1" max="180" required value={custom} onChange={event=>setCustom(event.target.value)}/></label><button type="submit">Set timer</button></form>
    <button className="sleep-at-end" aria-pressed={sleep.setting.kind==='end'} onClick={()=>{sleep.end(editionId);setPanel(null);}}><Headphones size={19}/><span><b>Stop at the end of this podcast</b><small>Finish every chapter, then stop.</small></span>{sleep.setting.kind==='end'&&<Check size={16}/>}</button>
    {sleep.setting.kind!=='off'&&<button className="cancel-sleep-timer" onClick={()=>{sleep.clear();setPanel(null);}}>Turn off sleep timer</button>}
    <p className="listening-options-note">The countdown uses real minutes, at any playback speed, while the app is open.</p>
   </>}
  </section></div>,document.querySelector('.phone-frame .app')||document.body)}
 </>;
}
