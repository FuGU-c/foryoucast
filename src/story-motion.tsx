import {useLayoutEffect,useRef, type ReactNode} from 'react';
import type {Story} from './types';

type Props = {
 stories:Story[];
 layout:'story-grid'|'reels-list';
 renderStory:(story:Story)=>ReactNode;
 totalMatches?:number;
};

export function StoryMotion({stories,layout,renderStory,totalMatches}:Props){
 const container=useRef<HTMLDivElement>(null);
 const ghosts=useRef<HTMLDivElement>(null);
 const previous=useRef(new Map<string,{x:number;y:number;width:number;height:number;node:HTMLElement}>());
 const status=useRef<HTMLSpanElement>(null);
 const signature=stories.map(story=>story.id).join('|');

 useLayoutEffect(()=>{
  const list=container.current;
  const layer=ghosts.current;
  if(!list||!layer)return;
  const old=previous.current;
  const bounds=list.getBoundingClientRect();
  const next=new Map<string,{x:number;y:number;width:number;height:number;node:HTMLElement}>();
  for(const node of list.querySelectorAll<HTMLElement>(':scope > [data-story]')){
   const rect=node.getBoundingClientRect();
   next.set(node.dataset.story!,{x:rect.left-bounds.left+list.scrollLeft,y:rect.top-bounds.top,width:rect.width,height:rect.height,node});
  }
  previous.current=next;
  const added=[...next.keys()].filter(id=>!old.has(id));
  const removed=[...old.keys()].filter(id=>!next.has(id));
  if(old.size&&status.current){
   const moved=[...next].some(([id,position])=>{const before=old.get(id);return before&&(Math.abs(position.x-before.x)+Math.abs(position.y-before.y)>1);});
   status.current.textContent=[added.length?`${added.length} shown`:'',removed.length?`${removed.length} hidden`:'',!added.length&&!removed.length&&moved?'Order updated':''].filter(Boolean).join(' · ');
  }
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  layer.replaceChildren();
  const animations:Animation[]=[];
  for(const [id,position] of next){
   const before=old.get(id);
   position.node.getAnimations().forEach(animation=>animation.cancel());
   if(!before){
    animations.push(position.node.animate([{opacity:0,transform:'translateY(10px) scale(.985)'},{opacity:1,transform:'none'}],{duration:245,easing:'cubic-bezier(.2,.7,.25,1)'}));
   }else{
    const dx=before.x-position.x,dy=before.y-position.y;
    if(Math.abs(dx)+Math.abs(dy)>1)animations.push(position.node.animate([{transform:`translate(${dx}px,${dy}px)`},{transform:'none'}],{duration:255,easing:'cubic-bezier(.2,.75,.25,1)'}));
   }
  }
  if(!next.size&&old.size)layer.style.height=`${Math.min(540,Math.max(...[...old.values()].map(card=>card.y+card.height)))}px`;
  else layer.style.height='';
  for(const id of removed){
   const oldCard=old.get(id)!;
   if(oldCard.y>list.clientHeight+240)continue;
   const ghost=oldCard.node.cloneNode(true) as HTMLElement;
   ghost.inert=true;
   Object.assign(ghost.style,{position:'absolute',left:`${oldCard.x-list.scrollLeft}px`,top:`${oldCard.y}px`,width:`${oldCard.width}px`});
   layer.append(ghost);
   const animation=ghost.animate([{opacity:.8,transform:'none'},{opacity:0,transform:'translateY(-7px) scale(.97)'}],{duration:170,easing:'ease-in'});
   animation.onfinish=()=>ghost.remove();
   animations.push(animation);
  }
  return ()=>{animations.forEach(animation=>animation.cancel());layer.replaceChildren();layer.style.height='';};
 },[signature]);

 return <div className={'motion-section '+layout+'-section'}>
  <div className="card-change-status" aria-live="polite"><span>{totalMatches!==undefined&&totalMatches>stories.length?`Showing ${stories.length} of ${totalMatches} matches`:`${stories.length} ${stories.length===1?'story':'stories'}`}</span><span ref={status}/></div>
  <div className="motion-shell">
   <div ref={container} className={layout}>{stories.map(story=><div className="animated-story" key={story.id} data-story={story.id}>{renderStory(story)}</div>)}</div>
   <div ref={ghosts} className="departing-cards" aria-hidden="true"/>
  </div>
 </div>;
}
