import {useState} from 'react';
import type {Story} from './types';

/** Ranking can change immediately; a reader's already-issued deck cannot. */
export function reconcileStoryDeck(previous:Story[],incoming:Story[]):Story[]{
 const latest=new Map(incoming.map(story=>[story.id,story]));
 const seen=new Set<string>();
 const result:Story[]=[];
 for(const story of [...previous,...incoming]){
  if(seen.has(story.id))continue;
  seen.add(story.id);
  result.push(latest.get(story.id)||story);
 }
 return result;
}

export function useStableStoryDeck(incoming:Story[],scope:string){
 const [snapshot,setSnapshot]=useState(()=>({scope,incoming,stories:reconcileStoryDeck([],incoming)}));
 if(snapshot.scope!==scope||snapshot.incoming!==incoming){
  const next={scope,incoming,stories:reconcileStoryDeck(snapshot.scope===scope?snapshot.stories:[],incoming)};
  setSnapshot(next);
  return next.stories;
 }
 return snapshot.stories;
}
