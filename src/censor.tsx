// Dataset-licensing censoring: original reporting, publishers and sources are masked.
export function redact(text?:string):string{
	if(!text)return '';
	return '█'.repeat(Math.min(text.length, 600));
}
export const CENSOR_SPEECH='Censored. Because of data privacy, we censored the voice examples.';
