import type {Edition} from './types';

// Measured offsets are supplied with episode audio. Estimates keep older editions usable.
export function chapterStart(edition:Edition,index:number):number{
 const chapter=edition.chapters[index];
 if(chapter&&Number.isFinite(chapter.start_seconds))return Math.max(0,chapter.start_seconds!);
 return edition.chapters.slice(0,index).reduce((total,item)=>total+item.estimated_seconds,0);
}
export function chapterEnd(edition:Edition,index:number):number{
 const chapter=edition.chapters[index];
 if(chapter&&Number.isFinite(chapter.end_seconds))return Math.max(chapterStart(edition,index),chapter.end_seconds!);
 return index+1<edition.chapters.length?chapterStart(edition,index+1):chapterStart(edition,index)+(chapter?.estimated_seconds||0);
}
export function episodeDuration(edition:Edition):number{
 const duration=edition.episode_audio?.duration_seconds;
 return duration&&Number.isFinite(duration)&&duration>0?duration:chapterEnd(edition,edition.chapters.length-1);
}
export function chapterAt(edition:Edition,seconds:number):number{
 let index=0;
 while(index+1<edition.chapters.length&&seconds>=chapterStart(edition,index+1))index++;
 return index;
}
