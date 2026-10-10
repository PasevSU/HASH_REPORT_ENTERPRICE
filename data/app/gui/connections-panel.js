(()=>{
'use strict';
// Connections panel: every registered folder and its remote link, with per-row manage + sync.
const $=id=>document.getElementById(id),api=window.repoAPI;
const host=document.getElementById('connections-panel');if(!host)return;
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const T={
 bg:{title:'Връзки между репозиториите',refresh:'Обнови всички',actions:'Действия',repo:'Регистрирана папка',branch:'Клон',remote:'Отдалечен адрес',status:'Състояние',notLinked:'Не е свързан',connect:'Свържи',change:'Смени remote',remove:'Премахни remote',push:'Качи',pull:'Изтегли',inSync:'В синхрон',ahead:'напред',behind:'назад',checking:'Проверка…',needMsg:'Съобщение за качване',send:'Качи',empty:'Няма регистрирани папки.'},
 de:{title:'Verbindungen zwischen Repositories',refresh:'Alle aktualisieren',actions:'Aktionen',repo:'Registrierter Ordner',branch:'Branch',remote:'Remote-URL',status:'Status',notLinked:'Nicht verbunden',connect:'Verbinden',change:'Remote ändern',remove:'Remote entfernen',push:'Push',pull:'Pull',inSync:'Synchron',ahead:'voraus',behind:'zurück',checking:'Prüfe…',needMsg:'Commit-Nachricht',send:'Hochladen',empty:'Keine Ordner registriert.'}
};
const L=()=>T[lang()];
const h=el('h2'),eyebrow=el('div',{className:'eyebrow'}),bRefresh=el('button',{type:'button',className:'outline'});
const ths=[0,1,2,3,4].map(()=>el('th'));
const tbody=el('tbody');
const wrap=el('div',{className:'table-wrap'},el('table',{},el('thead',{},el('tr',{},...ths)),tbody));
host.append(el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},eyebrow,h),bRefresh),wrap));
function render(){
 const l=L();h.textContent=l.title;eyebrow.textContent='CONNECTIONS';bRefresh.textContent=l.refresh;
 ths[0].textContent=l.actions;ths[1].textContent=l.repo;ths[2].textContent=l.branch;ths[3].textContent=l.remote;ths[4].textContent=l.status;
 tbody.replaceChildren();
 if(!folders.length){tbody.append(el('tr',{},el('td',{colSpan:5,className:'empty',textContent:l.empty})));return}
 for(const dir of folders)renderRow(dir);
}
function renderRow(dir){
 const r=repoData.get(dir);
 const tr=el('tr');tr.dataset.dir=dir;tr.onclick=()=>selectRepo(dir);
 const acts=el('td');
 acts.append(el('button',{type:'button',className:'outline',textContent:'↻',title:L().refresh,onclick:async e=>{e.stopPropagation();await refreshOne(dir);render()}}));
 if(r&&!r.remote&&window.GitSUConnect){acts.append(' ',el('button',{type:'button',className:'outline',textContent:'⇪',title:L().connect,onclick:e=>{e.stopPropagation();window.GitSUConnect.open(null,{dir})}}))}
 if(r?.remote){
  const inp=el('input',{type:'text',value:r.remote,hidden:true});
  const bSave=el('button',{type:'button',className:'primary',textContent:L().send,hidden:true});
  const editBox=el('span',{className:'conn-push'},inp,bSave);
  const bChg=el('button',{type:'button',className:'outline',textContent:'⚙',title:L().change,onclick:e=>{e.stopPropagation();const open=inp.hidden;inp.hidden=!open;bSave.hidden=open;if(!inp.hidden)inp.focus()}});
  bSave.onclick=async e=>{e.stopPropagation();const url=inp.value.trim();if(!url)return;if(!(await gsConfirm(`Change remote for ${nameOf(dir)} to ${url}?`)))return;try{await api.remoteSetUrl({dir,url});await refreshOne(dir);render()}catch(err){log(err.message)}};
  const bRm=el('button',{type:'button',className:'outline',textContent:'✕',title:L().remove,onclick:async e=>{e.stopPropagation();if(!(await gsConfirm(`Remove remote from ${nameOf(dir)}?`)))return;try{await api.remoteRemove(dir);await refreshOne(dir);render()}catch(err){log(err.message)}}});
  acts.append(' ',bChg,editBox,' ',bRm);
 }
 tr.append(acts);
 tr.append(el('td',{},el('strong',{textContent:nameOf(dir)}),el('small',{textContent:dir})));
 tr.append(el('td',{},el('strong',{textContent:r?.branch||'—'})));
 tr.append(el('td',{},el('strong',{textContent:r?.remote||L().notLinked})));
 const tdStatus=el('td');tdStatus.className='conn-status';
 tr.append(tdStatus);
 tbody.append(tr);
 renderStatus(dir,tdStatus);
}
function pullButton(dir){
 const b=el('button',{type:'button',className:'outline',textContent:'↓ '+L().pull});
 b.onclick=async e=>{e.stopPropagation();if(!(await gsConfirm(`Pull ${nameOf(dir)}?`)))return;try{await api.operation({dir,action:'update',apply:true});await refreshOne(dir);render()}catch(err){log(err.message)}};
 return b;
}
function pushButton(dir){
 const msg=el('input',{type:'text',placeholder:L().needMsg,hidden:true});
 const send=el('button',{type:'button',className:'primary',textContent:L().send,hidden:true,disabled:true});
 const b=el('button',{type:'button',className:'primary',textContent:'↗ '+L().push});
 b.onclick=e=>{e.stopPropagation();const open=msg.hidden;msg.hidden=!open;send.hidden=open;if(!msg.hidden)msg.focus()};
 msg.oninput=()=>{send.disabled=!msg.value.trim().length};
 send.onclick=async e=>{e.stopPropagation();const m=msg.value.trim();if(!m)return;if(!(await gsConfirm(`Upload ${nameOf(dir)}?`)))return;try{await api.operation({dir,action:'push',apply:true,message:m});await refreshOne(dir);render()}catch(err){log(err.message)}};
 return el('span',{className:'conn-push'},b,msg,send);
}
async function renderStatus(dir,tdStatus){
 const r=repoData.get(dir);
 if(!r?.remote){tdStatus.textContent=(r&&r.isRepo)?L().notLinked:'—';return}
 tdStatus.textContent=L().checking;
 try{
  const s=await api.remoteStatus(dir);
  tdStatus.replaceChildren();
  if(!s.upstreamKnown){tdStatus.textContent=L().notLinked;return}
  const parts=[];if(s.ahead)parts.push(`${s.ahead} ${L().ahead}`);if(s.behind)parts.push(`${s.behind} ${L().behind}`);
  tdStatus.append(el('span',{className:'chip'+(s.ahead?' warn':' good'),textContent:parts.length?parts.join(' · '):L().inSync}));
  if(s.ahead)tdStatus.append(' ',pushButton(dir));else if(s.behind)tdStatus.append(' ',pullButton(dir));
 }catch(e){tdStatus.textContent=e.message}
}
let timer=null;function scheduleRender(){clearTimeout(timer);timer=setTimeout(render,120)}
bRefresh.onclick=async()=>{for(const d of folders){try{await refreshOne(d)}catch(e){}}render()};
api.on('state',scheduleRender);api.on('repo',scheduleRender);
$('language-select')?.addEventListener('change',()=>setTimeout(render,0));
render();
})();
