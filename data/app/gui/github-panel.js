(()=>{
'use strict';
// GitHub connection panel (#3): auth status, account repos (HTTPS+SSH), login/logout, selected-repo sync.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.ghAccountStatus)return;
const host=document.getElementById('github-panel');if(!host)return;
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const sel=()=>typeof selected!=='undefined'?selected:null;
const T={
 bg:{title:'GitHub връзка',auth:'Състояние на връзката',repos:'Вашите репозитори',sel:'Избрано репозитори',refresh:'Обнови',loginBrowser:'Вход през браузър',loginToken:'Вход с токен',logout:'Изход',tokenLabel:'Личен токен (PAT)',tokenUse:'Задай токен',copy:'Копирай',copied:'Копирано',none:'Няма открити репозитори за този акаунт.',needLogin:'Влезте в GitHub, за да видите репозиторите.',busy:'Изпълнява се…',methodToken:'Токен',methodBrowser:'Браузър',methodSsh:'SSH',methodNone:'Няма',notAuthed:'Не сте влезли.',authedAs:'Влезли сте като',cli:'GitHub CLI',available:'наличен',unavailable:'не е наличен',upToDate:'В синхрон с remote',ahead:'напред',behind:'назад',noUpstream:'Няма свързан remote',notSelected:'Изберете репозитори, за да проверите синхронизацията.',msg:'Съобщение за качване',sync:'Синхронизирай / Обнови',pull:'Изтегли (pull)',push:'Качи (push)',needMsg:'Изисква се съобщение за качване.',wait:'Работи…',checking:'Проверка…'},
 de:{title:'GitHub-Verbindung',auth:'Verbindungsstatus',repos:'Deine Repositories',sel:'Ausgewähltes Repository',refresh:'Aktualisieren',loginBrowser:'Per Browser anmelden',loginToken:'Mit Token anmelden',logout:'Abmelden',tokenLabel:'Persönliches Token (PAT)',tokenUse:'Token setzen',copy:'Kopieren',copied:'Kopiert',none:'Keine Repositories für dieses Konto gefunden.',needLogin:'Bei GitHub anmelden, um Repositories zu sehen.',busy:'Läuft…',methodToken:'Token',methodBrowser:'Browser',methodSsh:'SSH',methodNone:'Keine',notAuthed:'Nicht angemeldet.',authedAs:'Angemeldet als',cli:'GitHub CLI',available:'verfügbar',unavailable:'nicht verfügbar',upToDate:'Mit Remote synchron',ahead:'voraus',behind:'zurück',noUpstream:'Kein Remote verknüpft',notSelected:'Repository wählen, um den Sync zu prüfen.',msg:'Commit-Nachricht',sync:'Synchronisieren / Aktualisieren',pull:'Herunterladen (pull)',push:'Hochladen (push)',needMsg:'Commit-Nachricht erforderlich.',wait:'Arbeitet…',checking:'Prüfe…'}
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const h=el('h2'),eyebrow=el('div',{className:'eyebrow'});
const bRefresh=el('button',{type:'button',className:'outline'});
// auth
const authBox=el('div',{className:'github-auth'});
const bBrowser=el('button',{type:'button',className:'primary'}),bToken=el('button',{type:'button',className:'outline'}),bLogout=el('button',{type:'button',className:'outline'});
const tokenLbl=el('label',{htmlFor:'gh-token'}),tokenInput=el('input',{id:'gh-token',type:'password',autocomplete:'new-password',spellcheck:false}),bTokenUse=el('button',{type:'button',className:'outline'});
// repos
const repoHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'GITHUB'),el('h2'))),repoList=el('div',{className:'ssh-list gh-repos'});
// selected repo sync
const selHead=el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'SYNC'),el('h2'))),selInfo=el('div',{className:'github-sel'});
const syncMsgLbl=el('label',{htmlFor:'gh-sync-msg'}),syncMsg=el('input',{id:'gh-sync-msg',placeholder:'Describe your changes'}),bSync=el('button',{type:'button',className:'primary'});
const bCopyUrl=(url,label)=>{const b=el('button',{type:'button',className:'outline',textContent:label,onclick:async()=>{await navigator.clipboard.writeText(url);say(L().copied+': '+url,'success')}});return b};
host.append(
 el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},eyebrow,h),bRefresh),authBox,
  el('div',{className:'action-row'},bBrowser,bToken,bLogout),
  tokenLbl,el('div',{className:'action-row'},tokenInput,bTokenUse),out),
 el('section',{className:'panel'},repoHead,repoList),
 el('section',{className:'panel'},selHead,selInfo,syncMsgLbl,el('div',{className:'action-row'},syncMsg,bSync))
);
const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
const methodLabel=m=>m==='token'?L().methodToken:m==='ssh'?L().methodSsh:m==='browser'?L().methodBrowser:L().methodNone;
async function guard(f){try{say(L().wait);const r=await f();return r}catch(e){say(e.message,'error')}}
function labels(){const l=L();h.textContent=l.title;eyebrow.textContent='GITHUB';bRefresh.textContent=l.refresh;bBrowser.textContent=l.loginBrowser;bToken.textContent=l.loginToken;bLogout.textContent=l.logout;tokenLbl.textContent=l.tokenLabel;bTokenUse.textContent=l.tokenUse;repoHead.querySelector('h2').textContent=l.repos;selHead.querySelector('h2').textContent=l.sel;syncMsgLbl.textContent=l.msg;syncGate();}
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
 selInfo.replaceChildren();syncMsg.hidden=true;bSync.disabled=true;bSync.textContent=L().sync;bSync.dataset.action='';
 const d=sel();if(!d){selInfo.textContent=L().notSelected;return}
 selInfo.textContent=L().checking;
 try{
  const r=await api.remoteStatus({dir:d,fetch:true});
  const name=String(d).split(/[\\/]/).filter(Boolean).pop()||d;
  if(!r.upstreamKnown){selInfo.replaceChildren(el('p',{className:'hint',textContent:L().noUpstream}));return}
  const parts=[];
  if(r.ahead)parts.push(`${r.ahead} ${L().ahead}`);if(r.behind)parts.push(`${r.behind} ${L().behind}`);
  selInfo.replaceChildren(el('div',{className:'github-status'},el('strong',{textContent:name}),el('span',{className:'chip'+(r.ahead?' warn':' good'),textContent:parts.length?parts.join(' · '):L().upToDate})));
  if(r.ahead){syncMsg.hidden=false;bSync.textContent=L().push;bSync.dataset.action='push';syncGate();}
  else if(r.behind){bSync.textContent=L().pull;bSync.dataset.action='pull';bSync.disabled=false;}
 }catch(e){selInfo.textContent=e.message}
}
function syncGate(){bSync.disabled=bSync.dataset.action==='push'?(!syncMsg.value.trim().length):false;}
bSync.onclick=async()=>{
 const d=sel();if(!d)return;const ahead=bSync.dataset.action==='push';
 if(ahead&&!syncMsg.value.trim().length)return syncGate();
 const action=ahead?'push':'update';const message=syncMsg.value.trim();
 if(!(await gsConfirm(`${ahead?'Upload':'Pull / update'} ${d}?`)))return;
 bSync.disabled=true;
 try{log(await api.operation({dir:d,action,apply:true,message}));syncMsg.value='';syncMsg.hidden=true}catch(e){selInfo.textContent=e.message}
 finally{await renderSelected()}
};
syncMsg.oninput=syncGate;
bRefresh.onclick=()=>guard(async()=>{await Promise.all([renderRepos(),renderSelected()]);say('')});
bBrowser.onclick=()=>guard(async()=>{await api.githubAuthStart();await renderRepos()});
bLogout.onclick=()=>guard(async()=>{await api.ghAuthLogout();await renderRepos()});
bTokenUse.onclick=()=>guard(async()=>{const t=tokenInput.value.trim();if(!t)return say(L().tokenLabel,'error');const r=await api.githubAuthToken(t);tokenInput.value='';await renderRepos();say(r?.message||'','success')});
api.on('github-auth',m=>{const x=m.state==='waiting'?(lang()==='de'?'GitHub: Code im Browser eingeben':'GitHub: въведи кода в браузъра'):m.message;say(x+(m.code?' · '+m.code:''),m.state==='error'?'error':m.state==='success'?'success':'review')});
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{labels();renderRepos();renderSelected()},0));
labels();renderRepos();renderSelected();
})();
