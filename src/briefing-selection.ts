import type {Edition} from './types';

export function latestPlayableBriefing(editions:Edition[], profileId:string):Edition|undefined {
 return editions.filter(edition=>edition.profile_id===profileId
  &&edition.audio_mode!=='summary-only'&&!edition.audio_removed_at
  &&edition.chapters.length>0&&(!edition.status||edition.status==='ready'))
  .sort((a,b)=>(Date.parse(b.created_at)||0)-(Date.parse(a.created_at)||0)
   ||Number(!!a.demo_sample)-Number(!!b.demo_sample))[0];
}
