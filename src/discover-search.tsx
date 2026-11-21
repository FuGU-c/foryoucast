import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {ArrowRight,Check,ChevronDown,Clock3,Globe2,Search,Sparkles,X} from 'lucide-react';
import {languages} from './preferences';
import {TopicQuestion} from './topic-question';
import type {NewsLanguage,TagSuggestion,Topic} from './types';
import './discover-search.css';

type Props={
 section:'filters'|'suggestions';onClose:()=>void;
 topics:Topic[];query:string;setQuery:(query:string)=>void;
 selectedTopics:string[];toggleTopic:(id:string)=>void;clearTopics:()=>void;
 selectedLanguages:NewsLanguage[];availableLanguages:NewsLanguage[];
 toggleLanguage:(language:NewsLanguage)=>void;clearLanguages:()=>void;
 archive:boolean;toggleArchive:()=>void;resultCount:number;loading:boolean;
 suggestions:TagSuggestion[];onFollow:(tag:string)=>void;
};

export function DiscoverSearch(props:Props){
 const {section,onClose,topics,query,setQuery,selectedTopics,toggleTopic,clearTopics,
  selectedLanguages,availableLanguages,toggleLanguage,clearLanguages,archive,toggleArchive,
  resultCount,loading,suggestions,onFollow}=props;
 const [expanded,setExpanded]=useState(false);
 const [topicQuery,setTopicQuery]=useState('');
 const panel=useRef<HTMLElement>(null);
 const search=useRef<HTMLInputElement>(null);
 const primary=topics.filter(topic=>!topic.parent||selectedTopics.includes(topic.id));
 const visible=(expanded?topics:primary).filter(topic=>topic.label.toLowerCase().includes(topicQuery.toLowerCase()));
 const count=selectedTopics.length+selectedLanguages.length+Number(archive)+Number(!!query);

 useEffect(()=>{
  const before=document.activeElement as HTMLElement|null;
  if(section==='filters')search.current?.focus({preventScroll:true});
  else panel.current?.focus({preventScroll:true});
  return ()=>{if(before?.isConnected)before.focus({preventScroll:true});};
 },[section]);

 function reset(){setQuery('');clearTopics();clearLanguages();if(archive)toggleArchive();setTopicQuery('');}

 return createPortal(<div className="discover-search-backdrop" onClick={onClose}>
  <section ref={panel} className="discover-search-sheet" role="dialog" aria-modal="true" tabIndex={-1}
   aria-label={section==='filters'?'Discover filters':'Topics to follow'} onClick={event=>event.stopPropagation()}
   onKeyDown={event=>{
    if(event.key==='Escape'){event.stopPropagation();onClose();}
    if(event.key!=='Tab')return;
    const controls=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input,a[href]')];
    const first=controls[0],last=controls.at(-1);
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===panel.current)){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
   }}>
   <div className="search-sheet-handle" aria-hidden="true"/>
   <header className="search-sheet-heading">
    <div><span className="search-sheet-kicker">YOUR NEXT READ</span><h2>{section==='filters'?'Find your story.':'A little more you.'}</h2>
     <p>{section==='filters'?'Search the news. Follow your curiosity.':'Fresh interests from the latest coverage.'}</p></div>
    <button className="search-sheet-close" aria-label="Close Discover options" onClick={onClose}><X size={19}/></button>
   </header>
   <div className="search-sheet-content">
    {section==='filters'?<>
     <label className="discover-search-field"><Search size={20}/><input ref={search} type="search" aria-label="Search stories"
      placeholder="Headlines, companies, ideas…" value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')onClose();}}/>
      {query&&<button aria-label="Clear search" onClick={()=>{setQuery('');search.current?.focus();}}><X size={16}/></button>}
     </label>
     <fieldset className="search-topic-section"><legend>What are you curious about?<span>Choose a few, or explore everything.</span></legend>
      {expanded&&<label className="topic-finder"><Search size={15}/><input aria-label="Find a topic" placeholder="Find a topic" value={topicQuery} onChange={event=>setTopicQuery(event.target.value)}/></label>}
      <div className="search-topic-chips">{visible.map(topic=><button key={topic.id} aria-pressed={selectedTopics.includes(topic.id)} onClick={()=>toggleTopic(topic.id)}>
       <span className={'topic-chip-mark topic-color-'+(topic.parent||topic.id)} aria-hidden="true">{selectedTopics.includes(topic.id)?<Check size={11}/>:<i/>}</span>{topic.label}
      </button>)}</div>
      {!visible.length&&<p className="no-topics-found">No topics match “{topicQuery}”.</p>}
      {topics.length>primary.length&&<button className="show-all-search-topics" aria-expanded={expanded} onClick={()=>{setExpanded(value=>!value);setTopicQuery('');}}>
       {expanded?'Fewer topics':`More topics · ${topics.length-primary.length}`}<ChevronDown size={14}/>
      </button>}
     </fieldset>
     <fieldset className="search-language-section"><legend><Globe2 size={16}/>Article languages<span>Original reporting, in the languages you choose.</span></legend>
      <div className="search-language-cards">{availableLanguages.map(language=><button key={language} aria-pressed={selectedLanguages.includes(language)} onClick={()=>toggleLanguage(language)}>
       <span className="language-monogram">{language.toUpperCase()}</span><span>{languages[language]}</span><span className="language-check" aria-hidden="true">{selectedLanguages.includes(language)&&<Check size={12}/>}</span>
      </button>)}</div>
      <p className="search-selection-help">{selectedLanguages.length?`${selectedLanguages.length} selected`:'All your article languages'}</p>
     </fieldset>
     <label className="search-archive-option"><span className="search-archive-icon"><Clock3 size={19}/></span><span><b>Include older stories</b><small>A little more context from the archive.</small></span>
      <input type="checkbox" role="switch" aria-label="Include older stories" checked={archive} onChange={toggleArchive}/><span className="archive-switch" aria-hidden="true"/>
     </label>
    </>:<div className="search-suggested-topics"><div className="search-suggestions-icon"><Sparkles size={23}/></div>{suggestions.length?<TopicQuestion suggestions={suggestions} onFollow={onFollow}/>:<p>You’re all caught up on new topics.</p>}</div>}
   </div>
   {section==='filters'&&<footer className="search-sheet-footer"><button className="reset-search" disabled={!count} onClick={reset}>Reset</button>
    <button className="show-search-results" aria-label="Show stories" onClick={onClose}>Show stories<span aria-live="polite">{loading?'…':resultCount}</span><ArrowRight size={17}/></button>
   </footer>}
  </section>
 </div>,document.querySelector('.phone-frame .app')||document.body);
}
