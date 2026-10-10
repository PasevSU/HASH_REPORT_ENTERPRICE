'use strict';
// One-step "folder + repository + action" connector.
const fs=require('node:fs'),fsp=fs.promises,path=require('node:path');
const rc=require('./repo-create');
const gitops=require('../lib/gitops');
const {run}=rc;
const must=async(args,cwd,timeout=60000)=>{const r=await run('git',args,{cwd,timeout});if(!r.ok)throw Error(r.stderr||r.stdout||'git '+args[0]+' failed');return r.stdout};

function normalizeRepo(input){
 if(typeof input!=='string')return '';
 const v=input.trim();
 if(!v)return '';
 if(/^[\w.-]+\/[\w.-]+$/.test(v)&&!path.isAbsolute(v))return `https://github.com/${v.replace(/\.git$/,'')}.git`;
 return rc.validSource(v);
}
function nameFromUrl(url,dir){
 const m=/([\w.-]+?)(?:\.git)?$/.exec((url||'').replace(/[\\/]+$/,''));
 return m?m[1]:path.basename(dir);
}

async function inspectFolder(dir,repoInput=''){
 if(typeof dir!=='string'||!path.isAbsolute(dir))throw Error('Folder must be an absolute path');
 dir=path.resolve(dir);
 const out={dir,exists:false,empty:true,isRepo:false,isRoot:false,branch:null,origin:null,hasCommits:false,dirty:0,actions:[]};
 try{const st=await fsp.stat(dir);if(!st.isDirectory())throw Error('Not a directory: '+dir);out.exists=true;out.empty=(await fsp.readdir(dir)).length===0}
 catch(e){if(e.code!=='ENOENT')throw e}
 if(out.exists){
  const top=await run('git',['rev-parse','--show-toplevel'],{cwd:dir});
  if(top.ok){
   out.isRepo=true;out.isRoot=path.resolve(top.stdout).toLowerCase()===dir.toLowerCase();
   if(out.isRoot){
    out.branch=(await run('git',['branch','--show-current'],{cwd:dir})).stdout||null;
    const o=await run('git',['remote','get-url','origin'],{cwd:dir});out.origin=o.ok?o.stdout:null;
    out.hasCommits=(await run('git',['rev-parse','--verify','HEAD'],{cwd:dir})).ok;
    out.dirty=(await run('git',['status','--porcelain'],{cwd:dir})).stdout.split('\n').filter(Boolean).length;
   }
  }
 }
 const hasRepo=!!repoInput.trim();
 const A=[];
 if(out.isRepo&&!out.isRoot)out.warning='Folder is inside another repository; choose its root.';
 else if(out.isRepo&&out.origin)A.push('register');
 else if(out.isRepo){hasRepo?A.push('link','create','register'):A.push('create','link','register')}
 else{
  if(out.empty)A.push('clone');
  hasRepo?A.push('link','create','local'):A.push('create','local','link');
  if(!hasRepo&&out.empty)A.splice(A.indexOf('clone'),1);
 }
 out.actions=out.warning?[]:A;
 out.defaultAction=out.actions[0]||null;
 return out;
}

async function probeRemote(url){
 const sym=await run('git',['ls-remote','--symref',url,'HEAD'],{timeout:30000});
 if(!sym.ok)throw Error('Repository is not reachable or access is denied: '+(sym.stderr||'unknown'));
 const head=/^ref: refs\/heads\/(\S+)\s+HEAD/m.exec(sym.stdout);
 const heads=await run('git',['ls-remote','--heads',url],{timeout:30000});
 return {defaultBranch:head?head[1]:null,empty:!heads.stdout.trim()};
}

async function plan(input,gh){
 const info=await inspectFolder(input?.dir,input?.repo||'');
 if(info.warning)throw Error(info.warning);
 const mode=input?.mode||info.defaultAction;
 if(!info.actions.includes(mode))throw Error(`Action "${mode}" is not possible for this folder (allowed: ${info.actions.join(', ')||'none'})`);
 const dir=info.dir,steps=[],warnings=[];
 const base={mode,dir,folder:info};
 if(mode==='register'){steps.push('Add the folder to GitSU workspace');if(info.dirty)warnings.push(`${info.dirty} uncommitted change(s) present`);return {...base,steps,warnings}}
 if(mode==='local'){steps.push(info.exists?'git init in the existing folder':'Create folder and run git init','Create missing .gitignore/.gitattributes','Add to GitSU workspace');return {...base,steps,warnings}}
 if(mode==='create'){
  const name=input?.name||path.basename(dir);
  const p=await rc.planPublish({dir:info.exists?dir:path.dirname(dir),name,visibility:input?.visibility||'private',description:input?.description||''},gh);
  if(!info.exists)steps.push('Create the folder');
  steps.push(p.willInit?'git init':'Use the existing repository',p.willCreateInitialCommit?`Initial commit (${p.initialFileCount} file(s))`:'Keep existing commits',`Create ${p.visibility} GitHub repository ${p.repository}`,'Link origin and push with SHA verification','Add to GitSU workspace');
  return {...base,steps,warnings,repository:p.repository,url:p.url,visibility:p.visibility,name};
 }
 const url=normalizeRepo(input?.repo);
 if(!url)throw Error('Enter the repository (owner/name or URL)');
 const remote=await probeRemote(url);
 if(mode==='clone'){
  if(info.exists&&!info.empty)throw Error('Clone needs an empty folder; use "link" to attach existing files');
  if(remote.empty)warnings.push('Remote repository is empty');
  steps.push(`git clone ${url}`,'Add to GitSU workspace');
  return {...base,steps,warnings,url,defaultBranch:remote.defaultBranch};
 }
 if(mode==='link'){
  if(info.origin)throw Error('Origin already exists: '+info.origin);
  steps.push(info.isRepo?'Keep the existing repository':'git init in the folder',`Set origin to ${url}`,'git fetch');
  if(remote.empty)warnings.push('Remote is empty: nothing to fetch; push afterwards');
  else if(!info.hasCommits)steps.push(`Align to origin/${remote.defaultBranch||'main'} without touching files (differences appear as changes)`);
  else steps.push('Verify histories are related and set upstream');
  steps.push('Add to GitSU workspace');
  return {...base,steps,warnings,url,defaultBranch:remote.defaultBranch,remoteEmpty:remote.empty};
 }
 throw Error('Unknown action');
}

async function apply(input,{ensureRules,gh}={}){
 const p=await plan(input,gh);
 const dir=p.dir;
 if(p.mode==='register')return {dir,mode:p.mode};
 if(p.mode==='local'){
  await fsp.mkdir(dir,{recursive:true});
  if(!p.folder.isRepo)await must(['init','-b','main'],dir);
  if(ensureRules)await ensureRules(dir);
  return {dir,mode:p.mode};
 }
 if(p.mode==='create'){
  if(!p.folder.exists)await fsp.mkdir(dir,{recursive:true});
  const r=await rc.applyPublish({dir,name:p.name,visibility:p.visibility,description:input?.description||''},ensureRules);
  return {...r,mode:p.mode};
 }
 if(p.mode==='clone'){const r=await rc.applyClone({url:p.url,dest:dir});return {...r,mode:p.mode}}
 // link — delegate to gitops so origin is set and upstream is always configured.
 const created=!p.folder.isRepo;
 try{
  await gitops.link(dir,p.url,{branch:p.defaultBranch||undefined});
 }catch(e){
  await run('git',['remote','remove','origin'],{cwd:dir});
  if(created)await fsp.rm(path.join(dir,'.git'),{recursive:true,force:true});
  throw e;
 }
 if(ensureRules)await ensureRules(dir);
 return {dir,mode:p.mode,url:p.url};
}

module.exports={inspectFolder,plan,apply,normalizeRepo,nameFromUrl};
