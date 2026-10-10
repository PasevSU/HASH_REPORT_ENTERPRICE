(()=>{
'use strict';
// Watcher creation/management panel (#4): build UI on the existing auto-sync backend.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.autoSyncStatus)return;
const host=document.getElementById('watcher-panel');if(!host)return;
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const sel=()=>typeof selected!=='undefined'?selected:null;
const nameOf=d=>String(d).split(/[\\/]/).filter(Boolean).pop()||d;
const T={
 bg:{title:'Наблюдатели на репозитори',create:'Създай наблюдател',manage:'Активни наблюдатели',folder:'Папка',branch:'Клон',mode:'Режим',dry:'Само проверка (dry run)',auto:'Автоматичен commit + push',lease:'Роля на lease',leaseHint:'Само един активен писател може да държи lease на клон.',start:'Стартирай',stop:'Спри',stopAll:'Спри всички',none:'Няма активни наблюдатели.',running:'активен',state:'Състояние',recent:'Последни събития',pick:'Изберете папка или репозитори.',invalid:'Невалидна папка.',confirmAuto:'Включване на автоматичен COMMIT + PUSH за {0} ({1})? Промените ще се качват без допълнителни подкани.',wait:'Изпълнява се…'},
 de:{title:'Repository-Watcher',create:'Watcher erstellen',manage:'Aktive Watcher',folder:'Ordner',branch:'Branch',mode:'Modus',dry:'Nur Prüfung (dry run)',auto:'Automatisch commit + push',lease:'Lease-Rolle',leaseHint:'Nur ein aktiver Schreiber kann das Lease eines Branches halten.',start:'Starten',stop:'Stoppen',stopAll:'Alle stoppen',none:'Keine aktiven Watcher.',running:'aktiv',state:'Status',recent:'Letzte Ereignisse',pick:'Ordner oder Repository wählen.',invalid:'Ungültiger Ordner.',confirmAuto:'Automatischen COMMIT + PUSH für {0} ({1}) aktivieren? Änderungen werden ohne weitere Nachfragen hochgeladen.',wait:'Läuft…'}
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const h=el('h2'),eyebrow=el('div',{className:'eyebrow'});
const dirInput=el('input',{spellcheck:false,placeholder:'C:\\path\\to\\repo'}),bBrowse=el('button',{type:'button',className:'outline'});
const branchInput=el('input',{spellcheck:false,value:'main'}),lDir=el('label'),lBranch=el('label');
const dryRadio=el('input',{type:'radio',name:'watcher-mode',value:'dry',checked:true}),autoRadio=el('input',{type:'radio',name:'watcher-mode',value:'auto'});
const lDry=el('label'),lAuto=el('label');
const leaseLbl=el('label'),leaseBox=el('span',{className:'chip'});
const bStart=el('button',{type:'button',className:'primary'}),bStop=el('button',{type:'button',className:'outline'}),bStopAll=el('button',{type:'button',className:'outline'});
const manageHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'AUTO-SYNC'),el('h2'))),jobList=el('div',{className:'ssh-list'});
host.append(
 el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},eyebrow,h)),lDir,el('div',{className:'action-row'},dirInput,bBrowse),lBranch,branchInput,
  el('label',{},dryRadio,' ',lDry),el('label',{},autoRadio,' ',lAuto),leaseLbl,leaseBox,el('div',{className:'action-row'},bStart),out),
 el('section',{className:'panel'},manageHead,jobList,el('div',{className:'action-row'},bStop,bStopAll))
);
const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
function labels(){const l=L();h.textContent=l.title;eyebrow.textContent='WATCHERS';lDir.textContent=l.folder;lBranch.textContent=l.branch;lDry.textContent=l.dry;lAuto.textContent=l.auto;leaseLbl.textContent=l.lease;leaseBox.textContent=l.leaseHint;bStart.textContent=l.start;bStop.textContent=l.stop;bStopAll.textContent=l.stopAll;manageHead.querySelector('h2').textContent=l.manage;renderJobs();}
async function renderJobs(){const jobs=await api.autoSyncStatus();jobList.replaceChildren();if(!jobs.length){jobList.textContent=L().none;return}for(const j of jobs){jobList.append(el('div',{className:'gv-row'},el('strong',{textContent:nameOf(j.dir)}),el('code',{textContent:j.branch}),el('span',{className:'chip'+(j.apply?' warn':' blue'),textContent:j.apply?L().auto:L().dry}),el('span',{className:'chip',textContent:j.state||L().running})))}
}
async function leaseInfo(){const d=dirInput.value.trim();if(!d)return leaseBox.textContent=L().leaseHint;try{const r=await api.autoSyncLease({dir:d,branch:branchInput.value.trim()||'main'});leaseBox.textContent=(r.ok?r.message:(r.message||L().invalid));leaseBox.className='chip'+(r.ok?' blue':' warn');}catch(e){leaseBox.textContent=e.message}}
dirInput.oninput=debounce(leaseInfo,500);branchInput.oninput=debounce(leaseInfo,500);
function debounce(f,ms){let t;return()=>{clearTimeout(t);t=setTimeout(f,ms)}}
bBrowse.onclick=async()=>{const d=await api.pickFolder();if(d){dirInput.value=d;leaseInfo()}};
bStart.onclick=async()=>{const dir=dirInput.value.trim()||sel();if(!dir)return say(L().pick,'error');const branch=branchInput.value.trim()||'main';const apply=autoRadio.checked;if(apply&&!(await gsConfirm(L().confirmAuto.replace('{0}',nameOf(dir)).replace('{1}',branch))))return;bStart.disabled=true;try{await api.autoSyncStart({dir,branch,apply});say('','success');await renderJobs()}catch(e){say(e.message,'error')}finally{bStart.disabled=false}};
bStop.onclick=async()=>{const d=sel();if(!d)return say(L().pick,'error');try{await api.autoSyncStop(d);await renderJobs()}catch(e){say(e.message,'error')}};
bStopAll.onclick=async()=>{for(const j of await api.autoSyncStatus()){try{await api.autoSyncStop(j.dir)}catch(e){say(e.message,'error')}}await renderJobs()};
api.on('auto-sync-state',()=>{if(window.GitSUPanels?.sectionVisible('watchers'))renderJobs()});api.on('auto-sync-log',x=>say(`${nameOf(x.dir)} [${x.kind}]: ${x.message}`,x.kind==='error'?'error':'review'));
setInterval(()=>{if(window.GitSUPanels?.sectionVisible('watchers'))renderJobs()},15000);
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('watchers'))labels()},0));
function refresh(){labels()}
window.GitSUPanels.hook('watchers',()=>window.GitSUPanels.sectionVisible('watchers'),refresh);
})();
