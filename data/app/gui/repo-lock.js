'use strict';
// Cross-process repo lock shared with gitsu-watcher (<gitdir>/gitsu-op.lock: directory with a pid file).
const fs=require('node:fs'),fsp=fs.promises,path=require('node:path'),{spawnSync}=require('node:child_process');
function gitDir(dir){const r=require('./git-trust').gitSync(['rev-parse','--absolute-git-dir'],{cwd:dir,encoding:'utf8',windowsHide:true});if(r.status!==0)throw Error('Not a Git repository: '+dir);return r.stdout.trim()}
function alive(pid){if(!Number.isInteger(pid)||pid<=0)return false;try{process.kill(pid,0);return true}catch(e){return e.code==='EPERM'}}
async function readPid(lock){try{return parseInt(await fsp.readFile(path.join(lock,'pid'),'utf8'),10)}catch{return NaN}}
async function tryTake(lock){
 try{await fsp.mkdir(lock)}
 catch(e){
  if(e.code!=='EEXIST')throw e;
  const pid=await readPid(lock);
  if(alive(pid)&&pid!==process.pid)return false;
  await fsp.rm(lock,{recursive:true,force:true});
  try{await fsp.mkdir(lock)}catch{return false}
 }
 await fsp.writeFile(path.join(lock,'pid'),String(process.pid));return true;
}
async function withRepoLock(dir,fn,{waitMs=30000,stepMs=500}={}){
 const lock=path.join(gitDir(dir),'gitsu-op.lock');const end=Date.now()+waitMs;
 while(!(await tryTake(lock))){
  if(Date.now()>=end)throw Error('Repository is busy: another Git operation or the watcher holds the lock');
  await new Promise(r=>setTimeout(r,stepMs));
 }
 try{return await fn()}finally{await fsp.rm(lock,{recursive:true,force:true}).catch(()=>{})}
}
module.exports={withRepoLock,gitDir};
