(()=>{
'use strict';
// Repository panel: active-repo overview + single-action upload/pull + add/clone/new/publish.
const $=id=>document.getElementById(id);const api=window.repoAPI;
const host=document.getElementById('repository-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
host.innerHTML='<div class="section-head"><div><div class="eyebrow" id="r-eyebrow1"></div><h2 id="breadcrumb"></h2></div><span id="repo-badge" class="chip"></span></div><div id="overview" class="detail-grid"></div><div class="section-head"><div><div class="eyebrow" id="r-eyebrow2"></div><h2 id="r-ops-title"></h2></div><span class="chip blue" id="r-ops-chip"></span></div><label for="message" id="r-msg-label"></label><input id="message" placeholder="Describe your changes"><div class="action-row"><button id="push" class="primary" disabled></button><button id="pull" class="outline"></button></div><p class="hint" id="upload-hint"></p><div class="section-head"><div><div class="eyebrow" id="r-eyebrow3"></div><h2 id="r-add-title"></h2></div></div><div class="action-row"><button data-action="add" class="primary"></button><button data-operation="cloneRepo" class="outline"></button><button data-operation="newLocal" class="outline"></button><button data-operation="publishNew" class="outline"></button></div>';
function detail(k,v,wide=false){const e=el('div',{className:'detail'+(wide?' wide':'')});e.append(el('span',{textContent:k}),el('strong',{textContent:v===undefined||v===null||v===''?'—':String(v)}));return e;}
function syncControls(info){const box=el('div',{className:'action-row remote-controls'});const inp=el('input',{type:'text',placeholder:t('Commit message')});const btn=el('button',{type:'button',className:'primary',textContent:t('Sync')});const gate=()=>{btn.disabled=!!info.dirty&&!inp.value.trim()};inp.oninput=gate;btn.onclick=async()=>{btn.disabled=true;try{const r=await api.repoSync({dir:info.dir,message:inp.value.trim(),apply:true});log(`Sync ${nameOf(info.dir)}: pulled=${r.pulled} pushed=${r.pushed} ahead=${r.ahead??'—'} behind=${r.behind??'—'}`);await refreshOne(info.dir)}catch(e){log(e.message)}finally{gate()}};gate();box.append(inp,btn);return box;}
function remoteControls(info){const box=el('div',{className:'action-row remote-controls'});const inp=el('input',{type:'text',value:info.remote||'',placeholder:t('Enter new remote URL')});const save=el('button',{type:'button',className:'primary',textContent:t('Save')});const chg=el('button',{type:'button',className:'outline',textContent:t('Change remote')});const rm=el('button',{type:'button',className:'outline',textContent:t('Remove remote')});inp.hidden=true;save.hidden=true;chg.onclick=()=>{const open=inp.hidden;inp.hidden=!open;save.hidden=open;if(!inp.hidden)inp.focus()};save.onclick=async()=>{const url=inp.value.trim();if(!url)return log(t('Enter new remote URL'));if(!(await gsConfirm(`Change remote for ${nameOf(info.dir)} to ${url}?`)))return;try{const r=await api.remoteSetUrl({dir:info.dir,url});log(`Remote ${r.name}: ${r.from||'—'} → ${r.to}`);await refreshOne(info.dir)}catch(e){log(e.message)}};rm.onclick=async()=>{if(!(await gsConfirm(`Remove remote from ${nameOf(info.dir)}?`)))return;try{const r=await api.remoteRemove(info.dir);log(`Removed remote ${r.name} (${r.url})`);await refreshOne(info.dir)}catch(e){log(e.message)}};box.append(chg,inp,save,rm);return box;}
function labels(){
 $('r-eyebrow1').textContent=t('SELECTED REPOSITORY');
 $('r-eyebrow2').textContent=t('AUDITED EXECUTION');
 $('r-ops-title').textContent=t('Repository operations');
 $('r-ops-chip').textContent=t('EXPLICIT APPROVAL');
 $('r-msg-label').textContent=t('Commit message');
 $('message').placeholder=t('Describe your changes');
 $('push').textContent=t('↑ Upload');
 $('pull').textContent=t('↓ Pull / update');
 $('r-eyebrow3').textContent=t('ADD REPOSITORY');
 $('r-add-title').textContent=t('Add or create');
 const add=host.querySelectorAll('[data-action="add"],[data-operation="cloneRepo"],[data-operation="newLocal"],[data-operation="publishNew"]');
 if(add[0])add[0].textContent=t('＋ Add folder');
 if(add[1])add[1].textContent=t('⇩ Clone');
 if(add[2])add[2].textContent=t('✚ New local');
 if(add[3])add[3].textContent=t('⇧ Publish new');
 uploadGate();
}
function renderOverview(info){
 if(!info||!info.dir){
  $('breadcrumb').textContent=t('Repository details');
  const badge=$('repo-badge');badge.textContent=t('NOT SELECTED');badge.className='chip';
  $('overview').replaceChildren(el('p',{className:'empty',textContent:t('Select a repository to inspect its state.')}));
  return;
 }
 $('breadcrumb').textContent=nameOf(info.dir);
 const badge=$('repo-badge');badge.textContent=info.isRepo?(info.dirty?t('MODIFIED'):t('CLEAN')):t('NO GIT');badge.className='chip '+(info.isRepo?(info.dirty?'warn':'good'):'bad');
 const kids=[detail(t('Directory'),info.dir,true),detail(t('Branch'),info.branch),detail(t('Working tree'),info.dirty?t('Modified'):t('Clean')),detail(t('Origin'),info.remote,true),detail(t('Local branches'),(info.branches||[]).join(', ')),detail(t('Remote references'),(info.remotes||[]).length),detail('.gitignore',info.files?.gitignore?t('Present'):t('Missing')),detail('.gitattributes',info.files?.gitattributes?t('Present'):t('Missing'))];
 if(info.isRepo&&info.remote){kids.push(remoteControls(info));kids.push(syncControls(info));}
 $('overview').replaceChildren(...kids);
 if(info.isRepo&&info.remote){api.remoteStatus(info.dir).then(x=>log(`Remote ${nameOf(info.dir)}: ahead=${x.ahead??t('unknown')} behind=${x.behind??t('unknown')} review=${x.requiresReview}`)).catch(e=>log('Remote check: '+e.message));}
}
function uploadGate(){const on=$('message').value.trim().length>0;$('push').disabled=!on;$('upload-hint').textContent=on?'':t('Upload requires a commit message.');}
$('message').oninput=uploadGate;
$('push').onclick=async()=>{if(!selected)return log(t('Select a repository first.'));const message=$('message').value.trim();if(!message)return uploadGate();if(!(await gsConfirm(`Upload ${nameOf(selected)}? This stages, commits and pushes in one operation.`)))return;try{log(await api.operation({dir:selected,action:'push',apply:true,message}));$('message').value='';uploadGate();await refreshOne(selected)}catch(e){log(e.message)}};
$('pull').onclick=async()=>{if(!selected)return log(t('Select a repository first.'));if(!(await gsConfirm(`Pull / update ${nameOf(selected)}? This fetches and merges remote changes.`)))return;try{log(await api.operation({dir:selected,action:'update',apply:true}));await refreshOne(selected)}catch(e){log(e.message)}};
window.GitSUUI.on('overview',info=>{labels();renderOverview(info)});
window.GitSUPanels.hook('repository',()=>window.GitSUPanels.sectionVisible('repository'),()=>{labels();renderOverview(selected&&repoData.has(selected)?repoData.get(selected):null)});
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('repository')){labels();renderOverview(selected&&repoData.has(selected)?repoData.get(selected):null)}},0));
labels();renderOverview(selected&&repoData.has(selected)?repoData.get(selected):null);
})();
