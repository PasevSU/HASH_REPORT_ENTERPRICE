'use strict';
const $=id=>document.getElementById(id);const api=window.repoAPI;
// Localized UI: language choice is saved locally; user data and paths are never translated.
const LANGUAGES=['bg','de'];
let currentLanguage=LANGUAGES.includes(localStorage.getItem('gitsu.language'))?localStorage.getItem('gitsu.language'):'bg';
const t=(key)=>window.GITSU_I18N?.[currentLanguage]?.[key]||key;
function translateStatic(){
 const root=document.body;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
 for(const n of nodes){if(n.parentElement?.closest('script,style,pre,code,#repo-rows,#overview,#job-history,#health-status,#log,#copyresult,#github-panel,#watcher-panel,#rules-panel,#connections-panel,#settings-panel,#dashboard-panel,#repositories-panel,#repository-panel,#sync-panel,#system-panel,#activity-panel,#about-panel'))continue;
   if(n._gitsuOriginal===undefined)n._gitsuOriginal=n.nodeValue;
   const original=n._gitsuOriginal;const key=original.trim();if(!key)continue;
   if(window.GITSU_I18N?.bg?.[key])n.nodeValue=original.replace(key,t(key));
 }
 for(const el of document.querySelectorAll('[placeholder],[title]'))for(const a of ['placeholder','title']){
   if(!el.hasAttribute(a))continue;const field='_gitsuOriginal'+a;
   if(el[field]===undefined)el[field]=el.getAttribute(a);
   if(window.GITSU_I18N?.bg?.[el[field]])el.setAttribute(a,t(el[field]));
 }
 document.documentElement.lang=currentLanguage;
 document.title='GitSU SUPERUSER Enterprise Pro · '+(currentLanguage==='bg'?'Български':'Deutsch');
}
function changeLanguage(lang){
 if(!LANGUAGES.includes(lang))return;
 currentLanguage=lang;localStorage.setItem('gitsu.language',lang);
 translateStatic();updateBreadcrumb();
 GitSUUI.emit('repoCount',folders.length);
 GitSUUI.emit('repos');
 if(selected&&repoData.has(selected))GitSUUI.emit('overview',repoData.get(selected));
 GitSUUI.emit('jobs',jobs);
 if(lastHealth)GitSUUI.emit('health',lastHealth);
 if(lastResources)GitSUUI.emit('resources',lastResources);
}
let lastHealth=null,lastResources=null;

let selected=null,folders=[],repoData=new Map(),jobs=[];
const nameOf=dir=>String(dir).split(/[\\/]/).filter(Boolean).at(-1)||dir;
function log(x){const el=$('log');if(!el)return;el.textContent+=(el.textContent?'\n':'')+(typeof x==='string'?x:JSON.stringify(x,null,2));if(el.textContent.length>40000)el.textContent=el.textContent.slice(-30000);el.scrollTop=el.scrollHeight;}
function chip(label,kind=''){const e=document.createElement('span');e.className='chip '+kind;e.textContent=label;return e;}
function percent(x){return Number.isFinite(x)?Math.max(0,Math.min(100,x*100)).toFixed(1)+'%':'—'}
// Lightweight in-page event hub: panels subscribe; core emits on data/language changes.
window.GitSUUI=(function(){const m=new Map();return {on:(ev,fn)=>{if(!m.has(ev))m.set(ev,[]);m.get(ev).push(fn);},emit:(ev,data)=>{for(const fn of m.get(ev)||[])try{fn(data)}catch(e){log(e&&e.message||e)}}}})();

function show(info){
 if(!info||!info.dir)return;
 repoData.set(info.dir,info);
 if(!folders.includes(info.dir))folders.push(info.dir);
 selected=info.dir;
 updateBreadcrumb();
 GitSUUI.emit('overview',info);
 GitSUUI.emit('repos');
}
async function selectRepo(dir){try{show(await api.refresh(dir))}catch(e){log('Refresh: '+e.message)}}
async function refreshOne(dir){try{const r=await api.refresh(dir);repoData.set(dir,r);if(dir===selected)show(r);else GitSUUI.emit('repos')}catch(e){log(e.message)}}

// Persistent global breadcrumb (#5): folder + branch + status, visible on every view.
function updateBreadcrumb(){const info=selected?repoData.get(selected):null;$('crumb-folder').textContent=selected?nameOf(selected):(currentLanguage==='de'?'Kein Repository ausgewählt':'Няма избрано репозитори');const br=$('crumb-branch');br.textContent=info?.branch||(currentLanguage==='de'?'kein Branch':'без клон');br.className='chip'+(info?.branch?' blue':'');const st=$('crumb-status');st.textContent=info?(info.isRepo?(info.dirty?t('MODIFIED'):t('CLEAN')):t('NO GIT')):(currentLanguage==='de'?'nicht ausgewählt':'не е избран');st.className='chip '+(!info?'':info.isRepo?(info.dirty?'warn':'good'):'bad');$('crumb-path').textContent=selected||'';}

// Left-nav panel switcher: each logical function is its own panel.
const VIEW_SECTIONS={dashboard:['dashboard','repo-table'],repositories:['repository','repo-table','changes-view','history-view','github','ssh','connections','watchers','rules','releases','details','sync'],connections:['connections'],github:['github','ssh'],watchers:['watchers'],rules:['rules'],releases:['releases'],sync:['sync'],system:['system'],settings:['settings'],activity:['activity']};
function view(name){if(!VIEW_SECTIONS[name])name='dashboard';for(const b of document.querySelectorAll('[data-view]'))b.classList.toggle('active',b.dataset.view===name);const show=new Set(VIEW_SECTIONS[name]);for(const s of document.querySelectorAll('[data-section]'))s.hidden=!show.has(s.dataset.section);window.GitSURepoTabs?.apply(name);window.GitSUPanels?.enter();}
window.view=view;
// Enterprise lazy-panel manager: panels register a {visible,run} hook; enter() runs only the visible
// ones so hidden panels never build/render/fetch and their background work stays suspended.
window.GitSUPanels=(function(){const hooks=[];const sectionVisible=s=>{const el=document.querySelector('[data-section="'+s+'"]');return !!el&&!el.hidden};return {sectionVisible,hook:(id,visible,run)=>hooks.push({id,visible,run}),enter:()=>{for(const h of hooks){if(h.visible()){try{h.run()}catch(e){log(e&&e.message||e)}}}}}})();

api.on('state',s=>{folders=Array.isArray(s.folders)?s.folders:[];GitSUUI.emit('repoCount',folders.length);GitSUUI.emit('repos');Promise.allSettled(folders.map(refreshOne));});
api.on('repo',info=>{repoData.set(info.dir,info);if(!folders.includes(info.dir))folders.push(info.dir);if(!selected||selected===info.dir)show(info);else GitSUUI.emit('repos')});
api.on('error',log);api.on('log',log);
api.on('resources',m=>{lastResources=m;GitSUUI.emit('resources',m)});
api.on('jobs',d=>{if(Array.isArray(d))jobs=d;GitSUUI.emit('jobs',jobs)});
api.on('health',h=>{lastHealth=h;GitSUUI.emit('health',h)});

for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>view(b.dataset.view);
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('search').focus()}});
$('clock').textContent=t('LOCAL SESSION');
api.jobsList().then(d=>{if(Array.isArray(d))jobs=d;GitSUUI.emit('jobs',jobs)}).catch(e=>log(e.message));
api.health().then(h=>{lastHealth=h;GitSUUI.emit('health',h)}).catch(e=>log(e.message));
view('dashboard');
$("language-select").value=currentLanguage;$("language-select").onchange=e=>changeLanguage(e.target.value);translateStatic();updateBreadcrumb();

// Local-only legal viewer: immutable bundled texts, no network request.
const legalDocs={license:'legal/LICENSE.txt',notice:'legal/NOTICE.txt'};
async function showLegal(which){
 const dialog=$('legal-dialog');const area=$('legal-text');
 $('legal-title').textContent=which==='license'?'Apache License, Version 2.0':'NOTICE — PasevSU-DEV';
 area.textContent=currentLanguage==='de'?'Dokument wird geladen…':'Зареждане на документа…';
 dialog.showModal();
 try{const response=await fetch(legalDocs[which]);if(!response.ok)throw Error('HTTP '+response.status);area.textContent=await response.text();}
 catch(err){area.textContent=(currentLanguage==='de'?'Dokument konnte nicht geladen werden: ':'Документът не може да бъде зареден: ')+err.message;}
 area.scrollTop=0;
}
$('footer-license').addEventListener('click',()=>showLegal('license'));
$('legal-close').addEventListener('click',()=>$('legal-dialog').close());
$('legal-dialog').addEventListener('click',e=>{if(e.target===$('legal-dialog'))e.target.close()});