import type {NewsLanguage} from './types';
export function deviceVoices(language:NewsLanguage){
 return (window.speechSynthesis?.getVoices()||[]).filter(voice=>voice.lang.toLowerCase().split(/[-_]/)[0]===language).sort((a,b)=>Number(/microsoft/i.test(b.name))-Number(/microsoft/i.test(a.name))||a.name.localeCompare(b.name));
}
export function voiceId(voice:SpeechSynthesisVoice){return voice.voiceURI||voice.name;}
export function chooseDevicePair(language:NewsLanguage,preferred:string[]=[]){
 const available=deviceVoices(language);
 const selected=preferred.map(id=>available.find(voice=>voiceId(voice)===id)).filter((v):v is SpeechSynthesisVoice=>!!v);
 const microsoft=available.filter(voice=>/microsoft/i.test(voice.name)&&!selected.includes(voice));
 const others=available.filter(voice=>!selected.includes(voice)&&!microsoft.includes(voice));
 const shuffle=(items:SpeechSynthesisVoice[])=>{for(let i=items.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[items[i],items[j]]=[items[j],items[i]];}return items;};
 return [...selected,...shuffle(microsoft),...shuffle(others)].slice(0,2);
}
