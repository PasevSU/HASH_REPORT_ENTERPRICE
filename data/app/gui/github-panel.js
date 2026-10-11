(()=>{
'use strict';
// GitHub connection panel: connection status + a single action button with 5 operations.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.ghAccountStatus)return;
const host=document.getElementById('github-panel');if(!host)return;
const lang=()=>{const v=$('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const sel=()=>typeof selected!=='undefined'?selected:null;
const T={
 en:{title:'GitHub connection',auth:'Connection status',repos:'Your repositories',sel:'Selected repository',loginBrowser:'Sign in via browser',loginToken:'Sign in with token',logout:'Sign out',tokenLabel:'Personal token (PAT)',tokenUse:'Set token',copy:'Copy',copied:'Copied',none:'No repositories found for this account.',needLogin:'Sign in to GitHub to see repositories.',busy:'Running…',methodToken:'Token',methodBrowser:'Browser',methodSsh:'SSH',methodNone:'None',notAuthed:'Not signed in.',authedAs:'Signed in as',cli:'GitHub CLI',available:'available',unavailable:'unavailable',upToDate:'In sync with remote',ahead:'ahead',behind:'behind',noUpstream:'No remote linked',notSelected:'Select a repository to check the connection.',wait:'Working…',checking:'Checking…',lastPush:'Last push',noLastPush:'no record',localChanges:'Local changes',noLocalChanges:'No local changes / in sync',files:'files',branch:'Branch',remote:'Remote',actions:'Actions',opFetch:'Fetch',opConnect:'Connect',opLoad:'Load',opSync:'Sync',opUpdate:'Update',msg:'Commit message',needMsg:'A commit message is required.',fetchOk:'Fetched',synced:'Synchronized',updated:'Updated',confirmSync:'Sync',confirmUpdate:'Update (pull)'},
 bg:{title:'GitHub връзка',auth:'Състояние на връзката',repos:'Вашите репозитори',sel:'Избрано репозитори',loginBrowser:'Вход през браузър',loginToken:'Вход с токен',logout:'Изход',tokenLabel:'Личен токен (PAT)',tokenUse:'Задай токен',copy:'Копирай',copied:'Копирано',none:'Няма открити репозитори за този акаунт.',needLogin:'Влезте в GitHub, за да видите репозиторите.',busy:'Изпълнява се…',methodToken:'Токен',methodBrowser:'Браузър',methodSsh:'SSH',methodNone:'Няма',notAuthed:'Не сте влезли.',authedAs:'Влезли сте като',cli:'GitHub CLI',available:'наличен',unavailable:'не е наличен',upToDate:'В синхрон с remote',ahead:'напред',behind:'назад',noUpstream:'Няма свързан remote',notSelected:'Изберете репозитори, за да проверите връзката.',wait:'Работи…',checking:'Проверка…',lastPush:'Последно качване',noLastPush:'няма запис',localChanges:'Локални промени',noLocalChanges:'Няма локални промени / в синхрон',files:'файла',branch:'Клон',remote:'Remote',actions:'Операции',opFetch:'Извличане',opConnect:'Свързване',opLoad:'Зареждане',opSync:'Синхронизиране',opUpdate:'Обновяване',msg:'Съобщение за качване',needMsg:'Изисква се съобщение за качване.',fetchOk:'Извлечено',synced:'Синхронизирано',updated:'Обновено',confirmSync:'Синхронизиране',confirmUpdate:'Обновяване (pull)'},
 de:{title:'GitHub-Verbindung',auth:'Verbindungsstatus',repos:'Deine Repositories',sel:'Ausgewähltes Repository',loginBrowser:'Per Browser anmelden',loginToken:'Mit Token anmelden',logout:'Abmelden',tokenLabel:'Persönliches Token (PAT)',tokenUse:'Token setzen',copy:'Kopieren',copied:'Kopiert',none:'Keine Repositories für dieses Konto gefunden.',needLogin:'Bei GitHub anmelden, um Repositories zu sehen.',busy:'Läuft…',methodToken:'Token',methodBrowser:'Browser',methodSsh:'SSH',methodNone:'Keine',notAuthed:'Nicht angemeldet.',authedAs:'Angemeldet als',cli:'GitHub CLI',available:'verfügbar',unavailable:'nicht verfügbar',upToDate:'Mit Remote synchron',ahead:'voraus',behind:'zurück',noUpstream:'Kein Remote verknüpft',notSelected:'Repository wählen, um die Verbindung zu prüfen.',wait:'Arbeitet…',checking:'Prüfe…',lastPush:'Letzter Push',noLastPush:'kein Eintrag',localChanges:'Lokale Änderungen',noLocalChanges:'Keine lokalen Änderungen / synchron',files:'Dateien',branch:'Branch',remote:'Remote',actions:'Aktionen',opFetch:'Abrufen',opConnect:'Verbinden',opLoad:'Laden',opSync:'Synchronisieren',opUpdate:'Aktualisieren',msg:'Commit-Nachricht',needMsg:'Commit-Nachricht erforderlich.',fetchOk:'Abgerufen',synced:'Synchronisiert',updated:'Aktualisiert',confirmSync:'Synchronisieren',confirmUpdate:'Aktualisieren (pull)'}
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const h=el('h2'),eyebrow=el('div',{className:'eyebrow'});
// auth
const authBox=el('div',{className:'github-auth'});
const bBrowser=el('button',{type:'button',className:'primary'}),bToken=el('button',{type:'button',className:'outline'}),bLogout=el('button',{type:'button',className:'outline'});
const tokenLbl=el('label',{htmlFor:'gh-token'}),tokenInput=el('input',{id:'gh-token',type:'password',autocomplete:'new-password',spellcheck:false}),bTokenUse=el('button',{type:'button',className:'outline'});
// repos
const repoHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'GITHUB'),el('h2'))),repoList=el('div',{className:'ssh-list gh-repos'});
// selected repo connection
const selHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'CONNECTION'),el('h2'))),selInfo=el('div',{className:'github-sel'});
const msgLbl=el('label',{htmlFor:'gh-msg'}),msg=el('input',{id:'gh-msg',placeholder:'Describe your changes'}),bActions=el('button',{type:'button',className:'primary'}),menu=el('div',{className:'gh-menu',hidden:true});
let cur=null;
const nm=d=>String(d).split(/[\\/]/).filter(Boolean).pop()||d;
const bCopyUrl=(url,label)=>{const b=el('button',{type:'button',className:'outline',textContent:label,onclick:async()=>{try{await navigator.clipboard.writeText(url);say(L().copied+': '+url,'success')}catch(e){say(L().copy+': '+(e?.message||e),'error')}}});return b};
host.append(
 el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},eyebrow,h)),authBox,
  el('div',{className:'action-row'},bBrowser,bToken,bLogout),
  tokenLbl,el('div',{className:'action-row'},tokenInput,bTokenUse),out),
 el('section',{className:'panel'},repoHead,repoList),
 el('section',{className:'panel'},selHead,selInfo,msgLbl,el('div',{className:'action-row'},msg,el('div',{className:'gh-actions'},bActions,menu)))
);
const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
const methodLabel=m=>m==='token'?L().methodToken:m==='ssh'?L().methodSsh:m==='browser'?L().methodBrowser:L().methodNone;
async function guard(f){try{say(L().wait);const r=await f();return r}catch(e){say(e.message,'error')}}
function labels(){const l=L();h.textContent=l.title;eyebrow.textContent='GITHUB';bBrowser.textContent=l.loginBrowser;bToken.textContent=l.loginToken;bLogout.textContent=l.logout;tokenLbl.textContent=l.tokenLabel;bTokenUse.textContent=l.tokenUse;repoHead.querySelector('h2').textContent=l.repos;selHead.querySelector('h2').textContent=l.sel;msgLbl.textContent=l.msg;bActions.textContent=l.actions+' ▾';buildMenu();}
function renderAuth(st){authBox.replaceChildren();if(!st.authenticated){authBox.append(el('p',{className:'hint',textContent:st.message||L().notAuthed}),el('p',{className:'hint'},L().cli+': '+(st.cliAvailable?L().available:L().unavailable)));bLogout.hidden=true;return}bLogout.hidden=false;authBox.append(el('div',{className:'github-status'},el('strong',{},L().authedAs),el('b',{textContent:st.username||'GitHub'}),el('span',{className:'chip blue',textContent:methodLabel(st.method)})),el('p',{className:'hint',textContent:st.message||''}));}
async function renderRepos(){
 repoList.replaceChildren(el('p',{className:'hint',textContent:L().busy}));
 const st=await api.ghAccountStatus();renderAuth(st);if(!st.authenticated){repoList.replaceChildren(el('p',{className:'hint',textContent:L().needLogin}));return}
 const r=await api.ghListRepos();if(!r.ok){repoList.replaceChildren(el('p',{className:'hint',textContent:r.error||L().none}));return}
 if(!r.repos.length){repoList.replaceChildren(el('p',{className:'hint',textContent:L().none}));return}
 repoList.replaceChildren();
 for(const x of r.repos){repoList.append(el('div',{className:'gv-row gh-repo'},el('strong',{textContent:x.name}),el('code',{textContent:x.https}),bCopyUrl(x.https,'HTTPS'),bCopyUrl(x.ssh,'SSH')))}
}
async function renderSelected(){
 selInfo.replaceChildren();msgLbl.hidden=true;msg.hidden=true;bActions.disabled=true;
 const d=sel();if(!d){selInfo.textContent=L().notSelected;return}
 selInfo.textContent=L().checking;
 try{
  const r=await api.remoteStatus({dir:d,fetch:true});cur=r;
  const name=nm(d);
  const hasUp=!!r.upstreamKnown;
  const parts=[];
  if(r.ahead)parts.push(`${r.ahead} ${L().ahead}`);if(r.behind)parts.push(`${r.behind} ${L().behind}`);
  const chipText=hasUp?(parts.length?parts.join(' · '):L().upToDate):L().noUpstream;
  selInfo.replaceChildren(el('div',{className:'github-status'},el('strong',{textContent:name}),el('span',{className:'chip'+(r.ahead?' warn':' good'),textContent:chipText})));
  selInfo.appendChild(el('div',{className:'github-meta'},el('strong',{textContent:L().branch+':'}),' ',el('span',{textContent:r.branch||'—'})));
  selInfo.appendChild(el('div',{className:'github-meta'},el('strong',{textContent:L().remote+':'}),' ',el('span',{textContent:r.remoteUrl||L().noUpstream})));
  const lp=r.lastPush;
  const lpRow=el('div',{className:'github-meta'},el('strong',{textContent:L().lastPush+':'}),' ');
  if(lp&&lp.short){const when=lp.date?lp.date.slice(0,16).replace('T',' '):'';lpRow.append(el('code',{textContent:lp.short}),' ',el('span',{textContent:[lp.message,lp.author,when].filter(Boolean).join(' · ')}))}else lpRow.append(el('span',{className:'hint',textContent:L().noLastPush}));
  selInfo.appendChild(lpRow);
  const ch=Array.isArray(r.changes)?r.changes:[];
  const lcRow=el('div',{className:'github-meta'},el('strong',{textContent:L().localChanges+':'}),' ');
  if(ch.length){lcRow.append(el('span',{textContent:`${ch.length} ${L().files}`}));const list=el('ul',{className:'gh-changes'});for(const c of ch.slice(0,8))list.append(el('li',{},el('code',{textContent:c.status||' '}),' ',c.path));if(ch.length>8)list.append(el('li',{className:'hint'},`+${ch.length-8}`));lcRow.appendChild(list)}else lcRow.append(el('span',{className:'hint',textContent:L().noLocalChanges}));
  selInfo.appendChild(lcRow);
  bActions.disabled=false;
  if(ch.length){msgLbl.hidden=false;msg.hidden=false}
 }catch(e){selInfo.textContent=e.message}
}
async function opFetch(d){say(L().wait);await api.remoteStatus({dir:d,fetch:true});say(L().fetchOk,'success');await renderSelected()}
function opConnect(d){window.GitSUConnect.open(null,{dir:d})}
function opLoad(d){window.GitSUConnect.open('clone',{dir:d})}
async function opSync(d){
 if(cur?.changes?.length&&!msg.value.trim())return say(L().needMsg,'error');
 if(!(await gsConfirm(`${L().confirmSync} ${nm(d)}?`)))return;
 say(L().wait);
 await api.repoSync({dir:d,apply:true,message:msg.value.trim()});
 say(L().synced,'success');msg.value='';await renderSelected();
}
async function opUpdate(d){
 if(!(await gsConfirm(`${L().confirmUpdate} ${nm(d)}?`)))return;
 say(L().wait);
 await api.operation({dir:d,action:'update',apply:true});
 say(L().updated,'success');await renderSelected();
}
const OPS=[['opFetch',opFetch],['opConnect',opConnect],['opLoad',opLoad],['opSync',opSync],['opUpdate',opUpdate]];
function buildMenu(){menu.replaceChildren();for(const[k,fn]of OPS){const b=el('button',{type:'button'},el('span',{textContent:L()[k]}));b.onclick=async()=>{closeMenu();const d=sel();if(!d){say(L().notSelected,'error');return}try{await fn(d)}catch(e){say(e.message,'error')}};menu.append(b)}}
function toggleMenu(){menu.hidden=!menu.hidden}
function closeMenu(){menu.hidden=true}
bActions.onclick=e=>{e.stopPropagation();toggleMenu()};
document.addEventListener('click',e=>{if(!menu.hidden&&e.target!==bActions&&!menu.contains(e.target))closeMenu()});
bBrowser.onclick=()=>guard(async()=>{await api.githubAuthStart();await renderRepos()});
bLogout.onclick=()=>guard(async()=>{await api.ghAuthLogout();await renderRepos()});
bTokenUse.onclick=()=>guard(async()=>{const t=tokenInput.value.trim();if(!t)return say(L().tokenLabel,'error');const r=await api.githubAuthToken(t);tokenInput.value='';await renderRepos();say(r?.message||'','success')});
api.on('github-auth',m=>{const x=m.state==='waiting'?(lang()==='de'?'GitHub: Code im Browser eingeben':lang()==='en'?'GitHub: enter the code in your browser':'GitHub: въведи кода в браузъра'):m.message;say(x+(m.code?' · '+m.code:''),m.state==='error'?'error':m.state==='success'?'success':'review')});
function refresh(){labels();renderRepos();renderSelected()}
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('github'))refresh()},0));
window.GitSUPanels.hook('github',()=>window.GitSUPanels.sectionVisible('github'),refresh);
})();
