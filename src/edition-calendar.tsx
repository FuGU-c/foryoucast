import {useEffect,useRef,useState} from 'react';
import {CalendarDays,ChevronLeft,ChevronRight,X} from 'lucide-react';
import {localToday} from './edition-dates';

export function EditionCalendar({days,selected,counts,onSelect}:{days:string[];selected:string;counts:Record<string,number>;onSelect:(day:string)=>void}){
 const [open,setOpen]=useState(false);
 const [month,setMonth]=useState((selected||days[0]||localToday()).slice(0,7));
 const wrapper=useRef<HTMLDivElement>(null);
 const trigger=useRef<HTMLButtonElement>(null);
 const dialog=useRef<HTMLElement>(null);
 const today=localToday();
 const earliest=days.at(-1)?.slice(0,7)||month;
 const latest=days[0]?.slice(0,7)||month;
 const first=new Date(month+'-01T12:00:00Z');
 const offset=(first.getUTCDay()+6)%7;
 const length=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
 const heading=first.toLocaleDateString('en-GB',{month:'long',year:'numeric',timeZone:'Europe/Brussels'});
 function close(){setOpen(false);trigger.current?.focus({preventScroll:true});}
 function changeMonth(delta:number){
  const date=new Date(month+'-01T12:00:00Z');
  date.setUTCMonth(date.getUTCMonth()+delta);
  setMonth(date.toISOString().slice(0,7));
 }
 useEffect(()=>{
  if(!open)return;
  const outside=(event:PointerEvent)=>{if(!wrapper.current?.contains(event.target as Node))setOpen(false);};
  document.addEventListener('pointerdown',outside);
  (dialog.current?.querySelector<HTMLButtonElement>('[aria-pressed=true]')||dialog.current?.querySelector<HTMLButtonElement>('.edition-calendar-days button:not(:disabled)'))?.focus({preventScroll:true});
  return ()=>document.removeEventListener('pointerdown',outside);
 },[open]);
 return <div className="edition-calendar" ref={wrapper}>
  <button ref={trigger} className="edition-calendar-trigger" aria-label="Choose a briefing date" aria-haspopup="dialog" aria-expanded={open} onClick={()=>{if(open)close();else{setMonth((selected||days[0]||today).slice(0,7));setOpen(true);}}}><CalendarDays size={18}/></button>
  {open&&<section ref={dialog} className="edition-calendar-popover" role="dialog" aria-modal="false" aria-label="Choose a briefing date" onKeyDown={event=>{if(event.key==='Escape'){event.stopPropagation();close();}}}>
   <div className="edition-calendar-heading"><div><span className="library-overline">FIND AN EDITION</span><h3>{heading}</h3></div><button aria-label="Close calendar" onClick={close}><X size={16}/></button></div>
   <div className="edition-calendar-month-nav"><button aria-label="Previous month" disabled={month<=earliest} onClick={()=>changeMonth(-1)}><ChevronLeft size={16}/></button><span>Choose a creation date</span><button aria-label="Next month" disabled={month>=latest} onClick={()=>changeMonth(1)}><ChevronRight size={16}/></button></div>
   <div className="edition-calendar-weekdays" aria-hidden="true">{['M','T','W','T','F','S','S'].map((day,index)=><span key={index}>{day}</span>)}</div>
   <div className="edition-calendar-days">{Array.from({length:offset},(_,index)=><span key={'empty-'+index}/>)}{Array.from({length},(_,index)=>{
    const day=month+'-'+String(index+1).padStart(2,'0');
    const available=days.includes(day);
    return <button key={day} disabled={!available} aria-label={new Date(day+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric',timeZone:'Europe/Brussels'})+(counts[day]?`, ${counts[day]} ${counts[day]===1?'edition':'editions'}`:'')}
     aria-pressed={selected===day} aria-current={day===today?'date':undefined} onClick={()=>{onSelect(day);close();}}><span>{index+1}</span>{!!counts[day]&&<i aria-hidden="true"/>}</button>;
   })}</div>
   <p className="edition-calendar-note"><span/>A dot marks a saved edition.<br/>Dates show when your briefings were created.</p>
  </section>}
 </div>;
}
