'use strict';
const path=require('node:path');
function isNetworkPath(p){return process.platform==='win32'?/^\\\\[^\\]+\\[^\\]+/.test(p):/^\/\//.test(p)}
class WatchPolicy{
 constructor({now=()=>Date.now()}={}){this.now=now;this.mode='normal';this.lagMs=0;this.lastRun=new Map();this.latencies=new Map()}
 update(metrics={}){this.mode=metrics.mode==='throttled'?'throttled':'normal';this.lagMs=Number.isFinite(metrics.eventLoopLagMs)?metrics.eventLoopLagMs:0}
 delay(dir){const network=isNetworkPath(dir);const base=this.mode==='throttled'?(network?15000:6000):(network?3500:1200);return Math.max(base,Math.min(30000,Math.ceil((this.latencies.get(dir)||0)*3)))}
 pollingInterval(dir){const base=this.mode==='throttled'?(isNetworkPath(dir)?300000:180000):(isNetworkPath(dir)?120000:60000);return Math.max(base,Math.min(600000,Math.ceil((this.latencies.get(dir)||0)*10)))}
 canRefresh(dir){const now=this.now(),last=this.lastRun.get(dir);if(last!==undefined&&now-last<this.delay(dir))return false;this.lastRun.set(dir,now);return true}
 observe(dir,elapsedMs){if(!Number.isFinite(elapsedMs)||elapsedMs<0)return;const previous=this.latencies.get(dir);this.latencies.set(dir,previous===undefined?elapsedMs:previous*.75+elapsedMs*.25)}
 forget(dir){this.lastRun.delete(dir);this.latencies.delete(dir)}
}
module.exports={WatchPolicy,isNetworkPath};
