(()=>{
'use strict';
// Activity & Logs: operation journal + diagnostic event log.
const $=id=>document.getElementById(id);
const host=document.getElementById('activity-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
host.innerHTML='<div class="section-head"><div><div class="eyebrow" id="a-eyebrow"></div><h2><span id="a-label"></span> <span id="job-count" class="count">0</span></h2></div><button id="clear-log" class="outline"></button></div><div id="job-history" class="job-history"></div><details><summary id="a-summary"></summary><pre id="log" aria-live="polite"></pre></details>';
function labels(){
 $('a-eyebrow').textContent=t('AUDIT TRAIL');
 $('a-label').textContent=t('Operations & activity');
 $('clear-log').textContent=t('Clear view');
 $('a-summary').textContent=t('Diagnostic event log');
}
function renderJobs(data){
 if(!Array.isArray(data))return;
 $('job-count').textContent=data.length;
 const box=$('job-history');box.replaceChildren();
 if(!data.length){box.textContent=t('No recorded operations.');return;}
 for(const j of [...data].reverse().slice(0,25)){
  const row=el('div',{className:'job'}),title=el('strong'),state=el('span'),sub=el('small');
  title.textContent=(j.kind||t('Operation'))+' · '+nameOf(j.dir||'');
  state.className='job-state '+(j.status||'');
  state.textContent=j.status||t('unknown');
  sub.textContent=[j.updatedAt,j.reason].filter(Boolean).join(' · ');
  row.append(title,state,sub);box.append(row);
 }
}
$('clear-log').onclick=()=>{$('log').textContent=''};
window.GitSUUI.on('jobs',d=>{labels();renderJobs(d)});
window.GitSUPanels.hook('activity',()=>window.GitSUPanels.sectionVisible('activity'),()=>{labels();renderJobs(jobs)});
labels();renderJobs(jobs);
})();
