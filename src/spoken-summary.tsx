import {useEffect,useRef,useState} from 'react';
import {Headphones,Pause,Play} from 'lucide-react';
import type {NewsLanguage,Story} from './types';
import {CENSOR_SPEECH} from './censor';

type Props={story:Story;language:NewsLanguage;available:boolean;onPlans:()=>void};
const languages={en:'en-GB',nl:'nl-NL',de:'de-DE'};
const sourceLabels={en:'Source',nl:'Bron',de:'Quelle'};
const announceStart=(usesDevice:boolean)=>window.dispatchEvent(new CustomEvent('foryoucast:audio-start',{detail:{source:'summary',usesDevice}}));

export function SpokenSummary({story,language,available,onPlans}:Props){
 const [playing,setPlaying]=useState(false),[started,setStarted]=useState(false),[status,setStatus]=useState('');
 const audio=useRef<HTMLAudioElement|null>(null),speech=useRef<SpeechSynthesisUtterance|null>(null);
 const intent=useRef(false),request=useRef(0),speechActive=useRef(false);
 const file=story.spoken_summary?.language===(story.summary_language||language)?story.spoken_summary:undefined;
 function pause(cancelSpeech=false){
  request.current++;intent.current=false;setPlaying(false);
  audio.current?.pause();
  if(speechActive.current&&window.speechSynthesis){
   if(cancelSpeech){window.speechSynthesis.cancel();speech.current=null;speechActive.current=false;}
   else window.speechSynthesis.pause();
  }
  setStatus('Summary paused.');
 }
 useEffect(()=>{
  const onOther=(event:Event)=>{if((event as CustomEvent<{source:string}>).detail?.source==='podcast'&&(intent.current||speechActive.current))pause(true);};
  window.addEventListener('foryoucast:audio-start',onOther);
  return ()=>{request.current++;intent.current=false;audio.current?.pause();audio.current=null;if(speechActive.current)window.speechSynthesis?.cancel();speechActive.current=false;window.removeEventListener('foryoucast:audio-start',onOther);};
 },[]);
 useEffect(()=>{if(!available&&(intent.current||speechActive.current))pause(true);},[available]);
 function play(){
  if(!available){onPlans();return;}
  if(intent.current){pause();return;}
  announceStart(!file);intent.current=true;setPlaying(true);setStarted(true);setStatus('Playing summary.');
  const token=++request.current;
  if(file){
   const element=audio.current||new Audio(file.url);audio.current=element;
   element.onended=()=>{if(audio.current!==element||!intent.current)return;intent.current=false;setPlaying(false);setStarted(false);setStatus('Summary finished.');};
   element.onerror=()=>{if(audio.current!==element)return;request.current++;intent.current=false;setPlaying(false);setStatus('Summary audio could not load.');};
   try{void element.play().then(()=>{if(audio.current!==element||!intent.current)element.pause();}).catch(()=>{if(token!==request.current||audio.current!==element||!intent.current)return;intent.current=false;setPlaying(false);setStatus('Summary audio could not play. Try again.');});}
   catch{if(token===request.current){intent.current=false;setPlaying(false);setStatus('Summary audio could not play. Try again.');}}
   return;
  }
  const synth=window.speechSynthesis;
  if(!synth||!('SpeechSynthesisUtterance' in window)){intent.current=false;setPlaying(false);setStatus('Device voice is unavailable in this browser.');return;}
  if(speech.current&&speechActive.current&&synth.paused){synth.resume();return;}
  synth.cancel();synth.resume();
  const voiceLanguage=story.summary_language||language,source=story.sources.find(item=>story.claim_source_ids.includes(item.article_id))||story.sources[0];
  const utterance=new SpeechSynthesisUtterance(CENSOR_SPEECH);
  utterance.lang=languages[voiceLanguage];speech.current=utterance;speechActive.current=true;
  utterance.onend=()=>{if(speech.current!==utterance||!intent.current)return;speech.current=null;speechActive.current=false;intent.current=false;setPlaying(false);setStarted(false);setStatus('Summary finished.');};
  utterance.onerror=event=>{if(speech.current!==utterance||!intent.current||event.error==='interrupted'||event.error==='canceled')return;speech.current=null;speechActive.current=false;intent.current=false;setPlaying(false);setStatus('Device voice is unavailable.');};
  synth.speak(utterance);
 }
 return <div style={{margin:'12px 0 16px'}}>
  <button type="button" className="quiet-button" onClick={play} aria-label={playing?'Pause summary':started?'Resume summary':'Listen to summary'}>{playing?<Pause size={15}/>:available?<Play size={15}/>:<Headphones size={15}/>} {playing?'Pause summary':started?'Resume summary':'Listen to summary'}</button>
  <span className="subtle" style={{display:'block',marginTop:5}}>{!available?'Available on paid plans':file?'Spoken summary':'Device voice preview'}</span>
  <span role="status" aria-live="polite" className="subtle" style={{display:'block'}}>{status}</span>
 </div>;
}
