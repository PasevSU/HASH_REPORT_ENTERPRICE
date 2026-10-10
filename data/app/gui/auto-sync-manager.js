'use strict';
const {spawn}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
function scriptPath(){const p=path.resolve(__dirname,'../scripts',process.platform==='win32'?'ha-git-sync.ps1':'ha-git-sync.sh');const u=p.replace('app.asar'+path.sep,'app.asar.unpacked'+path.sep);return fs.existsSync(u)?u:p}
class AutoSyncManager {
 constructor({emit=()=>{}}={}){this.jobs=new Map();this.emit=emit;}
 status(){return [...this.jobs.values()].map(j=>({dir:j.dir,branch:j.branch,apply:j.apply,pid:j.child.pid,startedAt:j.startedAt,state:j.state,phase:j.phase,node:j.node,lease:j.lease,recent:j.recent}));}
 start({dir,branch='main',apply=false,poll=5,debounce=30,lease=true,node=''}){
  if(node&&!/^[A-Za-z0-9._-]{1,64}$/.test(node))throw Error('Invalid node name');
  if(typeof dir!=='string'||!path.isAbsolute(dir))throw Error('Absolute repository path required');
  if(!/^[a-zA-Z0-9][a-zA-Z0-9._/-]*$/.test(branch)||branch.includes('..')||branch.endsWith('/')||branch.startsWith('-'))throw Error('Invalid branch');
  if(!Number.isInteger(poll)||poll<2||poll>3600||!Number.isInteger(debounce)||debounce<5||debounce>3600)throw Error('Invalid watcher intervals');
  if(this.jobs.has(dir))throw Error('Watcher already active for repository');
  const script=scriptPath();
  if(!fs.existsSync(script))throw Error('Watcher script missing');
  const command=process.platform==='win32'?'pwsh':'bash';
  const child=spawn(command,process.platform==='win32'?['-NoProfile','-NonInteractive','-File',script]:[script],{
   cwd:dir,shell:false,windowsHide:true,env:{...process.env,REPO_PATH:dir,BRANCH:branch,APPLY:apply?'1':'0',POLL_INTERVAL:String(poll),DEBOUNCE:String(debounce),LEASE:lease?'1':'0',...(node?{NODE_ID:node}:{}),GIT_TERMINAL_PROMPT:'0'}});
  const job={dir,branch,apply,child,state:'running',phase:'INIT',node:node||'',lease:apply&&lease,recent:[],startedAt:new Date().toISOString()};this.jobs.set(dir,job);
  const forward=(kind,chunk)=>{const msg=String(chunk).replace(/\x1b\[[0-9;]*m/g,'').slice(0,4096);if(kind==='stdout'||kind==='stderr')this.track(job,msg);this.emit('auto-sync-log',{dir,kind,message:msg});};
  child.stdout.on('data',d=>forward('stdout',d));child.stderr.on('data',d=>forward('stderr',d));
  child.on('error',e=>{forward('error',e.message);job.state='failed';this.jobs.delete(dir);this.emit('auto-sync-state',this.status());});
  child.on('exit',(code,signal)=>{forward('exit',`Watcher exited: code=${code} signal=${signal}`);this.jobs.delete(dir);this.emit('auto-sync-state',this.status());});
  this.emit('auto-sync-state',this.status());return {dir,branch,apply,pid:child.pid,startedAt:job.startedAt};
 }
 track(job,msg){for(const line of msg.split(/\r?\n/).filter(Boolean)){const m=/\[([A-Z]+)\]/.exec(line);if(m)job.phase=m[1];job.recent.push(line.slice(0,300));if(job.recent.length>12)job.recent.shift();}this.emit('auto-sync-state',this.status());}
 stop(dir){const job=this.jobs.get(dir);if(!job)return false;job.state='stopping';job.child.kill();this.emit('auto-sync-state',this.status());return true;}
 close(){for(const dir of this.jobs.keys())this.stop(dir);}
}
const LEASE_MODES=process.platform==='win32'?{status:['-Mode','lease-status'],break:['-Mode','lease-break']}:{status:['--lease-status'],break:['--lease-break']};
function leaseCommand(kind,{dir,branch='main'}){
 if(typeof dir!=='string'||!path.isAbsolute(dir))throw Error('Absolute repository path required');if(!/^[a-zA-Z0-9][a-zA-Z0-9._/-]*$/.test(branch)||branch.includes('..'))throw Error('Invalid branch');
 const script=scriptPath();
 return new Promise(resolve=>{let out='';const c=spawn(process.platform==='win32'?'pwsh':'bash',process.platform==='win32'?['-NoProfile','-NonInteractive','-File',script,...LEASE_MODES[kind]]:[script,...LEASE_MODES[kind]],{cwd:dir,shell:false,windowsHide:true,env:{...process.env,REPO_PATH:dir,BRANCH:branch,GIT_TERMINAL_PROMPT:'0'}});const t=setTimeout(()=>c.kill(),30000);c.stdout.on('data',d=>out+=d);c.stderr.on('data',d=>out+=d);c.on('error',e=>{clearTimeout(t);resolve({ok:false,message:e.message})});c.on('close',code=>{clearTimeout(t);resolve({ok:code===0,message:out.replace(/\x1b\[[0-9;]*m/g,'').trim().slice(0,1000)})})})
}
module.exports={AutoSyncManager,leaseCommand};

