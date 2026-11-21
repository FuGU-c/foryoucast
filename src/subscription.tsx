import {useEffect,useRef} from 'react';
import {Check,ChevronRight,Sparkles,X} from 'lucide-react';
import type {Profile} from './types';
import type {ProfileChange} from './live-preferences';
import {normalizePlan,planFor,plans,type PlanId} from './plans';
export function SubscriptionCard({profile,onOpen}:{profile:Profile;onOpen:()=>void}){
 return <button className="subscription-shortcut" aria-label="Subscription and plans" onClick={onOpen}><span className="subscription-symbol"><Sparkles size={21}/></span><span><b>Your subscription</b><small>Seranews {planFor(profile).name} · Find your rhythm</small></span><ChevronRight size={18}/></button>;
}
const rows=[
 ['Podcast length','~7 min','~15 min','~40 min'],
 ['Podcasts','1 / day','Unlimited','Unlimited'],
 ['Natural voice','—','1 / day','Unlimited'],
 ['Basic voice','1 / day','Unlimited','Unlimited'],
 ['News & summaries','Included','Included','Included'],
 ['Spoken summaries','—','Included','Included'],
 ['AI translations','—','Included','Included'],
 ['Personalization','Included','Included','Included'],
 ['Advertising','With ads','With ads','Ad-free'],
];
export function SubscriptionModal({profile,onEdit,onClose}:{profile:Profile;onEdit:(change:ProfileChange)=>void;onClose:()=>void}){
 const current=profile.plan||'free',sheet=useRef<HTMLElement>(null);
 useEffect(()=>{const before=document.activeElement as HTMLElement|null;sheet.current?.focus();return()=>{if(before?.isConnected)before.focus();};},[]);
 function choose(plan:PlanId){onEdit(previous=>normalizePlan({...previous,plan}));}
 return <div className="overlay subscription-overlay" onClick={onClose}><section ref={sheet} tabIndex={-1} className="subscription-sheet plan-comparison-sheet" role="dialog" aria-modal="true" aria-label="Subscription plans" onClick={event=>event.stopPropagation()} onKeyDown={event=>{if(event.key==='Tab'){const buttons=[...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')],first=buttons[0],last=buttons.at(-1);if(event.shiftKey&&(document.activeElement===first||document.activeElement===sheet.current)){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}}}>
  <header><div><span className="settings-kicker">YOUR NEWS. YOUR PERSPECTIVE.</span><h2>A clearer choice.</h2></div><button className="icon-button" aria-label="Close subscription plans" onClick={onClose}><X size={20}/></button></header>
  <p className="plan-comparison-intro">Start with the essentials. Make room for more.</p>
  <div className="plan-comparison" role="table" aria-label="Compare all three plans">
   <div className="plan-compare-head" role="row"><span role="columnheader">Your day,<br/>your way.</span>{(Object.keys(plans) as PlanId[]).map(id=><div key={id} role="columnheader" data-plan={id} className={'plan-column '+(current===id?'is-current':'')}><b>{plans[id].name}</b><strong>{plans[id].price}</strong><span>{id==='free'?'The essentials':id==='plus'?'Recommended':'All access'}</span></div>)}</div>
   <div className="plan-compare-body">{rows.map(([label,...values])=><div className="plan-compare-row" role="row" key={label}><span role="rowheader">{label}</span>{values.map((value,i)=><span role="cell" data-plan={Object.keys(plans)[i]} className={(Object.keys(plans)[i]===current?'is-current ':'')+(value==='—'?'not-included':'')} key={i}>{value==='Included'?<Check aria-label="Included" size={16}/>:value}</span>)}</div>)}</div>
   <div className="plan-compare-actions" role="row"><span role="rowheader">Your plan</span>{(Object.keys(plans) as PlanId[]).map(id=><button key={id} data-plan={id} aria-label={'Choose '+plans[id].name+' plan'} aria-pressed={current===id} disabled={current===id} onClick={()=>choose(id)}>{current===id?<><Check size={12}/>Current</>:'Try '+plans[id].name}</button>)}</div>
  </div>
  <p className="plans-footnote">Flow: one natural-voice edition daily, then unlimited Basic voice. Lengths are estimates at 1×.</p>
  <p className="plans-demo-note">Demo plans · paid prices are placeholders. No payment is taken.</p>
  <button className="plans-done" onClick={onClose}>Done<ChevronRight size={16}/></button>
 </section></div>;
}
import './plan-comparison.css';
