(()=>{
'use strict';
// Changes (stage / diff / commit) and History (log / commit details) tabs.
const $=id=>document.getElementById(id),api=window.repoAPI;
const T={en:{ch:'Changes',hi:'History',stage:'Stage',unstage:'Unstage',all:'All',msg:'Commit message',commit:'Commit',pushSel:'Commit + push selection',needMsg:'Enter a commit message.',staged:'Staged',modified:'Modified',deleted:'Deleted',stagedDeleted:'Deleted in index',untracked:'New',none:'No changes.',pick:'Select a repository.',more:'More',refresh:'Refresh',nostaged:'No files staged.',empty:'No commits.',conflict:'CONFLICT',done:'Commit',select:'Select a file for diff.',selAll:'Select all',ignore:'Ignore',ignored:'Added to .gitignore',already:'Already ignored',showIgn:'Show ignored',hideIgn:'Hide ignored',allIgnored:'All changes are ignored.'},bg:{ch:'Промени',hi:'История',stage:'Добави (stage)',unstage:'Махни (unstage)',all:'Всички',msg:'Съобщение за commit',commit:'Commit',pushSel:'Commit + качи избраните',needMsg:'Въведете съобщение за commit.',staged:'В индекса',modified:'Променени',deleted:'Изтрити',stagedDeleted:'Изтрити в индекса',untracked:'Нови',none:'Няма промени.',pick:'Изберете репозитори.',more:'Още',refresh:'Обнови',nostaged:'Няма добавени файлове.',empty:'Няма commit-и.',conflict:'КОНФЛИКТ',done:'Commit',select:'Изберете файл за diff.',selAll:'Избери всички',ignore:'Игнорирай',ignored:'Добавено в .gitignore',already:'Вече е игнориран',showIgn:'Покажи игнорирани',hideIgn:'Скрий игнорирани',allIgnored:'Всички промени са игнорирани.'},
 de:{ch:'Änderungen',hi:'Verlauf',stage:'Stagen',unstage:'Unstagen',all:'Alle',msg:'Commit-Nachricht',commit:'Commit',pushSel:'Commit + Push (Auswahl)',needMsg:'Commit-Nachricht eingeben.',staged:'Im Index',modified:'Geändert',deleted:'Gelöscht',stagedDeleted:'Gelöscht im Index',untracked:'Neu',none:'Keine Änderungen.',pick:'Repository wählen.',more:'Mehr',refresh:'Aktualisieren',nostaged:'Keine Dateien gestaged.',empty:'Keine Commits.',conflict:'KONFLIKT',done:'Commit',select:'Datei für Diff wählen.',selAll:'Alle auswählen',ignore:'Ignorieren',ignored:'Zu .gitignore hinzugefügt',already:'Bereits ignoriert',showIgn:'Ignorierte anzeigen',hideIgn:'Ignorierte ausblenden',allIgnored:'Alle Änderungen sind ignoriert.'}};
const L=()=>T[$('language-select')?.value]||T.bg;
const sel=()=>typeof selected!=='undefined'?selected:null;
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
const sectionBefore=document.querySelector('#changes-anchor');
if(!sectionBefore)return;

// ---- Changes ----
const chTitle=el('h2'),chRefresh=el('button',{type:'button',className:'outline'});
const bHideIgn=el('button',{type:'button',className:'outline',ariaPressed:'true'});
const chHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'WORKING TREE'),chTitle),bHideIgn,chRefresh);
const chList=el('div',{className:'gv-list'}),chDiff=el('pre',{className:'log-preview gv-diff'});
const bStage=el('button',{type:'button',className:'outline'}),bUn=el('button',{type:'button',className:'outline'}),bAll=el('button',{type:'button',className:'outline'});
const msgLabel=el('label',{htmlFor:'gv-msg'}),msg=el('input',{id:'gv-msg',maxLength:500}),bCommit=el('button',{type:'button',className:'primary'}),bPushSel=el('button',{type:'button',className:'primary'}),out=el('p',{className:'hint'});
const chSec=el('section',{className:'panel'},chHead,el('div',{className:'action-row'},bStage,bUn,bAll),chList,chDiff,msgLabel,el('div',{className:'action-row'},msg,bCommit,bPushSel),out);
chSec.dataset.section='changes-view';chSec.hidden=true;

// ---- History ----
const hiTitle=el('h2'),hiList=el('div',{className:'gv-list'}),hiShow=el('pre',{className:'log-preview gv-diff'}),bMore=el('button',{type:'button',className:'outline'}),hiRefresh=el('button',{type:'button',className:'outline'});
const hiSec=el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'COMMIT LOG'),hiTitle),hiRefresh),hiList,el('div',{className:'action-row'},bMore),hiShow);
hiSec.dataset.section='history-view';hiSec.hidden=true;
sectionBefore.before(chSec);
document.querySelector('[data-section="activity"]')?.before(hiSec);

function labels(){const l=L();chTitle.textContent=l.ch;hiTitle.textContent=l.hi;bStage.textContent=l.stage;bUn.textContent=l.unstage;bAll.textContent=l.selAll;msgLabel.textContent=l.msg;bCommit.textContent=l.commit;bPushSel.textContent=l.pushSel;bMore.textContent=l.more;chRefresh.textContent=hiRefresh.textContent=l.refresh;chDiff.textContent=hiShow.textContent='';applyHide()}
const checked=()=>[...chList.querySelectorAll('input[type=checkbox]:checked')].map(c=>c.dataset.path);
const fail=e=>{out.textContent=String(e.message||e).replace(/^Error invoking remote method '[^']*': (Error: )?/,'')};
let current=null;
let hideIgnored=true,ignoredCount=0;
function applyHide(){bHideIgn.textContent=(hideIgnored?L().showIgn:L().hideIgn)+(ignoredCount?` (${ignoredCount})`:'');bHideIgn.setAttribute('aria-pressed',String(hideIgnored));}
bHideIgn.onclick=()=>{hideIgnored=!hideIgnored;loadChanges()};

async function ignoreFile(p){
 const d=sel();if(!d)return;
 if(!(await gsConfirm(`${L().ignore}: ${p}?`)))return;
 try{const r=await api.gitignoreAdd({dir:d,path:p});out.textContent=r.already?`${L().already}: ${r.entry}`:`${L().ignored}: ${r.entry}`;await loadChanges()}catch(e){fail(e)}
}
function group(title,items,staged){
 if(!items.length)return null;
 const box=el('div',{className:'gv-group'},el('strong',{},`${title} (${items.length})`));
 for(const f of items){
  const cb=el('input',{type:'checkbox'});cb.dataset.path=f.path;
  const code=staged?f.index:(f.untracked?'?':f.worktree);
  const label=el('label',{className:'gv-file'},cb,el('code',{},code||' '),' ',f.path+(f.from?` ← ${f.from}`:'')+(f.conflict?` · ${L().conflict}`:''));
  const ib=el('button',{type:'button',className:'gv-ignore',title:L().ignore,textContent:'⊘'});
  ib.onclick=async e=>{e.stopPropagation();e.preventDefault();await ignoreFile(f.path)};
  const row=el('div',{className:'gv-row'+(f.conflict?' gv-conflict':'')},label,ib);
  row.onclick=async e=>{if(e.target===cb||e.target.closest('button'))return;current={file:f.path,staged};try{chDiff.textContent=(await api.gvDiff({dir:sel(),file:f.path,staged})).text||'—'}catch(x){fail(x)}};
  box.appendChild(row);
 }
 return box;
}
let chSeq=0,hiSeq=0;
async function loadChanges(){
 const d=sel(),my=++chSeq;chList.replaceChildren();
 if(!d){chList.textContent=L().pick;ignoredCount=0;applyHide();return}
 try{
  const s=await api.gvStatus(d);if(my!==chSeq)return;
  chTitle.textContent=`${L().ch} · ${s.branch||'—'}${s.ahead?` ↑${s.ahead}`:''}${s.behind?` ↓${s.behind}`:''}`;
  ignoredCount=s.files.filter(f=>f.ignored).length;const vis=f=>!(hideIgnored&&f.ignored);
  const staged=s.files.filter(f=>f.index&&!f.untracked&&vis(f)),work=s.files.filter(f=>f.worktree&&!f.untracked&&vis(f)),untr=s.files.filter(f=>f.untracked&&vis(f));
  const parts=[group(L().staged,staged.filter(f=>f.index!=='D'),true),group(L().stagedDeleted,staged.filter(f=>f.index==='D'),true),group(L().modified,work.filter(f=>f.worktree!=='D'),false),group(L().deleted,work.filter(f=>f.worktree==='D'),false),group(L().untracked,untr,false)].filter(Boolean);
  if(!parts.length)chList.textContent=s.files.length?L().allIgnored:L().none;else chList.append(...parts);
  applyHide();
 }catch(e){fail(e)}
}
async function act(fn,files){const d=sel();if(!d||!files.length)return;try{await fn({dir:d,files});out.textContent='';await loadChanges()}catch(e){fail(e)}}
bStage.onclick=()=>act(api.gvStage,checked());
bUn.onclick=()=>act(api.gvUnstage,checked());
bAll.onclick=()=>{const cbs=[...chList.querySelectorAll('input[type=checkbox]')];if(!cbs.length)return;const all=cbs.every(c=>c.checked);for(const cb of cbs)cb.checked=!all};
bCommit.onclick=async()=>{
 const d=sel();if(!d)return;bCommit.disabled=true;
 try{const r=await api.gvCommit({dir:d,message:msg.value});msg.value='';out.textContent=`${L().done} ${r.sha.slice(0,7)} · ${r.files}`;chDiff.textContent='';await loadChanges();await loadLog(true)}
 catch(e){fail(e)}finally{bCommit.disabled=false}
};
// Upload only the selected set (#7): unstage all → stage selection → commit → push HEAD.
bPushSel.onclick=async()=>{
 const d=sel();if(!d)return;const files=checked();const message=msg.value.trim();
 if(!files.length)return fail(L().nostaged);if(!message)return fail(L().needMsg);
 if(!(await gsConfirm(`${L().pushSel} · ${d}?`)))return;
 bPushSel.disabled=true;
 try{
  const s=await api.gvStatus(d);
  const staged=s.files.filter(f=>f.index&&!f.untracked).map(f=>f.path);
  if(staged.length)await api.gvUnstage({dir:d,files:staged});
  await api.gvStage({dir:d,files});
  const r=await api.gvCommit({dir:d,message});
  await api.gitPushHead(d);
  msg.value='';out.textContent=`${L().done} ${r.sha.slice(0,7)} · ${r.files}`;chDiff.textContent='';
  await loadChanges();await loadLog(true);
 }catch(e){fail(e)}finally{bPushSel.disabled=false}
};
chRefresh.onclick=loadChanges;

// ---- History logic ----
const PAGE=50;let logCount=0;
async function loadLog(reset){
 const d=sel();if(reset){hiSeq++;hiList.replaceChildren();logCount=0;hiShow.textContent=''}const my=hiSeq;
 if(!d){hiList.textContent=L().pick;return}
 try{
  const rows=await api.gvLog({dir:d,limit:PAGE,skip:logCount});if(my!==hiSeq)return;
  if(!rows.length&&!logCount)hiList.textContent=L().empty;
  for(const c of rows){
   const r=el('div',{className:'gv-row gv-commit'},el('code',{},c.short),' ',c.subject,c.refs?el('small',{},' · '+c.refs):'',el('small',{},` · ${c.author} · ${c.date.slice(0,16).replace('T',' ')}`));
   r.onclick=async()=>{try{hiShow.textContent=(await api.gvShow({dir:d,sha:c.sha})).text}catch(e){hiShow.textContent=e.message}};
   hiList.appendChild(r);
  }
  logCount+=rows.length;bMore.hidden=rows.length<PAGE;
 }catch(e){hiShow.textContent=e.message}
}
bMore.onclick=()=>loadLog(false);hiRefresh.onclick=()=>loadLog(true);

// Reload whenever the tab becomes visible, the repository changes or the language switches.
let lastDir=null;
function sync(){
 const d=sel();
 if(!chSec.classList.contains('tab-off')&&!chSec.hidden&&d){loadChanges()}
 if(!hiSec.classList.contains('tab-off')&&!hiSec.hidden&&d&&(d!==lastDir||!logCount)){lastDir=d;loadLog(true)}
}
new MutationObserver(sync).observe(chSec,{attributes:true,attributeFilter:['class','hidden']});
new MutationObserver(sync).observe(hiSec,{attributes:true,attributeFilter:['class','hidden']});
api.on('repo',info=>{if(info?.dir===sel()&&!chSec.hidden)loadChanges()});
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{labels();if(!chSec.hidden)loadChanges();if(!hiSec.hidden)loadLog(true)},0));
labels();
})();

