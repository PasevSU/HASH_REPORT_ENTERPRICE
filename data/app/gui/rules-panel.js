(()=>{
'use strict';
// Structured .gitignore editor (#6): numbered, collapsible rules on the right and a
// free-text raw editor on the left. Structured edits serialize into the raw view; the
// raw view is the source of truth when saving.
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.gitignoreLoad)return;
const host=document.getElementById('rules-panel');if(!host)return;
const lang=()=>$('language-select')?.value==='de'?'de':'bg';
const sel=()=>typeof selected!=='undefined'?selected:null;
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const T={
 bg:{title:'Правила за игнориране (.gitignore)',raw:'Свободен текст (.gitignore)',structured:'Структурирани правила',save:'Запиши',refresh:'Обнови',pick:'Избери репозитори, за да редактираш .gitignore.',saved:'Записано.',wait:'Изпълнява се…',presets:'Практически случаи'},
 de:{title:'Ignorierregeln (.gitignore)',raw:'Freitext (.gitignore)',structured:'Strukturierte Regeln',save:'Speichern',refresh:'Aktualisieren',pick:'Repository wählen, um .gitignore zu bearbeiten.',saved:'Gespeichert.',wait:'Läuft…',presets:'Praktische Fälle'}
};
const L=()=>T[lang()];
const DIR_SUGGESTS=['node_modules/','dist/','build/','.vscode/'];
let meta=null,baseCustom=[],presetChecks={},inputs={},dirChecks={};
async function loadMeta(){if(meta)return meta;meta=await api.gitignoreMeta();return meta}
const h=el('h2'),eyebrow=el('div',{className:'eyebrow'});
const bSave=el('button',{type:'button',className:'primary'}),bRefresh=el('button',{type:'button',className:'outline'});
const rawLabel=el('label',{className:'field-label'}),raw=el('textarea',{rows:18,spellcheck:false});
const structLabel=el('label',{className:'field-label'});
const list=el('div',{className:'rules-list'});
const globalBox=el('div',{className:'global-hint'});
const out=el('div',{className:'workflow-result','aria-live':'polite'});
host.append(el('section',{className:'panel'},el('div',{className:'section-head'},el('div',{},eyebrow,h),bRefresh),el('div',{className:'rules-layout'},el('div',{className:'rules-col'},rawLabel,raw),el('div',{className:'rules-col'},structLabel,list,globalBox)),el('div',{className:'action-row'},bSave),out));
function setNav(hasRules){const btn=document.querySelector('[data-view="rules"]');if(btn)btn.hidden=false;}
async function syncNav(d){try{const r=await api.gitignoreLoad(d);setNav(!!r.exists)}catch{}}
const say=(t,type)=>{out.textContent=t;out.dataset.type=type||''};
function labelFor(key){return (meta.categories.find(c=>c.key===key)?.label||{})[lang()]||key}
function placeholderFor(key){return (meta.categories.find(c=>c.key===key)?.placeholder||{})[lang()]||''}
function presetLabel(p){return (p.label||{})[lang()]||p.labelEn||p.name||''}
function splitV(v){return String(v||'').split(/[\n,]+/).map(s=>s.trim()).filter(Boolean)}
async function syncToRaw(){try{const m=readModel();raw.value=await api.gitignoreSerialize(m)}catch(e){say(e.message,'error')}}
function buildStructured(){
 list.replaceChildren();inputs={};dirChecks={};presetChecks={};
 meta.categories.forEach((c,i)=>{
  const inp=el('input',{spellcheck:false});inp.dataset.key=c.key;inp.placeholder=placeholderFor(c.key);inputs[c.key]=inp;inp.oninput=()=>syncToRaw();
  const body=[];
  if(c.key==='dirs'){
   const quick=el('div',{className:'rule-quick'});
   for(const d of DIR_SUGGESTS){const cb=el('input',{type:'checkbox'});cb.value=d;dirChecks[d]=cb;cb.onchange=()=>syncToRaw();quick.append(el('label',{className:'preset-check'},cb,' ',d));}
   body.push(quick);
  }
  body.push(el('span',{className:'rule-example',textContent:placeholderFor(c.key)||''}),inp);
  list.append(el('details',{className:'rule-item'},el('summary',{},el('span',{className:'rule-num',textContent:String(i+1)}),el('span',{className:'rule-title',textContent:labelFor(c.key)})),el('div',{className:'rule-body'},...body)));
 });
 const quick=el('div',{className:'rule-quick'});
 for(const [name,p] of Object.entries(meta.presets)){const cb=el('input',{type:'checkbox'});cb.dataset.preset=name;presetChecks[name]=cb;cb.onchange=()=>syncToRaw();quick.append(el('label',{className:'preset-check'},cb,' ',presetLabel(p)));}
 list.append(el('details',{className:'rule-item'},el('summary',{},el('span',{className:'rule-num',textContent:String(meta.categories.length+1)}),el('span',{className:'rule-title',textContent:L().presets})),el('div',{className:'rule-body'},quick)));
}
function readModel(){
 const m={files:[],patterns:[],dirs:[],subdirs:[],exceptions:[],rootOnly:[],presets:[],custom:baseCustom};
 for(const c of meta.categories){const v=String(inputs[c.key]?.value||'').trim();if(v)m[c.key]=splitV(v)}
 if(dirChecks)for(const d in dirChecks){if(dirChecks[d].checked&&!m.dirs.includes(d))m.dirs.push(d)}
 for(const n in presetChecks){if(presetChecks[n].checked)m.presets.push(n)}
 return m;
}
function applyModel(m){
 for(const c of meta.categories){if(inputs[c.key])inputs[c.key].value=(m[c.key]||[]).join(', ')}
 if(dirChecks){const dirs=m.dirs||[];for(const d in dirChecks)dirChecks[d].checked=dirs.includes(d)}
 for(const n in presetChecks)presetChecks[n].checked=(m.presets||[]).includes(n);
}
function labels(){
 const l=L();h.textContent=l.title;eyebrow.textContent='RULES';bSave.textContent=l.save;bRefresh.textContent=l.refresh;rawLabel.textContent=l.raw;structLabel.textContent=l.structured;
 for(const c of meta.categories){if(inputs[c.key])inputs[c.key].placeholder=placeholderFor(c.key)}
 const g=meta.globalHint;globalBox.replaceChildren(el('span',{textContent:((g.label||{})[lang()]||g.labelEn)+': '}),el('code',{textContent:g.command}));
}
async function refresh(){const d=sel();if(!d){say(L().pick);return}say(L().wait);try{const r=await api.gitignoreLoad(d);baseCustom=(r.model&&r.model.custom)||[];raw.value=r.content||'';applyModel(r.model);setNav(!!r.exists);say('')}catch(e){say(e.message,'error')}}
bSave.onclick=async()=>{const d=sel();if(!d)return say(L().pick,'error');bSave.disabled=true;try{await api.gitignoreSaveRaw({dir:d,content:raw.value});say(L().saved,'success')}catch(e){say(e.message,'error')}finally{bSave.disabled=false}};
bRefresh.onclick=()=>refresh().catch(e=>say(e.message,'error'));
api.on('repo',info=>{if(info?.dir!==sel())return;syncNav(info.dir);if(window.GitSUPanels?.sectionVisible('rules'))refresh().catch(()=>{})});
$('language-select')?.addEventListener('change',()=>setTimeout(()=>{if(window.GitSUPanels?.sectionVisible('rules')){labels();refresh()}},0));
async function init(){try{await loadMeta();buildStructured();labels();await refresh()}catch(e){say(e.message,'error')}}
window.GitSUPanels.hook('rules',()=>window.GitSUPanels.sectionVisible('rules'),init);
})();
