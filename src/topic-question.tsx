import {useState} from 'react';
import {ArrowRight, Check, Plus, Sparkles} from 'lucide-react';
import type {TagSuggestion} from './types';

export function TopicQuestion({suggestions,onFollow}:{suggestions:TagSuggestion[];onFollow:(id:string)=>void}){
 const [skipped,setSkipped]=useState<Record<string,string>>({});
 const [lastFollowed,setLastFollowed]=useState('');
 const topic=suggestions.find(item=>skipped[item.id]!==item.latest);
 const skip=()=>{if(topic){setSkipped(current=>({...current,[topic.id]:topic.latest}));setLastFollowed('');}};
 if(!topic)return suggestions.length||lastFollowed? <div className="topic-question-end"><Check size={16}/><span>{lastFollowed?`Following ${lastFollowed}`:'You’ve seen these suggestions.'}</span>{!!suggestions.length&&<button onClick={()=>setSkipped({})}>See again</button>}</div>:null;

 return <section className="topic-question" aria-label="Suggested interests">
  <div className="topic-question-overline"><Sparkles size={13}/> From recent coverage</div>
  <div className="topic-question-content" key={topic.id+topic.latest}>
   <h3>Follow {topic.label}?</h3>
   <p>{topic.example||`${topic.count} recent ${topic.count===1?'story':'stories'}`}</p>
   <div className="topic-question-actions">
    <button className="follow-topic-button" onClick={()=>{setLastFollowed(topic.label);onFollow(topic.id);setSkipped(current=>({...current,[topic.id]:topic.latest}));}}><Plus size={15}/>Follow topic</button>
    <button className="skip-topic-button" onClick={skip}>Skip<ArrowRight size={12}/></button>
   </div>
  </div>
  {!!lastFollowed&&<div className="topic-question-feedback" role="status"><Check size={13}/> Following {lastFollowed}</div>}
 </section>;
}
