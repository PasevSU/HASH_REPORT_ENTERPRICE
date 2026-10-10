(()=>{
'use strict';
// Live watcher / lease view inside the Sync tab.
const $=id=>document.getElementById(id),api=window.repoAPI;
const anchor=$('auto-sync-status');if(!anchor)return;
const T={bg:{lease:'Lease статус',brk:'Освободи lease',none:'Няма активен watcher.',node:'Възел',role:'Роля',writer:'ПИШЕ',follower:'СЛЕДВА',off:'без lease',state:'Състояние',confirm:'Принудително освобождаване на lease? Другият възел може да започне да пише веднага.'},
 de:{lease:'Lease-Status',brk:'Lease freigeben',none:'Kein aktiver Watcher.',node:'Knoten',role:'Rolle',writer:'SCHREIBT',follower:'FOLGT',off:'ohne Lease',state:'Zustand',confirm:'Lease zwangsweise freigeben? Ein anderer Knoten kann sofort schreiben.'}};
const L=()=>T[$('language-select')?.value]||T.bg;
const live=document.createElement('div');live.id='sync-live';live.className='sync-live';
const log=document.createElement('pre');log.id='sync-recent';log.className='log-preview';
const row=document.createElement('div');row.className='action-row';
const bs=document.createElement('button'),bb=document.createElement('button');
for(const b of [bs,bb]){b.type='button';b.className='outline'}
row.append(bs,bb);anchor.after(live,log,row);anchor.hidden=true;
const out=document.createElement('p');out.className='hint';row.after(out);
const sel=()=>typeof selected!=='undefined'?selected:null;
const branch=()=>{try{return repoData.get(sel())?.branch||'main'}catch{return 'main'}};
function labels(){bs.textContent=L().lease;bb.textContent=L().brk}
function render(jobs){
 const l=L(),cur=sel();
 if(!Array.isArray(jobs)||!jobs.length){live.textContent=l.none;log.textContent='';return}
 live.replaceChildren();
 for(const j of jobs){
  const role=!j.apply?'DRY RUN':!j.lease?l.off:(j.phase==='FOLLOWING'?l.follower:l.writer);
  const d=document.createElement('div');d.className='resource-row';
  const a=document.createElement('span'),b=document.createElement('b');
  a.textContent=j.dir.split(/[\\/]/).filter(Boolean).pop()||j.dir;
  b.textContent=`${j.phase||j.state} · ${role}${j.node?' · '+j.node:''}`;
  d.append(a,b);live.appendChild(d);
 }
 const j=jobs.find(x=>x.dir===cur)||jobs[0];log.textContent=(j.recent||[]).join('\n');
}
async function poll(){try{render(await api.autoSyncStatus())}catch{}}
api.on('auto-sync-state',render);
bs.onclick=async()=>{const d=sel();if(!d){out.textContent='—';return}out.textContent='…';const r=await api.autoSyncLease({dir:d,branch:branch()});out.textContent=r.message||(r.ok?'OK':'Error')};
bb.onclick=async()=>{const d=sel();if(!d||!(await gsConfirm(L().confirm)))return;out.textContent='…';const r=await api.autoSyncLease({dir:d,branch:branch(),break:true});out.textContent=r.message||(r.ok?'OK':'Error')};
document.getElementById('language-select')?.addEventListener('change',()=>setTimeout(()=>{labels();poll()},0));
labels();poll();setInterval(poll,5000);
})();
