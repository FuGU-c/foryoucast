/** Interpret trackpad gestures while suppressing the inertial tail of a swipe. */
export class SwipeNavigation {
 private lastEvent=-Infinity;
 private lastCommit=-Infinity;
 private direction=0;
 private total=0;
 private committed=false;
 private magnitude=0;

 reset(){
  this.lastEvent=-Infinity;
  this.lastCommit=-Infinity;
  this.direction=0;
  this.total=0;
  this.committed=false;
  this.magnitude=0;
 }

 wheel(deltaX:number,deltaY:number,now:number):number {
  const delta=Math.abs(deltaX)>Math.abs(deltaY)?deltaX:deltaY;
  const magnitude=Math.abs(delta);
  if(magnitude<.3)return 0;
  const direction=Math.sign(delta);
  const pause=now-this.lastEvent;
  const reversed=direction!==this.direction;
  // A fresh acceleration after a decaying tail identifies a second forward swipe.
  const freshPush=this.committed&&now-this.lastCommit>220&&magnitude>12&&magnitude>this.magnitude*2.2;
  if(pause>170||reversed||freshPush){this.total=0;this.committed=false;}
  this.lastEvent=now;
  this.direction=direction;
  this.magnitude=magnitude;
  if(this.committed)return 0;
  this.total+=magnitude;
  if(this.total<24)return 0;
  this.committed=true;
  this.lastCommit=now;
  return direction;
 }
}
