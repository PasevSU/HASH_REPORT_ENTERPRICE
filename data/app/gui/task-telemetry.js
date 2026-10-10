'use strict';
class TaskTelemetry {
 constructor({clock=()=>Date.now(),alpha=.25}={}){if(!(alpha>0&&alpha<=1))throw Error('Invalid smoothing factor');this.clock=clock;this.alpha=alpha;this.stats=new Map()}
 async measure(key,fn){const start=this.clock();let ok=false;try{const value=await fn();ok=value?.ok!==false;return value}finally{this.record(key,Math.max(0,this.clock()-start),ok)}}
 record(key,ms,ok=true){if(typeof key!=='string'||!Number.isFinite(ms)||ms<0)throw Error('Invalid telemetry');const previous=this.stats.get(key);const n=(previous?.count||0)+1;const entry={count:n,avgMs:previous?previous.avgMs*(1-this.alpha)+ms*this.alpha:ms,lastMs:ms,failures:(previous?.failures||0)+(ok?0:1)};this.stats.set(key,entry);return {...entry}}
 get(key){const value=this.stats.get(key);return value?{...value}:null}
 snapshot(){return Object.fromEntries([...this.stats].map(([key,value])=>[key,{...value}]))}
}
module.exports={TaskTelemetry};
