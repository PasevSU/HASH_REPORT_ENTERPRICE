'use strict';
// Multi-layer verification engine. Every action passes:
//  L1 environment -> L2 repository -> L3 transport/method selection -> L4 action rules
//  -> (apply) -> L5 post-verification with an independent second method and retries.
// Each check may have several redundant methods; the first that answers wins, a failed primary
// with a working fallback is reported as "degraded", never silently ignored.
const fs=require('node:fs'),fsp=fs.promises,path=require('node:path'),{spawn}=require('node:child_process');
const trust=require('./git-trust');
const {filterSensitive}=require('./sensitive');

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function sh(cmd,args,{cwd,timeout=20000}={}){
 return new Promise(resolve=>{
  let out='',err='',done=false,p;
  const end=r=>{if(!done){done=true;clearTimeout(t);resolve({ok:r.code===0,code:r.code,stdout:out.trim(),stderr:err.trim()||r.error||''})}};
  try{p=spawn(cmd,args,{cwd,windowsHide:true,shell:false,env:{...process.env,GIT_TERMINAL_PROMPT:'0',GCM_INTERACTIVE:'never',GIT_SSH_COMMAND:process.env.GIT_SSH_COMMAND||'ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new'}})}catch(e){return resolve({ok:false,code:-1,stdout:'',stderr:e.message})}
  const t=setTimeout(()=>{try{p.kill()}catch{}end({code:-2,error:'timeout'})},timeout);
  p.stdout.on('data',d=>{out+=d;if(out.length>2e6)out=out.slice(-1e6)});p.stderr.on('data',d=>err+=d);
  p.on('error',e=>end({code:-1,error:e.message}));p.on('close',c=>end({code:c}));
 });
}
const git=(dir,args,t)=>sh('git',args,{cwd:dir,timeout:t});

class Report{
 constructor(){this.checks=[];}
 add(layer,name,ok,detail='',extra={}){this.checks.push({layer,name,ok:!!ok,level:extra.level||(ok?'ok':'block'),detail:String(detail||'').slice(0,300),method:extra.method||null});return ok}
 warn(layer,name,detail,method){this.checks.push({layer,name,ok:true,level:'warn',detail:String(detail||'').slice(0,300),method:method||null})}
 get blockers(){return this.checks.filter(c=>!c.ok)}
 get ok(){return this.blockers.length===0}
 summary(){return this.checks.map(c=>`${c.ok?(c.level==='warn'?'!':'✓'):'✗'} L${c.layer} ${c.name}${c.method?' ['+c.method+']':''}${c.detail?': '+c.detail:''}`)}
}

// Run several independent methods for one check. Returns first success; reports degradation.
async function redundant(rep,layer,name,methods){
 const errs=[];
 for(const [label,fn] of methods){
  try{const r=await fn();if(r&&r.ok!==false){if(errs.length)rep.warn(layer,name,`основният метод даде грешка (${errs[0]}), мина през резервен`,label);else rep.add(layer,name,true,r.info||'',{method:label});return r}errs.push(`${label}: ${(r&&r.detail)||'failed'}`)}
  catch(e){errs.push(`${label}: ${e.message}`)}
 }
 rep.add(layer,name,false,errs.join(' | '));return null;
}

// ---------- URL / method helpers ----------
function kindOf(url){
 if(!url)return 'none';
 if(/^https?:\/\//i.test(url))return 'https';
 if(/^(ssh:\/\/|[\w.-]+@[\w.-]+:)/i.test(url))return 'ssh';
 if(/^file:\/\//i.test(url)||/^([a-z]:[\\/]|\\\\|\/)/i.test(url))return 'local';
 return 'unknown';
}
function toSsh(url){const m=/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?$/i.exec(url||'');return m?`git@github.com:${m[1]}/${m[2]}.git`:null}
function toHttps(url){const m=/^git@github\.com:([\w.-]+)\/([\w.-]+?)(?:\.git)?$/i.exec(url||'');return m?`https://github.com/${m[1]}/${m[2]}.git`:null}

async function lsRemote(url,dir,ref){
 const r=await git(dir,['ls-remote','--heads','--',url],25000).catch(()=>null);
 if(!r)return {ok:false,detail:'no result'};
 if(!r.ok)return {ok:false,detail:r.stderr.split('\n')[0]};
 const heads=Object.fromEntries(r.stdout.split('\n').filter(Boolean).map(l=>{const [sha,name]=l.split(/\s+/);return [name.replace('refs/heads/',''),sha]}));
 return {ok:true,heads,empty:Object.keys(heads).length===0,sha:ref?heads[ref]:undefined,detail:Object.keys(heads).length?`${Object.keys(heads).length} клона`:'празно'};
}

// Chooses the transport that really works right now. Order: configured URL, then the sibling transport.
async function selectMethod(rep,layer,url,dir,{allowSwitch=false}={}){
 const kind=kindOf(url);
 if(kind==='none'){rep.add(layer,'remote',false,'няма remote URL');return null}
 const cands=[{method:kind==='ssh'?'ssh':kind==='local'?'local':'https',url}];
 const alt=kind==='https'?toSsh(url):kind==='ssh'?toHttps(url):null;
 if(alt&&allowSwitch)cands.push({method:kind==='https'?'ssh':'https',url:alt});
 const failures=[];
 for(const c of cands){
  const r=await lsRemote(c.url,dir);
  if(r.ok){
   const switched=c.url!==url;
   if(switched)rep.warn(layer,'транспорт',`${kind} не работи (${failures[0]||''}); работещ метод: ${c.method}`,c.method);
   else rep.add(layer,'транспорт',true,r.detail,{method:c.method});
   return {...c,remote:r,switched};
  }
  failures.push(`${c.method}: ${r.detail}`);
 }
 rep.add(layer,'транспорт',false,failures.join(' | '));return null;
}

// ---------- layers ----------
async function layerEnv(rep,dir,{write=false}={}){
 await redundant(rep,1,'git',[['git --version',async()=>{const r=await sh('git',['--version']);return {ok:r.ok,info:r.stdout,detail:r.stderr}}],['where',async()=>{const r=await sh(process.platform==='win32'?'where':'which',['git']);return {ok:r.ok,info:r.stdout.split('\n')[0],detail:r.stderr}}]]);
 if(!dir)return;
 await redundant(rep,1,'папка',[['stat',async()=>{const s=await fsp.stat(dir);return {ok:s.isDirectory(),info:dir,detail:'не е папка'}}],['readdir',async()=>{await fsp.readdir(dir);return {ok:true,info:dir}}]]);
 if(write)await redundant(rep,1,'запис',[['access',async()=>{await fsp.access(dir,fs.constants.W_OK);return {ok:true}}],['temp-file',async()=>{const f=path.join(dir,'.gitsu-w-'+process.pid);await fsp.writeFile(f,'');await fsp.unlink(f);return {ok:true}}]]);
}

async function layerRepo(rep,dir,{needCommit=false}={}){
 const t=trust.ensureSafe(dir);
 if(t.added)rep.warn(2,'доверие','добавен safe.directory за тази папка (авто-поправка)');
 await redundant(rep,2,'репозиторий',[['rev-parse',async()=>{const r=await git(dir,['rev-parse','--git-dir']);return {ok:r.ok,detail:r.stderr}}],['.git',async()=>({ok:fs.existsSync(path.join(dir,'.git')),detail:'няма .git'})]]);
 if(!rep.ok)return;
 const gd=(await git(dir,['rev-parse','--absolute-git-dir'])).stdout||path.join(dir,'.git');
 const busy=['MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply'].filter(n=>fs.existsSync(path.join(gd,n)));
 rep.add(2,'без незавършена операция',busy.length===0,busy.join(', '));
 const lock=path.join(gd,'index.lock');
 if(fs.existsSync(lock)){
  const age=Date.now()-fs.statSync(lock).mtimeMs;
  const STALE_MS=30000;
  if(process.platform==='win32'){
   // Windows: a live git process holds index.lock with an exclusive handle, so
   // fs.unlinkSync fails (EBUSY/EPERM) while it is genuinely in use. This makes
   // the "is it really held?" decision OS-backed instead of guessing from tasklist,
   // which falsely treats any unrelated git.exe as "working in this repo".
   if(age>STALE_MS){try{fs.unlinkSync(lock);rep.warn(2,'index.lock','остарял lock е премахнат (авто-поправка)')}catch(e){rep.add(2,'index.lock',false,'друг git процес работи в това репо'+(e.code?` (${e.code})`:''))}}
   else rep.add(2,'index.lock',false,'друг git процес работи в това репо');
  } else {
   const running=(await sh('pgrep',['-x','git'])).stdout;
   if(age>600000||(age>STALE_MS&&!running)){try{fs.unlinkSync(lock);rep.warn(2,'index.lock','остарял lock е премахнат (авто-поправка)')}catch(e){rep.add(2,'index.lock',false,e.message)}}
   else rep.add(2,'index.lock',false,'друг git процес работи в това репо');
  }
 }
 if(needCommit)await redundant(rep,2,'HEAD',[['rev-parse',async()=>{const r=await git(dir,['rev-parse','--verify','HEAD']);return {ok:r.ok,detail:'няма commit'}}],['log',async()=>{const r=await git(dir,['log','-1','--format=%H']);return {ok:r.ok&&!!r.stdout,detail:'няма commit'}}]]);
}

async function originOf(dir){
 const a=await git(dir,['remote','get-url','origin']);if(a.ok&&a.stdout)return a.stdout;
 const b=await git(dir,['config','--get','remote.origin.url']);return b.ok?b.stdout:'';
}
async function branchOf(dir){
 const a=await git(dir,['branch','--show-current']);if(a.ok&&a.stdout)return a.stdout;
 const b=await git(dir,['symbolic-ref','--short','-q','HEAD']);return b.ok?b.stdout:'';
}
async function stagedFiles(dir){
 const a=await git(dir,['diff','--cached','--name-only','-z']);if(a.ok)return a.stdout.split('\0').filter(Boolean);
 const b=await git(dir,['status','--porcelain=v1']);return b.stdout.split('\n').filter(l=>/^[MADRC]/.test(l)).map(l=>{const s=l.slice(0,2),p=l.slice(3);return /^[RC]/.test(s)&&p.includes(' -> ')?p.split(' -> ').pop():p});
}

// ---------- preflight ----------
async function preflight(action,ctx={}){
 const rep=new Report(),dir=ctx.dir?path.resolve(ctx.dir):null;let method=null;
 const apply=ctx.apply!==false;
 const envDir=dir&&ctx.mayCreate&&!fs.existsSync(dir)?path.dirname(dir):dir;
 await layerEnv(rep,envDir,{write:apply&&!['view','probe'].includes(action)});
 if(!rep.ok)return {rep,method};
 const repoActions=['push','update','commit','publish','ssh-use'];
 if(repoActions.includes(action)||(action==='link'&&ctx.hasRepo)){
  await layerRepo(rep,dir,{needCommit:['push','publish'].includes(action)&&ctx.needCommit!==false});
  if(!rep.ok)return {rep,method};
 }
 if(action==='push'||action==='update'){
  const branch=await branchOf(dir);rep.add(2,'клон',!!branch,branch||'detached HEAD — превключете на клон');
  const url=await originOf(dir);
  method=await selectMethod(rep,3,url,dir,{allowSwitch:true});
  if(method&&action==='push'){
   const remoteSha=method.remote.heads?.[branch];
   const localSha=(await git(dir,['rev-parse','HEAD'])).stdout;
   if(remoteSha&&remoteSha!==localSha){
    await redundant(rep,4,'fast-forward',[
     ['merge-base',async()=>{const r=await git(dir,['merge-base','--is-ancestor',remoteSha,'HEAD']);return {ok:r.code===0,detail:r.code===1?'remote има commit-и, които липсват локално — първо „Обнови“':'remote commit липсва локално — първо fetch'}}],
     ['rev-list',async()=>{const r=await git(dir,['rev-list','--count',`${remoteSha}..HEAD`]);return {ok:r.ok&&Number(r.stdout)>0,detail:'няма нищо за качване или разминаване'}}],
    ]);
   }else if(remoteSha===localSha)rep.warn(4,'push','remote вече е на същия commit — няма какво да се качва');
   else rep.add(4,'push',true,method.remote.empty?'празно remote — ще бъде създаден клон '+branch:'нов клон '+branch);
  }
  if(action==='update'){
   const dirty=(await git(dir,['status','--porcelain'])).stdout;
   if(dirty)rep.warn(4,'update','има неcommit-нати промени — pull може да откаже');
  }
 }
 if(action==='commit'){
  const staged=await stagedFiles(dir);
  rep.add(4,'staged файлове',staged.length>0,staged.length?staged.length+' файла':'нищо за commit — първо „Всички“ (stage)');
  const del=await git(dir,['diff','--cached','--diff-filter=D','--name-only','-z']);
  const deleted=new Set(del.ok?del.stdout.split('\0').filter(Boolean):[]);
  const bad=await filterSensitive(staged,n=>fsp.readFile(path.join(dir,n),'utf8'),n=>deleted.has(n));
  rep.add(4,'чувствителни файлове',bad.length===0,bad.slice(0,3).join(', '));
  const nm=(await git(dir,['config','user.name'])).stdout,em=(await git(dir,['config','user.email'])).stdout;
  rep.add(4,'автор',!!(nm&&em),nm&&em?`${nm} <${em}>`:'не е зададено git user.name/user.email');
  rep.add(4,'съобщение',String(ctx.message||'').trim().length>0,'въведете съобщение');
 }
 if(action==='link'||action==='clone'){
  const url=ctx.url;
  rep.add(4,'URL формат',kindOf(url)!=='unknown'&&kindOf(url)!=='none',url||'липсва');
  if(rep.ok)method=await selectMethod(rep,3,url,dir&&fs.existsSync(dir)?dir:process.cwd(),{allowSwitch:true});
  if(action==='clone'&&ctx.dest){
   const empty=await fsp.readdir(ctx.dest).then(x=>x.length===0,()=>true);
   rep.add(4,'целева папка',empty,'папката не е празна');
  }
 }
 if(action==='publish'||action==='create'){
  await redundant(rep,3,'gh вход',[['gh auth status',async()=>{const r=await sh('gh',['auth','status']);return {ok:r.ok,detail:'gh не е влязъл — влезте от акаунт'}}],['gh api user',async()=>{const r=await sh('gh',['api','user','-q','.login']);return {ok:r.ok,detail:'няма достъп'}}]]);
  const sc=await sh('gh',['api','-i','user'],{timeout:20000});
  const sm=/^x-oauth-scopes:\s*(.*)$/im.exec(sc.stdout||'');
  const scopes=sm?sm[1].split(',').map(s=>s.trim()).filter(Boolean):[];
  const canCreate=scopes.includes('repo')||scopes.includes('public_repo');
  const why=!sc.ok?'няма достъп до GitHub API':(sm?`токенът няма scope "repo" (${scopes.join(', ')||'без scope-ове'})`:'fine-grained токен — GitHub не позволява създаване на репа с него');
  rep.add(3,'право за създаване на репо',sc.ok&&canCreate,sc.ok&&canCreate?'scope: repo':why+'. Влезте през браузър (Акаунт → Вход през GitHub) или с classic токен със scope "repo".',{method:'x-oauth-scopes'});
  const nm=String(ctx.name||'');
  if(rep.ok&&ctx.owner&&nm){
   const r=await sh('gh',['repo','view',`${ctx.owner}/${nm}`,'--json','name']);
   rep.add(4,'име свободно',!r.ok,r.ok?`${ctx.owner}/${nm} вече съществува`:'');
  }
 }
 return {rep,method};
}

// ---------- post verification ----------
async function postVerify(action,ctx={},before={}){
 const rep=new Report(),dir=ctx.dir?path.resolve(ctx.dir):null;
 const retry=async(fn,n=3)=>{let last;for(let i=0;i<n;i++){last=await fn();if(last.ok)return last;await sleep(700*(i+1))}return last};
 if(action==='push'){
  const branch=await branchOf(dir),local=(await git(dir,['rev-parse','HEAD'])).stdout,url=ctx.url||await originOf(dir);
  await redundant(rep,5,'remote = локален HEAD',[
   ['ls-remote',async()=>{const r=await retry(async()=>{const x=await lsRemote(url,dir,branch);return {...x,ok:x.ok&&x.sha===local}});return {ok:r.ok,info:local.slice(0,8),detail:`remote ${String(r.sha||'—').slice(0,8)} ≠ ${local.slice(0,8)}`}}],
   ['fetch+rev-parse',async()=>{const f=await git(dir,['fetch','origin',branch],40000);const r=await git(dir,['rev-parse',`origin/${branch}`]);return {ok:f.ok&&r.stdout===local,detail:f.ok?'origin/'+branch+' различен':f.stderr}}],
  ]);
 }
 if(action==='update'){
  const u=(await git(dir,['diff','--name-only','--diff-filter=U'])).stdout;
  rep.add(5,'без конфликти',!u,u.split('\n').slice(0,3).join(', '));
  await redundant(rep,5,'HEAD валиден',[['rev-parse',async()=>{const r=await git(dir,['rev-parse','--verify','HEAD']);return {ok:r.ok}}],['fsck',async()=>{const r=await git(dir,['fsck','--connectivity-only','--no-dangling'],60000);return {ok:r.ok,detail:r.stderr}}]]);
 }
 if(action==='commit'){
  const head=(await git(dir,['rev-parse','--verify','HEAD'])).stdout;
  await redundant(rep,5,'commit записан',[['cat-file',async()=>{const r=await git(dir,['cat-file','-e',head+'^{commit}']);return {ok:r.ok&&head!==before.head,detail:head!==before.head?'':'HEAD не се е променил'}}],['log',async()=>{const r=await git(dir,['log','-1','--format=%H']);return {ok:r.stdout===head&&head!==before.head,detail:'HEAD не се е променил'}}]]);
  const left=await stagedFiles(dir);rep.add(5,'индекс изчистен',left.length===0,left.length+' файла остават staged');
 }
 if(action==='link'||action==='connect'){
  const o=await originOf(dir);
  rep.add(5,'origin зададен',!ctx.url||o===ctx.url||o===toSsh(ctx.url)||o===toHttps(ctx.url),`origin = ${o||'—'}`);
  if(o)await redundant(rep,5,'remote достъпен',[['ls-remote',async()=>{const x=await retry(()=>lsRemote(o,dir));return {ok:x.ok,detail:x.detail}}],['gh/ssh алтернатива',async()=>{const alt=kindOf(o)==='https'?toSsh(o):toHttps(o);if(!alt)return {ok:false,detail:'няма'};const x=await lsRemote(alt,dir);return {ok:x.ok,detail:x.detail}}]]);
 }
 if(action==='clone'||action==='new'){
  await redundant(rep,5,'репозиторий създаден',[['rev-parse',async()=>{const r=await git(ctx.dest||dir,['rev-parse','--git-dir']);return {ok:r.ok,detail:r.stderr}}],['.git',async()=>({ok:fs.existsSync(path.join(ctx.dest||dir,'.git'))})]]);
  if(action==='clone')await redundant(rep,5,'HEAD',[['rev-parse',async()=>{const r=await git(ctx.dest,['rev-parse','--verify','HEAD']);return {ok:r.ok,detail:'празно репо'}}]]).then(()=>{rep.checks=rep.checks.map(c=>c.name==='HEAD'&&!c.ok?{...c,ok:true,level:'warn'}:c)});
 }
 if(action==='publish'||action==='create'){
  const o=await originOf(dir);
  await redundant(rep,5,'remote съдържа commit',[['ls-remote',async()=>{const x=await retry(async()=>{const r=await lsRemote(o,dir);return {...r,ok:r.ok&&!r.empty}});return {ok:x.ok,detail:x.detail}}],['gh repo view',async()=>{const m=/github\.com[/:]([\w.-]+\/[\w.-]+?)(?:\.git)?$/.exec(o||'');if(!m)return {ok:false,detail:'не е GitHub'};const r=await sh('gh',['repo','view',m[1],'--json','pushedAt','-q','.pushedAt']);return {ok:r.ok&&!!r.stdout,detail:r.stderr}}]]);
 }
 return rep;
}

// Wraps an action: preflight -> apply -> post-verify. One automatic retry of the whole cycle on a
// transient failure of the apply step (network), never on a precondition failure.
async function guarded(action,ctx,fn,{retries=1}={}){
 const {rep:pre,method}=await preflight(action,ctx);
 if(!pre.ok){
  const e=Error('Проверката блокира „'+action+'“:\n'+pre.blockers.map(c=>`✗ L${c.layer} ${c.name}: ${c.detail}`).join('\n'));
  e.guard={pre:pre.summary(),blocked:true};throw e;
 }
 if(ctx.apply===false)return {...(await fn(method)),guard:{pre:pre.summary(),method:method?.method||null}};
 const apply=ctx.apply!==false;
 const before={head:ctx.dir?(await git(path.resolve(ctx.dir),['rev-parse','--verify','HEAD'])).stdout:''};
 if(method?.switched&&apply&&['push','update'].includes(action)){const s=await git(path.resolve(ctx.dir),['remote','set-url','origin',method.url]);pre.warn(3,'origin',s.ok?'origin превключен към работещия транспорт: '+method.url:'неуспешно превключване: '+s.stderr)}
 let result,attempt=0,err;
 for(;;){
  try{result=await fn(method);
   if(result&&result.ok===false&&!result.message)result.message='Неуспех';
   if(result&&result.ok===false&&attempt<retries&&/timed? ?out|network|could not resolve|connection/i.test(JSON.stringify(result))){attempt++;await sleep(1500);continue}
   break}
  catch(e){err=e;if(attempt<retries&&/timed? ?out|network|could not resolve|connection/i.test(e.message)){attempt++;err=null;await sleep(1500);continue}throw e}
 }
 const vctx={...ctx,url:method?.url||ctx.url,dir:result?.dir||ctx.dir,dest:result?.dir||ctx.dest};
 const post=(result&&result.ok===false)?null:await postVerify(action,vctx,before);
 const guard={pre:pre.summary(),post:post?post.summary():[],verified:post?post.ok:false,method:method?.method||null,attempts:attempt+1};
 if(post&&!post.ok){const e=Error('Операцията е изпълнена, но проверката след нея НЕ потвърди резултата:\n'+post.blockers.map(c=>`✗ L${c.layer} ${c.name}: ${c.detail}`).join('\n'));e.guard=guard;e.result=result;throw e}
 return {...(result||{}),guard};
}

module.exports={guarded,preflight,postVerify,selectMethod,kindOf,toSsh,toHttps,redundant,Report,lsRemote};
