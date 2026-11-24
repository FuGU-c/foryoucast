import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Check,Moon,Sun,X} from 'lucide-react';
import palettes from './theme-palettes.json';

export type ThemeId='signal'|'cobalt'|'edition'|'afterhours';
export type Appearance={theme:ThemeId;mode:'light'|'dark'};
const STORAGE_KEY='foryoucast-appearance';
export const themes=palettes;

export function readAppearance():Appearance{
 try{
  const saved=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');
  if(themes.some(theme=>theme.id===saved?.theme)&&(saved.mode==='light'||saved.mode==='dark'))return saved;
 }catch{/* A blocked or damaged browser store must not prevent opening the app. */}
 return {theme:'signal',mode:'light'};
}

export function applyAppearance(value:Appearance){
 const palette=themes.find(theme=>theme.id===value.theme)||themes[0];
 const root=document.documentElement;
 root.dataset.theme=palette.id;root.dataset.appearance=value.mode;
 root.style.colorScheme=value.mode;
 for(const [key,color] of Object.entries(palette[value.mode]))root.style.setProperty('--theme-'+key,color);
 document.querySelector('meta[name="theme-color"]')?.setAttribute('content',palette[value.mode].background);
}

export function useAppearance(){
 const [appearance,setAppearance]=useState<Appearance>(readAppearance);
 useLayoutEffect(()=>{
  applyAppearance(appearance);
  try{localStorage.setItem(STORAGE_KEY,JSON.stringify(appearance));}catch{/* Keep the current session usable without storage. */}
 },[appearance]);
 useEffect(()=>{
  const changed=(event:StorageEvent)=>{if(event.key===STORAGE_KEY)setAppearance(readAppearance());};
  window.addEventListener('storage',changed);return()=>window.removeEventListener('storage',changed);
 },[]);
 return {appearance,setAppearance};
}

export function AppearanceModal({value,onChange,onClose}:{value:Appearance;onChange:(value:Appearance)=>void;onClose:()=>void}){
 const sheet=useRef<HTMLElement>(null),close=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  const before=document.activeElement as HTMLElement|null;
  close.current?.focus();
  return()=>{if(before?.isConnected)before.focus();else document.querySelector<HTMLButtonElement>('.profile-button')?.focus();};
 },[]);
 function choose(index:number){const theme=themes[index];onChange({theme:theme.id as ThemeId,mode:theme.default as Appearance['mode']});}
 return <div className="overlay appearance-overlay" onClick={onClose}>
  <section className="appearance-sheet" role="dialog" aria-modal="true" aria-labelledby="appearance-title" aria-describedby="appearance-description" ref={sheet} onClick={event=>event.stopPropagation()} onKeyDown={event=>{
   if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onClose();}
   if(event.key==='Tab'){
    const controls=[...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled):not([tabindex="-1"])')];
    const first=controls[0],last=controls.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
   }
  }}>
   <header className="appearance-heading"><div><span className="settings-kicker">MAKE IT YOURS</span><h2 id="appearance-title">A different point of view.</h2></div><button ref={close} className="icon-button" aria-label="Close appearance" onClick={onClose}><X size={20}/></button></header>
   <p id="appearance-description">Four looks. Tap one to make it yours.</p>
   <div className="appearance-grid" role="radiogroup" aria-label="App theme" onKeyDown={event=>{
    const direction=['ArrowRight','ArrowDown'].includes(event.key)?1:['ArrowLeft','ArrowUp'].includes(event.key)?-1:0;
    if(direction||event.key==='Home'||event.key==='End'){
     event.preventDefault();const current=themes.findIndex(theme=>theme.id===value.theme);
     const next=event.key==='Home'?0:event.key==='End'?themes.length-1:(current+direction+themes.length)%themes.length;
     choose(next);event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
    }
   }}>
    {themes.map((theme,index)=><button key={theme.id} type="button" role="radio" aria-checked={value.theme===theme.id} aria-label={theme.name+' theme'} tabIndex={value.theme===theme.id?0:-1} className="appearance-card" onClick={()=>choose(index)}>
     <span className="appearance-preview"><img src={'/theme-previews/'+theme.id+'.webp'} alt={'ForYouCast screen in '+theme.name+' colors'} width="425" height="279" draggable={false}/><span className="appearance-check" aria-hidden="true">{value.theme===theme.id&&<Check size={13}/>}</span></span>
     <span className="appearance-card-info"><b>{theme.name}</b><small>{['Charcoal & electric lime','Cobalt & clean white','Paper & vermilion','Deep ink & orchid'][index]}</small></span>
    </button>)}
   </div>
   <div className="appearance-mode"><span>Appearance</span><div role="group" aria-label="Color mode"><button type="button" aria-pressed={value.mode==='light'} onClick={()=>onChange({...value,mode:'light'})}><Sun size={14}/>Light</button><button type="button" aria-pressed={value.mode==='dark'} onClick={()=>onChange({...value,mode:'dark'})}><Moon size={14}/>Dark</button></div></div>
   <p className="appearance-saved" role="status">Saved automatically on this device.</p>
   <button type="button" className="primary-button appearance-done" onClick={onClose}>Looks good<Check size={15}/></button>
  </section>
 </div>;
}
