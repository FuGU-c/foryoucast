import {useRef,useState} from 'react';
import {ArrowLeft, ArrowRight, Check, ChevronRight, Compass, Headphones, Plus, RefreshCw, Upload, X} from 'lucide-react';
import {VoicePreferences} from './voice-preferences';
import {planFor} from './plans';
import {SubscriptionCard} from './subscription';
import './account-settings.css';
import type {Goal, GoalId, Memory, NewsLanguage, Profile, TagSuggestion, Topic} from './types';
import {nextNewsLanguages,toggleGoal as updateGoal,updateTag,type ProfileChange} from './live-preferences';
import {TopicQuestion} from './topic-question';
import {TopicBalance} from './topic-balance';

export const languages:Record<NewsLanguage,string>={en:'English',de:'Deutsch',nl:'Nederlands'};
const depthLabels={simple:'Simple explanations',balanced:'A little context',detailed:'Detailed explanations'} as const;

export function extractSymbols(text:string, csv:boolean):string[]{
 const lines=text.trim().split(/\r?\n/).filter(Boolean);
 if(!lines.length)return [];
 const symbolPattern=/^[A-Z][A-Z0-9]{0,7}(?:[.-][A-Z0-9]{1,5})?$/;
 const parseRow=(row:string,delimiter:string)=>(row.match(new RegExp(`(?:^|[${delimiter}])("(?:[^"]|"")*"|[^${delimiter}]*)`,'g'))||[])
  .map((cell,i)=>cell.slice(i?1:0).trim().replace(/^"|"$/g,'').replace(/""/g,'"'));
 const delimiter=lines[0].includes(';')?';':lines[0].includes('\t')?'\t':',';
 const header=parseRow(lines[0],delimiter);
 const symbolColumn=header.findIndex(cell=>/^(ticker|symbol|ticker symbol|stock symbol)$/i.test(cell));
 if(csv&&symbolColumn<0)throw new Error('Use a CSV with a Symbol or Ticker column, or a text file with one ticker per line.');
 const candidates=csv?lines.slice(1).map(row=>parseRow(row,delimiter)[symbolColumn]):lines.flatMap(row=>row.split(/[\s,;]+/));
 return [...new Set(candidates.map(symbol=>symbol?.trim().toUpperCase()).filter(symbol=>symbol&&symbolPattern.test(symbol)))].slice(0,50);
}

type Props = {
 profile:Profile; topics:Topic[]; goals:Goal[]; onboarding:boolean; memory?:Memory; suggestions?:TagSuggestion[];
 onClose:()=>void; onEdit:(change:ProfileChange)=>void; onFinish:()=>void; onRestart:()=>void;
 syncError?:string; syncing:boolean; onRetry:()=>void;
 onPlans:()=>void;onPreviewStart:()=>void;
};

export function PreferencesModal({profile:draft,topics,goals,onboarding,memory,suggestions=[],onClose,onEdit,onFinish,onRestart,syncError,syncing,onRetry,onPlans,onPreviewStart}:Props){
 const [step,setStep]=useState(0);
 const [watchlistOpen,setWatchlistOpen]=useState(false);
 const [customTime,setCustomTime]=useState(![2,5,10].includes(draft.duration));
 const [durationInput,setDurationInput]=useState(String(draft.duration));
 const [nameInput,setNameInput]=useState(draft.name);
 const [fileNote,setFileNote]=useState('');
 const [manualSymbol,setManualSymbol]=useState('');
 const fileInput=useRef<HTMLInputElement>(null);
 const selectedGoals=goals.filter(goal=>draft.goals.includes(goal.id));
 const suggestedIds=new Set(selectedGoals.flatMap(goal=>goal.tags));
 const recommended=topics.filter(topic=>suggestedIds.has(topic.id));
 const balance=draft.effective_interests||draft.interests;
 const selectedTopics=topics.filter(topic=>(balance[topic.id]||0)>0);
 const adjustableTopics=topics.filter(topic=>(balance[topic.id]||0)>0||!!draft.learned_interests?.[topic.id]);
 const allExtraTopics=topics.filter(topic=>!suggestedIds.has(topic.id));
 const maxMinutes=planFor(draft).maxMinutes;
 const durationValid=Number.isInteger(draft.duration)&&draft.duration>=1&&draft.duration<=maxMinutes;
 const sections=[{label:'Interests',icon:Compass},{label:'Listening',icon:Headphones}];
 const show=(section:number)=>section===2?step===1:step===0;

 function update<K extends keyof Profile>(key:K,value:Profile[K]){
  onEdit(previous=>({...previous,[key]:value}));
 }
 function toggleGoal(id:GoalId){
  onEdit(previous=>updateGoal(previous,id,goals));
 }
 function changeLanguage(id:NewsLanguage){
  onEdit(previous=>({...previous,news_languages:nextNewsLanguages(id,previous.news_languages)}));
 }
 function setTag(id:string,weight:number){
  onEdit(previous=>updateTag(previous,id,weight));
 }
 function toggleTag(id:string){onEdit(previous=>updateTag(previous,id,(previous.effective_interests||previous.interests)[id]>0?0:3));}
 function addSymbols(symbols:string[]){
  onEdit(previous=>({...previous,symbols:[...new Set([...previous.symbols,...symbols])].slice(0,50)}));
 }
 async function importFile(file?:File){
  if(!file)return;
  if(!/\.(csv|txt|tsv)$/i.test(file.name)||file.size>1_000_000){
   setFileNote('Choose a CSV, TSV or text file under 1 MB.');
   return;
  }
  try{
   const symbols=extractSymbols(await file.text(),/\.(csv|tsv)$/i.test(file.name));
   if(!symbols.length)throw new Error('No ticker symbols found.');
   addSymbols(symbols);
   setFileNote(`Added to your watchlist: ${symbols.join(', ')}.`);
  }catch(error){setFileNote((error as Error).message);}
  finally{if(fileInput.current)fileInput.current.value='';}
 }
 function submit(){
  if(onboarding&&step===0){setStep(1);return;}
  if(onboarding)onFinish();
  else onClose();
 }
 const tagButton=(topic:Topic)=><button key={topic.id} aria-pressed={balance[topic.id]>0} className={balance[topic.id]>0?'chosen':''} onClick={()=>toggleTag(topic.id)}>
  {balance[topic.id]>0?<Check size={15}/>:<Plus size={15}/>} {topic.label}
 </button>;

 return <div className="overlay preferences-overlay" onClick={onClose}>
  <section className={'preferences-modal '+(onboarding?'onboarding-modal':'')} role="dialog" aria-modal="true" aria-label={onboarding?'Personalize your briefing':'Preferences'} onClick={event=>event.stopPropagation()}>
   <header className="modal-heading">
    <div><div className="eyebrow">{onboarding?`STEP ${step+1} OF 2`:'SERANEWS'}</div><h2>{onboarding?['Make it yours','Listen your way'][step]:'Settings'}</h2></div>
    <button className="icon-button" aria-label="Close preferences" onClick={onClose}><X/></button>
   </header>
   <nav className="settings-tabs" aria-label="Settings sections">{sections.map(({label,icon:Icon},i)=><button key={label} aria-pressed={step===i} onClick={()=>setStep(i)}><Icon size={17}/>{label}</button>)}</nav>
   <div className="preferences-content preferences-v2" key={step}>
    {show(0)&&<>
     <fieldset className="field-label plain-fieldset"><legend>What do you want to hear about?</legend>
      <p className="field-help">Pick one or more. Your topics update below.</p>
      <div className="goal-options">{goals.map(goal=><label className={'goal-option '+(draft.goals.includes(goal.id)?'chosen':'')} key={goal.id}>
       <input type="checkbox" checked={draft.goals.includes(goal.id)} onChange={()=>toggleGoal(goal.id)}/>
       <span><b>{goal.label}</b></span>
      </label>)}</div>
     </fieldset>
     <fieldset className="field-label plain-fieldset"><legend>On your radar</legend><p className="field-help">{recommended.length||selectedTopics.length?'Tap a topic to follow or remove it.':'Pick an interest above or browse more topics below.'}</p><div className="interest-options">{(recommended.length?topics.filter(topic=>suggestedIds.has(topic.id)||balance[topic.id]>0):selectedTopics).map(tagButton)}</div></fieldset>
     <TopicBalance profile={draft} topics={topics} onWeight={setTag}/>
     <TopicQuestion suggestions={suggestions} onFollow={id=>setTag(id,3)}/>
    </>}
    {show(1)&&<>
     <details className="settings-details"><summary>More topics and priorities<ChevronRight size={15}/></summary>
      <div className="interest-options">{allExtraTopics.map(tagButton)}</div>
      <div className="tag-weight-list">{adjustableTopics.map(topic=><label key={topic.id}><span>{topic.label}<small>{Math.round((balance[topic.id]||0)*20)}% · {draft.learned_interests?.[topic.id]?'Adjusted from feedback':'Your choice'}</small></span><input aria-label={topic.label+' priority'} type="range" min={0} max={5} step={0.01} value={Number((balance[topic.id]||0).toFixed(2))} onChange={event=>setTag(topic.id,Number(event.target.value))}/></label>)}</div>
     </details>
     <details className="settings-details"><summary>Add a specific interest<ChevronRight size={15}/></summary><label className="field-label">What else should we look for?<textarea maxLength={500} value={draft.custom_interests} onChange={event=>update('custom_interests',event.target.value)} placeholder="For example, renewable energy in Europe"/></label></details>
     <section className="watchlist-card">
      <button className="watchlist-heading" onClick={()=>setWatchlistOpen(open=>!open)} aria-expanded={watchlistOpen}>
       <span><b>Stock watchlist</b><small>{draft.symbols.length?`${draft.symbols.length} symbols followed`:'See more news about the stocks you follow.'}</small></span><ChevronRight size={17}/>
      </button>
      {watchlistOpen&&<div className="portfolio-import">
      <form className="ticker-entry" onSubmit={event=>{event.preventDefault();const symbols=extractSymbols(manualSymbol,false);if(symbols.length){addSymbols(symbols);setManualSymbol('');setFileNote('');}else setFileNote('Enter a stock symbol, such as NVDA.');}}>
       <input aria-label="Ticker symbol" value={manualSymbol} onChange={event=>setManualSymbol(event.target.value)} placeholder="Stock symbol, e.g. NVDA"/>
       <button className="quiet-button" type="submit">Add</button>
      </form>
      <div className="interest-options">{draft.symbols.map(symbol=><button key={symbol} aria-label={`Remove ${symbol}`} className="chosen" onClick={()=>onEdit(previous=>({...previous,symbols:previous.symbols.filter(item=>item!==symbol)}))}>{symbol}<X size={13}/></button>)}</div>
      <input ref={fileInput} type="file" accept=".csv,.tsv,.txt" hidden onChange={event=>void importFile(event.target.files?.[0])}/>
      <button className="import-action" onClick={()=>fileInput.current?.click()}><Upload size={15}/>Import a list instead</button>
      <p className="field-help">Choose a CSV with a “Symbol” column or a text list. Seranews keeps only the stock symbols.</p>
      {fileNote&&<p className="field-help" role="status">{fileNote}</p>}
     </div>}
     </section>
    </>}
    {show(2)&&<>
     <fieldset className="field-label plain-fieldset"><legend>Podcast language</legend><div className="segmented">{Object.entries(languages).map(([id,label])=><button aria-pressed={draft.language===id} key={id} className={draft.language===id?'selected':''} onClick={()=>update('language',id as NewsLanguage)}>{label}</button>)}</div></fieldset>
     <VoicePreferences profile={draft} onEdit={onEdit} onPlans={onPlans} onPreviewStart={onPreviewStart}/>
     <section className="translation-setting"><label><span><b>News beyond your languages</b><small>Include foreign-language reporting in your podcast language.</small></span><input type="checkbox" aria-label="Translate news into my podcast language" checked={draft.plan!=='free'&&!!draft.plan&&!!draft.translate_news} onChange={event=>draft.plan!=='free'&&!!draft.plan?update('translate_news',event.target.checked):onPlans()}/></label><p>{draft.plan!=='free'&&!!draft.plan?'The demo can use reviewed translated summaries. Live article translation is coming with AI integration.':'Available with Flow and Horizon. Original articles keep their source languages.'}</p></section>
     <fieldset className="field-label news-language-options"><legend>Article languages</legend><p className="field-help">Choose the original languages you want in Discover.</p>
      <div className="interest-options">{(Object.keys(languages) as NewsLanguage[]).map(id=><label key={id} className={draft.news_languages.includes(id)?'chosen':''}><input type="checkbox" checked={draft.news_languages.includes(id)} disabled={draft.news_languages.length===1&&draft.news_languages[0]===id} onChange={()=>changeLanguage(id)}/>{languages[id]}</label>)}</div>
     </fieldset>
     <fieldset className="field-label plain-fieldset"><legend>Explanation depth</legend><div className="segmented">{Object.entries(depthLabels).map(([id,label])=><button key={id} aria-pressed={draft.depth===id} className={draft.depth===id?'selected':''} onClick={()=>update('depth',id as Profile['depth'])}>{label}</button>)}</div></fieldset>
     <fieldset className="field-label plain-fieldset"><legend>Podcast length</legend><div className="segmented">
      {[2,5,maxMinutes].map(minutes=><button key={minutes} aria-pressed={!customTime&&draft.duration===minutes} className={!customTime&&draft.duration===minutes?'selected':''} onClick={()=>{setCustomTime(false);update('duration',minutes);}}>~{minutes} min</button>)}
      <button aria-pressed={customTime} className={customTime?'selected':''} onClick={()=>{setDurationInput(String(draft.duration));setCustomTime(true);}}>Custom</button>
     </div>
     {customTime&&<label className="field-label">Approximate minutes (1–{maxMinutes})<input type="number" min={1} max={maxMinutes} step={1} value={durationInput} onChange={event=>{const number=event.target.valueAsNumber;setDurationInput(event.target.value);if(Number.isInteger(number)&&number>=1&&number<=maxMinutes)update('duration',number);}} onBlur={()=>setDurationInput(String(draft.duration))}/></label>}
     <p className="field-help">Approximate length at 1× speed. Actual audio length varies; fewer matching stories can make a shorter briefing.</p>
     </fieldset>
     <label className="field-label schedule-check"><input type="checkbox" checked={draft.scheduled} onChange={event=>update('scheduled',event.target.checked)}/>Prepare an edition before my wake-up time</label>
     {draft.scheduled&&<div className="time-settings">
      <label className="field-label">Ready by<input type="time" value={draft.wake_time} onChange={event=>{if(event.target.value)update('wake_time',event.target.value);}}/></label>
      <label className="field-label">Timezone<select value={draft.timezone} onChange={event=>update('timezone',event.target.value)}>{['Europe/Brussels','Europe/Amsterdam','Europe/Berlin','Europe/London','America/New_York','Asia/Tokyo'].map(zone=><option key={zone}>{zone}</option>)}</select></label>
     </div>}
     <details className="settings-details"><summary>Display name<ChevronRight size={15}/></summary><label className="field-label">Your name<input maxLength={40} value={nameInput} onChange={event=>{const value=event.target.value;setNameInput(value);if(value.trim())update('name',value.trim());}} onBlur={()=>setNameInput(nameInput.trim()||draft.name)}/></label></details>
    </>}
    <details className="preference-memory settings-details">
     <summary>What Seranews has learned<ChevronRight size={15}/></summary>
     <p><b>{languages[draft.language]}</b> · {depthLabels[draft.depth]} · {durationValid?`~${draft.duration} min`:'choose a duration'}</p>
     <p><b>On your radar:</b> {selectedTopics.map(topic=>topic.label).join(', ')||'No tags selected yet.'}</p>
     {!!draft.symbols.length&&<p><b>Watchlist:</b> {draft.symbols.join(', ')}</p>}
     <p><b>You’ve liked:</b> {memory?.liked_topics?.join(', ')||'No votes yet.'}</p>
     <p><b>You’ve liked less:</b> {memory?.disliked_topics?.join(', ')||'No votes yet.'}</p>
    </details>
    <SubscriptionCard profile={draft} onOpen={onPlans}/>
    {!onboarding&&<button className="text-button restart-button" onClick={onRestart}><RefreshCw size={15}/>Go through personalization again</button>}
   </div>
   <div className="live-preference-strip" aria-live="polite"><span>{selectedTopics.length} {selectedTopics.length===1?'tag':'tags'}</span><span>{depthLabels[draft.depth]}</span><span>{durationValid?`~${draft.duration} min`:'Set length'}</span></div>
   <footer className="modal-footer">
    {onboarding&&step>0?<button className="quiet-button" onClick={()=>setStep(step-1)}><ArrowLeft size={15}/>Back</button>:<span className="subtle" role="status">{syncError|| (syncing?'Applying changes…':'Changes apply automatically.')}{syncError&&<button className="text-button" onClick={onRetry}>Retry</button>}</span>}
    <button className="primary-button" onClick={submit}>
     {onboarding&&step===0?'Continue':'Done'}<ArrowRight size={15}/>
    </button>
   </footer>
  </section>
 </div>;
}
