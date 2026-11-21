export type EditionPeriod='all'|'today'|'week'|'month'|'custom';
export const periodLabels={all:'All editions',today:'Today',week:'This week',month:'This month',custom:'Selected date'};

export function localToday(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Brussels',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
 const part=(type:string)=>parts.find(item=>item.type===type)!.value;
 return `${part('year')}-${part('month')}-${part('day')}`;
}

export function editionDay(edition:{created_at:string}){return localToday(new Date(edition.created_at));}

export function matchesEditionPeriod(day:string,period:EditionPeriod,custom:string,today:string){
 if(period==='all')return true;
 if(period==='custom')return day===custom;
 if(day>today)return false;
 if(period==='today')return day===today;
 if(period==='month')return day>=today.slice(0,7)+'-01';
 const monday=new Date(today+'T12:00:00Z');
 monday.setUTCDate(monday.getUTCDate()-(monday.getUTCDay()+6)%7);
 return day>=monday.toISOString().slice(0,10);
}
