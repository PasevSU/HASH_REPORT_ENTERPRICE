'use strict';
// Git "dubious ownership" on NAS/UNC shares: the share owner SID never matches the Windows user.
// safe.directory is honoured ONLY in global/system config (not -c / env), so we add one exact path
// (never '*') to the user's global config, and only for folders the user explicitly registered/connected.
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const DUBIOUS=/dubious ownership|safe\.directory/i;

const isDubious=text=>DUBIOUS.test(String(text||''));

// Git's own spelling: UNC "//host/share/x" is stored as "%(prefix)///host/share/x".
function safeDirectoryValue(dir){
 let p=path.resolve(dir).replace(/\\/g,'/').replace(/\/+$/,'');
 if(p.startsWith('//'))return '%(prefix)/'+p;
 return p;
}

// Git accepts both the bare UNC spelling ("//host/share/x") and the %(prefix)/ spelling
// ("%(prefix)///host/share/x") for the same path. Normalize both before comparing so we never
// add a duplicate safe.directory entry.
function normalizeSafeDirectory(v){
 let p=String(v||'').trim().toLowerCase().replace(/\\/g,'/');
 if(p.startsWith('%(prefix)/'))p=p.slice('%(prefix)/'.length);
 return p.replace(/\/+$/,'');
}

function ensureSafe(dir,{spawn=spawnSync}={}){
 const probe=()=>spawn('git',['rev-parse','--git-dir'],{cwd:dir,encoding:'utf8',windowsHide:true,timeout:20000});
 const first=probe();
 if(!first.error&&first.status===0)return {ok:true,added:false};
 if(!isDubious(first.stderr))return {ok:false,added:false,reason:'not-dubious',message:String(first.stderr||first.error?.message||'').trim()};
 const value=safeDirectoryValue(dir);
 const list=spawn('git',['config','--global','--get-all','safe.directory'],{encoding:'utf8',windowsHide:true,timeout:20000});
 const have=String(list.stdout||'').split(/\r?\n/).map(normalizeSafeDirectory).filter(Boolean);
 if(!have.includes(normalizeSafeDirectory(value))){
  const add=spawn('git',['config','--global','--add','safe.directory',value],{encoding:'utf8',windowsHide:true,timeout:20000});
  if(add.status!==0)return {ok:false,added:false,reason:'config-failed',message:String(add.stderr||'').trim()};
 }
 const second=probe();
 if(!second.error&&second.status===0)return {ok:true,added:true,value};
 return {ok:false,added:true,reason:'still-failing',value,message:String(second.stderr||'').trim()};
}

// spawnSync('git') that heals dubious-ownership once and retries.
function gitSync(args,options={}){
 const r=spawnSync('git',args,options);
 if(r.status!==0&&options.cwd&&isDubious(r.stderr)&&ensureSafe(options.cwd).ok)return spawnSync('git',args,options);
 return r;
}

module.exports={isDubious,safeDirectoryValue,ensureSafe,gitSync};
