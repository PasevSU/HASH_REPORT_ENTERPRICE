'use strict';
const {EventEmitter}=require('node:events');
const {spawn}=require('node:child_process');
const path=require('node:path');
class GitOrchestrator extends EventEmitter {
 constructor({runner,limit=1,journal=null}={}){super();this.runner=runner||runGit;this.limit=limit;this.active=0;this.queue=[];this.locks=new Set();this.closed=false;this.journal=journal;}
 enqueue({dir,args,kind='read',timeoutMs=120000}){
  if(this.closed)return Promise.reject(Error('Orchestrator is closed'));
  if(!path.isAbsolute(dir)||!Array.isArray(args)||!args.length||args.some(a=>typeof a!=='string'))return Promise.reject(Error('Invalid Git task'));
  return new Promise((resolve,reject)=>{const id=this.journal?.create({dir:path.resolve(dir),args,kind});this.queue.push({id,dir:path.resolve(dir),args,kind,timeoutMs,resolve,reject});this.emit('queue',{pending:this.queue.length,active:this.active});this.drain()});
 }
 drain(){for(let i=0;this.active<this.limit&&i<this.queue.length;){const job=this.queue[i];if(this.locks.has(job.dir)){i++;continue;}this.queue.splice(i,1);this.active++;this.locks.add(job.dir);this.emit('start',{dir:job.dir,kind:job.kind});if(job.id)this.journal.set(job.id,'running');Promise.resolve().then(()=>this.runner(job.dir,job.args,job.timeoutMs)).then(value=>{if(job.id)this.journal.set(job.id,'completed');job.resolve(value)},error=>{if(job.id)this.journal.set(job.id,'failed',error.message);job.reject(error)}).finally(()=>{this.active--;this.locks.delete(job.dir);this.emit('finish',{dir:job.dir,kind:job.kind});this.drain()});}}
 async inspectRemote(dir){const results=await Promise.all([this.enqueue({dir,args:['status','--porcelain'],kind:'status'}),this.enqueue({dir,args:['rev-list','--left-right','--count','HEAD...@{upstream}'],kind:'divergence'}).catch(()=>({stdout:''}))]);const [status,divergence]=results;const m=/^\s*(\d+)\s+(\d+)\s*$/.exec(divergence.stdout||'');return {dirty:Boolean((status.stdout||'').trim()),ahead:m?Number(m[1]):null,behind:m?Number(m[2]):null,upstreamKnown:!!m,requiresReview:!m||Number(m[2])>0};}
 close(){this.closed=true;for(const job of this.queue.splice(0))(job.id&&this.journal.set(job.id,'interrupted','Orchestrator stopped'),job.reject(Error('Orchestrator stopped')));}
}
async function runGit(dir,args,timeoutMs){try{return await runGitOnce(dir,args,timeoutMs)}catch(e){const T=require('./git-trust');if(T.isDubious(e.message)&&T.ensureSafe(dir).ok)return runGitOnce(dir,args,timeoutMs);throw e}}
function runGitOnce(dir,args,timeoutMs){return new Promise((resolve,reject)=>{const child=spawn('git',args,{cwd:dir,shell:false,windowsHide:true,env:{...process.env,GIT_TERMINAL_PROMPT:'0'}});let stdout='',stderr='';const timer=setTimeout(()=>child.kill(),timeoutMs);child.stdout.on('data',b=>stdout+=String(b));child.stderr.on('data',b=>stderr+=String(b));child.once('error',reject);child.once('close',(code,signal)=>{clearTimeout(timer);if(code!==0)reject(Error(`git ${args[0]} failed (${code??signal}): ${stderr.trim()}`));else resolve({code,stdout,stderr})});});}
module.exports={GitOrchestrator,runGit};
