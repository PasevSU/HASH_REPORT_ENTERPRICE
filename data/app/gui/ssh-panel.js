(()=>{
'use strict';
// SSH panel (Settings → SSH tab): list keys, generate, publish to GitHub, test, switch repo to SSH.
const api=window.repoAPI;if(!api?.sshStatus)return;
const sel=()=>typeof selected!=='undefined'?selected:null;
const lang=()=>document.getElementById('language-select')?.value==='de'?'de':'bg';
const T={
 bg:{title:'SSH ключове за GitHub',name:'Име на ключа',email:'Email / коментар',pass:'Парола на ключа (по избор)',gen:'Създай ключ',test:'Тествай връзка с GitHub',refresh:'Обнови',
  copy:'Копирай',add:'Добави в GitHub',use:'Използвай SSH за това репо',useHttps:'Върни към HTTPS',none:'Няма ключове в ~/.ssh.',noSsh:'OpenSSH (ssh-keygen) не е намерен. Инсталирайте „OpenSSH Client“ от Windows → Optional features.',copied:'Копирано',wait:'Изпълнява се…',pick:'Изберете репозитори, за да превключите remote към SSH.'},
 de:{title:'SSH-Schlüssel für GitHub',name:'Schlüsselname',email:'E-Mail / Kommentar',pass:'Passphrase (optional)',gen:'Schlüssel erstellen',test:'GitHub-Verbindung testen',refresh:'Aktualisieren',
  copy:'Kopieren',add:'Zu GitHub hinzufügen',use:'SSH für dieses Repo verwenden',useHttps:'Zurück zu HTTPS',none:'Keine Schlüssel in ~/.ssh.',noSsh:'OpenSSH (ssh-keygen) nicht gefunden. „OpenSSH-Client“ in Windows installieren.',copied:'Kopiert',wait:'Läuft…',pick:'Repository wählen, um den Remote auf SSH umzustellen.'}
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const main=document.querySelector('.main-column');if(!main)return;

const out=el('div',{className:'workflow-result','aria-live':'polite'});
const name=el('input',{value:'id_ed25519',spellcheck:false}),email=el('input',{type:'email'}),pass=el('input',{type:'password',autocomplete:'new-password'});
const lN=el('label'),lE=el('label'),lP=el('label');
const bGen=el('button',{type:'button',className:'primary'}),bTest=el('button',{type:'button',className:'outline'}),bUse=el('button',{type:'button',className:'outline'}),bUseHttps=el('button',{type:'button',className:'outline'}),bRef=el('button',{type:'button',className:'outline'});
const list=el('div',{className:'ssh-list'}),h=el('h2');
const sec=el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'SSH'),h),bRef),list,lN,name,lE,email,lP,pass,el('div',{className:'action-row'},bGen,bTest,bUse,bUseHttps),out);
sec.dataset.section='ssh';sec.hidden=true;main.appendChild(sec);

const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
async function guard(f){try{say(L().wait);const r=await f();return r}catch(e){say(e.message,'error')}}
function labels(){const l=L();h.textContent=l.title;lN.textContent=l.name;lE.textContent=l.email;lP.textContent=l.pass;bGen.textContent=l.gen;bTest.textContent=l.test;bUse.textContent=l.use;bUseHttps.textContent=l.useHttps;bRef.textContent=l.refresh}
async function render(){
 const s=await api.sshStatus();list.replaceChildren();
 if(!s.available){list.textContent=L().noSsh;return}
 if(!s.keys.length){list.textContent=L().none;return}
 for(const k of s.keys){
  const copy=el('button',{type:'button',className:'outline',textContent:L().copy,onclick:async()=>{await navigator.clipboard.writeText(k.publicKey);say(L().copied+': '+k.name)}});
  const add=el('button',{type:'button',className:'outline',textContent:L().add,onclick:()=>guard(async()=>{const r=await api.sshAdd({name:k.name});say(r.message,'success')})});
  list.append(el('div',{className:'gv-row'},el('strong',{textContent:k.name}),el('code',{textContent:k.fingerprint||k.publicKey.slice(0,60)}),copy,add));
 }
}
bRef.onclick=()=>guard(async()=>{await render();say('')});
bGen.onclick=()=>guard(async()=>{const r=await api.sshGenerate({name:name.value.trim(),email:email.value.trim(),passphrase:pass.value});pass.value='';await render();say(r.name+'\n'+r.publicKey,'success')});
bTest.onclick=()=>guard(async()=>{const r=await api.sshTest();say(r.message,r.ok?'success':'error')});
bUse.onclick=()=>guard(async()=>{const d=sel();if(!d)return say(L().pick,'error');const r=await api.sshUseForRepo(d);say(r.from+'\n→ '+r.to,'success')});
bUseHttps.onclick=()=>guard(async()=>{const d=sel();if(!d)return say(L().pick,'error');const r=await api.sshUseHttps(d);say(r.from+'\n→ '+r.to,'success')});
document.getElementById('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('ssh'))refresh()},0));
function refresh(){labels();return render().catch(e=>say(e.message,'error'))}
window.GitSUPanels.hook('ssh',()=>window.GitSUPanels.sectionVisible('ssh'),refresh);
})();
