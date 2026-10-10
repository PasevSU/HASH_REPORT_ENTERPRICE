(()=>{
'use strict';
// Unified "Repositories" hub: one tab bar + repository picker giving single-panel access
// to every repository option and information panel (Overview / Changes / History /
// Remote / Watchers / Rules / Sync). Reuses the existing panels; no logic is changed.
const $=id=>document.getElementById(id);
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const T={
 bg:{overview:'Преглед',changes:'Промени',history:'История',remote:'Remote',watchers:'Watchers',rules:'Правила',releases:'Релизи',details:'Детайли',sync:'Синхронизация',pick:'Изберете репозитори'},
 de:{overview:'Übersicht',changes:'Änderungen',history:'Verlauf',remote:'Remote',watchers:'Watcher',rules:'Regeln',releases:'Releases',details:'Details',sync:'Synchronisierung',pick:'Repository wählen'}
};
const TABS=[
 {id:'overview',sec:['repository','repo-table']},
 {id:'changes',sec:['changes-view']},
 {id:'history',sec:['history-view']},
 {id:'remote',sec:['github','ssh','connections']},
 {id:'watchers',sec:['watchers']},
 {id:'rules',sec:['rules']},
 {id:'releases',sec:['releases']},
 {id:'details',sec:['details']},
 {id:'sync',sec:['sync']}
];
const KEY='gitsu.repoTab';
let current=localStorage.getItem(KEY);
if(!TABS.some(t=>t.id===current))current='overview';

const main=document.querySelector('.main-column');if(!main)return;

const bar=document.createElement('nav');bar.id='repo-tabs';bar.className='repo-tabs';bar.setAttribute('role','tablist');bar.hidden=true;
for(const t of TABS){const b=document.createElement('button');b.type='button';b.className='repo-tab';b.dataset.tab=t.id;b.setAttribute('role','tab');b.onclick=()=>setTab(t.id);bar.appendChild(b)}
const pick=document.createElement('select');pick.id='repo-switcher';pick.setAttribute('aria-label',T.bg.pick);
pick.onchange=()=>{const d=pick.value;if(d&&typeof selectRepo==='function')selectRepo(d)};
bar.appendChild(pick);
main.prepend(bar);

const tt=key=>T[lang()]?.[key]||key;
function labels(){const l=T[lang()];for(const b of bar.querySelectorAll('.repo-tab'))b.textContent=l[b.dataset.tab]||b.dataset.tab;syncSwitcher()}

function syncSwitcher(){
 const dirs=typeof folders!=='undefined'?folders:[];
 const cur=typeof selected!=='undefined'?selected:null;
 pick.replaceChildren();
 const ph=document.createElement('option');ph.value='';ph.textContent=tt('pick');pick.appendChild(ph);
 for(const d of dirs){const o=document.createElement('option');o.value=d;o.textContent=typeof nameOf==='function'?nameOf(d):d;if(d===cur)o.selected=true;pick.appendChild(o)}
 pick.value=cur||'';
 pick.disabled=!dirs.length;
}

function activeView(){return document.querySelector('[data-view].active')?.dataset.view}

function apply(name){
 if(name===undefined)name=activeView();
 const repos=name==='repositories';
 bar.hidden=!repos;
 if(!repos)return;
 const active=TABS.find(t=>t.id===current)||TABS[0];
 const allowed=new Set(active.sec);
 for(const s of document.querySelectorAll('[data-section]')){
  if(TABS.some(t=>t.sec.includes(s.dataset.section)))s.hidden=!allowed.has(s.dataset.section);
 }
 for(const b of bar.querySelectorAll('.repo-tab')){const a=b.dataset.tab===current;b.classList.toggle('active',a);b.setAttribute('aria-selected',String(a))}
 syncSwitcher();
}

function setTab(id){if(!TABS.some(t=>t.id===id))return;current=id;localStorage.setItem(KEY,id);apply();window.GitSUPanels?.enter()}

// renderRepos() rebuilds #repo-rows on list/selection changes; mirror that into the picker.
const rows=$('repo-rows');
if(rows)new MutationObserver(()=>syncSwitcher()).observe(rows,{childList:true,subtree:true});
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{labels();apply()},0));

labels();apply();
window.GitSURepoTabs={apply,setTab};
})();
