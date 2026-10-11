(()=>{
'use strict';
// In-page replacement for window.confirm: native dialogs steal keyboard focus on Windows/Electron,
// after which no input field accepts typing until the window is re-activated.
const lang=()=>{const v=document.getElementById('language-select')?.value;return v==='de'?'de':v==='en'?'en':'bg'};
const L={en:['Confirmation','Confirm','Cancel'],bg:['Потвърждение','Потвърди','Отказ'],de:['Bestätigung','Bestätigen','Abbrechen']};
let dlg;
function build(){
 dlg=document.createElement('dialog');dlg.id='gs-confirm';dlg.className='legal-dialog gs-confirm';
 dlg.innerHTML='<h3 id="gs-c-title"></h3><pre id="gs-c-msg"></pre><div class="gs-c-actions"><button type="button" id="gs-c-no" class="outline"></button><button type="button" id="gs-c-yes"></button></div>';
 document.body.appendChild(dlg);
}
function ask(message){
 if(!dlg)build();
 const [t,y,n]=L[lang()];
 dlg.querySelector('#gs-c-title').textContent=t;dlg.querySelector('#gs-c-msg').textContent=String(message||'');
 dlg.querySelector('#gs-c-yes').textContent=y;dlg.querySelector('#gs-c-no').textContent=n;
 const back=document.activeElement;
 return new Promise(resolve=>{
  const done=v=>{dlg.removeEventListener('cancel',onCancel);dlg.close();try{back?.focus?.()}catch{}resolve(v)};
  const onCancel=e=>{e.preventDefault();done(false)};
  dlg.addEventListener('cancel',onCancel);
  dlg.querySelector('#gs-c-yes').onclick=()=>done(true);
  dlg.querySelector('#gs-c-no').onclick=()=>done(false);
  dlg.showModal();dlg.querySelector('#gs-c-yes').focus();
 });
}
window.gsConfirm=ask;
})();
