import type {Profile} from './types';
export type PlanId='free'|'plus'|'premium';
export const plans={free:{name:'Free',price:'$0',maxMinutes:7},plus:{name:'Flow',price:'$ A BIT',maxMinutes:15},premium:{name:'Horizon',price:'$ A LOT',maxMinutes:40}} as const;
export function planFor(profile:Profile){return plans[profile.plan||'free'];}
export function normalizePlan(profile:Profile):Profile{
 return {...profile,duration:Math.max(1,Math.min(planFor(profile).maxMinutes,profile.duration)),...(profile.plan==='free'||!profile.plan?{tts_provider:'device' as const,translate_news:false}:{}),ai_settings:{provider:'demo',personalization_model:'',summary_model:'',script_model:''}};
}
