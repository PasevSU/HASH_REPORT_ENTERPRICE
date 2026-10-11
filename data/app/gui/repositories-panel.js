(()=>{
'use strict';
// Repositories table: search/filter/list of registered folders with per-repo actions.
const $=id=>document.getElementById(id);const api=window.repoAPI;
const host=document.getElementById('repositories-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
host.innerHTML='<div class="section-head"><div><div class="eyebrow" id="rep-eyebrow"></div><h2><span id="rep-label"></span> <span class="count" id="table-count">0</span></h2></div><div class="section-tools"><select id="repo-filter" aria-label="Filter"><option value="all"></option><option value="dirty"></option><option value="clean"></option><option value="uninitialized"></option></select><button id="refresh-all" class="outline"></button></div></div><div class="table-wrap"><table><thead><tr><th id="rep-h1"></th><th id="rep-h2"></th><th id="rep-h3"></th><th id="rep-h4"></th><th id="rep-h5"></th></tr></thead><tbody id="repo-rows"></tbody></table></div>';
const textCell=(tr,main,sub)=>{const td=el('td'),strong=el('strong',{textContent:main||'—'});td.append(strong);if(sub)td.append(el('small',{textContent:sub}));tr.append(td);return td};
function labels(){
 $('rep-eyebrow').textContent=t('REPOSITORY INTELLIGENCE');
 $('rep-label').textContent=t('Repositories');
 $('repo-filter').options[0].textContent=t('All repositories');
 $('repo-filter').options[1].textContent=t('Modified');
 $('repo-filter').options[2].textContent=t('Clean');
 $('repo-filter').options[3].textContent=t('Not initialized');
 $('refresh-all').textContent=t('↻ Refresh');
 $('repo-filter').setAttribute('aria-label',t('Filter'));
 ['REPOSITORY','BRANCH','STATUS','REMOTE','ACTIONS'].forEach((k,i)=>$('rep-h'+(i+1)).textContent=t(k));
}
function render(){
 const term=$('search')?.value.trim().toLowerCase()||'',filter=$('repo-filter').value;
 const rows=folders.filter(dir=>{const r=repoData.get(dir);if(term&&!`${dir} ${r?.branch||''} ${r?.remote||''}`.toLowerCase().includes(term))return false;if(filter==='dirty')return !!r?.dirty;if(filter==='clean')return !!r?.isRepo&&!r.dirty;if(filter==='uninitialized')return !!r&&!r.isRepo;return true;});
 $('table-count').textContent=rows.length;
 const body=$('repo-rows');body.replaceChildren();
 if(!rows.length){const tr=el('tr'),td=el('td',{colSpan:5,className:'empty',textContent:folders.length?t('No repositories match the current filter.'):t('No repositories registered. Add a local folder to begin.')});tr.append(td);body.append(tr);return;}
 for(const dir of rows){
  const r=repoData.get(dir),tr=el('tr');
  if(selected===dir)tr.className='selected';
  tr.tabIndex=0;tr.onclick=()=>selectRepo(dir);tr.onkeydown=e=>{if(e.key==='Enter')selectRepo(dir)};
  textCell(tr,nameOf(dir),dir);
  textCell(tr,r?.branch||'—');
  const status=el('td');status.append(chip(!r?t('CHECKING'):!r.isRepo?t('NO GIT'):r.dirty?t('MODIFIED'):t('CLEAN'),!r?'':!r.isRepo?'bad':r.dirty?'warn':'good'));tr.append(status);
  textCell(tr,r?.remote?nameOf(r.remote):t('Not linked'));
  const actions=el('td');
  const b=el('button',{className:'outline',textContent:'↻',title:t('Refresh repository')});b.onclick=async e=>{e.stopPropagation();await refreshOne(dir)};actions.append(b);
  const rmf=el('button',{className:'outline',textContent:'🗑',title:t('Remove folder')});rmf.onclick=async e=>{e.stopPropagation();if(!(await gsConfirm(`Remove ${nameOf(dir)} from GitSU? Files stay on disk.`)))return;try{folders=await api.remove(dir);repoData.delete(dir);if(selected===dir){selected=null;window.GitSUUI.emit('overview',null);}window.GitSUUI.emit('repos');window.GitSUUI.emit('repoCount',folders.length);updateBreadcrumb();log(`Removed ${nameOf(dir)}`)}catch(err){log(err.message)}};actions.append(' ',rmf);
  if(r&&!r.remote&&window.GitSUConnect){const up=el('button',{className:'outline',textContent:'⇪',title:t('Connect to GitHub / upload')});up.onclick=e=>{e.stopPropagation();window.GitSUConnect.open(null,{dir})};actions.append(' ',up)}
  if(r?.remote){const gear=el('button',{className:'outline',textContent:'⚙',title:t('Manage remote')});gear.onclick=e=>{e.stopPropagation();selectRepo(dir);view('repositories')};actions.append(' ',gear);const rm=el('button',{className:'outline',textContent:'✕',title:t('Remove remote')});rm.onclick=async e=>{e.stopPropagation();if(!(await gsConfirm(`Remove remote from ${nameOf(dir)}?`)))return;try{await api.remoteRemove(dir);await refreshOne(dir)}catch(err){log(err.message)}};actions.append(' ',rm)}
  tr.append(actions);body.append(tr);
 }
}
$('repo-filter').onchange=()=>window.GitSUUI.emit('repos');
if($('search'))$('search').oninput=()=>window.GitSUUI.emit('repos');
$('refresh-all').onclick=()=>Promise.allSettled(folders.map(refreshOne));
window.GitSUUI.on('repos',()=>{labels();render()});
window.GitSUPanels.hook('repositories',()=>window.GitSUPanels.sectionVisible('repo-table'),()=>{labels();render()});
labels();render();
})();
