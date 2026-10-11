(()=>{
'use strict';
// About panel + legal/license actions + bilingual organization note.
const $=id=>document.getElementById(id);
const host=document.getElementById('about-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const aboutOrg={
 bg:'PasevSU-DEV е независима организация за софтуерна разработка, ръководена от Денислав Пасев. Работи по системни инструменти, Home Assistant интеграции и проекти за киберсигурност. По информация от разработчика, той участва доброволно в инициативата „NO TRUST“, насочена към уязвимости в критична инфраструктура. Това описание не означава институционално одобрение.',
 de:'PasevSU-DEV ist eine unabhängige Softwareentwicklungsorganisation unter Leitung von Denislav Pasev. Zu den Projekten gehören Systemwerkzeuge, Home-Assistant-Integrationen und Cybersicherheit. Nach Angaben des Entwicklers engagiert er sich freiwillig in der Initiative „NO TRUST“ zu Schwachstellen kritischer Infrastruktur. Diese Beschreibung stellt keine institutionelle Bestätigung dar.',
 en:'PasevSU-DEV is an independent software development organization led by Denislav Pasev. It works on system tools, Home Assistant integrations, and cybersecurity projects. According to the developer, he volunteers in the "NO TRUST" initiative focused on critical infrastructure vulnerabilities. This description does not imply institutional endorsement.'
};
host.innerHTML='<div class="section-head"><h2 id="about-title"></h2></div><p id="about-description"></p><p id="about-safety"></p><p id="about-organization"></p><p><strong>PasevSU-DEV</strong> · <a href="https://pasevsu.github.io/" target="_blank" rel="noopener noreferrer">https://pasevsu.github.io/</a></p><div class="legal-actions"><button id="show-license" class="outline" type="button">License · Apache 2.0</button><button id="show-notice" class="outline" type="button">Attribution · NOTICE</button></div><small id="about-version"></small>';
function labels(){
 $('about-title').textContent=t('About GitSU');
 $('about-description').textContent=t('GitSU SUPERUSER is a local center for managing Git repositories with controlled operations, file monitoring, and system resource metrics.');
 $('about-safety').textContent=t('Operations that change data require confirmation. A backup is recommended before synchronization.');
 $('about-organization').textContent=aboutOrg[currentLanguage]||aboutOrg.en;
 $('about-version').textContent=t('Version 0.43.4 · Windows verification pending.');
 $('show-license').textContent=t('License · Apache 2.0');
 $('show-notice').textContent=t('Attribution · NOTICE');
}
$('show-license').addEventListener('click',()=>showLegal('license'));
$('show-notice').addEventListener('click',()=>showLegal('notice'));
$('language-select')?.addEventListener('change',()=>setTimeout(labels,0));
labels();
})();
