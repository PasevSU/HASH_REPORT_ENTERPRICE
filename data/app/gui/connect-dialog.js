(()=>{
'use strict';
const $=id=>document.getElementById(id),api=window.repoAPI;
const T={
 en:{title:'Connect folder to repository',folder:'Folder',browse:'Browse…',repo:'Repository (optional)',repoHint:'owner/name or URL. Empty = new repository from the folder.',action:'Action',check:'Check',run:'Run',close:'Close',
  vis:'Visibility',private:'Private',public:'Public',name:'New repository name',
  a:{register:'Add to GitSU (folder is already a repository)',clone:'Clone into an empty folder',link:'Link folder with an existing repository',create:'Create a new GitHub repository from the folder and upload',local:'Local only: git init'},
  none:'Select a folder.',nothing:'No actions possible.',steps:'Will run:',done:'Done',wait:'Running…',warn:'Warning'},
 bg:{title:'Свързване на папка с репозитори',folder:'Папка',browse:'Избери…',repo:'Репозитори (по избор)',repoHint:'owner/name или URL. Празно = ново репозитори от папката.',action:'Действие',check:'Провери',run:'Изпълни',close:'Затвори',
  vis:'Видимост',private:'Частно',public:'Публично',name:'Име на новото репо',
  a:{register:'Добави в GitSU (папката вече е репозитори)',clone:'Изтегли (clone) в празна папка',link:'Свържи папката със съществуващо репо',create:'Създай ново GitHub репо от папката и качи',local:'Само локално: git init'},
  none:'Изберете папка.',nothing:'Няма възможни действия.',steps:'Ще се изпълни:',done:'Готово',wait:'Изпълнява се…',warn:'Внимание'},
 de:{title:'Ordner mit Repository verbinden',folder:'Ordner',browse:'Wählen…',repo:'Repository (optional)',repoHint:'owner/name oder URL. Leer = neues Repository aus dem Ordner.',action:'Aktion',check:'Prüfen',run:'Ausführen',close:'Schließen',
  vis:'Sichtbarkeit',private:'Privat',public:'Öffentlich',name:'Name des neuen Repos',
  a:{register:'Zu GitSU hinzufügen (Ordner ist bereits Repository)',clone:'In leeren Ordner klonen',link:'Ordner mit bestehendem Repo verbinden',create:'Neues GitHub-Repo aus Ordner erstellen und hochladen',local:'Nur lokal: git init'},
  none:'Ordner wählen.',nothing:'Keine Aktion möglich.',steps:'Wird ausgeführt:',done:'Fertig',wait:'Läuft…',warn:'Achtung'}
};
const L=()=>T[($('language-select')?.value)||'bg']||T.bg;
let dlg,state={info:null,planned:false,busy:false};

function build(){
 dlg=document.createElement('dialog');dlg.id='connect-dialog';dlg.className='connect-dialog';
 dlg.innerHTML=`<div class="legal-header"><h2 data-k="title"></h2><button type="button" class="outline" data-k="close" id="cd-close"></button></div>
 <label data-k="folder"></label><div class="action-row"><input id="cd-dir" placeholder="C:\\path\\to\\repo"><button type="button" class="outline" id="cd-browse" data-k="browse"></button></div>
 <label data-k="repo"></label><input id="cd-repo" placeholder="owner/name or https://github.com/owner/name"><p class="hint" data-k="repoHint"></p>
 <div id="cd-info" class="hint"></div>
 <label data-k="action"></label><div id="cd-actions" class="cd-actions"></div>
 <div id="cd-create" class="cd-create" hidden><div class="action-row"><input id="cd-name" aria-label="name"><select id="cd-vis"><option value="private"></option><option value="public"></option></select></div></div>
 <div class="action-row"><button type="button" class="primary" id="cd-run" disabled data-k="run"></button></div>
 <div id="cd-result" class="workflow-result" aria-live="polite"></div>`;
 document.body.appendChild(dlg);
 $('cd-close').onclick=()=>dlg.close();
 $('cd-browse').onclick=async()=>{const d=await api.pickFolder();if(d){$('cd-dir').value=d;refresh()}};
 $('cd-dir').onchange=refresh;$('cd-repo').oninput=debounce(()=>{state.reset=true;state.done=false;refresh()},400);
 $('cd-run').onclick=runIt;$('cd-name').oninput=()=>autoPlan();$('cd-vis').onchange=()=>autoPlan();
 dlg.addEventListener('change',e=>{if(e.target.name==='cd-action'){state.planned=false;state.done=false;$('cd-run').disabled=true;$('cd-create').hidden=e.target.value!=='create';autoPlan()}});
}
function debounce(f,ms){let t;return()=>{clearTimeout(t);t=setTimeout(f,ms)}}
const autoPlan=debounce(()=>{if(dlg?.open&&selected()&&!state.done)check()},350);
function labels(){const l=L();for(const el of dlg.querySelectorAll('[data-k]'))el.textContent=l[el.dataset.k];
 const o=$('cd-vis').options;o[0].textContent=l.private;o[1].textContent=l.public;$('cd-name').placeholder=l.name}
function box(text,type){const r=$('cd-result');r.textContent=text;r.dataset.type=type||''}
function selected(){return dlg.querySelector('input[name="cd-action"]:checked')?.value}

async function refresh(){
 const dir=$('cd-dir').value.trim();state.planned=false;$('cd-run').disabled=true;
 if(!dir){$('cd-actions').replaceChildren();$('cd-info').textContent=L().none;return}
 try{
  const info=await api.connectInspect({dir,repo:$('cd-repo').value});state.info=info;
  if(!$('cd-name').value)$('cd-name').value=dir.split(/[\\/]/).filter(Boolean).pop()||'';
  const bits=[info.exists?(info.isRepo?'git':(info.empty?'empty':'files')):'new'];
  if(info.branch)bits.push(info.branch);if(info.origin)bits.push(info.origin);if(info.dirty)bits.push(info.dirty+' changes');
  $('cd-info').textContent=info.warning||bits.join(' · ');
  const prev=state.reset?null:selected(),box_=$('cd-actions');box_.replaceChildren();
  if(!info.actions.length){box_.textContent=L().nothing;return}
  for(const a of info.actions){
   const lab=document.createElement('label'),r=document.createElement('input');
   r.type='radio';r.name='cd-action';r.value=a;r.checked=a===(info.actions.includes(prev)?prev:info.defaultAction);
   lab.append(r,' '+L().a[a]);box_.appendChild(lab);
  }
  $('cd-create').hidden=selected()!=='create';
  autoPlan();
 }catch(e){$('cd-info').textContent=e.message}
}
function payload(){return {dir:$('cd-dir').value.trim(),repo:$('cd-repo').value.trim(),mode:selected(),name:$('cd-name').value.trim(),visibility:$('cd-vis').value}}
let planSeq=0;
async function check(){
 const my=++planSeq;
 try{
  box(L().wait);const p=await api.connectPlan(payload());if(my!==planSeq)return;
  box(L().steps+'\n'+p.steps.map((s,i)=>`${i+1}. ${s}`).join('\n')+(p.warnings.length?`\n\n${L().warn}: `+p.warnings.join('; '):''),'review');
  state.planned=true;$('cd-run').disabled=false;
 }catch(e){if(my!==planSeq)return;box(e.message,'error');$('cd-run').disabled=true}
}
async function runIt(){
 if(state.busy||!state.planned)return;state.busy=true;planSeq++;$('cd-run').disabled=true;box(L().wait);
 try{const r=await api.connectApply(payload());box(`${L().done}: ${r.dir}${r.url?'\n'+r.url:''}${r.guard?'\n\n'+[...(r.guard.post||[])].join('\n'):''}`,'success');state.planned=false;state.done=true}
 catch(e){box(e.message,'error')}
 finally{state.busy=false;state.reset=false;refresh()}
}
function open(mode,preset){
 if(!dlg)build();labels();
 if(preset?.dir)$('cd-dir').value=preset.dir;
 if(preset?.repo)$('cd-repo').value=preset.repo;
 box('');state.done=false;state.reset=false;dlg.showModal();refresh().then(()=>{if(mode){const r=dlg.querySelector(`input[name="cd-action"][value="${mode}"]`);if(r){r.checked=true;$('cd-create').hidden=mode!=='create';state.planned=false;check()}}});
}
window.GitSUConnect={open};

// Replace the separate Add / Clone / New / Publish flows with the single dialog.
const MODE={cloneRepo:'clone',newLocal:'local',publishNew:'create'};
document.addEventListener('click',e=>{
 const b=e.target.closest('#add,[data-action="add"],[data-operation="cloneRepo"],[data-operation="newLocal"],[data-operation="publishNew"]');
 if(!b)return;e.preventDefault();e.stopImmediatePropagation();
 open(MODE[b.dataset.operation]||null);
},true);
})();
