(()=>{
'use strict';
// "Старт" launcher: every entry point that does not need a selected repository, in one place.
const main=document.querySelector('.main-column');if(!main)return;
const lang=()=>{const v=document.getElementById('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const T={
 en:{title:'Start here',sub:'All actions work even without a selected repository.',
  g1:'Repository',g2:'Account & access',g3:'More',
  connect:['Connect / upload folder','Folder with files → new or existing GitHub repo'],
  create:['New GitHub repo','Creates a repo and uploads the first commit'],
  clone:['Clone repo','From GitHub, URL or NAS into a new folder'],
  add:['Add local folder','Register an existing git repo'],
  login:['Sign in to GitHub','Via browser (recommended)'],
  token:['Sign in with token','Classic token with scope "repo"'],
  ssh:['SSH keys','Create, test and add a key to GitHub'],
  ops:['All operations','Grouped by task, with checks before and after'],
  ha:['Home Assistant','Integration check and scaffold']},
 bg:{title:'Започнете оттук',sub:'Всички действия работят и без избрано репозитори.',
  g1:'Репозитори',g2:'Акаунт и достъп',g3:'Още',
  connect:['Свържи / качи папка','Папка с файлове → ново или съществуващо GitHub репо'],
  create:['Ново репо в GitHub','Създава репо и качва първия commit'],
  clone:['Клонирай (изтегли) репо','От GitHub, URL или NAS в нова папка'],
  add:['Добави локална папка','Регистрира вече съществуващо git репо'],
  login:['Вход в GitHub','През браузър (препоръчително)'],
  token:['Вход с токен','Classic токен със scope „repo“'],
  ssh:['SSH ключове','Създай, тествай и добави ключ в GitHub'],
  ops:['Всички операции','Групирани по задачи, с проверки преди и след'],
  ha:['Home Assistant','Проверка и скеле на интеграция']},
 de:{title:'Hier starten',sub:'Alle Aktionen funktionieren auch ohne ausgewähltes Repository.',
  g1:'Repository',g2:'Konto & Zugang',g3:'Weitere',
  connect:['Ordner verbinden / hochladen','Ordner → neues oder bestehendes GitHub-Repo'],
  create:['Neues GitHub-Repo','Erstellt Repo und lädt den ersten Commit hoch'],
  clone:['Repo klonen','Von GitHub, URL oder NAS in neuen Ordner'],
  add:['Lokalen Ordner hinzufügen','Bestehendes Git-Repo registrieren'],
  login:['Bei GitHub anmelden','Per Browser (empfohlen)'],
  token:['Anmeldung per Token','Classic-Token mit Scope „repo“'],
  ssh:['SSH-Schlüssel','Erstellen, testen, bei GitHub hinzufügen'],
  ops:['Alle Vorgänge','Nach Aufgaben gruppiert, mit Prüfungen davor und danach'],
  ha:['Home Assistant','Prüfung und Gerüst der Integration']}
};
const sec=document.createElement('section');sec.className='panel start-panel';sec.dataset.section='start';
const nav=v=>()=>window.view?.(v);
const GROUPS=[
 ['g1',[['connect',()=>window.GitSUConnect?.open(null,{}),'⇪'],['create',()=>window.GitSUConnect?.open('create',{}),'✚'],['clone',()=>window.GitSUConnect?.open('clone',{}),'⇩'],['add',()=>document.querySelector('[data-action="add"]')?.click(),'▣']]],
 ['g2',[['login',nav('github'),'🔑'],['token',nav('github'),'🔐'],['ssh',nav('github'),'🛡']]],
 ['g3',[['ops',nav('github'),'⚙'],['ha',nav('settings'),'⌂']]]
];
function render(){
 const t=T[lang()];sec.textContent='';
 const h=document.createElement('div');h.className='section-head';
 const d=document.createElement('div');const e=document.createElement('div');e.className='eyebrow';e.textContent='START';const h2=document.createElement('h2');h2.textContent=t.title;const p=document.createElement('small');p.textContent=t.sub;
 d.append(e,h2,p);h.append(d);sec.append(h);
 for(const [g,items] of GROUPS){
  const gt=document.createElement('h3');gt.className='start-group';gt.textContent=t[g];sec.append(gt);
  const row=document.createElement('div');row.className='start-grid';
  for(const [k,fn,icon] of items){
   const b=document.createElement('button');b.type='button';b.className='start-card';b.dataset.start=k;
   const i=document.createElement('span');i.className='start-icon';i.textContent=icon;
   const w=document.createElement('span');const s=document.createElement('strong');s.textContent=t[k][0];const m=document.createElement('small');m.textContent=t[k][1];w.append(s,m);
   b.append(i,w);b.onclick=fn;row.append(b);
  }
  sec.append(row);
 }
}
main.prepend(sec);render();
document.getElementById('language-select')?.addEventListener('change',()=>setTimeout(render,0));
})();
