import {ThumbsDown,ThumbsUp} from 'lucide-react';
import {useEffect,useRef,useState,type CSSProperties} from 'react';
import './vote-button.css';

const sparks=Array.from({length:7},(_,index)=>{
 const angle=(index*360/7-100)*Math.PI/180;
 return {'--spark-x':`${Math.cos(angle)*26}px`,'--spark-y':`${Math.sin(angle)*26}px`,'--spark-delay':`${index%3*14}ms`} as CSSProperties;
});

export function VoteButton({value,active,label,onVote,size=17}:{value:1|-1;active:boolean;label:string;onVote:()=>void;size?:number}){
 const Icon=value===1?ThumbsUp:ThumbsDown;
 const [burst,setBurst]=useState(0);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
 return <button className={'vote-button '+(value===1?'vote-up':'vote-down')+(active?(value===1?' voted-up':' voted-down'):'')}
  aria-label={label} aria-pressed={active} onClick={event=>{
   event.stopPropagation();
   const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
   const icon=event.currentTarget.querySelector('svg');
   if(!active&&!reduced){
    if(timer.current)clearTimeout(timer.current);
    setBurst(current=>current+1);
    if(icon?.animate){
     icon.getAnimations?.().forEach(animation=>animation.cancel());
     const tilt=value===1?-18:16;
     icon.animate([{transform:'scale(1) rotate(0deg)'},{transform:`translateY(${value===1?-3:3}px) scale(1.24) rotate(${tilt}deg)`,offset:.35},{transform:'scale(.96) rotate(4deg)',offset:.75},{transform:'scale(1) rotate(0deg)'}],{duration:480,easing:'cubic-bezier(.2,.8,.25,1)'});
    }
    timer.current=setTimeout(()=>{setBurst(0);timer.current=null;},650);
   }
   onVote();
  }}><Icon size={size} fill={active?'currentColor':'none'}/>{burst>0&&<span key={burst} className="vote-burst" aria-hidden="true">{sparks.map((style,index)=><i key={index} className="vote-spark" style={style}/>)}</span>}</button>;
}
