'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {inspectAsync,ensureRules}=require('./core');
const {WatchPolicy}=require('./watch-policy');
const {RecoveryPolicy}=require('./recovery-policy');
class RepositoryLifecycle {
  constructor({emit=()=>{},intervalMs=60000,policy=new WatchPolicy(),recovery=new RecoveryPolicy()}={}){this.emit=emit;this.intervalMs=intervalMs;this.policy=policy;this.recovery=recovery;this.entries=new Map();this.timer=null;}
  async add(dir,{createMissingRules=true}={}){
    const resolved=await fs.promises.realpath(dir);
    const st=await fs.promises.stat(resolved);if(!st.isDirectory())throw Error('Not a directory');
    let created=[];
    if(createMissingRules)created=await ensureRules(resolved);
    const existing=this.entries.get(resolved);
    if(existing)return {info:await inspectAsync(resolved),created,alreadyRegistered:true};
    const entry={watcher:null,pending:null,busy:false,rerun:false};this.entries.set(resolved,entry);
    try{
      entry.watcher=fs.watch(resolved,{recursive:true},(_event,file)=>{
        if(!file||/(^|[\\/])(?:\.git|node_modules|dist|build|\.cache)(?:[\\/]|$)/.test(file))return;
        clearTimeout(entry.pending);entry.pending=setTimeout(()=>this.refresh(resolved),this.policy.delay(resolved));
      });
      entry.watcher.on('error',error=>{this.emit('error',{dir:resolved,message:error.message});entry.watcher?.close();entry.watcher=null;this.recovery.fail(resolved+':watch');});
    }catch(error){this.recovery.fail(resolved+':watch');this.emit('error',{dir:resolved,message:'Filesystem watcher unavailable; periodic polling remains active: '+error.message});}
    const info=await inspectAsync(resolved);this.emit('repo',info);return {info,created,alreadyRegistered:false};
  }
  async refresh(dir){const entry=this.entries.get(dir);if(!entry)return;if(!this.policy.canRefresh(dir))return;if(entry.busy){entry.rerun=true;return;}entry.busy=true;const started=process.hrtime.bigint();try{const info=await inspectAsync(dir);if(this.entries.has(dir))this.emit('repo',info);this.recovery.success(dir+':inspect')}catch(error){this.recovery.fail(dir+':inspect');this.emit('error',{dir,message:error.message})}finally{this.policy.observe(dir,Number(process.hrtime.bigint()-started)/1e6);entry.busy=false;if(entry.rerun){entry.rerun=false;queueMicrotask(()=>this.refresh(dir));}}}
  start(){if(this.timer)return;this.timer=setInterval(()=>{const now=Date.now();for(const [dir,entry] of this.entries){if(this.recovery.ready(dir+':inspect')&&(!entry.lastPoll||now-entry.lastPoll>=this.policy.pollingInterval(dir))){entry.lastPoll=now;this.refresh(dir)}}},Math.min(this.intervalMs,15000));this.timer.unref?.()}
  updateLoad(metrics){this.policy.update(metrics);}
  remove(dir){const entry=this.entries.get(dir);if(!entry)return false;clearTimeout(entry.pending);entry.watcher?.close();this.entries.delete(dir);this.policy.forget(dir);this.recovery.forget(dir+':inspect');this.recovery.forget(dir+':watch');return true}
  close(){if(this.timer)clearInterval(this.timer);this.timer=null;for(const dir of [...this.entries.keys()])this.remove(dir)}
  list(){return [...this.entries.keys()]}
  status(){return [...this.entries].map(([dir,entry])=>({dir,watching:!!entry.watcher,busy:entry.busy,inspectRecovery:this.recovery.state(dir+':inspect'),watchRecovery:this.recovery.state(dir+':watch')}))}
}
module.exports={RepositoryLifecycle};
