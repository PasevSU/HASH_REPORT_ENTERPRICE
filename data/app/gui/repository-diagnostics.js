
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {probe}=require('./repository-trust');
function command(binary,args,cwd,timeout=12000){
 const r=spawnSync(binary,args,{cwd,encoding:'utf8',windowsHide:true,shell:false,timeout,maxBuffer:1024*1024});
 return {ok:!r.error&&r.status===0,code:r.status,output:(r.stdout||'').trim().slice(0,1500),error:(r.stderr||r.error?.message||'').trim().slice(0,1500)};
}
function diagnose(dir,{run=command}={}){
 const directory=path.resolve(dir);
 const result={directory,networkPath:/^(\\\\|\/\/)/.test(directory),checks:[],ready:false};
 const add=(id,ok,detail,remedy)=>result.checks.push({id,status:ok?'PASS':'BLOCKED',detail,remedy:ok?null:remedy});
 let stat;try{stat=fs.statSync(directory)}catch(e){add('directory',false,e.message,'Check NAS connection and permissions');return result;}
 if(!stat.isDirectory()){add('directory',false,'Not a directory','Choose a directory');return result;}
 add('directory',true,'Directory accessible');
 const git=run('git',['--version'],directory);add('git',git.ok,git.ok?git.output:git.error,'Install Git for Windows and check PATH');
 if(!git.ok)return result;
 const trust=probe(directory);add('ownership',trust.ok,trust.diagnostic,trust.dubious?'Use Git trust operation after verifying NAS ownership':'Inspect Git repository and permissions');
 if(!trust.ok)return result;
 const root=run('git',['rev-parse','--show-toplevel'],directory);add('repository',root.ok,root.ok?root.output:root.error,'Initialize or choose a Git repository');
 if(!root.ok)return result;
 const remote=run('git',['remote','get-url','origin'],directory);add('origin',remote.ok,remote.ok?remote.output:remote.error,'Use GitHub connection operation');
 const gh=run('gh',['auth','status'],directory);add('githubAuth',gh.ok,gh.ok?'GitHub CLI authentication active':gh.error,'Sign in using GitHub token or browser');
 const status=run('git',['status','--porcelain=v1'],directory);add('gitStatus',status.ok,status.ok?(status.output?'Uncommitted changes present':'Clean working tree'):status.error,'Resolve Git status errors');
 result.ready=result.checks.filter(x=>['directory','git','ownership','repository','gitStatus'].includes(x.id)).every(x=>x.status==='PASS');
 return result;
}
module.exports={diagnose};
