(()=>{
'use strict';
// Settings panel: restores Home Assistant, GitHub workflow, export and repository-trust operations
// (previously only reachable through the removed operation dropdown).
const $=id=>document.getElementById(id),api=window.repoAPI;if(!api?.haValidate&&!api?.exportIndex&&!api?.trustProbe)return;
const host=document.getElementById('settings-panel');if(!host)return;
const lang=()=>{const v=$('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const sel=()=>typeof selected!=='undefined'?selected:null;
const T={
 en:{
  title:'Settings & advanced operations',
  trust:'Trust repository',trustHint:'Checks Git ownership and adds the selected repository to global safe.directory.',
  trustProbe:'Check ownership',trustApply:'Trust repository',
  ha:'Home Assistant / HACS',haHint:'Structural validation and a starter package for integrations, plugins and themes.',
  haValidate:'Validate',haType:'Type',haAuto:'auto',haIntegration:'integration',haPlugin:'plugin',haTheme:'theme',
  haScaffold:'Create scaffold',haDomain:'Domain (snake_case)',
  wf:'GitHub Workflow',wfHint:'Review and create .github/workflows/gitsu-validation.yml without overwriting.',
  wfPlan:'Review',wfApply:'Create',
  exportTitle:'Export',exportHint:'Writes the list of registered repositories (repositories.json).',
  exportBtn:'Export repositories.json',
  needRepo:'Select a repository first.',run:'Running…',cancelled:'Cancelled',ok:'Done'
 },
 bg:{
  title:'Настройки и разширени операции',
  trust:'Доверяване на репозитори',trustHint:'Проверява Git собствеността и добавя избраното репозитори към global safe.directory.',
  trustProbe:'Провери собствеността',trustApply:'Довери се на репозиторито',
  ha:'Home Assistant / HACS',haHint:'Структурна проверка и начален пакет за интеграции, плъгини и теми.',
  haValidate:'Провери',haType:'Тип',haAuto:'авто',haIntegration:'интеграция',haPlugin:'плъгин',haTheme:'тема',
  haScaffold:'Създай пакет',haDomain:'Домейн (snake_case)',
  wf:'GitHub Workflow',wfHint:'Преглед и създаване на .github/workflows/gitsu-validation.yml без презаписване.',
  wfPlan:'Прегледай',wfApply:'Създай',
  exportTitle:'Експорт',exportHint:'Записва списък с регистрираните репозитории (repositories.json).',
  exportBtn:'Експортирай repositories.json',
  needRepo:'Първо изберете репозитори.',run:'Изпълнява се…',cancelled:'Отказано',ok:'Готово'
 },
 de:{
  title:'Einstellungen & erweiterte Operationen',
  trust:'Repository vertrauen',trustHint:'Prüft die Git-Eigentümerschaft und markiert das gewählte Repository global als sicher.',
  trustProbe:'Eigentümer prüfen',trustApply:'Repository vertrauen',
  ha:'Home Assistant / HACS',haHint:'Strukturprüfung und Grundgerüst für Integrationen, Plugins und Themes.',
  haValidate:'Prüfen',haType:'Typ',haAuto:'auto',haIntegration:'Integration',haPlugin:'Plugin',haTheme:'Theme',
  haScaffold:'Gerüst erstellen',haDomain:'Domain (snake_case)',
  wf:'GitHub Workflow',wfHint:'Prüft und erstellt .github/workflows/gitsu-validation.yml ohne Überschreiben.',
  wfPlan:'Prüfen',wfApply:'Erstellen',
  exportTitle:'Export',exportHint:'Speichert die Liste registrierter Repositories (repositories.json).',
  exportBtn:'repositories.json exportieren',
  needRepo:'Bitte zuerst ein Repository wählen.',run:'Läuft…',cancelled:'Abgebrochen',ok:'Fertig'
 }
};
const L=()=>T[lang()];
const el=(t,p={},...k)=>{const e=document.createElement(t);Object.assign(e,p);e.append(...k);return e};
const out=el('div',{className:'workflow-result','aria-live':'polite'});
const say=(x,cls='')=>{out.textContent=typeof x==='string'?x:JSON.stringify(x,null,2);out.className='workflow-result'+(cls?' '+cls:'');};
const need=()=>{const d=sel();if(!d){say(L().needRepo);return null}return d};

const hTitle=el('h2');
const trustH=el('h2'),trustHint=el('p',{className:'hint'});
const bTrustProbe=el('button',{type:'button',className:'outline'});
const bTrustApply=el('button',{type:'button',className:'primary'});
bTrustProbe.onclick=async()=>{const d=need();if(!d)return;say(L().run);try{say(await api.trustProbe(d))}catch(e){say(e.message)}};
bTrustApply.onclick=async()=>{const d=need();if(!d)return;if(!(await gsConfirm(`Trust ${nameOf(d)}?`)))return;say(L().run);try{say(await api.trustApply(d))}catch(e){say(e.message)}};

const haH=el('h2'),haHint=el('p',{className:'hint'});
const haTypeLbl=el('label',{htmlFor:'ha-type'});
const haType=el('select',{id:'ha-type'},
 el('option',{value:'auto'}),el('option',{value:'integration'}),el('option',{value:'plugin'}),el('option',{value:'theme'}));
const bHaValidate=el('button',{type:'button',className:'outline'});
const haDomainLbl=el('label',{htmlFor:'ha-domain'});
const haDomain=el('input',{id:'ha-domain',placeholder:'my_integration',spellcheck:false});
const bHaScaffold=el('button',{type:'button',className:'primary'});
bHaValidate.onclick=async()=>{const d=need();if(!d)return;say(L().run);try{say(await api.haValidate({dir:d,type:haType.value}))}catch(e){say(e.message)}};
bHaScaffold.onclick=async()=>{const d=need();if(!d)return;const domain=haDomain.value.trim();if(!/^[a-z][a-z0-9_]*$/.test(domain)){say(L().haDomain);return}if(!(await gsConfirm(`Scaffold Home Assistant integration "${domain}" in ${nameOf(d)}?`)))return;say(L().run);try{say(await api.haScaffoldApply({dir:d,domain}))}catch(e){say(e.message)}};

const wfH=el('h2'),wfHint=el('p',{className:'hint'});
const bWfPlan=el('button',{type:'button',className:'outline'});
const bWfApply=el('button',{type:'button',className:'primary'});
bWfPlan.onclick=async()=>{const d=need();if(!d)return;say(L().run);try{say(await api.workflowPlan(d))}catch(e){say(e.message)}};
bWfApply.onclick=async()=>{const d=need();if(!d)return;if(!(await gsConfirm(`Create GitHub workflow in ${nameOf(d)}?`)))return;say(L().run);try{say(await api.workflowApply(d))}catch(e){say(e.message)}};

const exportH=el('h2'),exportHint=el('p',{className:'hint'});
const bExport=el('button',{type:'button',className:'outline'});
bExport.onclick=async()=>{say(L().run);try{const r=await api.exportIndex();say(r?`${L().ok}: ${typeof r==='string'?r:JSON.stringify(r)}`:L().cancelled)}catch(e){say(e.message)}};

function labels(){const l=L();
 hTitle.textContent=l.title;
 trustH.textContent=l.trust;trustHint.textContent=l.trustHint;bTrustProbe.textContent=l.trustProbe;bTrustApply.textContent=l.trustApply;
 haH.textContent=l.ha;haHint.textContent=l.haHint;haTypeLbl.textContent=l.haType;bHaValidate.textContent=l.haValidate;haDomainLbl.textContent=l.haDomain;bHaScaffold.textContent=l.haScaffold;
 haType.options[0].textContent=l.haAuto;haType.options[1].textContent=l.haIntegration;haType.options[2].textContent=l.haPlugin;haType.options[3].textContent=l.haTheme;
 wfH.textContent=l.wf;wfHint.textContent=l.wfHint;bWfPlan.textContent=l.wfPlan;bWfApply.textContent=l.wfApply;
 exportH.textContent=l.exportTitle;exportHint.textContent=l.exportHint;bExport.textContent=l.exportBtn;
}
host.append(
 el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'ADVANCED'),hTitle)),
 el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'GIT TRUST'),trustH)),trustHint,
 el('div',{className:'action-row'},bTrustProbe,bTrustApply),
 el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'HOME ASSISTANT'),haH)),haHint,
 haTypeLbl,el('div',{className:'action-row'},haType,bHaValidate),
 haDomainLbl,el('div',{className:'action-row'},haDomain,bHaScaffold),
 el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'GITHUB'),wfH)),wfHint,
 el('div',{className:'action-row'},bWfPlan,bWfApply),
 el('div',{className:'section-head'},el('div',{},el('div',{className:'eyebrow'},'EXPORT'),exportH)),exportHint,
 el('div',{className:'action-row'},bExport),
 out
);
labels();
$('language-select')?.addEventListener('change',()=>setTimeout(labels,0));
})();
