(()=>{
'use strict';
// System & Performance: resource controller + system health.
const $=id=>document.getElementById(id);
const host=document.getElementById('system-panel');if(!host)return;
const t=k=>window.GITSU_I18N?.[currentLanguage]?.[k]||k;
const percent=x=>Number.isFinite(x)?Math.max(0,Math.min(100,x*100)).toFixed(1)+'%':'—';
const el=(tag,props={},...kids)=>{const e=document.createElement(tag);Object.assign(e,props);e.append(...kids);return e};
host.innerHTML='<div class="section-head"><h2 id="sys-title"></h2><span id="controller-badge" class="chip"></span></div><div class="resource-row"><span id="sys-cpu"></span><b id="cpu-label">—</b></div><div class="track"><i id="cpu-bar"></i></div><div class="resource-row"><span id="sys-ram"></span><b id="ram-label">—</b></div><div class="track green"><i id="ram-bar"></i></div><div class="resource-row"><span id="sys-conc"></span><b id="concurrency">—</b></div><div class="resource-row"><span id="sys-io"></span><b id="io">—</b></div><p class="hint" id="performance-status"></p><div class="section-head"><h2 id="sys-health"></h2></div><div id="health-status" class="health"></div>';
function labels(){
 $('sys-title').textContent=t('Resource Controller');
 const badge=$('controller-badge');badge.textContent=t('WAITING');badge.className='chip';
 $('sys-cpu').textContent=t('System CPU');
 $('sys-ram').textContent=t('Free RAM');
 $('sys-conc').textContent=t('Concurrency');
 $('sys-io').textContent=t('Process I/O');
 $('performance-status').textContent=t('Waiting for live measurements.');
 $('sys-health').textContent=t('System Health');
 $('health-status').textContent=t('Waiting for checks…');
}
function resources(m){
 const cpu=percent(m?.systemCpu??m?.cpu),ram=percent(m?.free);
 $('cpu-label').textContent=cpu;$('ram-label').textContent=ram;
 $('cpu-bar').style.width=cpu==='—'?'0%':cpu;
 $('ram-bar').style.width=ram==='—'?'0%':ram;
 $('io').textContent=Number.isFinite(m?.ioOpsPerSecond)?Math.round(m.ioOpsPerSecond)+' ops/s':'—';
 $('concurrency').textContent=String(m?.concurrency??1);
 const badge=$('controller-badge');
 if(m){badge.textContent=(m.mode||t('unknown')).toUpperCase();badge.className='chip '+(m.mode==='normal'?'good':'warn');}
 else{badge.textContent=t('WAITING');badge.className='chip';}
 if(m)$('connection').textContent=m.mode==='throttled'?t('THROTTLED'):t('ACTIVE');
 $('performance-status').textContent=m?.error?('Controller error: '+m.error):(m?'Local CPU, memory and process I/O measurements. Network throughput is not measured.':t('Waiting for live measurements.'));
}
function health(h){
 const box=$('health-status');box.replaceChildren();
 if(!h||!Object.keys(h).length){box.textContent=t('Waiting for checks…');return;}
 for(const [key,value] of Object.entries(h)){if(!value||typeof value!=='object'||!('available' in value))continue;const row=el('div'),label=el('span'),status=el('b');label.textContent=key.toUpperCase();status.textContent=value.available?t('AVAILABLE'):t('UNAVAILABLE');status.className=value.available?'':'off';row.append(label,status);box.append(row);}
}
window.GitSUUI.on('resources',m=>{labels();resources(m)});
window.GitSUUI.on('health',h=>health(h));
window.GitSUPanels.hook('system',()=>window.GitSUPanels.sectionVisible('system'),()=>{labels();resources(lastResources);health(lastHealth)});
labels();resources(lastResources);health(lastHealth);
})();
