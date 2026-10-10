(()=>{
'use strict';
// Sync panel: file copy plan -> review -> apply.
const $=id=>document.getElementById(id);const api=window.repoAPI;
const host=document.getElementById('sync-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
host.innerHTML='<div class="section-head"><div><div class="eyebrow" id="s-eyebrow"></div><h2 id="s-title"></h2></div><span class="chip" id="s-chip"></span></div><label for="target" id="s-label"></label><input id="target" placeholder="Absolute path to destination"><div class="action-row"><button id="plan" class="outline"></button><button id="applycopy" class="primary" disabled></button></div><pre id="copyresult" class="log-preview"></pre>';
let copyPlan=null;
function labels(){
 $('s-eyebrow').textContent=t('CONTROLLED FILE TRANSFER');
 $('s-title').textContent=t('File synchronization');
 $('s-chip').textContent=t('PLAN FIRST');
 $('s-label').textContent=t('Destination directory');
 $('target').placeholder=t('Absolute path to destination');
 $('plan').textContent=t('Generate copy plan');
 $('applycopy').textContent=t('Apply approved plan');
}
$('plan').onclick=async()=>{if(!selected)return log(t('Select a repository first.'));try{copyPlan=await api.copyPlan({from:selected,to:$('target').value});$('copyresult').textContent=JSON.stringify(copyPlan.changes,null,2);$('applycopy').disabled=!copyPlan.changes.some(x=>x.type==='copy')}catch(e){log(e.message)}};
$('applycopy').onclick=async()=>{if(!copyPlan||!(await gsConfirm(`Copy files into ${copyPlan.dst}?`)))return;try{log(await api.copyApply(copyPlan));copyPlan=null;$('applycopy').disabled=true}catch(e){log(e.message)}};
$('language-select')?.addEventListener('change',()=>setTimeout(labels,0));
labels();
})();
