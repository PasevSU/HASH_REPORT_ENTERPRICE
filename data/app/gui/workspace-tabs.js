(()=>{
'use strict';
// Tabbed workspace for the Repository view. Moves existing sections into tabs; no logic is changed.
const D={
 bg:{start:'Старт',overview:'Преглед',ssh:'SSH',changes:'Промени',ops:'Операции',sync:'Синхронизация',history:'История',settings:'Настройки'},
 de:{start:'Start',overview:'Übersicht',ssh:'SSH',changes:'Änderungen',ops:'Vorgänge',sync:'Synchronisierung',history:'Verlauf',settings:'Einstellungen'}
};
const TABS=[
 ['start',['start','repositories']],
 ['overview',['details']],
 ['changes',['changes-view','hub']],
 ['ops',['hub']],
 ['sync',['hub','watcher','sync']],
 ['history',['history-view','activity']],
 ['settings',['remotes','policies']],
 ['ssh',['ssh']]
];
const NONE=['start','ops','ssh'];
const KEY='gitsu.tab';
let current=localStorage.getItem(KEY);if(!TABS.some(t=>t[0]===current))current='changes';
const lang=()=>document.getElementById('language-select')?.value||'bg';
const main=document.querySelector('.main-column');
const watcher=document.getElementById('auto-sync-start')?.closest('section');
if(watcher){watcher.dataset.section='watcher';main.appendChild(watcher)}
const sections=()=>[...document.querySelectorAll('[data-section]')];

const bar=document.createElement('nav');bar.id='repo-tabs';bar.className='repo-tabs';bar.setAttribute('role','tablist');
const title=document.createElement('span');title.className='repo-tabs-title';
for(const [id] of TABS){const b=document.createElement('button');b.type='button';b.className='repo-tab';b.dataset.tab=id;b.setAttribute('role','tab');b.onclick=()=>setTab(id);bar.appendChild(b)}
const pick=document.createElement('button');pick.type='button';pick.className='repo-tab repo-pick';pick.onclick=()=>{picking=true;apply()};bar.prepend(pick);bar.appendChild(title);
const repos=document.querySelector('[data-section="repositories"]');
repos.insertAdjacentElement('afterend',bar);

function labels(){pick.textContent=lang()==='de'?'☰ Repository wechseln':'☰ Смени репозитори';for(const b of bar.children)if(b.dataset.tab)b.textContent=D[lang()]?.[b.dataset.tab]||b.dataset.tab}
function name(){const n=document.getElementById('hub-name');title.textContent=n?n.textContent:''}
function isRepoView(){return document.querySelector('[data-view="repositories"]')?.classList.contains('active')}

function hasSelection(){const n=document.getElementById('hub-name')?.textContent||'';return n!==''&&!/^(Изберете репозитори|Repository auswählen)$/.test(n.trim())}
let picking=true;
function activeView(){return document.querySelector('[data-view].active')?.dataset.view}
function apply(){
 const v=activeView(),work=document.querySelector('.workspace'),tabbed=v==='repositories';
 const none=tabbed&&!hasSelection();
 const showTabs=tabbed&&(none||(hasSelection()&&!picking));
 let cur=current;if(none&&!NONE.includes(cur))cur='start';if(!none&&cur==='start')cur='changes';
 work.classList.toggle('tabbed',tabbed);bar.hidden=!showTabs;
 for(const s of sections())s.classList.remove('tab-off');
 if(watcher&&v!=='dashboard'&&!tabbed)watcher.classList.add('tab-off');if(!tabbed)document.querySelector('[data-section=ssh]')?.classList.add('tab-off');
 if(v==='dashboard'){for(const s of sections())if(!['repositories','watcher'].includes(s.dataset.section))s.classList.add('tab-off');return}
 if(!tabbed)return;
 const show=new Set(showTabs?TABS.find(t=>t[0]===cur)[1]:['repositories']);
 for(const s of sections()){const on=show.has(s.dataset.section);s.classList.toggle('tab-off',!on);if(on)s.hidden=false}
 pick.hidden=none;for(const b of bar.children)if(b.dataset.tab){const a=b.dataset.tab===cur;b.hidden=none?!NONE.includes(b.dataset.tab):b.dataset.tab==='start';b.classList.toggle('active',a);b.setAttribute('aria-selected',a)}
}function setTab(id){if(!TABS.some(t=>t[0]===id))return;current=id;localStorage.setItem(KEY,id);apply()}

const origView=window.view;
window.view=function(n){const r=origView.apply(this,arguments);apply();return r};
document.addEventListener('click',e=>{
 if(e.target.closest('[data-operation]'))setTab('ops');
 const row=e.target.closest('[data-section="repositories"] tbody tr');
 if(row&&!row.querySelector('.empty')){picking=false;setTimeout(()=>{if(activeView()==='dashboard'&&window.view)window.view('repositories');else apply()},0)}
},true);
document.getElementById('language-select')?.addEventListener('change',()=>setTimeout(labels,0));
const hn=document.getElementById('hub-name');if(hn)new MutationObserver(name).observe(hn,{childList:true,characterData:true,subtree:true});
new MutationObserver(apply).observe(document.getElementById('navigation'),{attributes:true,subtree:true,attributeFilter:['class']});
if(hn)new MutationObserver(apply).observe(hn,{childList:true,characterData:true,subtree:true});
labels();name();apply();
window.GitSUTabs={setTab};
})();

