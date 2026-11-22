import {useEffect,useRef,useState} from 'react';
import {ArrowLeft, ArrowRight, ExternalLink, Globe2, LoaderCircle, X} from 'lucide-react';
import {languages} from './preferences';
import type {Source, Story} from './types';
import {redact} from './censor';

export type Reading = {source:Source; sources:Source[]; story?:Story;mode?:'summary'|'full'};
type OriginalArticle={article_id:string;language:string;paragraphs:string[];word_count:number};

export function SourceReader({reading,onChange,onClose}:{reading:Reading;onChange:(source:Source)=>void;onClose:()=>void}){
 const {source,sources,story}=reading;
 const editions=sources.filter(other=>other.article_id===source.article_id||
  (source.translation_key&&source.translation_key===other.translation_key));
 const languagesInGroup=[...new Set(editions.map(item=>item.language))];
 const summary=story?.summaries?.[source.language];
 const [mode,setMode]=useState<'summary'|'full'>(reading.mode||'summary');
 const [body,setBody]=useState<OriginalArticle|null>(null);
 const [error,setError]=useState('');
 const [retry,setRetry]=useState(0);
 const content=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  if(mode!=='full')return;
  const controller=new AbortController();
  setBody(null);
  setError('');
  fetch('/api/articles/'+encodeURIComponent(source.article_id),{signal:controller.signal})
   .then(async response=>{
    if(!response.ok)throw new Error(response.status===404?'The complete text is unavailable in this dataset. You can open the publisher’s article below.':'The article could not load. Please try again.');
    return response.json() as Promise<OriginalArticle>;
   })
   .then(setBody)
   .catch(cause=>{if(cause.name!=='AbortError')setError(cause.message);});
  return ()=>controller.abort();
 },[mode,source.article_id,retry]);
 useEffect(()=>{content.current?.scrollTo({top:0,behavior:'auto'});},[source.article_id,mode]);
 return <div className="overlay source-reader-overlay" onClick={onClose}>
  <article ref={content} className="source-reader" role="dialog" aria-modal="true" aria-label="Source article" onClick={event=>event.stopPropagation()}>
   <header><button className="quiet-button" onClick={onClose}><ArrowLeft size={16}/>Back</button><button aria-label="Close source article" className="icon-button" onClick={onClose}><X/></button></header>
   <div className="source-reader-body"><div className="censor-note">Censored — original reporting, publishers and sources are masked for licensing reasons.</div>
    <div className="eyebrow">Publisher ████████ · {languages[source.language]} · {new Date(source.date).toLocaleDateString()}</div>
    <h2 lang={source.language}>{redact(source.headline)||'Original headline ████████'}</h2>
    {languagesInGroup.length>1&&<div className="source-editions"><Globe2 size={16}/><div className="topic-row" aria-label="Article language">
     {languagesInGroup.map(language=><button key={language} aria-pressed={source.language===language} className={source.language===language?'selected':''} onClick={()=>{const edition=editions.find(item=>item.language===language);if(edition)onChange(edition);}}>{languages[language]}</button>)}
    </div></div>}
    <div className="reader-mode" aria-label="Reading mode">
     <button aria-pressed={mode==='summary'} onClick={()=>setMode('summary')}>Summary</button>
     <button aria-pressed={mode==='full'} onClick={()=>setMode('full')}>Full article</button>
    </div>
    {mode==='summary'?<>
     {summary?<section className="reader-summary" lang={source.language}><h3>{source.language==='de'?'Seranews-Zusammenfassung':source.language==='nl'?'Seranews-samenvatting':'Seranews story summary'}</h3>{!sources.some(item=>story?.claim_source_ids.includes(item.article_id)&&item.language===source.language)&&<span className="ai-translation-label">Translated by AI</span>}<p>{redact(summary)}</p></section>:source.snippet?<blockquote lang={source.language}>{redact(source.snippet)}…</blockquote>:<p className="field-help">Read the original article for this story.</p>}
    </>:<section className="original-article" aria-label="Full article text" lang={source.language}>
     {body?.article_id===source.article_id?<><div className="article-reading-meta">{Math.max(1,Math.ceil(body.word_count/210))} min read · Original reporting</div>{body.paragraphs.map((paragraph,index)=><p key={index}>{redact(paragraph)}</p>)}</>:error?<div className="article-load-error" role="alert"><p>{error}</p><button className="quiet-button" onClick={()=>setRetry(value=>value+1)}>Try again</button></div>:<p className="article-loading" role="status"><LoaderCircle className="spin" size={16}/>Loading article…</p>}
    </section>}
    <div className="reader-actions" role="group" aria-label="Article actions">
     {mode==='summary'&&<button type="button" className="primary-button read-full-article" onClick={()=>setMode('full')}><span>Read full article</span><ArrowRight size={16}/></button>}
     <span className="publisher-link reader-publisher-action" aria-disabled="true"><span>Publisher ████████</span></span>
    </div>
   </div>
  </article>
 </div>;
}
