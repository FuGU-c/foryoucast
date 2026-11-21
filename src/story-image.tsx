import {useState} from 'react';
import {BarChart3,Coins,Cpu,Globe2,Landmark,Leaf,Newspaper,Palette, type LucideIcon} from 'lucide-react';
import type {Story} from './types';
import './story-image.css';

export function storyImageUrls(story:Story):string[]{
 const primary=story.sources.filter(source=>story.claim_source_ids.includes(source.article_id));
 const translations=new Set(primary.map(source=>source.translation_key).filter(Boolean));
 const supporting=story.claim_source_ids.length
  ?story.sources.filter(source=>story.claim_source_ids.includes(source.article_id)||!!source.translation_key&&translations.has(source.translation_key))
  :story.sources;
 return [...new Set([...primary,...supporting].flatMap(source=>{
  const url=source.image_url?.trim();
  if(!url)return [];
  try{return new URL(url).protocol==='https:'?[url]:[];}catch{return [];}
 }))];
}

function Picture({story,urls,large}:{story:Story;urls:string[];large:boolean}){
 const [candidate,setCandidate]=useState(0),[loaded,setLoaded]=useState(false);
 const topic=story.primary_topic||story.tags[0];
 const icons:Record<string,LucideIcon>={markets:BarChart3,economy:Landmark,forex:Coins,crypto:Coins,technology:Cpu,energy:Leaf,world:Globe2,culture:Palette,money:Landmark};
 const Icon=icons[topic]||Newspaper;
 const url=urls[candidate];
 return <div className={'story-art story-image '+(large?'art-large ':'')+(loaded?'image-ready':'image-placeholder')} aria-hidden="true">
  <div className="story-image-illustration"><span className="story-image-orbit"/><span className="story-image-orbit orbit-offset"/><Icon className="story-image-symbol" size={64}/><span className="story-image-caption">EDITORIAL ILLUSTRATION</span></div>
  {url&&<img key={url} src={url} alt="" draggable={false} decoding="async" referrerPolicy="no-referrer" onLoad={()=>setLoaded(true)} onError={()=>{setLoaded(false);setCandidate(index=>index+1);}}/>}
 </div>;
}

export function StoryImage({story,large=false}:{story:Story;large?:boolean}){
 const urls=storyImageUrls(story);
 // A recycled Discover card must not inherit another article's failure index.
 return <Picture key={JSON.stringify([story.id,urls])} story={story} urls={urls} large={large}/>;
}
