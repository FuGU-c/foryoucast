import {ArrowDownRight,ArrowUpRight,SlidersHorizontal} from 'lucide-react';
import type {Profile,Topic} from './types';
export function TopicBalance({profile,topics,onWeight}:{profile:Profile;topics:Topic[];onWeight:(id:string,weight:number)=>void}){
 const learned=profile.learned_interests||{},weights=profile.effective_interests||profile.interests;
 const changed=topics.filter(topic=>Math.abs(learned[topic.id]||0)>.0001).sort((a,b)=>Math.abs(learned[b.id])-Math.abs(learned[a.id])).slice(0,4);
 return <section className="topic-balance" aria-label="Learning from your votes"><header><span className="balance-icon"><SlidersHorizontal size={16}/></span><div><h3>Your topic mix</h3><p>Your votes fine-tune how much you see.</p></div><span className="balance-live">Live</span></header>
 {!changed.length?<p className="balance-empty">Like a story for more of its topics. Dislike it for less. You can adjust the balance yourself, too.</p>:<div className="learned-topics">{changed.map(topic=><div className="learned-topic" key={topic.id}><div className="learned-topic-heading"><span>{learned[topic.id]>0?<ArrowUpRight size={14}/>:<ArrowDownRight size={14}/>}<b>{topic.label}</b><small>{learned[topic.id]>0?'More like this':'Less like this'}</small></span><output aria-label={topic.label+' topic balance'}>{Math.round((weights[topic.id]||0)*20)}%</output></div><input aria-label={topic.label+' amount'} type="range" min="0" max="5" step="0.01" value={Number((weights[topic.id]||0).toFixed(2))} onChange={event=>onWeight(topic.id,Number(event.target.value))}/><div className="balance-scale"><span>Less</span><span>More</span></div></div>)}</div>}
 <p className="balance-footnote">Each topic has its own balance. Your manual changes take priority.</p>
 </section>;
}
