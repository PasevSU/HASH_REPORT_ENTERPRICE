(()=>{
'use strict';
// Dashboard: enterprise metrics grid (registered repos, active ops, CPU, event-loop lag, free RAM).
const $=id=>document.getElementById(id);
const host=document.getElementById('dashboard-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const percent=x=>Number.isFinite(x)?Math.max(0,Math.min(100,x*100)).toFixed(1)+'%':'—';
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
const cards=[['REGISTERED REPOSITORIES','metric-repos','▥'],['ACTIVE OPERATIONS','metric-active','⇄'],['SYSTEM CPU','metric-cpu','◴'],['EVENT LOOP LAG','lag','⌁'],['FREE MEMORY','metric-ram','▤']];
const grid=el('div',{className:'metric-grid'});
const refs=cards.map(([label,id,glyph])=>{
 const m=el('div',{className:'metric'});
 const lab=el('span'),strong=el('strong',{id}),g=el('b',{textContent:glyph}),small=el('small');
 m.append(lab,el('div',{},strong,g),small);
 grid.appendChild(m);
 return {label,lab,strong,small};
});
host.appendChild(grid);
const nFolders=()=>folders.length;
function labels(){
 refs.forEach(r=>r.lab.textContent=t(r.label));
 refs[3].small.textContent=t('Live process measurement');
 refs[4].small.textContent=t('Operating system');
}
function count(n){refs[0].strong.textContent=String(n);refs[0].small.textContent=n+' '+t('registered');}
function resources(m){
 refs[1].strong.textContent=String(m?.active??0);
 refs[1].small.textContent=String(m?.queued??0)+' '+t('queued');
 refs[2].strong.textContent=percent(m?.systemCpu??m?.cpu);
 refs[2].small.textContent=m?(m.mode||t('unknown')):t('Awaiting metrics');
 refs[3].strong.textContent=Number.isFinite(m?.eventLoopLagMs)?m.eventLoopLagMs.toFixed(1)+' ms':'—';
 refs[4].strong.textContent=percent(m?.free);
}
labels();count(nFolders());resources(null);
window.GitSUUI.on('repoCount',n=>{labels();count(n)});
window.GitSUUI.on('resources',m=>{labels();resources(m)});
window.GitSUPanels.hook('dashboard',()=>window.GitSUPanels.sectionVisible('dashboard'),()=>{labels();count(nFolders());resources(lastResources)});
})();
