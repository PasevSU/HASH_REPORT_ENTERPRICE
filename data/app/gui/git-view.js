'use strict';
// Read/stage/commit helpers for the Changes and History tabs.
const path=require('node:path');
const fs=require('node:fs');
const {isIgnoredPath}=require('../lib/gitignore');
const {run}=require('./repo-create');
const {withRepoLock}=require('./repo-lock');
const {filterSensitive}=require('./sensitive');
const TOKEN=/-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}/;
const MAX_DIFF=200000;
const g=async(dir,args,timeout=30000)=>{const r=await run('git',args,{cwd:dir,timeout});if(!r.ok)throw Error(r.stderr||r.stdout||'git '+args[0]+' failed');return r.stdout};

function cleanPath(p){
 if(typeof p!=='string'||!p||p.includes('\0')||path.isAbsolute(p)||p.startsWith('-')||p.split(/[\\/]/).includes('..'))throw Error('Invalid path: '+p);
 return p;
}
function cleanPaths(list){if(!Array.isArray(list)||!list.length||list.length>5000)throw Error('Select 1-5000 files');return list.map(cleanPath)}

async function status(dir){
 const r=await run('git',['-c','core.quotepath=false','status','--porcelain=v1','-z','--branch','--untracked-files=all'],{cwd:dir,timeout:60000});
 if(!r.ok)throw Error(r.stderr||'git status failed');
 const parts=r.stdout.split('\0').filter(x=>x!==''),files=[];let branch=null,ahead=0,behind=0;
 for(let i=0;i<parts.length;i++){
  const e=parts[i];
  if(e.startsWith('## ')){
   const m=/^## (?:No commits yet on |Initial commit on )?(.+?)(?:\.\.\.(\S+))?(?: \[(.*)\])?$/.exec(e);
   if(m){branch=m[1];const a=/ahead (\d+)/.exec(m[3]||''),b=/behind (\d+)/.exec(m[3]||'');ahead=a?+a[1]:0;behind=b?+b[1]:0}
   continue;
  }
  const x=e[0],y=e[1],file=e.slice(3);let from=null;
  if(x==='R'||x==='C'){from=parts[++i]}
  files.push({path:file,from,index:x===' '||x==='?'?'':x,worktree:y===' '?'':y,untracked:x==='?',conflict:/^(DD|AU|UD|UA|DU|AA|UU)$/.test(x+y)});
 }
 let ignoreContent='';
 try{const gi=path.join(dir,'.gitignore');if(fs.existsSync(gi))ignoreContent=fs.readFileSync(gi,'utf8')}catch{}
 for(const f of files)f.ignored=f.untracked&&ignoreContent?isIgnoredPath(f.path,ignoreContent):false;
 return {branch,ahead,behind,files};
}
async function diff(dir,{file,staged=false}){
 cleanPath(file);
 const st=await status(dir);const f=st.files.find(x=>x.path===file);
 let args;
 if(f?.untracked)args=['diff','--no-index','--no-color','--',process.platform==='win32'?'NUL':'/dev/null',file];
 else args=['-c','core.quotepath=false','diff','--no-color',...(staged?['--cached']:[]),'--',file];
 const r=await run('git',args,{cwd:dir,timeout:30000});
 if(!r.ok&&r.code!==1)throw Error(r.stderr||'git diff failed');
 const text=r.stdout;return {text:text.length>MAX_DIFF?text.slice(0,MAX_DIFF)+'\n… truncated':text,truncated:text.length>MAX_DIFF};
}
const stage=(dir,files)=>withRepoLock(dir,()=>g(dir,['add','--',...cleanPaths(files)]));
const unstage=(dir,files)=>withRepoLock(dir,async()=>{
 const hasHead=(await run('git',['rev-parse','--verify','HEAD'],{cwd:dir})).ok;
 return g(dir,hasHead?['reset','-q','HEAD','--',...cleanPaths(files)]:['rm','-q','--cached','-r','--',...cleanPaths(files)]);
});
async function commit(dir,{message,allowSensitive=false}){
 if(typeof message!=='string'||!message.trim()||message.length>5000)throw Error('Commit message required (max 5000 chars)');
 return withRepoLock(dir,async()=>{
  const names=(await g(dir,['diff','--cached','--name-only','-z'])).split('\0').filter(Boolean);
  if(!names.length)throw Error('Nothing staged');
  if(!allowSensitive){
   const deleted=new Set((await g(dir,['diff','--cached','--diff-filter=D','--name-only','-z'])).split('\0').filter(Boolean));
   const bad=await filterSensitive(names,n=>g(dir,['show',':'+n]),n=>deleted.has(n));
   if(bad.length)throw Error('Sensitive files staged: '+bad.slice(0,5).join(', '));
   const added=(await g(dir,['diff','--cached','-U0','--no-color'])).split('\n').filter(l=>l.startsWith('+'));
   if(added.some(l=>TOKEN.test(l)))throw Error('Staged diff contains a key/token pattern');
  }
  await g(dir,['commit','-q','-m',message.trim()],60000);
  return {sha:await g(dir,['rev-parse','HEAD']),files:names.length};
 });
}
async function log(dir,{limit=50,skip=0}={}){
 limit=Math.min(Math.max(parseInt(limit,10)||50,1),500);skip=Math.max(parseInt(skip,10)||0,0);
 if(!(await run('git',['rev-parse','--verify','HEAD'],{cwd:dir})).ok)return [];
 const out=await g(dir,['log',`-n${limit}`,`--skip=${skip}`,'--date=iso-strict','--format=%H%x1f%h%x1f%an%x1f%ad%x1f%s%x1f%D%x1e'],60000);
 return out.split('\x1e').map(s=>s.trim()).filter(Boolean).map(s=>{const [sha,short,author,date,subject,refs]=s.split('\x1f');return {sha,short,author,date,subject,refs:refs||''}});
}
async function show(dir,sha){
 if(!/^[0-9a-f]{7,40}$/i.test(sha||''))throw Error('Invalid commit id');
 const text=await g(dir,['show','--no-color','--stat','--patch','--format=fuller',sha],60000);
 return {text:text.length>MAX_DIFF?text.slice(0,MAX_DIFF)+'\n… truncated':text};
}
module.exports={status,diff,stage,unstage,commit,log,show,cleanPath};
