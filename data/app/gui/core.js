 'use strict';
const fs=require('node:fs'), fsp=fs.promises, path=require('node:path'), {spawnSync}=require('node:child_process');
function git(dir,args,allowFailure=false){const r=require('./git-trust').gitSync(args,{cwd:dir,encoding:'utf8',windowsHide:true,timeout:20000,shell:false});if(r.error||r.status!==0){if(allowFailure)return null;throw Error((r.stderr||r.error?.message||'Git error').trim())}return r.stdout.trim()}
function inspect(dir){const full=path.resolve(dir);if(!fs.existsSync(full)||!fs.statSync(full).isDirectory())throw Error('Directory does not exist');const trustCheck=spawnSync('git',['status','--short'],{cwd:full,encoding:'utf8',windowsHide:true,timeout:20000,shell:false});
 if(/detected dubious ownership/i.test(trustCheck.stderr||'')){
   const err=Error('Git ownership blocked. Use the Git trust operation for this repository.\n'+(trustCheck.stderr||'').trim());
   err.code='GIT_DUBIOUS_OWNERSHIP';throw err;
 }
 const root=git(full,['rev-parse','--show-toplevel'],true);return {dir:full,isRepo:!!root,root:root||null,branch:root?git(full,['branch','--show-current'],true):null,remote:root?git(full,['remote','get-url','origin'],true):null,dirty:root?Boolean(git(full,['status','--porcelain'],true)):false,branches:root?(git(full,['branch','--format=%(refname:short)'],true)||'').split('\n').filter(Boolean):[],remotes:root?(git(full,['remote','-v'],true)||'').split('\n').filter(Boolean):[],files:{gitignore:fs.existsSync(path.join(full,'.gitignore')),gitattributes:fs.existsSync(path.join(full,'.gitattributes')),workflow:fs.existsSync(path.join(full,'.github','workflows'))}}}
async function inspectAsync(dir){
  const {run}=require('./repo-create');
  const full=path.resolve(dir);
  const st=await fsp.stat(full).catch(()=>null);
  if(!st||!st.isDirectory())throw Error('Directory does not exist');
  const o={cwd:full,timeout:60000};
  const top=await run('git',['rev-parse','--show-toplevel'],o);
  const root=top.ok?top.stdout:null;
  const files={gitignore:fs.existsSync(path.join(full,'.gitignore')),gitattributes:fs.existsSync(path.join(full,'.gitattributes')),workflow:fs.existsSync(path.join(full,'.github','workflows'))};
  if(!root)return {dir:full,isRepo:false,root:null,branch:null,remote:null,dirty:false,branches:[],remotes:[],files};
  const [br,rem,dirty,list,rv]=await Promise.all([
    run('git',['branch','--show-current'],o),
    run('git',['remote','get-url','origin'],o),
    run('git',['status','--porcelain'],o),
    run('git',['branch','--format=%(refname:short)'],o),
    run('git',['remote','-v'],o)
  ]);
  return {dir:full,isRepo:true,root,branch:br.ok?br.stdout:null,remote:rem.ok?rem.stdout:null,dirty:dirty.ok&&Boolean(dirty.stdout),branches:(list.stdout||'').split('\n').filter(Boolean),remotes:(rv.stdout||'').split('\n').filter(Boolean),files};
}
function safePair(a,b){
  const x=path.resolve(a),y=path.resolve(b);
  if(x===y||x.startsWith(y+path.sep)||y.startsWith(x+path.sep))throw Error('Source and destination must not overlap');
  if(!fs.existsSync(x)||!fs.statSync(x).isDirectory())throw Error('Source must be an existing directory');
  // Reject existing symlink ancestors, including destination parents.
  for(const root of [x,y]){let current=path.parse(root).root;for(const segment of path.relative(current,root).split(path.sep).filter(Boolean)){
    current=path.join(current,segment);
    try{if(fs.lstatSync(current).isSymbolicLink())throw Error('Symbolic link in source/destination path: '+current)}catch(e){if(e.code!=='ENOENT')throw e}
  }}
  const realX=fs.realpathSync(x),realY=fs.existsSync(y)?fs.realpathSync(y):y;
  if(realX===realY||realX.startsWith(realY+path.sep)||realY.startsWith(realX+path.sep))throw Error('Resolved source and destination overlap');
  return [x,y];
}
function validRelative(rel){if(typeof rel!=='string'||!rel||path.isAbsolute(rel)||rel.split(/[\\/]/).some(x=>x==='..'||x==='.'||!x))throw Error('Invalid relative file path');return rel}
async function hashFile(file){const crypto=require('node:crypto');return new Promise((resolve,reject)=>{const h=crypto.createHash('sha256'),stream=fs.createReadStream(file);stream.on('data',x=>h.update(x));stream.on('error',reject);stream.on('end',()=>resolve(h.digest('hex')))});}
async function assertNoLinks(root,rel){let current=root;for(const segment of rel.split(path.sep)){current=path.join(current,segment);try{if((await fsp.lstat(current)).isSymbolicLink())throw Error('Symbolic link blocked: '+current)}catch(e){if(e.code!=='ENOENT')throw e}}}
async function planCopy(from,to){const [src,dst]=safePair(from,to),changes=[];async function walk(dir,rel=''){for(const e of await fsp.readdir(dir,{withFileTypes:true})){if(e.name==='.git')continue;const r=path.join(rel,e.name),source=path.join(dir,e.name),target=path.join(dst,r);if(e.isSymbolicLink()){changes.push({type:'skip-link',path:r});continue}if(e.isDirectory())await walk(source,r);else if(e.isFile()){
  await assertNoLinks(dst,r);let changed=true;
  try{const a=await fsp.stat(source),b=await fsp.stat(target);if(!b.isFile())throw Error('Destination is not a regular file: '+target);if(a.size===b.size)changed=(await hashFile(source))!==(await hashFile(target))}catch(e){if(e.code!=='ENOENT')throw e}
  if(changed)changes.push({type:'copy',path:r,sourceHash:await hashFile(source),targetHash:await fsp.stat(target).then(st=>st.isFile()?hashFile(target):null).catch(e=>{if(e.code==='ENOENT')return null;throw e})});
}}}await walk(src);return {src,dst,changes}}
const activeCopies=new Set();
async function applyCopy(plan){
 if(!plan||!Array.isArray(plan.changes))throw Error('Invalid plan');
 const [src,dst]=safePair(plan.src,plan.dst),lock=path.normalize(dst).toLowerCase();
 if(activeCopies.has(lock))throw Error('Destination already has an active copy operation');
 activeCopies.add(lock);
 const crypto=require('node:crypto'),transaction=crypto.randomUUID(),completed=[],staged=[];
 try{
  const fresh=await planCopy(src,dst);
  if(JSON.stringify(fresh.changes)!==JSON.stringify(plan.changes))throw Error('Copy preview is stale: compare folders again');
  for(const item of plan.changes){
   if(item.type!=='copy')continue;
   const rel=validRelative(item.path),source=path.join(src,rel),target=path.join(dst,rel);
   await assertNoLinks(src,rel);await assertNoLinks(dst,rel);
   if(!(await fsp.lstat(source)).isFile()||(await hashFile(source))!==item.sourceHash)throw Error('Source changed since preview: '+rel);
   const temp=target+'.gitsu-stage-'+transaction,backup=target+'.gitsu-backup-'+transaction;
   await fsp.mkdir(path.dirname(target),{recursive:true});await assertNoLinks(dst,rel);
   const exists=await fsp.lstat(target).then(x=>{if(!x.isFile())throw Error('Target is not a regular file: '+rel);return true}).catch(e=>{if(e.code==='ENOENT')return false;throw e});
   const current=exists?await hashFile(target):null;
   if(current!==item.targetHash)throw Error('Destination changed since preview: '+rel);
   await fsp.copyFile(source,temp,fs.constants.COPYFILE_EXCL);staged.push(temp);
   if((await hashFile(temp))!==item.sourceHash)throw Error('Staged file integrity failure: '+rel);
   // Recheck the destination immediately before replacement.
   await assertNoLinks(dst,rel);
   const before=await fsp.lstat(target).then(x=>{if(!x.isFile())throw Error('Target changed type: '+rel);return hashFile(target)}).catch(e=>{if(e.code==='ENOENT')return null;throw e});
   if(before!==item.targetHash)throw Error('Destination changed during copy: '+rel);
   if(exists)await fsp.rename(target,backup);
   try{await fsp.rename(temp,target)}catch(e){if(exists)await fsp.rename(backup,target);throw e}
   completed.push({target,backup,exists});
  }
  const cleanupWarnings=[];for(const item of completed){if(item.exists)await fsp.unlink(item.backup).catch(e=>cleanupWarnings.push(e.message))}
  return {copied:completed.length,cleanupWarnings};
 }catch(e){
  const rollbackErrors=[];
  for(const item of completed.reverse())try{await fsp.unlink(item.target);if(item.exists)await fsp.rename(item.backup,item.target)}catch(err){rollbackErrors.push(err.message)}
  if(rollbackErrors.length)throw new AggregateError([e,...rollbackErrors.map(x=>Error(x))],'Copy failed and rollback incomplete');
  throw e;
 }finally{for(const temp of staged)await fsp.unlink(temp).catch(()=>{});activeCopies.delete(lock)}
}
async function ensureRules(dir){const target=path.resolve(dir);if(!fs.existsSync(target)||!fs.statSync(target).isDirectory())throw Error('Directory missing');const files={'.gitignore':'node_modules/\n.env\n.env.*\n!.env.example\ndist/\n*.log\n','.gitattributes':'* text=auto\n*.bat text eol=crlf\n*.ps1 text eol=crlf\n*.png binary\n*.pdf binary\n'};const created=[];for(const [name,content] of Object.entries(files)){try{await fsp.writeFile(path.join(target,name),content,{flag:'wx'});created.push(name)}catch(e){if(e.code!=='EEXIST')throw e}}return created}
module.exports={git,inspect,inspectAsync,safePair,planCopy,applyCopy,ensureRules};
