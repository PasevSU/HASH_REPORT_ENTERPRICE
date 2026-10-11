(()=>{
'use strict';
// Repository details panel: view/edit GitHub repository metadata (description, homepage,
// topics, visibility, default branch) and generate the mandatory project documents
// (README.md / CONTRIBUTING.md / SECURITY.md). Thin UI over lib/repo-details + lib/docs
// via the preload bridge. No git/GitHub logic lives here.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.repoDetails||!api?.docsMeta)return;
const host=document.getElementById('repo-details-panel');if(!host)return;
const lang=()=>{const v=$('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const sel=()=>typeof selected!=='undefined'?selected:null;
const nameOf=d=>String(d).split(/[\\/]/).filter(Boolean).pop()||d;
const T={
 en:{
  title:'Repository details',details:'Repository details',docs:'Project documents',
  fullName:'Full name',url:'URL',ssh:'SSH URL',visibility:'Visibility',private:'Private',public:'Public',internal:'Internal',
  description:'Description',homepage:'Homepage',topics:'Topics (comma separated)',defaultBranch:'Default branch',
  save:'Save details',saved:'Details saved.',notLinked:'Repository is not linked to GitHub.',pick:'Select a repository.',
  name:'Project name',repoSlug:'owner/repo',license:'License',stack:'Stack (comma separated)',
  preview:'Preview',write:'Write files',wrote:'Written files:',refresh:'Refresh',wait:'Running…',error:'Error',
  docsHint:'Generates tailored README.md, CONTRIBUTING.md and SECURITY.md in the selected repository.',
  dir:'Repository folder',browse:'Browse folder'
 },
 bg:{
  title:'Репозитори детайли',details:'Детайли на репозиторито',docs:'Проектни документи',
  fullName:'Пълно име',url:'URL',ssh:'SSH URL',visibility:'Видимост',private:'Частно',public:'Публично',internal:'Вътрешно',
  description:'Описание',homepage:'Начална страница',topics:'Теми (със запетая)',defaultBranch:'Клон по подразбиране',
  save:'Запиши детайлите',saved:'Детайлите са записани.',notLinked:'Репото не е свързано с GitHub.',pick:'Изберете репозитория.',
  name:'Име на проекта',repoSlug:'owner/repo',license:'Лиценз',stack:'Стек (със запетая)',
  preview:'Преглед',write:'Запиши файловете',wrote:'Записани файлове:',refresh:'Обнови',wait:'Изпълнява се…',error:'Грешка',
  docsHint:'Генерира адаптираните README.md, CONTRIBUTING.md и SECURITY.md в избраното репозитори.',
  dir:'Папка на репозиторито',browse:'Избери папка'
 },
 de:{
  title:'Repository-Details',details:'Repository-Details',docs:'Projektdokumente',
  fullName:'Vollständiger Name',url:'URL',ssh:'SSH-URL',visibility:'Sichtbarkeit',private:'Privat',public:'Öffentlich',internal:'Intern',
  description:'Beschreibung',homepage:'Startseite',topics:'Themen (kommagetrennt)',defaultBranch:'Standard-Branch',
  save:'Details speichern',saved:'Details gespeichert.',notLinked:'Repository ist nicht mit GitHub verknüpft.',pick:'Repository wählen.',
  name:'Projektname',repoSlug:'owner/repo',license:'Lizenz',stack:'Stack (kommagetrennt)',
  preview:'Vorschau',write:'Dateien schreiben',wrote:'Geschriebene Dateien:',refresh:'Aktualisieren',wait:'Läuft…',error:'Fehler',
  docsHint:'Erzeugt angepasste README.md, CONTRIBUTING.md und SECURITY.md im ausgewählten Repository.',
  dir:'Repository-Ordner',browse:'Ordner wählen'
 }
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const docsOut=el('div',{className:'workflow-result','aria-live':'polite'});
const say=(t,type)=>{out.textContent=typeof t==='string'?t:JSON.stringify(t,null,2);out.dataset.type=type||''};
const sayDocs=(t,type)=>{docsOut.textContent=typeof t==='string'?t:JSON.stringify(t,null,2);docsOut.dataset.type=type||''};
const fail=e=>say(String(e.message||e).replace(/^Error invoking remote method '[^']*': (Error: )?/,''),'error');
const failDocs=e=>sayDocs(String(e.message||e).replace(/^Error invoking remote method '[^']*': (Error: )?/,''),'error');
const labeled=(id,labelText,input)=>{const lb=el('label',{id});lb.append(el('span',{textContent:labelText}),input);return lb};

// — Repository metadata form —
const fullNameBox=el('div',{className:'github-meta'}),urlBox=el('div',{className:'github-meta'}),sshBox=el('div',{className:'github-meta'});
const descInput=el('textarea',{rows:3,spellcheck:false}),homepageInput=el('input',{spellcheck:false}),topicsInput=el('input',{spellcheck:false}),branchInput=el('input',{spellcheck:false});
const visSelect=el('select',{},el('option',{value:'public'}),el('option',{value:'private'}),el('option',{value:'internal'}));
const bSave=el('button',{type:'button',className:'primary'}),bRefreshD=el('button',{type:'button',className:'outline'});
const dirInput=el('input',{spellcheck:false,placeholder:'C:\\path\\to\\repo'}),bBrowse=el('button',{type:'button',className:'outline'});

// — Documents generator —
const nameInput=el('input',{spellcheck:false}),repoInput=el('input',{spellcheck:false}),docDescInput=el('textarea',{rows:2,spellcheck:false});
const docHomepageInput=el('input',{spellcheck:false}),stackInput=el('input',{spellcheck:false});
const licenseSelect=el('select',{},['Apache-2.0','MIT','GPL-3.0','BSD-3-Clause','Unlicense'].map(x=>el('option',{value:x,textContent:x})));
const fileChecks={};
const checksBox=el('div',{className:'action-row'});
const bPreview=el('button',{type:'button',className:'outline'}),bWrite=el('button',{type:'button',className:'primary'});
const previewBox=el('pre',{className:'log-preview'});

const dirRow=el('div',{className:'action-row'},labeled('rd-dir-label',L().dir,dirInput),bBrowse);
host.append(
 el('section',{className:'panel'},
  el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'DETAILS'),el('h2',{id:'rd-details-title'})),el('div',{className:'action-row'},bRefreshD)),
  dirRow,
  fullNameBox,urlBox,sshBox,
  labeled('rd-desc',L().description,descInput),
  labeled('rd-home',L().homepage,homepageInput),
  labeled('rd-topics',L().topics,topicsInput),
  labeled('rd-branch',L().defaultBranch,branchInput),
  labeled('rd-vis',L().visibility,visSelect),
  el('div',{className:'action-row'},bSave),out),
 el('section',{className:'panel'},
  el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'DOCS'),el('h2',{id:'rd-docs-title'})),el('p',{className:'hint',id:'rd-docs-hint'})),
  labeled('rd-name',L().name,nameInput),
  labeled('rd-repo',L().repoSlug,repoInput),
  labeled('rd-ddesc',L().description,docDescInput),
  labeled('rd-dhome',L().homepage,docHomepageInput),
  labeled('rd-stack',L().stack,stackInput),
  labeled('rd-license',L().license,licenseSelect),
  checksBox,
  el('div',{className:'action-row'},bPreview,bWrite),
  docsOut,
  previewBox)
);

const metaRow=(box,labelText)=>box.replaceChildren(el('strong',{textContent:labelText+': '}),el('code',{textContent:box.dataset.v||'—'}));
function labels(){
 const l=L();
 $('rd-details-title').textContent=l.details;$('rd-docs-title').textContent=l.docs;$('rd-docs-hint').textContent=l.docsHint;
 const spanMap=[['rd-desc',l.description],['rd-home',l.homepage],['rd-topics',l.topics],['rd-branch',l.defaultBranch],['rd-vis',l.visibility],['rd-dir-label',l.dir],['rd-name',l.name],['rd-repo',l.repoSlug],['rd-ddesc',l.description],['rd-dhome',l.homepage],['rd-stack',l.stack],['rd-license',l.license]];
 for(const [k,v] of spanMap){const s=$(k)?.querySelector('span');if(s)s.textContent=v;}
 bSave.textContent=l.save;bRefreshD.textContent=l.refresh;bPreview.textContent=l.preview;bWrite.textContent=l.write;bBrowse.textContent=l.browse;
 if(!dirInput.value&&sel())dirInput.value=sel();
 dirInput.placeholder=sel()?nameOf(sel()):'C:\\path\\to\\repo';
 metaRow(fullNameBox,l.fullName);metaRow(urlBox,l.url);metaRow(sshBox,l.ssh);
 const vo=visSelect.options;vo[0].textContent=l.public;vo[1].textContent=l.private;vo[2].textContent=l.internal;
}
const d=()=>dirInput.value.trim()||sel();
function checksMeta(){
 const files=Object.keys(fileChecks).filter(f=>fileChecks[f].checked);
 const stack=stackInput.value.split(/[,]/).map(s=>s.trim()).filter(Boolean);
 return {name:nameInput.value.trim()||nameOf(d())||'project',repo:repoInput.value.trim(),description:docDescInput.value.trim(),homepage:docHomepageInput.value.trim()||'https://pasevsu.github.io/',license:licenseSelect.value,stack:stack.length?stack:['Node.js']};
}
async function ensureChecks(){
 const meta=await api.docsMeta();checksBox.replaceChildren();
 for(const x of meta.docs){
  const c=el('input',{type:'checkbox'});c.checked=true;c.id='doc-'+x.file;
  fileChecks[x.file]=c;
  checksBox.append(el('label',{},c,' ',el('span',{textContent:x.file})));
 }
}
function applyDetails(x){
 if(!x){fullNameBox.dataset.v='';urlBox.dataset.v='';sshBox.dataset.v='';descInput.value='';homepageInput.value='';topicsInput.value='';branchInput.value='';labels();return}
 fullNameBox.dataset.v=x.fullName||'';urlBox.dataset.v=x.url||'';sshBox.dataset.v=x.sshUrl||'';
 descInput.value=x.description||'';homepageInput.value=x.homepage||'';topicsInput.value=(x.topics||[]).join(', ');branchInput.value=x.defaultBranch||'';
 visSelect.value=x.isPrivate?'private':'public';
 // Pre-fill the docs generator from the repository identity.
 if(!nameInput.value&&x.name)nameInput.value=x.name;
 if(!repoInput.value&&x.fullName)repoInput.value=x.fullName;
 if(!docDescInput.value&&x.description)docDescInput.value=x.description;
 if(!docHomepageInput.value&&x.homepage)docHomepageInput.value=x.homepage;
 labels();
}
async function loadDetails(){
 const dd=d();if(!dd){say(L().pick,'error');return}
 try{const x=await api.repoDetails(dd);if(x===null){say(L().notLinked,'error');applyDetails(null);return}applyDetails(x);say('','');}catch(e){fail(e)}
}
async function refreshAll(){await ensureChecks();labels();await loadDetails();}
bSave.onclick=async()=>{
 const dd=d();if(!dd)return say(L().pick,'error');
 const topics=topicsInput.value.split(/[,]/).map(s=>s.trim()).filter(Boolean);
 bSave.disabled=true;bSave.textContent=L().wait;
 try{await api.repoDetailsEdit({dir:dd,description:descInput.value.trim(),homepage:homepageInput.value.trim(),topics,visibility:visSelect.value,defaultBranch:branchInput.value.trim()});say(L().saved,'success');await loadDetails()}catch(e){fail(e)}finally{bSave.disabled=false;labels()}
};
bPreview.onclick=async()=>{try{const files=await api.docsGenerate(checksMeta());previewBox.replaceChildren();for(const f of Object.keys(files)){previewBox.append(el('div',{className:'doc-file'},el('strong',{textContent:'# '+f}),el('pre',{textContent:files[f]})))}}catch(e){failDocs(e)}};
bWrite.onclick=async()=>{
 const dd=d();if(!dd)return sayDocs(L().pick,'error');
 const files=Object.keys(fileChecks).filter(f=>fileChecks[f].checked);
 if(!files.length)return sayDocs(L().error,'error');
 bWrite.disabled=true;bWrite.textContent=L().wait;
 try{const r=await api.docsWrite({dir:dd,meta:checksMeta(),files});sayDocs(L().wrote+' '+r.written.join(', ')+'\n→ '+dd,'success')}catch(e){failDocs(e)}finally{bWrite.disabled=false;labels()}
};
bRefreshD.onclick=loadDetails;
bBrowse.onclick=async()=>{const info=await api.add();if(info){dirInput.value=info.dir;if(typeof show==='function')show(info);else if(typeof selected!=='undefined')selected=info.dir;labels();await loadDetails()}};
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('details')){labels();loadDetails()}},0));
window.GitSURepoDetails={refresh:refreshAll};
function init(){refreshAll()}
window.GitSUPanels.hook('details',()=>window.GitSUPanels.sectionVisible('details'),init);
})();
