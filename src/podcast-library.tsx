import {useState,type ReactNode} from 'react';
import {ArrowDownToLine,ArrowRight,AudioLines,BookOpen,CalendarDays,Check,FileText,Headphones,LoaderCircle,MoreHorizontal,Play,Plus,Trash2,X} from 'lucide-react';
import type {DailyUsage,Edition,Profile,Source} from './types';
import {languages} from './preferences';
import {EditionCalendar} from './edition-calendar';
import {editionDay,localToday,matchesEditionPeriod,periodLabels,type EditionPeriod} from './edition-dates';
import {latestPlayableBriefing} from './briefing-selection';
import './library-history.css';

const labelDate=(day:string)=>new Date(day+'T12:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'long',timeZone:'Europe/Brussels'});
type Props={usage?:DailyUsage;playbackControls:ReactNode;profile:Profile;editions:Edition[];dates:string[];busy:boolean;createBusy?:boolean;onCreate:(day?:string)=>void;onPlay:(edition:Edition)=>void;onSummary:(edition:Edition)=>void;onScript:(edition:Edition)=>void;onRemoveAudio:(edition:Edition)=>Promise<void>};

export function PodcastLibrary({usage,playbackControls,profile,editions,dates,busy,createBusy=false,onCreate,onPlay,onSummary,onScript,onRemoveAudio}:Props){
 const [period,setPeriod]=useState<EditionPeriod>('all');
 const [selected,setSelected]=useState('');
 const [menu,setMenu]=useState('');
 const [removing,setRemoving]=useState('');
 const today=localToday();
 const days=[...new Set([today,...editions.map(editionDay)])].sort().reverse();
 const shown=editions.filter(edition=>matchesEditionPeriod(editionDay(edition),period,selected,today));
 const canCreate=dates.length>0&&usage?.can_create!==false;
 const counts:Record<string,number>={};
 for(const edition of editions){const day=editionDay(edition);counts[day]=(counts[day]||0)+1;}
 const chooseDate=(day:string)=>{setSelected(day);setPeriod('custom');};
 function create(){if(canCreate){setPeriod('today');setSelected('');onCreate();}}
 const emptyTitle=period==='all'?'Your first briefing is waiting.':period==='custom'?'No editions on '+labelDate(selected)+'.':period==='today'?'No editions for today yet.':period==='week'?'No editions this week yet.':'No editions this month yet.';
 const latest=latestPlayableBriefing(editions,profile.id);
 return <section className="podcast-library">
  <div className="podcast-library-heading"><div><span className="library-overline">A LITTLE CLARITY, KEPT</span><h1>Podcasts<span>.</span></h1><p>Your days, in perspective.</p></div><button className="library-create" aria-label="Create a new briefing" disabled={busy||createBusy||!canCreate} onClick={create}>{busy||createBusy?<LoaderCircle size={17} className="spin"/>:<Plus size={17}/>}New briefing</button></div>
  <div className="library-listen-card"><span className="library-listen-icon"><Headphones size={28}/></span><div><span className="library-overline">{period==='all'?'YOUR DAILY RITUAL':period==='custom'?labelDate(selected).toUpperCase():periodLabels[period].toUpperCase()}</span><h2>A good day starts<br/>with a little perspective.</h2><p>{languages[profile.language]} · ~{profile.duration} min</p></div><button aria-label="Play latest briefing" disabled={busy||(!latest&&(!canCreate||createBusy))} onClick={()=>latest?onPlay(latest):create()}>{latest?<Play size={20} fill="currentColor"/>:<Plus size={22}/>}</button></div>
  {usage&&<p className="podcast-allowance">{profile.plan==='free'||!profile.plan?(usage.can_create?'Your daily edition is waiting · Basic voice':'Today’s edition is ready. Replay it anytime.'):profile.plan==='plus'?(usage.natural_remaining?'1 natural-voice edition available today · unlimited Basic voice':'Natural-voice edition used today · unlimited Basic voice continues'):'Unlimited editions · Natural or Basic voice'}</p>}
  {playbackControls}
  <div className="library-section-heading"><h2>Your editions<span>{shown.length}</span></h2><EditionCalendar days={days} selected={period==='custom'?selected:''} counts={counts} onSelect={chooseDate}/></div>
  <div className="edition-date-tabs" aria-label="Briefing dates">{(['today','week','month','all'] as EditionPeriod[]).map(value=><button key={value} aria-pressed={period===value} onClick={()=>setPeriod(value)}>{periodLabels[value]}</button>)}</div>
  {period==='custom'&&<button className="edition-custom-date" aria-label="Clear selected date" onClick={()=>setPeriod('all')}><CalendarDays size={13}/>{labelDate(selected)}<X size={12}/></button>}
  <p className="library-sample-note">{dates[0]?`News coverage through ${labelDate(dates[0])}. Editions are saved by creation date.`:'The calendar shows when your editions were created.'}</p>
  {!shown.length?<div className="library-empty"><CalendarDays size={28}/><h3>{emptyTitle}</h3><p>{period==='custom'?'No editions were created on this date. New briefings are saved under today.':'Create a briefing for today using your latest available news.'}</p><button disabled={busy||createBusy||!canCreate} onClick={create}>{busy||createBusy?'Preparing…':'Create today’s briefing'}<ArrowRight size={15}/></button></div>:<div className="saved-edition-list">{shown.map(edition=>{
   const day=editionDay(edition),summaryOnly=edition.audio_mode==='summary-only';
   const versions=editions.filter(other=>editionDay(other)===day).slice().reverse();
   const version=versions.findIndex(other=>other.id===edition.id)+1;
   return <article key={edition.id} className={'saved-edition '+(summaryOnly?'summary-kept':'')}>
    <div className="saved-edition-main"><button className={'saved-edition-art '+(summaryOnly?'sage':'coral')} aria-label={summaryOnly?'Read saved summary':'Play this edition'} onClick={()=>summaryOnly?onSummary(edition):onPlay(edition)}>{summaryOnly?<FileText size={28}/>:<AudioLines size={30}/>}</button>
     <div><span className="saved-edition-day">{labelDate(day)}<span> · Edition {version}</span></span><h3>{edition.title}</h3><p>{edition.chapters.length} stories · ~{Math.max(1,edition.episode_audio?Math.round(edition.episode_audio.duration_seconds/60):Math.ceil(edition.estimated_seconds/60))} min · {languages[edition.language]}</p>{edition.news_date&&edition.news_date!==day&&<span className="edition-news-date">News through {labelDate(edition.news_date)}</span>}<small>{summaryOnly?<><Check size={10}/>Summary kept</>:edition.episode_audio?`${edition.demo_sample?'Demo sample · ':''}${edition.tts_provider==='elevenlabs'?'Natural voices':'Basic voices'} · audio ready`:edition.audio_mode==='elevenlabs'?'Natural voice narration':'Basic voice · no audio file stored'}</small></div>
     <button className="edition-menu-button" aria-label="Edition options" aria-expanded={menu===edition.id} onClick={()=>setMenu(value=>value===edition.id?'':edition.id)}><MoreHorizontal size={20}/></button>
    </div>
    {menu===edition.id&&<div className="edition-options-menu"><button onClick={()=>{setMenu('');onScript(edition);}}><FileText size={16}/><span>Script & sources</span><ArrowRight size={14}/></button>{!summaryOnly&&<button disabled={removing===edition.id} onClick={async()=>{setRemoving(edition.id);try{await onRemoveAudio(edition);setMenu('');}finally{setRemoving('');}}}>{removing===edition.id?<LoaderCircle className="spin" size={16}/>:<Trash2 size={16}/>}<span><b>Keep summary only</b><small>Remove audio, keep the words and sources.</small></span></button>}</div>}
    <div className="saved-edition-actions"><button onClick={()=>onSummary(edition)}><BookOpen size={15}/>Brief summary</button><span>{new Date(edition.created_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Brussels'})} created</span>{!summaryOnly&&<button className="saved-edition-play" aria-label="Play edition" onClick={()=>onPlay(edition)}><Play size={17}/></button>}</div>
   </article>;
  })}</div>}
 </section>;
}

export function BriefSummary({edition,onClose,onSource}:{edition:Edition;onClose:()=>void;onSource:(source:Source,sources:Source[])=>void}){
 return <div className="overlay brief-summary-overlay" onClick={onClose}><section className="brief-summary-sheet" role="dialog" aria-modal="true" aria-label="Brief summary" onClick={event=>event.stopPropagation()}>
  <header><div><span className="library-overline">{labelDate(editionDay(edition)).toUpperCase()}</span><h2>Your brief, kept.</h2></div><button className="icon-button" aria-label="Close brief summary" onClick={onClose}><X size={20}/></button></header>
  <div className="brief-summary-intro"><span><FileText size={15}/>{edition.chapters.length} stories · {languages[edition.language]}</span><a href={'/api/editions/'+edition.id+'/export?kind=report'}><ArrowDownToLine size={14}/>Download summary</a></div>
  {edition.news_date&&<p className="brief-summary-coverage">News coverage through {labelDate(edition.news_date)} · Created {labelDate(editionDay(edition))}</p>}
  {edition.audio_mode==='summary-only'&&<p className="summary-kept-note"><Check size={14}/>Audio removed. Your summary and sources are here to stay.</p>}
  <div className="brief-summary-chapters">{edition.chapters.map((chapter,index)=><section key={chapter.story_id}><span>{String(index+1).padStart(2,'0')}</span><div><h3>{chapter.title}</h3>{chapter.translated_by_ai&&<span className="ai-translation-label">Translated by AI</span>}<p>{chapter.summary||chapter.text}</p><div className="summary-source-links">{chapter.sources.filter(source=>chapter.claim_source_ids.includes(source.article_id)).map(source=><button key={source.article_id} onClick={()=>onSource(source,chapter.sources)}><BookOpen size={12}/>{source.outlet}<ArrowRight size={12}/></button>)}</div></div></section>)}</div>
 </section></div>;
}
