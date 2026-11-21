import type {Profile} from './types';
import './profile-avatar.css';

const portraits=new Set(['mila','jonas','alex','sam','free-demo','medium-demo']);

export function Avatar({p,small=false}:{p:Profile;small?:boolean}){
 const portrait=portraits.has(p.id);
 return <span className={'avatar '+p.color+(small?' avatar-small':'')+(portrait?' avatar-portrait':'')} aria-hidden="true">
  {portrait?<img src={'/avatars/'+p.id+'.svg'} alt="" draggable={false}/>:p.initials}
 </span>;
}
