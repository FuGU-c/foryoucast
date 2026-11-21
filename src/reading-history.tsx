import {useEffect,useState} from 'react';
import {ArrowLeft,ArrowUp,ArrowDown,ChevronRight,History,LoaderCircle,Search,X} from 'lucide-react';
import type {ReadingHistory,Story} from './types';
import {filterSavedRecords,readSavedStoryCache,savedRecordsFromStories,writeSavedStoryCache} from './saved-stories';
import './library-history.css';

type HistoryTab='recent'|'saved';
type DisplayItem={story:Story;timestamp:string;meta:string;kind:'recent'|'saved';articleId?:string|null};

export function ReadingHistoryPage({profileId,revision,onOpen,onBack}:{profileId:string;revision:number;onOpen:(story:Story)=>void;onBack:()=>void}){
 const [tab,setTab]=useState<HistoryTab>('recent');
 const [query,setQuery]=useState('');
 const [period,setPeriod]=useState('all');
 const [feedback,setFeedback]=useState('all');
 const [result,setResult]=useState<ReadingHistory>({entries:[],total:0,matches:0});
 const [savedStories,setSavedStories]=useState(()=>{
  const records=filterSavedRecords(readSavedStoryCache(profileId),'','all');
  return {stories:records.map(record=>record.story),total:records.length};
 });
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState('');
 const [retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();
  const timer=setTimeout(()=>{
   setLoading(true);setError('');
   if(tab==='recent'){
    const params=new URLSearchParams({q:query,period,feedback,limit:'200'});
    fetch('/api/profiles/'+profileId+'/history?'+params,{signal:controller.signal})
     .then(async response=>{if(!response.ok)throw new Error('Your history could not load.');return response.json();})
     .then(setResult).catch(cause=>{if(cause.name!=='AbortError')setError(cause.message);})
     .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return;
   }
   const params=new URLSearchParams({q:query,period});
   const fallback=()=>{
    const records=filterSavedRecords(readSavedStoryCache(profileId),query,period);
    return {stories:records.map(record=>record.story),total:records.length};
   };
   fetch('/api/profiles/'+profileId+'/saved?'+params,{signal:controller.signal})
    .then(async response=>response.ok?response.json():null)
    .then(payload=>{
     if(controller.signal.aborted)return;
     if(!Array.isArray(payload?.stories)){setSavedStories(fallback());return;}
     const allRecords=savedRecordsFromStories(payload.stories);
     if(!query&&period==='all')writeSavedStoryCache(profileId,allRecords);
     const records=filterSavedRecords(allRecords,query,period);
     setSavedStories({stories:records.map(record=>record.story),total:payload.total??records.length});
    }).catch(()=>{if(!controller.signal.aborted)setSavedStories(fallback());})
    .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
  },query?150:0);
  return ()=>{clearTimeout(timer);controller.abort();};
 },[profileId,tab,query,period,feedback,revision,retry]);
 const day=(timestamp:string)=>new Date(timestamp).toLocaleDateString('en-CA',{timeZone:'Europe/Brussels'});
 const today=day(new Date().toISOString());
 const items:DisplayItem[]=tab==='recent'
  ?result.entries.map(entry=>({story:entry.story,timestamp:entry.last_viewed_at,meta:entry.story.sources[0]?.outlet||'Source',kind:'recent',articleId:entry.article_id}))
  :savedStories.stories.map(story=>({story,timestamp:story.saved_at||new Date().toISOString(),meta:story.sources[0]?.outlet||'Saved story',kind:'saved'}));
 const count=tab==='recent'?result.matches:savedStories.total;
 const clearFilters=()=>{setQuery('');setPeriod('all');setFeedback('all');};
 return <section className="reading-history-page">
  <button className="history-back" onClick={onBack}><ArrowLeft size={15}/>Back to your feed</button>
  <div className="history-heading"><div><span className="library-overline">{tab==='recent'?'YOUR READING TRAIL':'YOUR SAVED STORIES'}</span><h1>History<span>.</span></h1><p>{tab==='recent'?'A story worth coming back to? Find it here.':'Your saved stories, ready when you are.'}</p></div><span className="history-heading-icon"><History size={25}/></span></div>
  <div className="history-tabs" role="tablist" aria-label="History sections">
   <button type="button" role="tab" aria-selected={tab==='recent'} onClick={()=>setTab('recent')}>Recently viewed</button>
   <button type="button" role="tab" aria-selected={tab==='saved'} onClick={()=>setTab('saved')}>Saved</button>
  </div>
  <label className="history-search"><Search size={18}/><input type="search" aria-label={tab==='saved'?'Search saved stories':'Search reading history'} placeholder="Search stories, sources or topics…" value={query} onChange={event=>setQuery(event.target.value)}/>{query&&<button type="button" aria-label="Clear history search" onClick={()=>setQuery('')}><X size={16}/></button>}</label>
  <div className="history-filter-row"><div className="history-periods">{[['all','All time'],['today','Today'],['week','This week']].map(([id,label])=><button type="button" key={id} aria-pressed={period===id} onClick={()=>setPeriod(id)}>{label}</button>)}</div>
   {tab==='recent'&&<select aria-label="Filter history feedback" value={feedback} onChange={event=>setFeedback(event.target.value)}><option value="all">All feedback</option><option value="liked">Liked</option><option value="disliked">Liked less</option></select>}
  </div>
  <div className="history-result-count" aria-live="polite">{loading?<><LoaderCircle className="spin" size={12}/>{tab==='saved'?'Finding saved stories…':'Finding your stories…'}</>:<>{count} {count===1?'story':'stories'}{query?' found':tab==='saved'?' saved':' revisited'}</>}</div>
  {error?<div className="history-empty"><History size={26}/><h3>{error}</h3><button onClick={()=>setRetry(value=>value+1)}>Try again</button></div>:!loading&&!items.length?<div className="history-empty"><History size={30}/><h3>{count?'No stories match this search.':tab==='saved'?'Nothing saved yet.':'Your next read starts here.'}</h3><p>{count?'Try a different word or filter.':tab==='saved'?'Save a story in Discover and it will be waiting here.':'Open a story or spend a moment with it in Discover. It will appear here automatically.'}</p><button onClick={()=>{if(count||query||period!=='all'){clearFilters();}else onBack();}}>{count||query||period!=='all'?'Clear filters':'Explore stories'}<ChevronRight size={14}/></button></div>:<div className="history-story-list">{items.map((item,index)=>{
   const first=index===0||day(item.timestamp)!==day(items[index-1].timestamp);
   const stamp=day(item.timestamp);
   const image=item.story.sources.find(source=>source.image_url)?.image_url;
   const detail=item.kind==='recent'
    ?item.story.vote===1?<><ArrowUp size={12}/>Liked</>:item.story.vote===-1?<><ArrowDown size={12}/>Liked less</>:item.articleId?'Original article':'Story summary'
    :null;
   return <div key={item.story.id}>{first&&<h2 className="history-day-label">{stamp===today?'Today':new Date(item.timestamp).toLocaleDateString('en-GB',{day:'numeric',month:'long',timeZone:'Europe/Brussels'})}</h2>}
    <button type="button" className={'history-story '+(item.kind==='saved'?'history-story-saved':'')} onClick={()=>onOpen(item.story)}>
     <div className={'history-story-art '+item.story.art}>{image&&<img src={image} alt="" referrerPolicy="no-referrer" onError={event=>{event.currentTarget.style.display='none';}}/>}<span>{item.story.entities[0]?.slice(0,2)||'S'}</span></div>
     <div className="history-story-copy"><small>{item.meta} · {item.kind==='saved'?'Saved':'Viewed'} {new Date(item.timestamp).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Brussels'})}</small><h3 lang={item.story.title_language}>{item.story.title}</h3>
      {item.kind==='saved'?<><span className="history-story-summary">{item.story.summary}</span><span className="history-story-tags">{item.story.tags.slice(0,3).map(tag=><i key={tag}>{tag.replaceAll('-',' ')}</i>)}</span></>:<span className="history-story-kind">{detail}</span>}
     </div><ChevronRight size={16}/>
    </button></div>;
  })}</div>}
  <p className="history-privacy">{tab==='saved'?'Saved stories stay with this profile.':'Only this profile’s history. Your likes and dislikes still guide your briefing.'}</p>
 </section>;
}
