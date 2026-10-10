(()=>{
'use strict';
// Releases panel: GitHub Release + git tag management for the selected repository.
// Thin UI over the lib/releases package (via the preload bridge). No git logic lives here.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.releaseList)return;
const host=document.getElementById('releases-panel');if(!host)return;
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const sel=()=>typeof selected!=='undefined'?selected:null;
const nameOf=d=>String(d).split(/[\\/]/).filter(Boolean).pop()||d;
const T={
 bg:{title:'Релизи на репозиторията',create:'Създай релиз',manage:'Съществуващи релизи',tags:'Тагове (local / remote)',tag:'Таг',name:'Име',notes:'Бележки (notes)',target:'Цел (target)',prerelease:'Pre-release',draft:'Draft',submit:'Публикувай релиз',none:'Няма релизи.',latest:'Последен релиз',noLatest:'Все още няма релиз.',local:'локални',remote:'отдалечени',noneTags:'Няма тагове.',pick:'Изберете репозитория.',delete:'Изтрий',confirm:'Изтриване на релиз {0}?',wait:'Изпълнява се…',error:'Грешка',refresh:'Обнови'},
 de:{title:'Repository-Releases',create:'Release erstellen',manage:'Vorhandene Releases',tags:'Tags (local / remote)',tag:'Tag',name:'Name',notes:'Notizen',target:'Ziel',prerelease:'Pre-release',draft:'Entwurf',submit:'Release veröffentlichen',none:'Keine Releases.',latest:'Neuestes Release',noLatest:'Noch kein Release.',local:'lokal',remote:'remote',noneTags:'Keine Tags.',pick:'Repository wählen.',delete:'Löschen',confirm:'Release {0} löschen?',wait:'Läuft…',error:'Fehler',refresh:'Aktualisieren'}
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
const fail=e=>say(String(e.message||e).replace(/^Error invoking remote method '[^']*': (Error: )?/,''),'error');
const dirInput=el('input',{spellcheck:false,placeholder:'C:\\path\\to\\repo'}),bBrowse=el('button',{type:'button',className:'outline'});
const tagInput=el('input',{spellcheck:false,placeholder:'v1.0.0'}),nameInput=el('input',{spellcheck:false}),notesInput=el('textarea',{rows:4}),targetInput=el('input',{spellcheck:false});
const preChk=el('input',{type:'checkbox'}),draftChk=el('input',{type:'checkbox'});
const bSubmit=el('button',{type:'button',className:'primary'}),bRefresh=el('button',{type:'button',className:'outline'});
const latestBox=el('div',{className:'log-preview'}),listBox=el('div',{className:'ssh-list'}),tagsBox=el('div',{className:'ssh-list'});
host.append(
 el('section',{className:'panel'},
  el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'RELEASES'),el('h2',{id:'releases-title'}))),
  el('label',{id:'releases-dir-label'}),el('div',{className:'action-row'},dirInput,bBrowse),
  el('div',{className:'action-row'},
   el('label',{id:'releases-tag-label'},tagInput),
   el('label',{id:'releases-name-label'},nameInput)),
  el('label',{id:'releases-notes-label'},notesInput),
  el('label',{id:'releases-target-label'},targetInput),
  el('div',{className:'action-row'},el('label',{},preChk,' ',el('span',{id:'releases-pre'})),el('label',{},draftChk,' ',el('span',{id:'releases-draft'}))),
  el('div',{className:'action-row'},bSubmit),out),
 el('section',{className:'panel'},
  el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'LATEST'),el('h2',{id:'releases-latest-label'})),el('div',{className:'action-row'},bRefresh)),
  latestBox,listBox),
 el('section',{className:'panel'},
  el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'TAGS'),el('h2',{id:'releases-tags-title'}))),
  tagsBox)
);
function labels(){const l=L();$('releases-title').textContent=l.title;$('releases-dir-label').textContent=l.title;$('releases-tag-label').textContent=l.tag;$('releases-name-label').textContent=l.name;$('releases-notes-label').textContent=l.notes;$('releases-target-label').textContent=l.target;$('releases-pre').textContent=l.prerelease;$('releases-draft').textContent=l.draft;bSubmit.textContent=l.submit;bRefresh.textContent=l.refresh;$('releases-latest-label').textContent=l.latest;$('releases-tags-title').textContent=l.tags;dirInput.placeholder=sel()?nameOf(sel()):'';}
const d=()=>dirInput.value.trim()||sel();
function renderLatest(x){latestBox.replaceChildren();if(!x){latestBox.textContent=L().noLatest;return}latestBox.append(el('div',{className:'gv-row'},el('strong',{textContent:x.tag+' — '+(x.title||'')}),el('small',{textContent:(x.publishedAt||'').slice(0,16).replace('T',' ')||''}),x.prerelease?el('span',{className:'chip',textContent:L().prerelease}):'',x.draft?el('span',{className:'chip',textContent:L().draft}):''))}
async function loadLatest(){try{renderLatest(await api.releaseLatest(d()))}catch(e){renderLatest(null)}}
async function loadList(){listBox.replaceChildren();const dd=d();if(!dd){listBox.textContent=L().pick;return}let items=[];try{items=await api.releaseList(dd)}catch(e){return fail(e)}if(!items.length){listBox.textContent=L().none;return}for(const r of items){const row=el('div',{className:'gv-row'},el('strong',{textContent:r.tag+' — '+(r.title||'')}),el('small',{textContent:(r.publishedAt||'').slice(0,16).replace('T',' ')||''}),r.prerelease?el('span',{className:'chip',textContent:L().prerelease}):'',r.draft?el('span',{className:'chip',textContent:L().draft}):'');if(r.url){const a=el('a',{href:r.url,target:'_blank',rel:'noopener noreferrer',textContent:'↗'});row.append(' ',a)}const del=el('button',{type:'button',className:'outline',textContent:L().delete});del.onclick=async()=>{if(!(await gsConfirm(L().confirm.replace('{0}',r.tag))))return;del.disabled=true;try{await api.releaseDelete({dir:dd,tag:r.tag});await loadList();await loadLatest()}catch(e){fail(e)}finally{del.disabled=false}};row.append(' ',del);listBox.append(row)}}
async function loadTags(){tagsBox.replaceChildren();const dd=d();if(!dd){tagsBox.textContent=L().pick;return}let r;try{r=await api.releaseTags(dd)}catch(e){return fail(e)}const lo=r.local||[],re=r.remote||[];if(!lo.length&&!re.length){tagsBox.textContent=L().noneTags;return}tagsBox.append(el('div',{className:'gv-row'},el('strong',{textContent:`${L().local}: ${lo.length}`}),el('code',{textContent:lo.join(', ')||'—'})));tagsBox.append(el('div',{className:'gv-row'},el('strong',{textContent:`${L().remote}: ${re.length}`}),el('code',{textContent:re.join(', ')||'—'})))}
async function refreshAll(){if(!d()){say(L().pick,'error');return}await loadLatest();await loadList();await loadTags()}
bBrowse.onclick=async()=>{const p=await api.pickFolder();if(p){dirInput.value=p;labels();refreshAll()}};
bSubmit.onclick=async()=>{const dd=d();if(!dd)return say(L().pick,'error');const tag=tagInput.value.trim();if(!tag)return say(L().tag+' '+L().error,'error');bSubmit.disabled=true;try{const r=await api.releaseCreate({dir:dd,tag,title:nameInput.value.trim(),notes:notesInput.value.trim(),target:targetInput.value.trim()||undefined,prerelease:preChk.checked,draft:draftChk.checked});say(r.tag+(r.url?' · '+r.url:''),'success');tagInput.value='';nameInput.value='';notesInput.value='';await refreshAll()}catch(e){fail(e)}finally{bSubmit.disabled=false}};
bRefresh.onclick=refreshAll;
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{labels();refreshAll()},0));
window.GitSUReleases={refresh:refreshAll};
labels();refreshAll();
})();
