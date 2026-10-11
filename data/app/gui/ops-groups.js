(()=>{
'use strict';
// Splits the flat operation dropdown into labelled groups and adds a one-click group bar.
const sel=document.getElementById('workflow-kind');if(!sel)return;
const G=[
 ['account',{en:'Account',bg:'Акаунт',de:'Konto'},['githubToken','githubLogin']],
 ['create',{en:'New repo',bg:'Ново репо',de:'Neues Repo'},['cloneRepo','newLocal','publishNew','remote']],
 ['sync',{en:'Sync',bg:'Синхронизация',de:'Sync'},['push','update','copy','localUpdate']],
 ['maint',{en:'Maintenance',bg:'Поддръжка',de:'Wartung'},['inspect','diagnostics','trust','rules','workflow','exportIndex']],
 ['ha',{en:'Home Assistant',bg:'Home Assistant',de:'Home Assistant'},['haValidate','haScaffold']]
];
const lang=()=>{const v=document.getElementById('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const opts=new Map([...sel.options].map(o=>[o.value,o]));
const bar=document.createElement('div');bar.className='ops-groups';bar.setAttribute('role','tablist');
const groups=[];
for(const [id,label,vals] of G){
 const og=document.createElement('optgroup');og.dataset.g=id;
 for(const v of vals)if(opts.has(v))og.appendChild(opts.get(v));
 if(!og.children.length)continue;
 sel.appendChild(og);
 const b=document.createElement('button');b.type='button';b.className='outline ops-group';b.dataset.g=id;
 b.onclick=()=>{if(!vals.includes(sel.value)){sel.value=vals.find(v=>opts.has(v));sel.dispatchEvent(new Event('change',{bubbles:true}))}mark()};
 groups.push({id,label,vals,og,b});bar.appendChild(b);
}
for(const o of opts.values())if(!o.parentElement||o.parentElement===sel)sel.appendChild(o);
sel.closest('.operation-selector')?.prepend(bar);
function labels(){for(const g of groups){g.og.label=g.label[lang()];g.b.textContent=g.label[lang()]}}
function mark(){for(const g of groups)g.b.classList.toggle('active',g.vals.includes(sel.value))}
sel.addEventListener('change',mark);
document.getElementById('language-select')?.addEventListener('change',()=>setTimeout(labels,0));
new MutationObserver(mark).observe(sel,{attributes:true});
setInterval(mark,800);
labels();mark();
})();
