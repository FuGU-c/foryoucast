import React, {useEffect,useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowDown,ArrowUp,ArrowLeft,ArrowRight,AudioLines,BookOpen,Check,CheckCheck,ChevronDown,ChevronRight,Clock3,Compass,ExternalLink,FileText,Globe2,Headphones,History,Layers3,LoaderCircle,LogIn,MoreHorizontal,Pause,Play,Plus,Palette,Radio,RefreshCw,Search,Settings2,ShieldCheck,SkipBack,SkipForward,SlidersHorizontal,Sparkles,Sun,Volume2,X,Zap,Wifi,Signal,BatteryFull} from 'lucide-react';
import type {Bootstrap,Chapter,CloudJob,Edition,Feed,NewsLanguage,Profile,Source,Story,Topic} from './types';
import {PreferencesModal} from './preferences';
import {SourceReader, type Reading} from './reader';
import {StoryMotion} from './story-motion';
import {Discover} from './discover';
import {preferenceKey,previewStories,updateTag,type ProfileChange} from './live-preferences';
import {usePreferenceSync} from './preference-sync';
import {useVoteSync} from './vote-sync';
import {VoteButton} from './vote-button';
import {ReadingHistoryPage} from './reading-history';
import {PodcastLibrary,BriefSummary} from './podcast-library';
import {PlaybackOptions,playbackSpeeds} from './playback-options';
import {useSleepTimer} from './sleep-timer';
import {SubscriptionModal} from './subscription';
import {chooseDevicePair} from './voices';
import {normalizePlan,planFor} from './plans';
import {clearEditedLearning,mergeLearningSnapshot} from './feedback-learning';
import {chapterAt,chapterEnd,chapterStart,episodeDuration} from './episode-timeline';
import {SpokenSummary} from './spoken-summary';
import {GenerationStatus} from './generation-status';
import {latestPlayableBriefing} from './briefing-selection';
import {Avatar} from './profile-avatar';
import {StoryImage} from './story-image';
import {WaveformSeek} from './waveform-seek';
import {AppearanceModal,applyAppearance,readAppearance,useAppearance,themes} from './appearance';
import './styles.css';
import './source-review.css';

async function api<T>(url:string,init?:RequestInit):Promise<T>{
 const r=await fetch('/api'+url,{...init,headers:{'Content-Type':'application/json',...init?.headers}});
 if(!r.ok){let message='Something went wrong. Please try again.';try{const x=await r.json();message=typeof x.detail==='string'?x.detail:message;}catch{}throw new Error(message);}return r.json();
}
const languageNames:Record<NewsLanguage,string>={nl:'Nederlands',de:'Deutsch',en:'English'};
const topicShort:Record<string,string>={markets:'Markets',economy:'Economy',technology:'Technology',crypto:'Crypto',world:'World',money:'Everyday money',culture:'Culture',energy:'Energy',forex:'Currencies'};
const greet:Record<string,string>={nl:'Goedemorgen',de:'Guten Morgen',en:'Good morning'};
const mins=(s:number)=>`~${Math.max(1,Math.ceil(s/60))} min`;
const time=(s:number)=>`${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,'0')}`;
const date=(s:string)=>new Date(s).toLocaleDateString('en-GB',{day:'numeric',month:'short',timeZone:'UTC'});
function Wave({small=false}:{small?:boolean}){return <div className={'wave '+(small?'wave-small':'')} aria-hidden="true">{Array.from({length:small?23:57},(_,i)=><i key={i} style={{height:(small?9:18)+Math.abs(Math.sin(i*.74)*Math.cos(i*.19))*(small?24:102)+'px',animationDelay:i*.024+'s'}}/>)}</div>}
function Brand(){return <span className="brand"><img src="/seranews-mark.png" alt="" aria-hidden="true"/><span className="brand-wordmark">Seranews</span></span>}
function Tag({id}:{id:string}){return <span className={'tag tag-'+id}>{topicShort[id]||id.replaceAll('-',' ').replace(/^./,letter=>letter.toUpperCase())}</span>}
function Art({story,large=false}:{story:Story;large?:boolean}){return <StoryImage story={story} large={large}/>;}

type GenerationTask={job:CloudJob;profileId:string;autoplay:boolean;dismissed:boolean;retrying?:boolean};
const terminalJob=(state:CloudJob['state'])=>state==='ready'||state==='failed';

function ChapterSourceReview({chapter,onOpenSource}:{chapter:Chapter;onOpenSource:(source:Source,sources:Source[])=>void}){
 const review=chapter.evidence_review,claims=review?.claims||[];
 if(!claims.length)return null;
 const reviewLabel=review?.reviewer?'AI source review':'Reviewed demo summary';
 return <details className="source-review">
  <summary aria-label={`Source review: ${reviewLabel}. Review supporting passages.`}>
   <span>Source review</span><small>Review supporting passages</small>
  </summary>
  <div className="source-review-content">
   <p className="source-review-note">{reviewLabel} · Checked against the supplied report.</p>
   <ol>{claims.map((claim,index)=>{
    const source=chapter.sources.find(item=>item.article_id===claim.article_id);
    const turn=chapter.turns?.[claim.turn_index];
    return <li key={`${claim.article_id}-${claim.turn_index}-${index}`}>
     <span className="source-review-turn">Transcript turn {claim.turn_index+1}{turn?` · ${turn.speaker==='maya'?'Maya':'Leo'}`:''}</span>
     <blockquote>{claim.quote}</blockquote>
     {source
      ? <button type="button" className="source-review-link" aria-label={`Open supplied report: ${source.outlet}`} onClick={()=>onOpenSource(source,chapter.sources)}><BookOpen size={13}/><span>{source.outlet}</span><ArrowRight size={13}/></button>
      : <span className="source-review-missing">Supplied report reference unavailable</span>}
    </li>;
   })}</ol>
  </div>
 </details>;
}

function App(){
 const [boot,setBoot]=useState<Bootstrap|null>(null),[pid,setPid]=useState(localStorage.getItem('liquid-profile')||'mila');
 const [discoverSearch,setDiscoverSearch]=useState(false);
 const [plansOpen,setPlansOpen]=useState(false);
 const [appearanceOpen,setAppearanceOpen]=useState(false);
 const {appearance,setAppearance}=useAppearance();
 const devicePair=useRef<{key:string;voices:SpeechSynthesisVoice[]}>({key:'',voices:[]});
 const [summary,setSummary]=useState<Edition|null>(null);
 const [historyRevision,setHistoryRevision]=useState(0);
 const recentViews=useRef(new Map<string,number>());
 const [page,setPage]=useState('today'),[feed,setFeed]=useState<Feed|null>(null),[editions,setEditions]=useState<Edition[]>([]);
 const [profileMenu,setProfileMenu]=useState(false),[settings,setSettings]=useState(false),[onboarding,setOnboarding]=useState(false),[selectedStory,setStory]=useState<Story|null>(null),[script,setScript]=useState<Edition|null>(null);
 const [reading,setReading]=useState<Reading|null>(null);
 const [toast,setToast]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[edition,setEdition]=useState<Edition|null>(null),[playerOpen,setPlayerOpen]=useState(false);
 const [generationTasks,setGenerationTasks]=useState<GenerationTask[]>([]);
 const [playing,setPlaying]=useState(false),[chapterIndex,setChapterIndex]=useState(0),[elapsed,setElapsed]=useState(0),[speed,setSpeed]=useState(()=>{const saved=Number(localStorage.getItem('seranews-playback-speed'));return playbackSpeeds.includes(saved)?saved:1;}),[audioError,setAudioError]=useState('');
 const [topicFilters,setTopicFilters]=useState<string[]>([]),[languageFilters,setLanguageFilters]=useState<NewsLanguage[]>([]),[sourceFilter,setSourceFilter]=useState<NewsLanguage|'all'>('all'),[catalogMode,setCatalogMode]=useState(false),[catalogStories,setCatalogStories]=useState<Story[]|null>(null),[catalogLimit,setCatalogLimit]=useState(25),[query,setQuery]=useState('');
 const speedRef=useRef(speed);
 const seeking=useRef(false);
 const audio=useRef<HTMLAudioElement|null>(null),audioEdition=useRef<string|null>(null),utterance=useRef<SpeechSynthesisUtterance|null>(null),generation=useRef(0),playRequest=useRef(0),playStart=useRef(0),offset=useRef(0),elapsedRef=useRef(0),playingRef=useRef(false),currentRef=useRef({edition:null as Edition|null,index:0,pid});
 const learningRevision=useRef(0);
 const finishingJobs=useRef(new Set<string>()),pollingJobs=useRef(new Set<string>());
 const serverProfile=boot?.profiles.find(x=>x.id===pid)||boot?.profiles[0];
 const sync=usePreferenceSync(
  profile=>api<Profile>('/profiles/'+profile.id,{method:'PUT',body:JSON.stringify(profile)}),
  async saved=>{
   if(activeProfile.current===saved.id){await load(saved.id);return;}
   setBoot(current=>current?{...current,profiles:current.profiles.map(profile=>profile.id===saved.id?saved:profile)}:current);
  },
 );
 const votes=useVoteSync({
  write:async(profile,change)=>{if(!await sync.flush(profile))throw new Error('Preferences have not synced');return api('/profiles/'+profile+'/feedback',{method:'POST',body:JSON.stringify({story_id:change.storyId,value:change.value,reason:change.reason,occurred_at:change.occurredAt})});},
  accept:(profile,result)=>{
   learningRevision.current++;if(result.profile){const saved=result.profile;sync.mergeLearning(saved);setBoot(current=>current?{...current,profiles:current.profiles.map(item=>item.id===profile?{...item,learned_interests:saved.learned_interests,effective_interests:saved.effective_interests,interest_resets:saved.interest_resets,feedback_count:saved.feedback_count}:item)}:current);}
   if(activeProfile.current===profile){setFeed(current=>current?{...current,memory:result.memory}:current);setHistoryRevision(value=>value+1);}
  },failed:()=>notify('Your vote could not be saved. Please try again.'),
 });
 const pendingProfile=sync.pending[pid],baseProfile=pendingProfile||serverProfile;
 const p=useMemo(()=>baseProfile?votes.withLearning(baseProfile):undefined,[baseProfile,votes.revision]);
 const currentProfileRef=useRef<Profile|null>(null);currentProfileRef.current=p||null;
 const editionProfileKey=useRef('');
 const displayedStories=useMemo(()=>{
  if(p&&feed?.preview_stories)return previewStories(feed.preview_stories.map(story=>votes.decorate(pid,story)),p);
  return feed?.stories||[];
 },[p,feed,pid,votes.revision]);
 const current=edition?.chapters[chapterIndex];
 const playerDuration=edition?.episode_audio?episodeDuration(edition):current?.estimated_seconds||0;
 const sinceStories=pendingProfile?(feed?.since||[]).flatMap(item=>{const current=displayedStories.find(story=>story.id===item.id);return current?[{...item,...current}]:[];}):feed?.since||[];
 const notify=(message:string)=>{setToast(message);setTimeout(()=>setToast(''),3500);};
 const sleep=useSleepTimer(()=>{pausePlayback();notify('Sleep timer ended. Playback paused.');});
 const activeProfile=useRef(pid);
 const story=selectedStory?votes.decorate(pid,selectedStory):null;
 const workspace=useRef<HTMLDivElement>(null);
 const goTo=(destination:string)=>{if(destination!=='discover')setQuery('');setPage(destination);if(destination==='today')void load(pid).catch(()=>{});workspace.current?.scrollTo({top:0,left:0,behavior:'auto'});};
 const toggleTopic=(id:string)=>setTopicFilters(keys=>keys.includes(id)?keys.filter(x=>x!==id):[...keys,id]);
 const toggleLanguage=(id:NewsLanguage)=>setLanguageFilters(keys=>keys.includes(id)?keys.filter(x=>x!==id):[...keys,id]);
 const loadSequence=useRef(0);
 const load=async(id=pid)=>{
  const request=++loadSequence.current,learningAtStart=learningRevision.current;
  const [f,e,b]=await Promise.all([api<Feed>('/feed/'+id),api<Edition[]>('/profiles/'+id+'/editions'),api<Bootstrap>('/bootstrap')]);
  if(activeProfile.current!==id||request!==loadSequence.current)return null;
  const changed=learningAtStart!==learningRevision.current;
  setFeed(previous=>changed&&previous?{...f,memory:previous.memory}:f);setEditions(e);setBoot(previous=>changed&&previous?{...b,profiles:b.profiles.map(incoming=>{const latest=previous.profiles.find(item=>item.id===incoming.id);return latest?mergeLearningSnapshot(incoming,latest):incoming;})}:b);
  return {feed:f,editions:e,bootstrap:b};
 };
 async function finishGeneration(task:GenerationTask,job:CloudJob){
  if(finishingJobs.current.has(job.job_id))return;
  finishingJobs.current.add(job.job_id);
  try{
   if(activeProfile.current!==task.profileId)return;
   const refreshed=await load(task.profileId);
   if(!refreshed||activeProfile.current!==task.profileId)return;
   const saved=job.edition_id?refreshed.editions.find(item=>item.id===job.edition_id):undefined;
   let preferencesChanged=false;
   if(task.autoplay&&saved&&activeProfile.current===task.profileId){
    const savedProfile=refreshed.bootstrap.profiles.find(item=>item.id===task.profileId);
    const activePreferences=currentProfileRef.current?.id===task.profileId?currentProfileRef.current:savedProfile;
    preferencesChanged=!!saved.profile_snapshot&&(!activePreferences||preferenceKey(saved.profile_snapshot)!==preferenceKey(activePreferences));
    if(!preferencesChanged){
     editionProfileKey.current=saved.profile_snapshot?preferenceKey(saved.profile_snapshot):activePreferences?preferenceKey(activePreferences):'';
     stop();setChapterIndex(0);elapsedRef.current=0;setElapsed(0);playChapter(saved,0,0);
     if(!saved.profile_snapshot&&activePreferences)editionProfileKey.current=preferenceKey(activePreferences);
    }
   }
   if(activeProfile.current===task.profileId)notify(preferencesChanged?'Your briefing is ready. Your preferences changed, so you can play it from Podcasts when you’re ready.':'Your personal briefing is ready.');
  }catch{
   if(activeProfile.current===task.profileId)notify('Your briefing is ready, but Podcasts could not refresh. Open Podcasts to try again.');
  }finally{finishingJobs.current.delete(job.job_id);}
 }
 async function retryGeneration(task:GenerationTask){
  if(!task.job.can_retry||task.retrying)return;
  setGenerationTasks(current=>current.map(item=>item.job.job_id===task.job.job_id?{...item,retrying:true,dismissed:false}:item));
  try{
   const job=await api<CloudJob>('/profiles/'+task.profileId+'/briefings/'+task.job.job_id+'/retry',{method:'POST'});
   const retried={...task,job,retrying:false,dismissed:false};
   setGenerationTasks(current=>current.map(item=>item.job.job_id===job.job_id?retried:item));
   if(job.state==='ready')void finishGeneration(retried,job);
  }catch(e){
   setGenerationTasks(current=>current.map(item=>item.job.job_id===task.job.job_id?{...item,retrying:false}:item));
   if(activeProfile.current===task.profileId)notify((e as Error).message);
  }
 }
 useEffect(()=>{
  api<Bootstrap>('/bootstrap').then(result=>{
   setBoot(result);
   for(const profile of result.profiles){const cached=sync.pending[profile.id];if(cached){if(cached.demo_reset_id!==profile.demo_reset_id)sync.dropPending(profile.id);else void sync.flush(profile.id);}}
  }).catch(e=>setError(e.message));
 },[]);
 useEffect(()=>{if(!boot)return;setFeed(null);setEditions([]);load(pid).catch(e=>setError(e.message));localStorage.setItem('liquid-profile',pid);},[pid,!!boot]);
 useEffect(()=>{
  if(!boot?.integrations?.generation)return;
  let cancelled=false;
  api<{jobs:CloudJob[]}>('/profiles/'+pid+'/briefings').then(result=>{
   if(cancelled)return;
   const jobs=result.jobs||[];
   const job=jobs.find(item=>!terminalJob(item.state))||(jobs[0]?.state==='failed'?jobs[0]:undefined);
   if(!job)return;
   setGenerationTasks(current=>current.some(item=>item.profileId===pid)?current:[...current,{job,profileId:pid,autoplay:false,dismissed:false}]);
  }).catch(()=>{});
  return()=>{cancelled=true;};
 },[pid,boot?.integrations?.generation]);
 const generationPollKey=pid+'|'+generationTasks.filter(task=>!terminalJob(task.job.state)).map(task=>task.profileId+':'+task.job.job_id+':'+task.job.state+':'+!!task.retrying).join('|');
 useEffect(()=>{
  const tasks=generationTasks.filter(task=>!terminalJob(task.job.state));
  if(!tasks.length)return;
  let stopped=false;
  const poll=async(task:GenerationTask)=>{
   if(pollingJobs.current.has(task.job.job_id))return;
   pollingJobs.current.add(task.job.job_id);
   try{
    const job=await api<CloudJob>('/profiles/'+task.profileId+'/briefings/'+task.job.job_id);
    if(stopped)return;
    setGenerationTasks(current=>current.map(item=>item.job.job_id===job.job_id?{...item,job}:item));
    if(job.state==='ready')void finishGeneration(task,job);
   }catch{}finally{pollingJobs.current.delete(task.job.job_id);}
  };
  const timer=setInterval(()=>tasks.forEach(task=>void poll(task)),1500);
  return()=>{stopped=true;clearInterval(timer);};
 },[generationPollKey]);
 useEffect(()=>{
  if(!boot?.catalog_version)return;
  const version=boot.catalog_version;
  const refresh=()=>{if(document.visibilityState==='visible')api<Bootstrap>('/bootstrap').then(next=>{
   if(next.catalog_version!==version&&activeProfile.current===pid)void load(pid).catch(()=>{});
  }).catch(()=>{});};
  const interval=setInterval(refresh,45000);
  document.addEventListener('visibilitychange',refresh);
  return ()=>{clearInterval(interval);document.removeEventListener('visibilitychange',refresh);};
 },[pid,boot?.catalog_version]);
 useEffect(()=>{
  if(page!=='discover'||!catalogMode)return;
  const controller=new AbortController();
  const debounce=setTimeout(()=>{
   const params=new URLSearchParams({all_items:'true',limit:String(catalogLimit),q:query,topics:topicFilters.join(','),languages:languageFilters.join(',')});
   api<Feed>('/feed/'+pid+'?'+params,{signal:controller.signal}).then(result=>setCatalogStories(result.stories)).catch(e=>{if(e.name!=='AbortError')notify(e.message);});
  },150);
  return ()=>{clearTimeout(debounce);controller.abort();};
 },[page,catalogMode,catalogLimit,query,topicFilters,languageFilters,pid,boot?.catalog_version,p?preferenceKey(p):'']);
 useEffect(()=>{currentRef.current={edition,index:chapterIndex,pid};},[edition,chapterIndex,pid]);
 useEffect(()=>{if(!playing)return;const handle=setInterval(()=>{if(!audio.current&&!seeking.current){const s=offset.current+(performance.now()-playStart.current)/1000*speed;elapsedRef.current=Math.min(s,current?.estimated_seconds||s);setElapsed(elapsedRef.current);}},250);return()=>clearInterval(handle);},[playing,speed,current]);
 useEffect(()=>{if(!playing)return;const handle=setInterval(()=>record(false),8000);return()=>clearInterval(handle);},[playing,chapterIndex,pid,edition]);
 useEffect(()=>{const onSummary=(event:Event)=>{const detail=(event as CustomEvent<{source:string;usesDevice?:boolean}>).detail;if(detail?.source!=='summary')return;if(playingRef.current)pausePlayback();if(detail.usesDevice&&!audio.current){generation.current++;utterance.current=null;}};window.addEventListener('seranews:audio-start',onSummary);return()=>window.removeEventListener('seranews:audio-start',onSummary);},[]);
 useEffect(()=>()=>{generation.current++;window.speechSynthesis?.cancel();audio.current?.pause();},[]);
 useEffect(()=>{const fn=(e:KeyboardEvent)=>{if(e.key==='Escape'){if(appearanceOpen){setAppearanceOpen(false);return;}if(plansOpen){setPlansOpen(false);return;}if(reading){setReading(null);return;}setStory(null);setSettings(false);setProfileMenu(false);setPlayerOpen(false);setScript(null);setSummary(null);setReading(null);setOnboarding(false);}};window.addEventListener('keydown',fn);return()=>window.removeEventListener('keydown',fn);},[reading,plansOpen,appearanceOpen]);

 function setPlayingIntent(value:boolean){playingRef.current=value;setPlaying(value);}
 function record(completed:boolean,position=elapsedRef.current){const r=currentRef.current;const ch=r.edition?.chapters[r.index];const seconds=r.edition?.episode_audio?Math.max(0,position-chapterStart(r.edition,r.index)):position;if(ch&&(seconds>=3||completed))api('/profiles/'+r.pid+'/listens',{method:'POST',body:JSON.stringify({story_id:ch.story_id,edition_id:r.edition?.id,seconds,completed})}).catch(()=>{});}
 function pausePlayback(){playRequest.current++;setPlayingIntent(false);if(audio.current)audio.current.pause();else window.speechSynthesis?.pause();offset.current=elapsedRef.current;record(false);}
 function stop(){pausePlayback();generation.current++;window.speechSynthesis?.cancel();utterance.current=null;audio.current=null;audioEdition.current=null;seeking.current=false;}
 function requestAudioPlay(element:HTMLAudioElement){
  const request=++playRequest.current,token=generation.current;
  window.dispatchEvent(new CustomEvent('seranews:audio-start',{detail:{source:'podcast'}}));
  setAudioError('');setPlayingIntent(true);
  try{void element.play().then(()=>{
   if(audio.current!==element||token!==generation.current||!playingRef.current)element.pause();
  }).catch(()=>{
   if(audio.current!==element||token!==generation.current||request!==playRequest.current||!playingRef.current)return;
   setPlayingIntent(false);setAudioError('Tap Play to allow audio in your browser.');
  });}catch{
   if(audio.current===element&&token===generation.current&&request===playRequest.current){setPlayingIntent(false);setAudioError('Tap Play to allow audio in your browser.');}
  }
 }
 function syncEpisodePosition(e:Edition,position:number,completePrevious=false){
  const next=chapterAt(e,position),previous=currentRef.current.index;
  if(next!==previous){
   if(completePrevious&&next>previous)record(true,chapterEnd(e,previous));
   currentRef.current={edition:e,index:next,pid};setChapterIndex(next);
  }
  elapsedRef.current=position;setElapsed(position);
 }
 function seekEpisode(e:Edition,position:number,autoplay=false){
  const element=audio.current;
  const target=Math.max(0,Math.min(position,episodeDuration(e)));
  record(false);seeking.current=false;
  if(!element||audioEdition.current!==e.id){
   syncEpisodePosition(e,target);
   if(autoplay){const index=chapterAt(e,target);playChapter(e,index,target-chapterStart(e,index));}
   return;
  }
  element.currentTime=target;syncEpisodePosition(e,target);
  if(autoplay&&!playingRef.current)requestAudioPlay(element);
 }
 function switchProfile(id:string){sleep.clear();stop();activeProfile.current=id;setEdition(null);elapsedRef.current=0;setElapsed(0);setChapterIndex(0);setPid(id);setTopicFilters([]);setLanguageFilters([]);setQuery('');setCatalogMode(false);setCatalogStories(null);goTo('today');setProfileMenu(false);setStory(null);setScript(null);setSummary(null);setReading(null);setPlayerOpen(false);setOnboarding(false);setSettings(false);if(boot?.profiles.find(x=>x.id===id)?.onboarded===false)setOnboarding(true);}
 function vote(s:Story,value:number,reason='interest'){votes.vote(pid,s,value,reason);}
 async function makeEdition(autoplay=false,day?:string){
  if(autoplay&&!day&&p){
   const saved=latestPlayableBriefing(editions,pid);
   if(saved){
    playSavedBriefing(saved);return saved;
   }
  }
  if(boot?.usage?.[pid]?.can_create===false&&(p?.plan||'free')==='free'){notify('Your daily edition is ready. Replay it, or explore another plan.');setPlansOpen(true);return;}
  if(boot?.integrations?.generation){
   if(generationTasks.some(task=>task.profileId===pid&&(!terminalJob(task.job.state)||task.retrying)))return;
   setBusy(true);
   try{
    if(!await sync.flush(pid)){notify('Reconnect to apply your preferences before creating a briefing.');return;}
    const job=await api<CloudJob>('/profiles/'+pid+'/briefings',{method:'POST',body:JSON.stringify(day?{day}:{})});
    const task:GenerationTask={job,profileId:pid,autoplay,dismissed:false};
    setGenerationTasks(current=>[...current.filter(item=>item.profileId!==pid),task]);
    if(job.state==='ready')void finishGeneration(task,job);
   }catch(e){if(activeProfile.current===pid)notify((e as Error).message);}
   finally{setBusy(false);}
   return;
  }
  setBusy(true);try{if(!await sync.flush(pid)){notify('Reconnect to apply your preferences before creating a briefing.');return;}const e=await api<Edition>('/profiles/'+pid+'/editions'+(day?'?day='+encodeURIComponent(day):''),{method:'POST'});if(activeProfile.current!==pid)return;editionProfileKey.current=e.profile_snapshot?preferenceKey(e.profile_snapshot):p&&(!day||day===boot?.latest_news_at?.slice(0,10))?preferenceKey(p):'';stop();setEdition(e);setChapterIndex(0);elapsedRef.current=0;setElapsed(0);await load();if(activeProfile.current!==pid)return;notify('Your personal briefing is ready.');if(autoplay){playChapter(e,0,0);if(!e.profile_snapshot&&p&&(!day||day===boot?.latest_news_at?.slice(0,10)))editionProfileKey.current=preferenceKey(p);}return e;}catch(e){notify((e as Error).message);}finally{setBusy(false);}
 }
 function selectChapter(index:number){
  const e=edition;
  if(!e||!e.chapters.length)return;
  const next=Math.max(0,Math.min(index,e.chapters.length-1));
  if(e.episode_audio&&audio.current&&audioEdition.current===e.id){
   // Seeking in a paused combined recording must never call play(). Keep its
   // media handlers alive so pressing Play afterwards resumes normally.
   playRequest.current++;audio.current.pause();setPlayingIntent(false);
   seekEpisode(e,chapterStart(e,next),false);
   return;
  }
  // Stop the previous clip/utterance without starting the newly selected one.
  stop();setEdition(e);setChapterIndex(next);setAudioError('');
  currentRef.current={edition:e,index:next,pid};
  const position=e.episode_audio?chapterStart(e,next):0;
  elapsedRef.current=position;offset.current=position;setElapsed(position);
 }
 function playSavedBriefing(saved:Edition){
  setGenerationTasks(tasks=>tasks.map(task=>task.profileId===pid?{...task,autoplay:false,dismissed:terminalJob(task.job.state)}:task));
  playChapter(saved,0);editionProfileKey.current=p?preferenceKey(p):'';
 }
 function playChapter(e:Edition,index:number,seek=0,rate=speedRef.current){
  if(e.audio_mode==='summary-only'){setSummary(e);return;}
  editionProfileKey.current=e.profile_snapshot?preferenceKey(e.profile_snapshot):'';
  sleep.bindEdition(e.id);
  if(index>=e.chapters.length){sleep.finishEdition(e.id);pausePlayback();if(audio.current&&audioEdition.current===e.id)audio.current.currentTime=0;else{generation.current++;window.speechSynthesis?.cancel();utterance.current=null;audio.current=null;audioEdition.current=null;}currentRef.current={edition:e,index:0,pid};elapsedRef.current=0;setChapterIndex(0);setElapsed(0);notify('You’re all caught up. See you tomorrow.');load().catch(()=>{});return;}
  window.dispatchEvent(new CustomEvent('seranews:audio-start',{detail:{source:'podcast'}}));
  if(e.episode_audio){
   const target=chapterStart(e,index)+seek;
   if(audio.current&&audioEdition.current===e.id){seekEpisode(e,target,true);return;}
   stop();setEdition(e);setChapterIndex(index);currentRef.current={edition:e,index,pid};
   const element=new Audio(e.episode_audio.url),token=++generation.current;
   audio.current=element;audioEdition.current=e.id;element.playbackRate=rate;element.currentTime=target;
   syncEpisodePosition(e,target);setAudioError('');
   element.ontimeupdate=()=>{if(token===generation.current&&!seeking.current)syncEpisodePosition(e,element.currentTime,true);};
   element.onended=()=>{if(token!==generation.current||!playingRef.current)return;syncEpisodePosition(e,episodeDuration(e),true);record(true,episodeDuration(e));playChapter(e,e.chapters.length);};
   element.onerror=()=>{if(token!==generation.current)return;playRequest.current++;setPlayingIntent(false);setAudioError('Audio could not load. Try again.');};
   requestAudioPlay(element);return;
  }
  seeking.current=false;generation.current++;const token=generation.current;window.speechSynthesis?.cancel();audio.current?.pause();audio.current=null;audioEdition.current=null;
  const ch=e.chapters[index];setEdition(e);setChapterIndex(index);elapsedRef.current=seek;setElapsed(seek);offset.current=seek;playStart.current=performance.now();setAudioError('');currentRef.current={edition:e,index,pid};
  const ended=()=>{if(token!==generation.current||!playingRef.current)return;elapsedRef.current=ch.estimated_seconds;record(true);playChapter(e,index+1,0);};
  if(ch.audio){const element=new Audio(ch.audio.url);audio.current=element;element.playbackRate=rate;element.currentTime=seek;element.onended=ended;element.ontimeupdate=()=>{if(token===generation.current&&!seeking.current){elapsedRef.current=element.currentTime;setElapsed(element.currentTime);}};element.onerror=()=>{if(token!==generation.current)return;playRequest.current++;setPlayingIntent(false);setAudioError('Audio could not load. Try again.');};requestAudioPlay(element);return;}
  if(!('speechSynthesis' in window)){setPlayingIntent(false);setAudioError('Voice preview is unavailable in this browser. You can read the script instead.');return;}
  const turns=ch.turns?.length?ch.turns:[{speaker:index%2?'leo':'maya',text:ch.text,estimated_seconds:ch.estimated_seconds}];
  const synth=window.speechSynthesis;
  synth.resume();
  const preferred=e.tts_provider==='device'?e.voice_ids||[]:p?.device_voices?.[e.language]||[];
  const pairKey=JSON.stringify([e.id,e.language,preferred]);
  if(devicePair.current.key!==pairKey||!devicePair.current.voices.length)devicePair.current={key:pairKey,voices:chooseDevicePair(e.language,preferred)};
  const voices=devicePair.current.voices;
  const speechLanguage={nl:'nl-NL',de:'de-DE',en:'en-GB'}[e.language];
  function speakTurn(turnIndex:number,startingAt:number){
   if(token!==generation.current||!playingRef.current)return;
   const turn=turns[turnIndex];
   if(!turn){ended();return;}
   const base=turns.slice(0,turnIndex).reduce((sum,part)=>sum+part.estimated_seconds,0);
   const cut=Math.floor(turn.text.length*Math.min(.97,startingAt/Math.max(1,turn.estimated_seconds)));
   const remaining=turn.text.slice(cut).replace(/^\S*\s+/,(match)=>cut? '':match);
   const speech=new SpeechSynthesisUtterance(remaining||turn.text);
   speech.lang=speechLanguage;
   speech.rate=rate*(turn.speaker==='leo'&&voices.length<2?.94:1);
   speech.pitch=turn.speaker==='leo'&&voices.length<2?.82:1.07;
   const voice=voices[turn.speaker==='leo'&&voices.length>1?1:0];
   if(voice)speech.voice=voice;
   speech.onstart=()=>{
    if(token!==generation.current||!playingRef.current)return;
    offset.current=base+startingAt;
    playStart.current=performance.now();
    elapsedRef.current=base+startingAt;
    setElapsed(base+startingAt);
    setPlayingIntent(true);
   };
   speech.onend=()=>speakTurn(turnIndex+1,0);
   speech.onerror=event=>{
    if(token!==generation.current||event.error==='interrupted'||event.error==='canceled')return;
    setPlayingIntent(false);
    setAudioError('Device voice unavailable. You can read the script or try a browser with local voices.');
   };
   utterance.current=speech;
   synth.speak(speech);
  }
  let first=0;
  let turnOffset=seek;
  while(first<turns.length-1&&turnOffset>=turns[first].estimated_seconds){turnOffset-=turns[first].estimated_seconds;first++;}
  offset.current=seek;
  setPlayingIntent(true);
  speakTurn(first,turnOffset);
 }
 function togglePlay(){
  setGenerationTasks(tasks=>tasks.map(task=>task.profileId===pid?{...task,autoplay:false,dismissed:terminalJob(task.job.state)}:task));
  if(!edition){void makeEdition(true);return;}
  if(playingRef.current){pausePlayback();return;}
  if(audio.current){requestAudioPlay(audio.current);return;}
  if(window.speechSynthesis?.paused&&utterance.current){window.dispatchEvent(new CustomEvent('seranews:audio-start',{detail:{source:'podcast'}}));playStart.current=performance.now();setPlayingIntent(true);window.speechSynthesis.resume();return;}
  playChapter(edition,chapterIndex,edition.episode_audio?Math.max(0,elapsed-chapterStart(edition,chapterIndex)):elapsed);
 }
 function changeSpeed(rate:number){
  speedRef.current=rate;setSpeed(rate);localStorage.setItem('seranews-playback-speed',String(rate));
  if(audio.current){audio.current.playbackRate=rate;return;}
  const active=currentRef.current;
  if(playingRef.current&&active.edition)playChapter(active.edition,active.index,elapsedRef.current,rate);
  else {generation.current++;window.speechSynthesis?.cancel();utterance.current=null;}
 }
 function editPreferences(change:ProfileChange){
  if(!p)return;
  const next=clearEditedLearning(p,normalizePlan(change(p)));
  setTopicFilters(filters=>filters.filter(tag=>!p.interests[tag]||next.interests[tag]));
  setLanguageFilters(filters=>filters.filter(lang=>next.news_languages.includes(lang)));
  sync.edit(p,current=>clearEditedLearning(current,normalizePlan(change(current))));
 }
 function finishOnboarding(){
  editPreferences(current=>({...current,onboarded:true}));
  setOnboarding(false);
  setSettings(false);
 }
 function closePreferences(){setSettings(false);setOnboarding(false);void sync.flush(pid);}
 const topicLabels=Object.fromEntries((boot?.topics||[]).map(topic=>[topic.id,topic.label]));
 function recordView(item?:Story,source?:Source){
  const key=pid+':'+(item?.id||source?.article_id);
  const timestamp=Date.now();
  if(timestamp-(recentViews.current.get(key)||0)<6000)return;
  recentViews.current.set(key,timestamp);
  void api('/profiles/'+pid+'/views',{method:'POST',body:JSON.stringify({story_id:item?.id,article_id:source?.article_id})})
   .then(()=>{if(activeProfile.current===pid){setHistoryRevision(value=>value+1);setFeed(current=>current?{...current,since:current.since.filter(story=>story.id!==item?.id&&!story.sources.some(candidate=>candidate.article_id===source?.article_id))}:current);}})
   .catch(()=>{recentViews.current.delete(key);});
 }
 async function removeEditionAudio(item:Edition){
  const requestedProfile=pid;
  try{
   const result=await api<{edition:Edition;reclaimed_bytes:number;shared_bytes:number;unreclaimed_bytes:number}>('/profiles/'+pid+'/editions/'+item.id+'/audio',{method:'DELETE'});
   if(activeProfile.current!==requestedProfile)return;
   if(currentRef.current.edition?.id===item.id){stop();setEdition(null);setPlayerOpen(false);setElapsed(0);}
   setEditions(current=>current.map(other=>other.id===item.id?result.edition:other));
   setScript(current=>current?.id===item.id?result.edition:current);
   setSummary(current=>current?.id===item.id?result.edition:current);
   notify(result.unreclaimed_bytes?'Summary kept. Some audio files could not be removed.':result.reclaimed_bytes?`Summary kept. ${(result.reclaimed_bytes/1024/1024).toFixed(1)} MB freed.`:result.shared_bytes?'Summary kept. Shared audio is still used by another edition.':'Summary kept. This voice preview had no stored audio.');
  }catch(cause){notify((cause as Error).message);}
 }
 const openStory=(s:Story)=>{recordView(s);setSourceFilter('all');setStory(s);};
 const openSource=(source:Source,sources:Source[],context?:Story)=>{const item=context||feed?.preview_stories?.find(item=>item.sources.some(src=>src.article_id===source.article_id));recordView(item,source);setReading({source,sources,mode:'full',story:item});};
 const followSuggestion=(id:string)=>editPreferences(current=>updateTag(current,id,3));
 const suggestions=(feed?.suggestions||[]).filter(topic=>!(p?.effective_interests||p?.interests||{})[topic.id]&&(p?.learned_interests?.[topic.id]||0)>=0);
 const filtered=(page==='discover'&&catalogMode&&catalogStories?catalogStories:displayedStories)
  .map(item=>votes.decorate(pid,item))
  .filter(s=>p?.news_languages.some(lang=>s.sources.some(source=>source.language===lang)))
  .filter(s=>!topicFilters.length||s.tags.some(t=>topicFilters.includes(t)))
  .filter(s=>page!=='discover'||!languageFilters.length||s.sources.some(source=>languageFilters.includes(source.language)))
  .filter(s=>!query||[s.title,s.summary,...s.sources.map(source=>source.headline)].join(' ').toLowerCase().includes(query.toLowerCase()));
 const generationForProfile=generationTasks.find(task=>task.profileId===pid);
 const generationInProgress=!!(generationForProfile&&(!terminalJob(generationForProfile.job.state)||generationForProfile.retrying));
 const latestSavedBriefing=latestPlayableBriefing(editions,pid);
 const canPlayCurrentEdition=!!edition&&edition.profile_id===pid&&edition.audio_mode!=='summary-only'&&!edition.audio_removed_at&&(playing||edition.id===latestSavedBriefing?.id);
 const canPlaySavedBriefing=canPlayCurrentEdition||!!latestSavedBriefing;
 const nav=[{id:'today',label:'Today',icon:Sun},{id:'discover',label:'Discover',icon:Compass},{id:'podcasts',label:'Your podcasts',icon:Headphones}];
 if(error&&!boot)return <div className="loading"><Brand/><p>{error}</p><button onClick={()=>location.reload()}>Try again</button></div>;
 if(!boot||!p)return <div className="loading"><Brand/><LoaderCircle className="spin"/><p>Finding your perspective…</p></div>;

 return <div className="demo-stage"><div className="phone-device"><div className="phone-frame"><div className={'app '+(edition?'has-player':'')}>
  <div className="phone-status" aria-hidden="true"><span>9:41</span><div className="phone-notch"/><span className="phone-signals"><Signal size={12}/><Wifi size={12}/><BatteryFull size={15}/></span></div>
  <div className={'workspace '+(page==='discover'?'workspace-reels':'')} ref={workspace}><header className="topbar"><div className="mobile-brand"><Brand/></div><div className="header-right"><button className="icon-button history-shortcut" aria-label="Reading history" aria-pressed={page==='history'} onClick={()=>{setProfileMenu(false);goTo('history');}}><History size={19}/></button><button className="icon-button search-shortcut" aria-label="Search and filter stories" onClick={()=>{setProfileMenu(false);goTo('discover');setDiscoverSearch(true);}}><Search size={20}/>{(query||topicFilters.length||languageFilters.length||catalogMode)?<span className="search-active-dot"/>:null}</button><div className="profile-wrap"><button className="profile-button" aria-label="Change listener profile" aria-expanded={profileMenu} onClick={()=>setProfileMenu(!profileMenu)}><Avatar p={p} small/><span>{p.name}</span><ChevronDown size={14}/></button>{profileMenu&&<><div className="click-away" onClick={()=>setProfileMenu(false)}/><div className="profile-menu"><div className="menu-heading">LISTEN AS SOMEONE ELSE</div>{boot.profiles.map(user=><button key={user.id} onClick={()=>switchProfile(user.id)}><Avatar p={user} small/><span><b>{user.name}</b><small>{user.role} · {languageNames[user.language]}</small></span>{pid===user.id?<Check size={17}/>:<ChevronRight size={15}/>}</button>)}<div className="menu-footer">Demo accounts · no password needed</div><button aria-label="Open settings" onClick={()=>{setProfileMenu(false);setSettings(true);}}><Settings2 size={17}/>Preferences & schedule</button><button aria-label="Open subscription" onClick={()=>{setProfileMenu(false);setPlansOpen(true);}}><Sparkles size={17}/>Subscription <span className="menu-plan-pill">{planFor(p).name}</span></button><button aria-label="Open appearance" onClick={()=>{setProfileMenu(false);setAppearanceOpen(true);}}><Palette size={17}/>Appearance <span className="menu-theme-name">{themes.find(theme=>theme.id===appearance.theme)?.name}</span></button></div></>}</div></div></header>
   <main className={'app-screen '+(page==='discover'?'reels-screen':'')} key={page}>
   {page==='today'&&<>
    <section className="page-heading"><div><div className="eyebrow"><span className="sun-icon">✳</span> {new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',timeZone:'Europe/Brussels'}).toUpperCase()} · DEMO</div><h1>{greet[p.language]}, {p.name}<span className="orange">.</span></h1><p>A little clarity for the day ahead. Made for you.</p></div><button className="quiet-button schedule-button" onClick={()=>setSettings(true)}><Clock3 size={16}/>{p.scheduled?`Ready by ${p.wake_time}`:'Your time. Your pace.'}<ChevronRight size={14}/></button></section>
    {!p.onboarded&&<button className="welcome-strip" onClick={()=>setOnboarding(true)}><Sparkles/><span><b>Let’s make this yours.</b> A few choices. A better first briefing.</span><ArrowRight/></button>}
    <section className="hero"><div className="hero-copy"><div className="pill hero-pill"><span className="live-dot"/>TODAY’S BRIEF</div><h2>The morning,<br/>made yours<span>.</span></h2><p>{p.bio}</p><div className="hero-meta"><span><Headphones size={15}/>{`~${p.duration} min`}</span><span className="dot-sep">•</span><span>{languageNames[p.language]}</span><span className="dot-sep">•</span><span>{p.depth==='simple'?'Simply explained':p.depth==='detailed'?'A closer look':'The right amount of detail'}</span></div><div className="hero-actions"><button className="primary-button" disabled={!feed||(busy&&(!boot.integrations?.generation||!canPlaySavedBriefing))||(generationInProgress&&!canPlaySavedBriefing)} onClick={()=>{if(canPlayCurrentEdition)togglePlay();else void makeEdition(true);}}>{(busy&&(!boot.integrations?.generation||!canPlaySavedBriefing))||(generationInProgress&&!canPlaySavedBriefing)?<LoaderCircle className="spin" size={18}/>:playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}{(busy&&(!boot.integrations?.generation||!canPlaySavedBriefing))||(generationInProgress&&!canPlaySavedBriefing)?'Making your briefing…':playing?'Pause briefing':'Play my briefing'}</button><button className="hero-more" aria-label="Generate a fresh briefing" onClick={()=>void makeEdition(false)} disabled={busy||generationInProgress}><RefreshCw size={18}/></button></div><div className="hero-foot"><ShieldCheck size={14}/>Source-linked stories. A voice made by AI.</div></div><div className="hero-visual" aria-hidden="true"><div className="orbit o1"/><div className="orbit o2"/><div className="orbit o3"/><span className="visual-plus vp1">+</span><span className="visual-plus vp2">+</span><div className="disc"><div className="disc-inner"><Wave/><span className="disc-label">THE LIQUID BRIEFING</span></div></div><div className="floating-label"><span className="live-dot"/>TUNED TO YOU</div><span className="visual-coord">50° 51′ N &nbsp; / &nbsp; A FRESH PERSPECTIVE</span></div></section>
    
    <section className="since-section"><div className="section-title"><div><div className="eyebrow">PICK UP THE THREAD</div><h2>Since your last visit<span className="orange">.</span></h2></div><span className="subtle since-time"><History size={15}/>{feed?.since_baseline?`Caught up through ${date(feed.since_baseline)}`:'Your reading trail starts here'}</span></div>{!feed?<Skeleton/>:sinceStories.length?<div className="since-grid">{sinceStories.slice(0,2).map((s,i)=><button className="update-card" key={s.id} onClick={()=>openStory(s)}><div className={'update-icon '+(i?'sage':'coral')}>{i?<RefreshCw size={20}/>:<Zap size={20}/>}</div><div><span className="update-label">{s.catch_up_kind==='development'?'A STORY YOU FOLLOWED':'NEW SINCE YOUR LAST VISIT'}<i>· {date(s.updated_at)}</i></span><h3>{s.title}</h3><p>{s.catch_up_kind==='development'?'New details · ':''}{s.sources[0].outlet} · {s.sources.length} source{s.sources.length!==1?'s':''}</p></div><ArrowUp className="diagonal" size={18}/></button>)}</div>:<div className="caught-up"><CheckCheck size={23}/><div><b>{feed?.since_baseline?'You’re all caught up.':'A fresh perspective starts here.'}</b><span>{feed?.since_baseline?'We’ll look for new stories and developments in what you’ve read or heard.':'Read a story or listen to a briefing. We’ll remember the stories you’ve caught up on.'}</span></div><button disabled={busy||generationInProgress} onClick={()=>void makeEdition(true)}>Listen now<ArrowRight size={15}/></button></div>}</section>
    <section className="stories-section"><div className="section-title"><div><div className="eyebrow">THE STORIES BEHIND YOUR BRIEF</div><h2>On your radar<span className="orange">.</span></h2></div><button className="text-button" onClick={()=>goTo('discover')}>Explore your feed<ArrowRight size={16}/></button></div><div className="topic-row"><button className={!topicFilters.length?'selected':''} onClick={()=>setTopicFilters([])}><Sparkles size={13}/>For you</button>{Object.keys(p.interests).filter(k=>p.interests[k]>0).sort((a,b)=>p.interests[b]-p.interests[a]).map(k=><button key={k} className={topicFilters.includes(k)?'selected':''} aria-pressed={topicFilters.includes(k)} onClick={()=>toggleTopic(k)}>{topicShort[k]||topicLabels[k]||k}</button>)}<button className="topic-add" onClick={()=>setSettings(true)} aria-label="Add interest"><Plus size={15}/></button></div>{!feed?<Skeleton/>:<><StoryMotion stories={filtered.slice(0,3)} totalMatches={filtered.length} layout="story-grid" renderStory={s=><StoryCard s={s} selected={topicFilters} labels={topicLabels} onOpen={openStory} onVote={vote}/>}/>{!filtered.length&&<div className="empty-state"><Compass/><h3>A little room to explore.</h3><p>There are no demo stories for this filter. Try another interest.</p><button onClick={()=>setTopicFilters([])}>Show all stories</button></div>}</>}</section>
    <div className="bottom-note"><AudioLines size={19}/><span>Less noise. More perspective.</span><small>Curated from {boot.stats.feeds} feeds, made personal for you.</small></div>
   </>}
   {page==='discover'&&<Discover profileId={pid} preferenceScope={preferenceKey(p)} searchOpen={discoverSearch} onSearchOpened={()=>setDiscoverSearch(false)} stories={filtered} topics={boot.topics} query={query} setQuery={setQuery}
    selectedTopics={topicFilters} toggleTopic={toggleTopic} clearTopics={()=>setTopicFilters([])}
    selectedLanguages={languageFilters} availableLanguages={p.news_languages} toggleLanguage={toggleLanguage} clearLanguages={()=>setLanguageFilters([])}
    archive={catalogMode} toggleArchive={()=>{setCatalogMode(enabled=>!enabled);setCatalogLimit(25);setCatalogStories(null);}}
    hasMore={catalogMode&&!!catalogStories&&catalogStories.length>=catalogLimit&&catalogLimit<150}
    onMore={()=>setCatalogLimit(limit=>Math.min(150,limit+25))} loading={!feed||(catalogMode&&!catalogStories)}
    suggestions={suggestions} onFollow={followSuggestion} onOpen={openStory} onVote={vote} onView={item=>recordView(item)} art={story=><Art story={story} large/>}/>}
   {page==='podcasts'&&<PodcastLibrary key={pid} profile={p} usage={boot.usage?.[pid]} editions={editions} dates={boot.briefing_dates||[boot.replay_day]} busy={boot.integrations?.generation?false:busy} createBusy={busy||generationInProgress}
    playbackControls={<PlaybackOptions speed={speed} onSpeed={changeSpeed} sleep={sleep} editionId={edition?.id||null}/>} onCreate={day=>void makeEdition(false,day)} onPlay={playSavedBriefing} onSummary={setSummary} onScript={setScript} onRemoveAudio={removeEditionAudio}/>}
   {page==='history'&&<ReadingHistoryPage key={pid} profileId={pid} revision={historyRevision} onOpen={openStory} onBack={()=>goTo('discover')}/>}

   {page!=='discover'&&<footer className="page-footer"><span className="footer-brand"><Brand/><i>The Liquid Briefing</i></span><span>Made for a more considered morning.</span><span>MAIN AI HACKATHON 2026</span></footer>}
   </main>
  </div>
  <nav className="mobile-nav" aria-label="Main navigation">{nav.map(n=><button type="button" key={n.id} aria-current={page===n.id?'page':undefined} className={page===n.id?'active':''} onClick={()=>{if(page!==n.id)goTo(n.id);}}><n.icon size={21}/><span>{n.id==='podcasts'?'Podcasts':n.label}</span></button>)}</nav>
  {generationForProfile&&!generationForProfile.dismissed&&<GenerationStatus job={generationForProfile.job} profileName={p.name} retrying={generationForProfile.retrying} onClose={()=>setGenerationTasks(current=>current.map(task=>task.job.job_id===generationForProfile.job.job_id?{...task,dismissed:true}:task))} onRetry={()=>void retryGeneration(generationForProfile)} onOpenPodcasts={()=>{goTo('podcasts');void load(pid).catch(()=>{});}}/>}
  {edition&&current&&<div className="mini-player"><button className="mini-cover coral" aria-label="Expand player" onClick={()=>setPlayerOpen(true)}><AudioLines size={25}/></button><button className="mini-info" onClick={()=>setPlayerOpen(true)}><b>{current.title}</b><span>{chapterIndex+1} / {edition.chapters.length} · {edition.demo_sample?'Sample podcast':edition.episode_audio?'Recorded podcast':edition.audio_mode==='elevenlabs'?'Natural voice':'Basic voice preview'}</span></button><div className="mini-controls"><button className="icon-button skip-mini" aria-label="Previous chapter" onClick={()=>selectChapter(chapterIndex-1)}><SkipBack size={18}/></button><button className="player-toggle" aria-label={playing?'Pause audio':'Play audio'} onClick={togglePlay}>{playing?<Pause size={19} fill="currentColor"/>:<Play size={19} fill="currentColor"/>}</button><button className="icon-button" aria-label="Next chapter" onClick={()=>selectChapter(chapterIndex+1)}><SkipForward size={18}/></button></div><span className="player-clock">{time(elapsed)} / {time(playerDuration)}</span><button className="quiet-button source-mini" onClick={()=>setScript(edition)}><FileText size={15}/>Sources</button><div className="mini-progress" style={{width:Math.min(100,playerDuration?elapsed/playerDuration*100:0)+'%'}}/></div>}
  {audioError&&<div className="audio-error" role="alert">{audioError}<button onClick={()=>setAudioError('')} aria-label="Dismiss audio error"><X size={15}/></button></div>}
  {story&&<div className="overlay" onClick={()=>setStory(null)}><section className="story-modal" role="dialog" aria-modal="true" aria-label="Story details" onClick={e=>e.stopPropagation()}><button className="close-button" aria-label="Close story" onClick={()=>setStory(null)}><X size={21}/></button><Art story={story} large/><div className="story-modal-body"><StoryTags story={story} selected={topicFilters} labels={topicLabels}/><h2 lang={story.title_language}>{story.title}</h2>{story.ai_translated&&<span className="ai-translation-label">Translated by AI</span>}<p className="story-summary" lang={story.summary_language}>{story.summary}</p><SpokenSummary key={pid+":"+story.id+":"+story.summary_language} story={story} language={p.language} available={p.plan==="plus"||p.plan==="premium"} onPlans={()=>setPlansOpen(true)}/><button className="full-article-in-story" onClick={()=>openSource(story.sources.find(source=>source.language===p.language)||story.sources[0],story.sources,story)}>Read full article<ArrowRight size={16}/></button><div className="story-reason"><Sparkles size={15}/>{story.reason}</div><div className="story-feedback"><span>Does this belong in your briefing?</span><Votes s={story} onVote={vote}/></div><h3><ShieldCheck size={18}/>Follow the reporting</h3><p className="subtle">The summary is attributed to the supporting report. Other links are related coverage and language editions.</p>{story.source_language_note&&<div className="source-language-note"><Globe2 size={16}/><span>{story.source_language_note}</span></div>}<SourceOptions sources={story.sources} selected={sourceFilter} onSelect={setSourceFilter}/><div className="sources-list">{story.sources.filter(source=>sourceFilter==='all'||source.language===sourceFilter).map(s=><button key={s.article_id} type="button" onClick={()=>openSource(s,story.sources,story)}><span className="source-avatar">{s.language.toUpperCase()}</span><span><b lang={s.language}>{s.headline||s.outlet}</b><small>{s.outlet} · {languageNames[s.language]}</small><small>{story.claim_source_ids.includes(s.article_id)?'Supports this summary':'Related coverage'} · {s.language.toUpperCase()} · {date(s.date)}</small><code>{s.article_id}</code></span><ChevronRight size={16}/></button>)}</div><div className="feedback-reasons"><span>Less of this because…</span>{[['repetition','Already heard it'],['technical','Too technical'],['basic','Too basic']].map(([reason,label])=><button key={reason} onClick={()=>void vote({...story,vote:0},-1,reason)}>{label}</button>)}</div></div></section></div>}
  {(settings||onboarding)&&<PreferencesModal profile={p} key={pid+String(onboarding)} topics={boot.topics} goals={boot.goals} onboarding={onboarding} memory={feed?.memory} suggestions={suggestions} onClose={closePreferences} onEdit={editPreferences} onFinish={finishOnboarding} syncing={!!pendingProfile} syncError={sync.errors[pid]} onRetry={()=>void sync.flush(pid)} onPlans={()=>setPlansOpen(true)} onPreviewStart={stop} onRestart={()=>{setSettings(false);setOnboarding(true);}}/>}
  {appearanceOpen&&<AppearanceModal value={appearance} onChange={setAppearance} onClose={()=>setAppearanceOpen(false)}/>}
  {plansOpen&&<SubscriptionModal profile={p} onEdit={editPreferences} onClose={()=>setPlansOpen(false)}/>}
  {script&&<div className="overlay" onClick={()=>setScript(null)}><section className="script-modal" role="dialog" aria-modal="true" aria-label="Script and sources" onClick={e=>e.stopPropagation()}><div className="modal-heading"><div><div className="eyebrow">THE WORDS. THE REPORTING.</div><h2>Script & sources</h2></div><button className="icon-button" aria-label="Close script" onClick={()=>setScript(null)}><X/></button></div><p className="subtle">{script.audio_mode==='summary-only'?'Audio removed. Your words and sources are kept.':script.demo_sample?'Sample podcast narration.':script.episode_audio?'Recorded podcast narration.':script.audio_mode==='elevenlabs'?'AI-generated natural narration.':'Basic voice preview. Natural audio availability depends on account setup.'} Source references are shown per chapter.</p>{script.chapters.map((ch,i)=><div className="script-chapter" key={ch.story_id}><div className="eyebrow">CHAPTER {String(i+1).padStart(2,'0')}</div><h3>{ch.title}</h3>{ch.turns?.length?<div className="dialogue-transcript">{ch.turns.map((turn,index)=><div key={index} className="dialogue-turn"><span className={turn.speaker==='maya'?'maya':'leo'}>{turn.speaker==='maya'?'Maya':'Leo'}</span><div><p>{turn.text}</p>{turn.source_ids.map(id=>{const source=ch.sources.find(item=>item.article_id===id);return source?<button key={id} className="text-button" onClick={()=>openSource(source,ch.sources)}><BookOpen size={13}/>{source.outlet}</button>:null;})}</div></div>)}</div>:<p>{ch.text}</p>}<div className="script-source-links">{ch.sources.filter(s=>ch.claim_source_ids.includes(s.article_id)).map(s=><button key={s.article_id} onClick={()=>openSource(s,ch.sources)}><BookOpen size={13}/>{s.outlet} · original report</button>)}</div><ChapterSourceReview chapter={ch} onOpenSource={openSource}/></div>)}</section></div>}
  {playerOpen&&edition&&current&&<div className="overlay" onClick={()=>setPlayerOpen(false)}><section className="expanded-player" role="dialog" aria-modal="true" aria-label="Audio player" onClick={e=>e.stopPropagation()}><div className="expanded-top"><button className="icon-button" aria-label="Minimize player" onClick={()=>setPlayerOpen(false)}><ChevronDown/></button><span className="eyebrow">YOUR DAILY PERSPECTIVE</span><button className="icon-button" aria-label="View transcript" onClick={()=>{setPlayerOpen(false);setScript(edition);}}><FileText/></button></div><div className="player-art"><div className="player-disc"><Wave/></div><span>THE LIQUID BRIEFING</span></div><div className="eyebrow">CHAPTER {chapterIndex+1} OF {edition.chapters.length}</div><h2>{current.title}</h2><p className="subtle">{edition.demo_sample?'Sample podcast · AI narration':edition.episode_audio?'Recorded podcast · AI narration':edition.audio_mode==='elevenlabs'?'Natural voice · AI narration':'Basic voice preview · estimated timing'}</p>{edition.audio_note&&<p className="subtle" role="status">{edition.audio_note}</p>}<WaveformSeek playing={playing} aria-label={edition.episode_audio?"Seek within briefing":"Seek within chapter"} min={0} max={playerDuration} value={Math.min(elapsed,playerDuration)} onPointerDown={()=>{seeking.current=true;}} onPointerCancel={()=>{seeking.current=false;setElapsed(elapsedRef.current);}} onChange={e=>setElapsed(Number(e.target.value))} onPointerUp={e=>edition.episode_audio?seekEpisode(edition,Number(e.currentTarget.value)):playChapter(edition,chapterIndex,Number(e.currentTarget.value))} onKeyUp={e=>{if(e.key.startsWith('Arrow')||e.key==='Home'||e.key==='End'){if(edition.episode_audio)seekEpisode(edition,Number(e.currentTarget.value));else playChapter(edition,chapterIndex,Number(e.currentTarget.value));}}} /><div className="time-row"><span>{time(elapsed)}</span><span>{time(playerDuration)}</span></div><div className="full-controls"><button className="icon-button" aria-label="Previous story" onClick={()=>selectChapter(chapterIndex-1)}><SkipBack size={27}/></button><button className="big-play" aria-label={playing?'Pause briefing':'Play briefing'} onClick={togglePlay}>{playing?<Pause size={29} fill="currentColor"/>:<Play size={29} fill="currentColor"/>}</button><button className="icon-button" aria-label="Next story" onClick={()=>selectChapter(chapterIndex+1)}><SkipForward size={27}/></button><button className="icon-button" aria-label="Open chapter sources" onClick={()=>{const source=current.sources.find(item=>current.claim_source_ids.includes(item.article_id))||current.sources[0];if(source)openSource(source,current.sources);}}><BookOpen size={22}/></button></div><PlaybackOptions speed={speed} onSpeed={changeSpeed} sleep={sleep} editionId={edition.id}/><div className="chapter-list">{edition.chapters.map((ch,i)=><button className={i===chapterIndex?'active':''} key={ch.story_id} onClick={()=>selectChapter(i)}><span>{i===chapterIndex&&playing?<AudioLines size={17}/>:String(i+1).padStart(2,'0')}</span><b>{ch.title}</b><small>{time(edition.episode_audio?chapterEnd(edition,i)-chapterStart(edition,i):ch.estimated_seconds)}</small></button>)}</div></section></div>}
  {summary&&<BriefSummary edition={summary} onClose={()=>setSummary(null)} onSource={openSource}/>}
  {reading&&<SourceReader reading={reading} onChange={source=>{recordView(reading.story,source);setReading({...reading,source});}} onClose={()=>setReading(null)}/>}
  {toast&&<div className="toast" role="status"><Check size={16}/>{toast}</div>}
  <div className="phone-home" aria-hidden="true"/>
 </div></div></div></div>
}

function Votes({s,onVote}:{s:Story;onVote:(s:Story,v:number)=>void}){return <div className="votes"><VoteButton value={1} active={s.vote===1} label={'More like '+s.title} onVote={()=>onVote(s,1)}/><span>{s.vote===1?'More':s.vote===-1?'Less':'For you'}</span><VoteButton value={-1} active={s.vote===-1} label={'Less like '+s.title} onVote={()=>onVote(s,-1)}/></div>}
function StoryCard({s,selected,labels,onOpen,onVote}:{s:Story;selected:string[];labels:Record<string,string>;onOpen:(s:Story)=>void;onVote:(s:Story,v:number)=>void}){return <article className="story-card"><button className="art-button" aria-label={'Read '+s.title} onClick={()=>onOpen(s)}><Art story={s}/></button><div className="story-card-body"><div className="article-meta"><span>{s.sources[0].outlet.replace('International Business Times UK','IBTimes UK')}</span><span>·</span><span>{date(s.updated_at)}</span></div><button className="headline-button" onClick={()=>onOpen(s)}><h3>{s.title}</h3></button><StoryTags story={s} selected={selected} labels={labels} limit={3}/><div className="card-footer"><Votes s={s} onVote={onVote}/><button className="source-count" onClick={()=>onOpen(s)}><ShieldCheck size={13}/>{s.sources.length} source{s.sources.length!==1?'s':''}</button></div></div></article>}
function SourceOptions({sources,selected,onSelect}:{sources:Source[];selected:NewsLanguage|'all';onSelect:(language:NewsLanguage|'all')=>void}){
 const languages=[...new Set(sources.map(source=>source.language))];
 return <div className="topic-row source-filter" aria-label="Original source editions"><button className={selected==='all'?'selected':''} aria-pressed={selected==='all'} onClick={()=>onSelect('all')}>All originals</button>{languages.map(id=><button key={id} className={selected===id?'selected':''} aria-pressed={selected===id} onClick={()=>onSelect(id)}>{languageNames[id]}</button>)}</div>;
}
function StoryTags({story,selected,labels,limit=Infinity}:{story:Story;selected:string[];labels:Record<string,string>;limit?:number}){
 const tags=[...new Set([...(selected.length?story.tags.filter(id=>selected.includes(id)):[]),...(story.primary_topic?[story.primary_topic]:[]),...story.tags])];
 const visible=Math.max(limit,story.tags.filter(id=>selected.includes(id)).length);
 return <div className="tags">{tags.slice(0,visible).map(id=><span className={`tag tag-${id} ${selected.includes(id)?'tag-matched':''}`} key={id}>{labels[id]||topicShort[id]||id}</span>)}
 {tags.length>visible&&<span className="tag-overflow" title={tags.slice(visible).map(id=>labels[id]||id).join(', ')}>+{tags.length-visible} more</span>}</div>;
}
function Skeleton(){return <div className="skeleton-grid">{[0,1,2].map(n=><div className="skeleton" key={n}/>)}</div>}

applyAppearance(readAppearance());
createRoot(document.getElementById('root')!).render(<App/>);
import './professional-theme.css';

import './theme.css';
