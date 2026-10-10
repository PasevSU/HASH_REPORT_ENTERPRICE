'use strict';
// New-repository lifecycle: clone, create local, publish to a new GitHub repository.
const fs=require('node:fs'),fsp=fs.promises,path=require('node:path'),{spawn}=require('node:child_process');
const GITHUB_URL=/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+?(?:\.git)?$|^git@github\.com:[\w.-]+\/[\w.-]+?(?:\.git)?$/;
const {filterSensitive,walk}=require('./sensitive');

async function run(cmd,args,opts={}){
 const r=await runOnce(cmd,args,opts);
 if(!r.ok&&cmd==='git'&&opts.cwd&&require('./git-trust').isDubious(r.stderr)&&require('./git-trust').ensureSafe(opts.cwd).ok)return runOnce(cmd,args,opts);
 return r;
}
function runOnce(cmd,args,{cwd,timeout=30000}={}){
 return new Promise(resolve=>{
  let out='',err='',done=false;
  const child=spawn(cmd,args,{cwd,shell:false,windowsHide:true,env:{...process.env,GIT_TERMINAL_PROMPT:'0',GH_PROMPT_DISABLED:'1'}});
  const finish=r=>{if(done)return;done=true;clearTimeout(timer);resolve({...r,stdout:out.trim(),stderr:err.trim()})};
  const timer=setTimeout(()=>{child.kill();finish({ok:false,code:null,timedOut:true})},timeout);
  child.stdout.on('data',d=>out+=d);child.stderr.on('data',d=>err+=d);
  child.on('error',e=>{err+=e.message;finish({ok:false,code:null})});
  child.on('close',code=>finish({ok:code===0,code}));
  child.stdin.end();
 });
}
const must=async(cmd,args,opts)=>{const r=await run(cmd,args,opts);if(!r.ok)throw Error((r.stderr||r.stdout||`${cmd} failed`)+(r.timedOut?' (timeout)':''));return r.stdout};

function validName(name){
 if(typeof name!=='string'||!/^[A-Za-z0-9._-]{1,100}$/.test(name)||name==='.'||name==='..'||name.startsWith('-')||name.endsWith('.git'))throw Error('Invalid repository name (letters, digits, . _ - only)');
 return name;
}
function validSource(url){
 if(typeof url!=='string')throw Error('Repository URL required');
 url=url.trim();
 if(GITHUB_URL.test(url))return url;
 if(path.isAbsolute(url))return url; // local or UNC bare/working repository
 throw Error('Use a GitHub URL (https or git@) or an absolute local/NAS path');
}
async function emptyOrMissing(dir){
 try{const st=await fsp.stat(dir);if(!st.isDirectory())throw Error('Destination exists and is not a directory');if((await fsp.readdir(dir)).length)throw Error('Destination folder is not empty: '+dir)}
 catch(e){if(e.code!=='ENOENT')throw e}
}
async function assertDir(dir,label){
 try{if(!(await fsp.stat(dir)).isDirectory())throw Error()}catch{throw Error(label+' does not exist: '+dir)}
}
function absolute(dir,label='Folder'){if(typeof dir!=='string'||!path.isAbsolute(dir))throw Error(label+' must be an absolute path');return path.resolve(dir)}

async function planClone({url,dest}){
 url=validSource(url);dest=absolute(dest,'Destination');
 await assertDir(path.dirname(dest),'Parent folder');await emptyOrMissing(dest);
 const probe=await run('git',['ls-remote','--symref',url,'HEAD'],{timeout:30000});
 if(!probe.ok)throw Error('Remote is not reachable or access is denied: '+(probe.stderr||'unknown error'));
 const head=/^ref: refs\/heads\/(\S+)\s+HEAD/m.exec(probe.stdout);
 return {url,dest,reachable:true,defaultBranch:head?head[1]:null,emptyRemote:probe.stdout.trim()===''};
}
async function applyClone({url,dest}){
 const plan=await planClone({url,dest});
 const r=await require('../lib/gitops').clone(plan.url,plan.dest);
 return {dir:r.dir,url:r.url,branch:r.branch};
}

async function planNewLocal({parent,name,branch='main'}){
 validName(name);parent=absolute(parent,'Parent folder');await assertDir(parent,'Parent folder');
 if(!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(branch)||branch.includes('..'))throw Error('Invalid branch');
 const dest=path.join(parent,name);await emptyOrMissing(dest);
 return {dest,branch,willCreateFolder:!fs.existsSync(dest),willCreate:['.git','.gitignore','.gitattributes']};
}
async function applyNewLocal({parent,name,branch='main'},ensureRules){
 const plan=await planNewLocal({parent,name,branch});
 await fsp.mkdir(plan.dest,{recursive:true});
 await must('git',['init','-b',plan.branch],{cwd:plan.dest});
 const rules=ensureRules?await ensureRules(plan.dest):[];
 return {dir:plan.dest,branch:plan.branch,rules};
}

async function ghInfo(){
 if(!(await run('gh',['--version'],{timeout:10000})).ok)throw Error('GitHub CLI (gh) is not installed or not in PATH');
 if(!(await run('gh',['auth','status'],{timeout:20000})).ok)throw Error('GitHub CLI is not authenticated. Use "GitHub · Login" first.');
 const u=await run('gh',['api','user','--jq','.login'],{timeout:20000});
 const proto=await run('gh',['config','get','git_protocol'],{timeout:10000});
 return {login:u.ok?u.stdout:null,protocol:proto.ok&&proto.stdout==='ssh'?'ssh':'https'};
}
async function planPublish({dir,name,visibility='private',description='',owner=''},gh=ghInfo){
 dir=absolute(dir,'Repository');validName(name);
 if(!['private','public'].includes(visibility))throw Error('Visibility must be private or public');
 if(typeof description!=='string'||description.length>350)throw Error('Description too long');
 if(owner&&!/^[A-Za-z0-9-]{1,39}$/.test(owner))throw Error('Invalid owner');
 await assertDir(dir,'Folder');
 const info=await gh();owner=owner||info.login;if(!owner)throw Error('Cannot determine GitHub account');
 const isRepo=(await run('git',['rev-parse','--is-inside-work-tree'],{cwd:dir})).ok;
 if(isRepo){
  const top=(await run('git',['rev-parse','--show-toplevel'],{cwd:dir})).stdout;
  if(path.resolve(top).toLowerCase()!==path.resolve(dir).toLowerCase())throw Error('Folder is inside another repository; select its root');
  const origin=await run('git',['remote','get-url','origin'],{cwd:dir});
  if(origin.ok)throw Error('Origin already exists ('+origin.stdout+'); use "GitHub connection" instead');
 }
 if((await run('gh',['repo','view',`${owner}/${name}`,'--json','name'],{timeout:20000})).ok)throw Error(`Repository ${owner}/${name} already exists on GitHub`);
 const hasCommits=isRepo&&(await run('git',['rev-parse','--verify','HEAD'],{cwd:dir})).ok;
 let initialFiles=[];
 if(!hasCommits){
  if(isRepo)initialFiles=(await run('git',['ls-files','--cached','--others','--exclude-standard'],{cwd:dir})).stdout.split('\n').filter(Boolean);
  else{
   initialFiles=await walk(dir);
   if(!fs.existsSync(path.join(dir,'.gitignore')))initialFiles=initialFiles.filter(f=>!/(^|\/)\.env(\.(?!example$).*)?$/.test(f));
  }
  const bad=await filterSensitive(initialFiles,f=>fsp.readFile(path.join(dir,f),'utf8'));  if(bad.length)throw Error('Sensitive files would be committed: '+bad.slice(0,5).join(', ')+'. Add them to .gitignore first.');
 }
 const url=info.protocol==='ssh'?`git@github.com:${owner}/${name}.git`:`https://github.com/${owner}/${name}.git`;
 return {dir,repository:`${owner}/${name}`,visibility,description,url,willInit:!isRepo,willCreateInitialCommit:!hasCommits,initialFileCount:initialFiles.length};
}
async function applyPublish(input,ensureRules){
 const plan=await planPublish(input);
 return require('../lib/gitops').publish(plan.dir,{
  repo:plan.repository,visibility:plan.visibility,description:plan.description,
  message:'Initial commit',apply:true,ensureRules
 });
}
module.exports={planClone,applyClone,planNewLocal,applyNewLocal,planPublish,applyPublish,validName,validSource,run};
