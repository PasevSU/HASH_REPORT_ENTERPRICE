'use strict';
class RecoveryPolicy {
 constructor({baseMs=2000,maxMs=300000,clock=()=>Date.now()}={}){this.baseMs=baseMs;this.maxMs=maxMs;this.clock=clock;this.failures=new Map()}
 fail(key){const prev=this.failures.get(key);const attempts=Math.min(30,(prev?.attempts||0)+1);const delay=Math.min(this.maxMs,this.baseMs*2**Math.min(20,attempts-1));const entry={attempts,nextRetry:this.clock()+delay,delay};this.failures.set(key,entry);return {...entry}}
 success(key){this.failures.delete(key)}
 ready(key){const state=this.failures.get(key);return !state||this.clock()>=state.nextRetry}
 state(key){return this.failures.get(key)||null}
 forget(key){this.failures.delete(key)}
}
module.exports={RecoveryPolicy};
