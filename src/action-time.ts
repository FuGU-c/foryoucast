let last=0;
/** Preserve action order even when several clicks share the same millisecond. */
export function actionTime(){last=Math.max(Date.now(),last+1);return new Date(last).toISOString();}
