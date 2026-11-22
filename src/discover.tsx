import {createContext,useContext,useEffect,useLayoutEffect,useRef,useState, type PointerEvent, type ReactNode} from 'react';
import {Bookmark,BookOpen, ChevronDown, ChevronUp, Search} from 'lucide-react';
import {languages} from './preferences';
import {DiscoverSearch} from './discover-search';
import {SwipeNavigation} from './swipe-navigation';
import {VoteButton} from './vote-button';
import type {NewsLanguage, Story, TagSuggestion, Topic} from './types';
import {readSavedStoryCache,savedRecordsFromStories,writeSavedStoryCache,type SavedStoryRecord} from './saved-stories';
import './discover-save.css';
import './reels-track.css';
import {useStableStoryDeck} from './stable-story-deck';

type DiscoverProps = {
 profileId:string;
 preferenceScope?:string;
 searchOpen:boolean;onSearchOpened:()=>void;
 stories:Story[]; topics:Topic[]; query:string; setQuery:(query:string)=>void;
 selectedTopics:string[]; toggleTopic:(id:string)=>void; clearTopics:()=>void;
 selectedLanguages:NewsLanguage[]; availableLanguages:NewsLanguage[];
 toggleLanguage:(language:NewsLanguage)=>void; clearLanguages:()=>void;
 archive:boolean; toggleArchive:()=>void; hasMore:boolean; onMore:()=>void; loading:boolean;
 suggestions:TagSuggestion[]; onFollow:(tag:string)=>void;
 onOpen:(story:Story)=>void; onVote:(story:Story,value:number)=>void;
 onView:(story:Story)=>void;
 art:(story:Story)=>ReactNode;
};

type SavedStoryContextValue={profileId:string;records:SavedStoryRecord[];toggle:(story:Story)=>void};
const SavedStoryContext=createContext<SavedStoryContextValue|null>(null);

function SavedStoryProvider({profileId,children}:{profileId:string;children:ReactNode}){
 const [state,setState]=useState(()=>({profileId,records:readSavedStoryCache(profileId)}));
 const stateRef=useRef(state);stateRef.current=state;
 const revision=useRef(0);
 const pending=useRef(new Map<string,Promise<void>>());
 useEffect(()=>{
  const controller=new AbortController();
  const initialRevision=revision.current;
  fetch(`/api/profiles/${encodeURIComponent(profileId)}/saved?q=&period=all`,{signal:controller.signal})
   .then(async response=>response.ok?response.json():null)
   .then(payload=>{
    if(controller.signal.aborted||revision.current!==initialRevision||!Array.isArray(payload?.stories))return;
    const records=savedRecordsFromStories(payload.stories);
    writeSavedStoryCache(profileId,records);
    const next={profileId,records};stateRef.current=next;setState(next);
   }).catch(()=>{});
  return ()=>controller.abort();
 },[profileId]);
 function toggle(story:Story){
  const current=stateRef.current.profileId===profileId?stateRef.current.records:readSavedStoryCache(profileId);
  const saved=current.some(record=>record.story.id===story.id);
  const savedAt=new Date().toISOString();
  const records=saved?current.filter(record=>record.story.id!==story.id):[
   {story:{...story,saved:true,saved_at:savedAt},saved_at:savedAt},
   ...current,
  ];
  const next={profileId,records};
  revision.current++;stateRef.current=next;setState(next);writeSavedStoryCache(profileId,records);
  const url=`/api/profiles/${encodeURIComponent(profileId)}/saved/${encodeURIComponent(story.id)}`;
  const previous=pending.current.get(story.id)||Promise.resolve();
  const operation=previous.catch(()=>{}).then(async()=>{
   const response=await fetch(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({saved:!saved})});
   if(!response.ok)throw new Error('Saved story could not sync.');
  });
  pending.current.set(story.id,operation);
  void operation.catch(()=>{}).finally(()=>{if(pending.current.get(story.id)===operation)pending.current.delete(story.id);});
 }
 const records=state.profileId===profileId?state.records:readSavedStoryCache(profileId);
 return <SavedStoryContext.Provider value={{profileId,records,toggle}}>{children}</SavedStoryContext.Provider>;
}

function SavedReelButton({profileId,story}:{profileId:string;story:Story}){
 const savedStories=useContext(SavedStoryContext);
 const saved=!!savedStories&&savedStories.profileId===profileId&&savedStories.records.some(record=>record.story.id===story.id);
 return <button type="button" className="reel-save-button" aria-label={saved?'Remove from saved stories':'Save story'} aria-pressed={saved} onClick={event=>{event.stopPropagation();savedStories?.toggle(story);}}>
  <Bookmark size={19} fill={saved?'currentColor':'none'}/>
  <small aria-hidden="true">{saved?'Saved':'Save'}</small>
 </button>;
}

function ReelPicture({story,art}:{story:Story;art:(story:Story)=>ReactNode}){
 return <div className="reel-picture" aria-hidden="true">{art(story)}</div>;
}

export function Discover(props:DiscoverProps){
 const {topics,query,setQuery,selectedTopics,toggleTopic,clearTopics,selectedLanguages,availableLanguages,
  toggleLanguage,clearLanguages,archive,toggleArchive,hasMore,onMore,loading,suggestions,onFollow,onOpen,onVote,art}=props;
 const filterKey=JSON.stringify([props.profileId,props.preferenceScope,query,selectedTopics,selectedLanguages,archive]);
 const stories=useStableStoryDeck(props.stories,filterKey);
 const [position,setPosition]=useState({id:'',index:0,filterKey});
 const track=useRef<HTMLDivElement>(null);
 const scrollTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const [filters,setFilters]=useState(false);
 const [section,setSection]=useState<'filters'|'suggestions'>('filters');
 const deck=useRef<HTMLDivElement>(null);
 const anchor=position.filterKey===filterKey?stories.findIndex(story=>story.id===position.id):-1;
 const currentIndex=anchor>=0?anchor:position.filterKey===filterKey?Math.min(position.index,Math.max(0,stories.length-1)):0;
 const current=stories[currentIndex];
 const wheel=useRef(new SwipeNavigation());
 const pointer=useRef<{id:number;y:number;x:number}|null>(null);
 const blockClick=useRef(0);
 const viewed=useRef(props.onView);
 viewed.current=props.onView;

 useEffect(()=>{
  if(!current)return;
  const timer=setTimeout(()=>{if(document.visibilityState==='visible')viewed.current(current);},1200);
  return ()=>clearTimeout(timer);
 },[current?.id]);

 useEffect(()=>{if(props.searchOpen){setSection('filters');setFilters(true);props.onSearchOpened();}},[props.searchOpen]);

 useLayoutEffect(()=>{setPosition({id:stories[0]?.id||'',index:0,filterKey});track.current?.scrollTo?.({top:0,behavior:'instant' as ScrollBehavior});wheel.current.reset();blockClick.current=0;},[filterKey]);
 useLayoutEffect(()=>{
  if(current&&position.id!==current.id)setPosition({id:current.id,index:currentIndex,filterKey});
 },[stories]);

 useEffect(()=>()=>{if(scrollTimer.current)clearTimeout(scrollTimer.current);},[]);
 const visibleIndex=useRef(currentIndex);visibleIndex.current=currentIndex;
 useLayoutEffect(()=>{
  const node=track.current;if(!node||typeof ResizeObserver==='undefined')return;
  let height=node.clientHeight;
  const observer=new ResizeObserver(()=>{
   if(node.clientHeight===height)return;
   height=node.clientHeight;node.scrollTop=visibleIndex.current*height;
  });
  observer.observe(node);return()=>observer.disconnect();
 },[!!current]);
 function move(delta:number){
  const next=Math.max(0,currentIndex+delta);
  if(next>=stories.length){if(delta>0&&hasMore&&!loading)onMore();return;}
  if(next===currentIndex)return;
  setPosition({id:stories[next].id,index:next,filterKey});
  const node=track.current;
  if(node){const top=next*node.clientHeight;if(node.scrollTo)node.scrollTo({top,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant' as ScrollBehavior:'smooth'});else node.scrollTop=top;}
 }
 const moveRef=useRef(move);
 moveRef.current=move;
 useEffect(()=>{
  const node=deck.current;
  if(!node)return;
  function onWheel(event:WheelEvent){
   if(event.ctrlKey)return;
   event.preventDefault();
   const unit=event.deltaMode===1?16:event.deltaMode===2?node!.clientHeight:1;
   const direction=wheel.current.wheel(event.deltaX*unit,event.deltaY*unit,performance.now());
   if(direction)moveRef.current(direction);
  }
  node.addEventListener('wheel',onWheel,{passive:false});
  return ()=>node.removeEventListener('wheel',onWheel);
 },[]);

 function pointerDown(event:PointerEvent<HTMLDivElement>){
  const button=(event.target as Element).closest('button');
  if(event.pointerType!=='mouse'||!event.isPrimary||event.button!==0||(button&&!button.classList.contains('reel-hit')))return;
  event.currentTarget.focus({preventScroll:true});
  
  pointer.current={id:event.pointerId,y:event.clientY,x:event.clientX};
 }
 function pointerUp(event:PointerEvent<HTMLDivElement>){
  const start=pointer.current;
  pointer.current=null;
  if(!start||start.id!==event.pointerId)return;
  const dy=event.clientY-start.y;
  const dx=event.clientX-start.x;
  const delta=Math.abs(dy)>=Math.abs(dx)?dy:dx;
  if(Math.abs(delta)<32)return;
  blockClick.current=performance.now()+280;
  move(delta<0?1:-1);
 }
 function pointerMove(event:PointerEvent<HTMLDivElement>){
  const start=pointer.current;
  if(!start||start.id!==event.pointerId)return;
  const dy=event.clientY-start.y;
  const dx=event.clientX-start.x;
  const delta=Math.abs(dy)>=Math.abs(dx)?dy:dx;
  if(Math.abs(delta)>8){
   blockClick.current=performance.now()+280;
   if(!event.currentTarget.hasPointerCapture?.(event.pointerId))event.currentTarget.setPointerCapture?.(event.pointerId);
  }
 }
 const tagsFor=(item:Story)=>[...new Set([...item.tags.filter(id=>selectedTopics.includes(id)),item.primary_topic||item.tags[0],...item.tags])].slice(0,2);
 const label=(id:string)=>topics.find(topic=>topic.id===id)?.label||id;
 const renderPage=(item:Story,index:number)=><article className="reel-card reel-card-full">
    <ReelPicture key={item.id} story={item} art={art}/>
    <div className="reel-shade"/>
    <div className="reel-count" aria-live="polite">{index+1} / {stories.length}</div>
    <button className="reel-hit" aria-label={'Read '+item.title} onClick={()=>{if(performance.now()>blockClick.current)onOpen(item);}}/>
    <div className="reel-copy">
     <div className="reel-labels"><span>Publisher ████████</span>{item.title_language&&<span>{languages[item.title_language]}</span>}</div>
     {item.ai_translated&&<span className="ai-translation-label">AI-translated summary</span>}<h2 lang={item.title_language}>{item.title}</h2>
     <div className="reel-labels reel-story-tags">{tagsFor(item).filter(Boolean).map(id=><span key={id}>{label(id)}</span>)}</div>
    </div>
    <div className="reel-actions">
     <div className="reel-vote-pair" role="group" aria-label="Tune your recommendations">
     <VoteButton value={1} active={item.vote===1} label="More like this" size={20} onVote={()=>onVote(item,1)}/>
     <VoteButton value={-1} active={item.vote===-1} label="Less like this" size={20} onVote={()=>onVote(item,-1)}/>
     </div>
     <SavedReelButton profileId={props.profileId} story={item}/>
     <button className="reel-read-button" aria-label="Read story and sources" onClick={()=>onOpen(item)}><BookOpen size={21}/><small aria-hidden="true">Read</small></button>
    </div>
   </article>;
  return <SavedStoryProvider key={props.profileId} profileId={props.profileId}><section className="discover-reels" aria-label="Discover">
  <div ref={deck} className="reel-deck" data-swipe="one-story" tabIndex={0} aria-label="Story deck. Swipe or use the arrow keys."
   onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={()=>{pointer.current=null;}}
   onKeyDown={event=>{if(event.target!==event.currentTarget)return;if(['ArrowDown','ArrowUp','PageDown','PageUp'].includes(event.key)){event.preventDefault();move(['ArrowDown','PageDown'].includes(event.key)?1:-1);}}}>
   <h1 className="discover-overlay-title">For you<span/></h1>
   {current?<div ref={track} className="reel-scroll-track" onScroll={()=>{
    if(scrollTimer.current)clearTimeout(scrollTimer.current);
    scrollTimer.current=setTimeout(()=>{
     const node=track.current;if(!node||!node.clientHeight)return;
     const index=Math.min(stories.length-1,Math.max(0,Math.round(node.scrollTop/node.clientHeight)));
     if(stories[index])setPosition({id:stories[index].id,index,filterKey});
    },100);
   }}>{stories.map((item,index)=><div key={item.id} className="reel-slide" aria-hidden={index!==currentIndex} inert={index!==currentIndex}>{renderPage(item,index)}</div>)}</div>:<div className="empty-state"><Search size={22}/><h3>{loading?'Looking for stories…':'No matching stories'}</h3>{!loading&&<button onClick={()=>{setQuery('');clearTopics();clearLanguages();}}>Clear filters</button>}</div>}

  </div>
  <div className="reel-bottom-bar">
   <button className="reel-prompts" onClick={()=>{setSection('suggestions');setFilters(true);}}>Topics to follow</button>
   <span>{current?'Swipe up to turn the page':''}</span>
   <div><button aria-label="Previous story" disabled={currentIndex===0} onClick={()=>move(-1)}><ChevronUp size={16}/></button><button aria-label="Next story" disabled={!current||currentIndex===stories.length-1&&!hasMore} onClick={()=>move(1)}><ChevronDown size={16}/></button></div>
  </div>
  {filters&&<DiscoverSearch section={section} onClose={()=>setFilters(false)}
   topics={topics} query={query} setQuery={setQuery} selectedTopics={selectedTopics} toggleTopic={toggleTopic} clearTopics={clearTopics}
   selectedLanguages={selectedLanguages} availableLanguages={availableLanguages} toggleLanguage={toggleLanguage} clearLanguages={clearLanguages}
   archive={archive} toggleArchive={toggleArchive} resultCount={stories.length} loading={loading} suggestions={suggestions} onFollow={onFollow}/>}

 </section></SavedStoryProvider>;
}
