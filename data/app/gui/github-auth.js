 'use strict';
const {spawn}=require('node:child_process');
const {EventEmitter}=require('node:events');
const DEVICE_URL='https://github.com/login/device';
function invokeGh(args,{spawnImpl=spawn,timeoutMs=15000}={}){
 return new Promise(resolve=>{let done=false,output='',child;
 const finish=r=>{if(done)return;done=true;clearTimeout(timer);resolve(r)};
 const timer=setTimeout(()=>{child?.kill();finish({ok:false,error:'GitHub CLI timeout'})},timeoutMs);
 try{child=spawnImpl('gh',args,{shell:false,windowsHide:true,env:process.env,stdio:['ignore','pipe','pipe']});}
 catch(e){finish({ok:false,error:e.message});return}
 for(const stream of [child.stdout,child.stderr])stream?.on('data',d=>{output=(output+String(d)).slice(-12000)});
 child.on('error',e=>finish({ok:false,error:e.code==='ENOENT'?'GitHub CLI (gh) is not installed or not in PATH':e.message}));
 child.on('close',code=>finish({ok:code===0,code,output}));
 });
}
class GitHubBrowserAuth extends EventEmitter{
 constructor({spawnImpl=spawn,openBrowser=()=>{},emit=()=>{}}={}){super();this.spawnImpl=spawnImpl;this.openBrowser=openBrowser;this.emitStatus=emit;this.child=null;this.busy=false;this.last='';}
 async status(){const r=await invokeGh(['auth','status','--hostname','github.com'],{spawnImpl:this.spawnImpl});return {authenticated:r.ok,cliAvailable:!r.error?.includes('not installed'),message:r.ok?'Authenticated with GitHub CLI':(r.error||'Not authenticated; use browser login'),busy:this.busy};}
 start(){if(this.busy)return {ok:false,error:'Authentication already in progress'};this.busy=true;this.last='';let child;
 try{child=this.spawnImpl('gh',['auth','login','--hostname','github.com','--git-protocol','https'],{shell:false,windowsHide:true,env:process.env,stdio:['ignore','pipe','pipe']});this.child=child;}
 catch(e){this.busy=false;return {ok:false,error:e.message}}
 this.emitStatus({state:'started',message:'Starting GitHub browser authentication…'});
 const onData=data=>{this.last=(this.last+String(data)).slice(-12000);const code=this.last.match(/(?:one.time code|code:)\s*([A-Z0-9]{4}-[A-Z0-9]{4})/i)?.[1];this.emitStatus({state:'waiting',message:'Open github.com/login/device and enter the displayed code.',code:code||null});};
 child.stdout?.on('data',onData);child.stderr?.on('data',onData);
 child.on('error',e=>{this.busy=false;this.child=null;this.emitStatus({state:'error',message:e.code==='ENOENT'?'GitHub CLI (gh) is not installed or not in PATH':e.message})});
 child.on('close',code=>{this.busy=false;this.child=null;this.emitStatus({state:code===0?'success':'error',message:code===0?'GitHub CLI authentication completed.':'GitHub CLI login ended without success.'})});
 // Opening the documented device page is safe; gh also opens its own browser if available.
 Promise.resolve().then(()=>this.openBrowser(DEVICE_URL)).catch(()=>{});
 return {ok:true,deviceUrl:DEVICE_URL};
 }
 async loginWithToken(token){
  if(this.busy)return {ok:false,error:'Authentication already in progress'};
  if(typeof token!=='string'||token.length<20||token.length>4096||/[\r\n\0]/.test(token))return {ok:false,error:'Invalid token format'};
  this.busy=true;
  try{
   return await new Promise(resolve=>{
    let child,settled=false,timer;
    const finish=result=>{if(settled)return;settled=true;clearTimeout(timer);this.busy=false;this.child=null;this.emitStatus({state:result.ok?'success':'error',message:result.ok?'GitHub token authentication completed.':'GitHub token authentication failed.'});resolve(result)};
    try{child=this.spawnImpl('gh',['auth','login','--hostname','github.com','--git-protocol','https','--with-token'],{shell:false,windowsHide:true,env:process.env,stdio:['pipe','ignore','ignore']});this.child=child;}
    catch(e){return finish({ok:false,error:'Could not start GitHub CLI'})}
    timer=setTimeout(()=>{child.kill();finish({ok:false,error:'GitHub CLI authentication timeout'})},30000);
    child.on('error',()=>finish({ok:false,error:'GitHub CLI unavailable or authentication failed'}));
    child.on('close',code=>finish({ok:code===0,error:code===0?undefined:'Token rejected or GitHub CLI failed'}));
    child.stdin?.on('error',()=>{});
    child.stdin?.end(token+'\n');
   });
  }finally{this.busy=false;}
 }
 cancel(){if(!this.child)return {ok:false,error:'No active authentication'};this.child.kill();return {ok:true};}
}
module.exports={GitHubBrowserAuth,invokeGh,DEVICE_URL};
