 'use strict';
const {app,BrowserWindow,ipcMain,dialog,shell}=require('electron');const path=require('node:path'),fs=require('node:fs');const {inspect,inspectAsync,git,planCopy,applyCopy,ensureRules}=require('./core');const {spawn}=require('node:child_process');const {GitHubBrowserAuth,invokeGh}=require('./github-auth');const {healthAsync:health}=require('./health');const {RepositoryLifecycle}=require('./lifecycle');const {GitOrchestrator}=require('./orchestrator');const {JobJournal}=require('./job-journal');const {OperationManager}=require('./operation-manager');const {ResourceController}=require('./resource-controller');const {PerformanceMonitor}=require('./performance-monitor');const {SystemMonitor}=require('./system-monitor');const {TaskTelemetry}=require('./task-telemetry');const {AutoSyncManager}=require('./auto-sync-manager');const guard=require('./guard');const gitops=require('../lib/gitops');const gitignore=require('../lib/gitignore');const repoSync=require('../lib/repo-sync');const releases=require('../lib/releases');const repoDetails=require('../lib/repo-details');const docs=require('../lib/docs');let orchestrator,operationManager,resources,performanceMonitor,telemetry;const autoSync=new AutoSyncManager({emit:(channel,data)=>emit(channel,data)});
// Portable mode: store all persistent state next to GitSU.exe, never in AppData.
// The launcher starts data/GitSU-Engine.exe; in development retain Electron defaults.
if(process.platform==='win32' && (app.isPackaged || process.env.GITSU_PORTABLE_DATA)){
 const portableRoot=path.resolve(path.dirname(process.execPath),'..');
 const dataRoot=process.env.GITSU_PORTABLE_DATA || path.join(portableRoot,'data','user-data');
 fs.mkdirSync(dataRoot,{recursive:true});
 app.setPath('userData',dataRoot);
}
let win;const jobs=new Map();const lifecycle=new RepositoryLifecycle({emit:(channel,data)=>emit(channel,data)});let poller=null;let state={folders:[],autoWatch:true};function stateFile(){return path.join(app.getPath('userData'),'state.json')}function save(){fs.writeFileSync(stateFile(),JSON.stringify(state,null,2))}function emit(channel,data){if(win&&!win.isDestroyed())win.webContents.send(channel,data)}
function registered(dir){const full=path.resolve(dir);if(!state.folders.includes(full))throw Error('Unregistered directory');return full}
// Enterprise cache: TTL-memoize expensive read-only IPC (remote status, diagnostics, gh account/repo
// listings, gitignore reads). Invalidation is wired into refresh() and every mutating handler.
const memoMap=new Map();function memoClear(prefix){if(!prefix){memoMap.clear();return}for(const k of [...memoMap.keys()])if(k.startsWith(prefix))memoMap.delete(k)}
async function memo(key,ttlMs,fn){const now=Date.now(),hit=memoMap.get(key);if(hit&&now-hit.at<ttlMs)return hit.value;const value=await fn();memoMap.set(key,{at:Date.now(),value});if(memoMap.size>800)memoMap.clear();return value}
function refresh(dir){memoClear(dir);return inspectAsync(dir).then(i=>emit('repo',i),e=>emit('error',{dir,message:e.message}))}
async function register(dir){const result=await lifecycle.add(dir,{createMissingRules:true});if(result.created.length)emit('log','Auto-created missing rules: '+result.created.join(', '));return result.info}
async function load(){health(path.join(__dirname,'..')).then(h=>emit('health',h));try{const s=JSON.parse(fs.readFileSync(stateFile(),'utf8'));if(Array.isArray(s.folders))state={folders:s.folders.filter(x=>typeof x==='string'),autoWatch:s.autoWatch!==false}}catch{}const valid=[];for(const dir of state.folders){try{const info=await register(dir);valid.push(info.dir)}catch(e){emit('error',{dir,message:e.message})}}state.folders=valid;save();emit('state',state);emit('jobs',operationManager.list());lifecycle.start()}
app.whenReady().then(()=>{const journal=new JobJournal(path.join(app.getPath('userData'),'job-journal.json'));performanceMonitor=new PerformanceMonitor().start();telemetry=new TaskTelemetry();const systemMonitor=new SystemMonitor();resources=new ResourceController({sample:()=>{const proc=performanceMonitor.sample(),system=systemMonitor.sample();return {...proc,cpu:system.cpu===null?1:system.cpu,systemCpu:system.cpu,cpuScope:'system',free:system.free};},adaptive:true,peakConcurrent:2});resources.on('metrics',m=>{lifecycle.updateLoad(m);emit('resources',m)});resources.start();orchestrator=new GitOrchestrator({journal,runner:(dir,args,timeout)=>resources.run(()=>require('./orchestrator').runGit(dir,args,timeout),{urgent:true})});operationManager=new OperationManager({journal,lock:require('./repo-lock').withRepoLock,execute:({dir,action,args,apply})=>{const message=args.includes('--message')?args[args.indexOf('--message')+1]:undefined;return action==='push'?gitops.push(dir,{message,apply}):gitops.pull(dir,{apply})},onChange:jobs=>{emit('jobs',jobs);emit('task-telemetry',telemetry.snapshot())},telemetry});win=new BrowserWindow({width:1440,height:900,minWidth:900,minHeight:600,backgroundColor:'#101827',webPreferences:{preload:path.join(__dirname,'preload.js'),contextIsolation:true,nodeIntegration:false,sandbox:true}});win.setTitle('GitSU SUPERUSER — Enterprise Pro');win.loadFile(path.join(__dirname,'index.html'));win.webContents.setWindowOpenHandler(({url})=>{if(url==='https://pasevsu.github.io/' )shell.openExternal(url);return {action:'deny'}});win.webContents.on('will-navigate',(event)=>event.preventDefault());win.webContents.on('did-finish-load',load)});app.on('window-all-closed',()=>app.quit());app.on('before-quit',()=>{lifecycle.close();orchestrator?.close();resources?.close();performanceMonitor?.close();autoSync.close()});
ipcMain.handle('health',()=>health(path.join(__dirname,'..')));ipcMain.handle('add',async()=>{const r=await dialog.showOpenDialog(win,{properties:['openDirectory']});if(r.canceled)return null;const dir=path.resolve(r.filePaths[0]);const info=await register(dir);if(!state.folders.includes(dir)){state.folders.push(dir);save()}return info});
ipcMain.handle('remove',(_e,dir)=>{dir=registered(dir);state.folders=state.folders.filter(x=>x!==dir);lifecycle.remove(dir);save();return state.folders});
ipcMain.handle('refresh',(_e,dir)=>inspectAsync(registered(dir)));ipcMain.handle('rules',async(_e,dir)=>ensureRules(registered(dir)));
ipcMain.handle('gitignore:load',(_e,dir)=>{dir=registered(dir);return memo(dir+'|gitignore:load',2000,()=>{const file=path.join(dir,'.gitignore');if(!fs.existsSync(file))return {exists:false,content:'',model:gitignore.emptyModel()};const content=fs.readFileSync(file,'utf8');return {exists:true,content,model:gitignore.parse(content)}})});
ipcMain.handle('gitignore:save',async(_e,{dir,model})=>{dir=registered(dir);const content=gitignore.serialize(model);fs.writeFileSync(path.join(dir,'.gitignore'),content,'utf8');refresh(dir);return {ok:true,content}});
ipcMain.handle('gitignore:meta',()=>({presets:gitignore.PRESETS,categories:gitignore.CATEGORIES,globalHint:gitignore.GLOBAL_HINT}));
ipcMain.handle('gitignore:serialize',(_e,model)=>gitignore.serialize(model));
ipcMain.handle('gitignore:save-raw',async(_e,{dir,content})=>{dir=registered(dir);fs.writeFileSync(path.join(dir,'.gitignore'),String(content??''),'utf8');refresh(dir);return {ok:true}});
ipcMain.handle('gitignore:add',async(_e,{dir,path:rel})=>{dir=registered(dir);let p=String(rel||'').trim();if(!p)throw Error('Path is required');p=p.replace(/\\/g,'/').replace(/^\.\//,'');if(p.startsWith('/')||p.split('/').includes('..')||p==='.gitignore')throw Error('Invalid path for ignore rule');p=p.replace(/[\\*?[\]]/g,(c)=>'\\'+c);if(/^[#!]/.test(p))p='\\'+p;const file=path.join(dir,'.gitignore');const existing=fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';if(existing.split(/\r?\n/).some(l=>l.trim()===p))return {ok:true,entry:p,already:true};let next=existing;if(next&&!next.endsWith('\n'))next+='\n';next+=p+'\n';fs.writeFileSync(file,next,'utf8');refresh(dir);return {ok:true,entry:p,already:false}});
ipcMain.handle('link',async(_e,{dir,url,branch})=>{if(!/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(?:\.git)?$|^git@github\.com:[\w.-]+\/[\w.-]+(?:\.git)?$/.test(url))throw Error('Invalid GitHub URL');dir=registered(dir);return gitops.link(dir,url,{branch:branch||undefined})});
// Local git-config remote edits: remove or change a wrong/mistaken remote. Confirmation happens in the UI.
ipcMain.handle('remote:remove',async(_e,dir)=>{dir=registered(dir);const cur=await gitops.resolveRemote(dir);if(!cur)throw Error('No remote configured');const out=await gitops.runGit(dir,['remote','remove',cur.name]);if(!out.ok)throw Error(out.stderr||out.stdout||'git remote remove failed');refresh(dir);return {name:cur.name,url:cur.url}});
ipcMain.handle('remote:set-url',async(_e,{dir,url,remote})=>{dir=registered(dir);url=String(url||'').trim();if(!url)throw Error('URL is required');const cur=await gitops.resolveRemote(dir);const name=remote||cur?.name||'origin';const before=cur?.url||'';const out=await gitops.runGit(dir,cur?['remote','set-url',name,url]:['remote','add',name,url]);if(!out.ok)throw Error(out.stderr||out.stdout||'git remote set-url failed');refresh(dir);return {name,from:before,to:url}});
ipcMain.handle('copy-plan',(_e,{from,to})=>planCopy(registered(from),to));ipcMain.handle('copy-apply',async(_e,plan)=>{if(!plan||!Array.isArray(plan.changes))throw Error('Invalid plan');registered(plan.src);return applyCopy(plan)});
ipcMain.handle('operation',async(_e,{dir,action,message,apply})=>{if(!state.folders.includes(dir))throw Error('Unregistered directory');const args=message&&action==='push'?['--message',message]:[];try{return await guard.guarded(action,{dir,apply:!!apply,message,needCommit:false},()=>operationManager.run({dir,action,args,apply:!!apply}))}finally{refresh(dir)}});
ipcMain.handle('jobs:list',()=>operationManager.list());ipcMain.handle('jobs:clear',()=>operationManager.clear());
ipcMain.handle('watch-status',()=>lifecycle.status());

// Read-only remote divergence check. Never fetch, pull or push without explicit approval.
ipcMain.handle('remote-status',(_e,x)=>{const dir=typeof x==='string'?x:x?.dir;const d=registered(dir);const fetchOpt=!!(x&&typeof x==='object'&&x.fetch);return memo(d+'|remote-status|'+(fetchOpt?'f':'l'),2000,async()=>{try{const s=await repoSync.status(d,{fetch:fetchOpt});return {...s,requiresReview:!s.upstreamKnown||(s.behind??0)>0}}catch{const s=await repoSync.status(d).catch(()=>null);if(s)return {...s,requiresReview:!s.upstreamKnown||(s.behind??0)>0,stale:true};return {dir:d,branch:null,dirty:false,remote:null,remoteUrl:null,upstream:false,sha:null,ahead:null,behind:null,upstreamKnown:false,requiresReview:true}}})});

// GitSU v0.26: guarded configuration generation and explicit repository-index export.
const configGenerator=require('./configuration-generator');
ipcMain.handle('workflow:plan',(_e,dir)=>configGenerator.planWorkflow(registered(dir)));
ipcMain.handle('workflow:apply',(_e,dir)=>configGenerator.applyWorkflow(registered(dir)));
ipcMain.handle('index:export',async()=>{const choice=await dialog.showSaveDialog(win,{title:'Export repositories.json',defaultPath:path.join(app.getPath('documents'),'repositories.json'),filters:[{name:'JSON',extensions:['json']}],properties:['createDirectory']});if(choice.canceled||!choice.filePath)return null;return configGenerator.exportRepositoryIndex(state.folders,choice.filePath)});

// Home Assistant repository operations: read-only validation and guarded scaffolding.
const haRepository=require('./home-assistant');
ipcMain.handle('ha:validate',(_e,{dir,type})=>haRepository.validate(registered(dir),type));
ipcMain.handle('ha:scaffold-plan',(_e,{dir,domain})=>haRepository.scaffoldPlan(registered(dir),domain));
ipcMain.handle('ha:scaffold-apply',(_e,{dir,domain})=>haRepository.scaffoldApply(registered(dir),domain));

// GitHub authentication is delegated to official gh CLI. Never collect credentials in GitSU.
const githubAuth=new GitHubBrowserAuth({spawnImpl:spawn,openBrowser:url=>shell.openExternal(url),emit:(message)=>emit('github-auth',message)});
ipcMain.handle('github:auth-status',()=>githubAuth.status());
ipcMain.handle('github:auth-start',()=>{memoClear('gh');return githubAuth.start()});
ipcMain.handle('github:auth-cancel',()=>githubAuth.cancel());

ipcMain.handle('github:auth-token',(_e,token)=>{memoClear('gh');return githubAuth.loginWithToken(token)});
ipcMain.handle('github:account',()=>memo('gh|account',15000,async()=>{const st=await invokeGh(['auth','status','--hostname','github.com'],{timeoutMs:15000});const login=st.ok?await invokeGh(['api','user','-q','.login'],{timeoutMs:15000}):null;let method=null;if(st.ok){if(process.env.GITHUB_TOKEN)method='token';else if(/(ssh protocol|ssh\.git|configured to use ssh)/i.test(st.output||''))method='ssh';else method='browser'}return {authenticated:st.ok,cliAvailable:!String(st.error||'').includes('not installed'),username:login&&login.ok?String(login.output||'').trim():null,method,message:st.ok?('Authenticated as '+((login&&login.ok&&login.output)?String(login.output).trim():'GitHub account')):(st.error||st.output||'Not authenticated')}}));
ipcMain.handle('github:repos',()=>memo('gh|repos',30000,async()=>{const r=await invokeGh(['repo','list','--limit','200','--json','nameWithOwner,sshUrl,url'],{timeoutMs:25000});if(!r.ok)return {ok:false,repos:[],error:r.error||r.output||'gh repo list failed'};let repos=[];try{repos=JSON.parse(r.output)}catch{return {ok:false,repos:[],error:'Could not parse gh repo list output'}}return {ok:true,repos:repos.map(x=>({name:x.nameWithOwner||'',https:x.url||'',ssh:x.sshUrl||''}))}}));
ipcMain.handle('github:auth-logout',async()=>{const r=await invokeGh(['auth','logout','--hostname','github.com'],{timeoutMs:15000});memoClear('gh');return {ok:r.ok,message:r.ok?('Signed out of GitHub'):(r.error||r.output||'gh auth logout failed')}});
ipcMain.handle('github:scopes',()=>memo('gh|scopes',15000,async()=>{
 const r=await invokeGh(['api','-i','user'],{timeoutMs:20000});
 if(!r.ok)return {ok:false,authenticated:false,scopes:[],permissions:{},tokenType:null,error:r.error||r.output||'gh api failed'};
 const out=String(r.output||'');
 const scopesHeader=(/^x-oauth-scopes:\s*(.*)$/im.exec(out)?.[1]||'').trim();
 const permsHeader=(/^x-accepted-github-permissions:\s*(.*)$/im.exec(out)?.[1]||'').trim();
 const tokenType=(/^x-github-token-type:\s*(.*)$/im.exec(out)?.[1]||'').trim()||null;
 const scopes=scopesHeader?scopesHeader.split(',').map(s=>s.trim()).filter(Boolean):[];
 const permissions={};
 if(permsHeader)for(const pair of permsHeader.split(',')){const i=pair.indexOf('=');if(i>0)permissions[pair.slice(0,i).trim()]=pair.slice(i+1).trim();}
 return {ok:true,authenticated:true,scopes,permissions,tokenType,error:null};
}));

// Per-repository Git trust requires explicit user confirmation in the workflow UI.
const repositoryTrust=require('./repository-trust');
ipcMain.handle('repository:trust-probe',(_e,dir)=>repositoryTrust.probe(registered(dir)));
ipcMain.handle('repository:trust-apply',(_e,dir)=>repositoryTrust.trust(registered(dir)));

// Read-only preflight: diagnose Git, NAS ownership, remote and GitHub CLI separately.
const {diagnose}=require('./repository-diagnostics');
ipcMain.handle('repository:diagnose',(_e,dir)=>{const d=registered(dir);return memo(d+'|diagnose',5000,()=>diagnose(d))});

// Separate opt-in automatic synchronization, never silently enabled on launch.
ipcMain.handle('auto-sync:start',(_e,x)=>{const dir=registered(x.dir);return autoSync.start({dir,branch:x.branch,apply:x.apply===true,poll:x.poll??5,debounce:x.debounce??30,lease:x.lease!==false,node:x.node||''})});
ipcMain.handle('auto-sync:stop',(_e,dir)=>autoSync.stop(registered(dir)));
ipcMain.handle('auto-sync:lease',(_e,x)=>require('./auto-sync-manager').leaseCommand(x?.break===true?'break':'status',{dir:registered(x?.dir),branch:x?.branch}));ipcMain.handle('auto-sync:status',()=>autoSync.status());

// New repositories: clone (fetch from remote), create local, publish to a new GitHub repository.
const repoCreate=require('./repo-create');
async function adopt(dir){const info=await register(dir);if(!state.folders.includes(info.dir)){state.folders.push(info.dir);save();emit('state',state)}emit('repo',info);return info}
ipcMain.handle('repo:clone-plan',(_e,x)=>repoCreate.planClone({url:x?.url,dest:x?.dest}));
ipcMain.handle('repo:clone-apply',async(_e,x)=>{const r=await guard.guarded('clone',{url:x?.url,dest:x?.dest,dir:x?.dest,mayCreate:true},()=>repoCreate.applyClone({url:x?.url,dest:x?.dest}));await adopt(r.dir);return r});
ipcMain.handle('repo:new-plan',(_e,x)=>repoCreate.planNewLocal({parent:x?.parent,name:x?.name,branch:x?.branch}));
ipcMain.handle('repo:new-apply',async(_e,x)=>{const r=await repoCreate.applyNewLocal({parent:x?.parent,name:x?.name,branch:x?.branch},ensureRules);await adopt(r.dir);return r});
ipcMain.handle('repo:publish-plan',(_e,x)=>repoCreate.planPublish({...x,dir:registered(x?.dir)}));
ipcMain.handle('repo:publish-apply',async(_e,x)=>{const d=registered(x?.dir);const r=await guard.guarded('publish',{dir:d,name:x?.name,needCommit:false},()=>repoCreate.applyPublish({...x,dir:d},ensureRules));refresh(r.dir);return r});
const sshKeys=require('./ssh');ipcMain.handle('ssh:status',()=>sshKeys.status());ipcMain.handle('ssh:generate',(_e,x)=>sshKeys.generate(x));ipcMain.handle('ssh:add',(_e,x)=>sshKeys.addToGitHub(x));ipcMain.handle('ssh:test',()=>sshKeys.test());ipcMain.handle('ssh:use',(_e,d)=>sshKeys.useSshForRepo(d));ipcMain.handle('ssh:use-https',(_e,d)=>sshKeys.useHttpsForRepo(d));const connector=require('./connect');ipcMain.handle('connect:inspect',(_e,x)=>connector.inspectFolder(x?.dir,x?.repo||''));ipcMain.handle('connect:plan',(_e,x)=>connector.plan(x));ipcMain.handle('connect:apply',async(_e,x)=>{const p=await connector.plan(x);const map={create:'create',link:'link',clone:'clone',local:'new'}[p.mode];const run=()=>connector.apply(x,{ensureRules});const r=map?await guard.guarded(map,{dir:p.dir,dest:p.dir,url:p.url,name:p.name,owner:(p.repository||'').split('/')[0],mayCreate:true,hasRepo:false},run):await run();await adopt(r.dir);return r});
const gv=require('./git-view');ipcMain.handle('gv:status',(_e,d)=>gv.status(registered(d)));ipcMain.handle('gv:diff',(_e,x)=>gv.diff(registered(x?.dir),{file:x?.file,staged:x?.staged===true}));ipcMain.handle('gv:stage',async(_e,x)=>{const d=registered(x?.dir);await gv.stage(d,x?.files);refresh(d)});ipcMain.handle('gv:unstage',async(_e,x)=>{const d=registered(x?.dir);await gv.unstage(d,x?.files);refresh(d)});ipcMain.handle('gv:commit',async(_e,x)=>{const d=registered(x?.dir);const r=await guard.guarded('commit',{dir:d,message:x?.message},()=>gv.commit(d,{message:x?.message}));refresh(d);return r});ipcMain.handle('gv:log',(_e,x)=>gv.log(registered(x?.dir),{limit:x?.limit,skip:x?.skip}));ipcMain.handle('gv:show',(_e,x)=>gv.show(registered(x?.dir),x?.sha));
// Push HEAD without staging/committing: used by the changed-files upload selector after the
// selected subset has already been committed. Guarded but never auto-commits.
ipcMain.handle('git:push-head',async(_e,dir)=>{dir=registered(dir);return guard.guarded('push',{dir,apply:true,needCommit:false},async()=>{const branch=await gitops.currentBranch(dir);const upstream=await gitops.hasUpstream(dir,branch);const r=await gitops.runGit(dir,upstream?['push']:['push','--set-upstream','origin',branch],{timeout:120000});if(!r.ok)throw Error(r.stderr||r.stdout||'git push failed');return {ok:true,stdout:r.stdout}}) });
ipcMain.handle('repo-sync:status',async(_e,{dir,fetch})=>repoSync.status(registered(dir),{fetch:fetch===true}));ipcMain.handle('repo-sync:sync',async(_e,{dir,message,apply})=>{const d=registered(dir);return guard.guarded('update',{dir:d,apply:!!apply},()=>repoSync.sync(d,{apply:!!apply,message}))});ipcMain.handle('releases:list',(_e,{dir})=>releases.list(registered(dir)));ipcMain.handle('releases:latest',(_e,{dir})=>releases.latest(registered(dir)));ipcMain.handle('releases:tags',(_e,{dir})=>releases.tags(registered(dir)));ipcMain.handle('releases:create',(_e,x)=>releases.create(registered(x?.dir),{tag:x?.tag,title:x?.title,notes:x?.notes,target:x?.target,prerelease:x?.prerelease===true,draft:x?.draft===true}));ipcMain.handle('releases:delete',(_e,x)=>releases.remove(registered(x?.dir),x?.tag));
// Repository metadata (description, homepage, topics, visibility, default branch) via gh repo view/edit.
ipcMain.handle('repo:details',(_e,dir)=>repoDetails.get(registered(dir)));
ipcMain.handle('repo:details-edit',(_e,x)=>repoDetails.edit(registered(x?.dir),{description:x?.description,homepage:x?.homepage,topics:x?.topics,removeTopics:x?.removeTopics,visibility:x?.visibility,defaultBranch:x?.defaultBranch}));
// Standard project documentation generator (README / CONTRIBUTING / SECURITY).
ipcMain.handle('docs:meta',()=>({defaults:docs.DEFAULT_META,docs:docs.DOCS}));
ipcMain.handle('docs:generate',(_e,meta)=>docs.generateAll(meta));
ipcMain.handle('docs:write',async(_e,{dir,meta,files})=>{const d=registered(dir);const all=docs.generateAll(meta);const wanted=Array.isArray(files)?files:Object.keys(all);const written=[];for(const f of wanted){if(!all[f])continue;fs.writeFileSync(path.join(d,f),all[f],'utf8');written.push(f)}return {ok:true,written}});
ipcMain.handle('repo:pick-folder',async()=>{const r=await dialog.showOpenDialog(win,{properties:['openDirectory','createDirectory']});return r.canceled?null:path.resolve(r.filePaths[0])});
