'use strict';
// Two nodes share one bare remote: only the lease holder pushes, the other follows, takeover after release.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn,spawnSync}=require('node:child_process');
const win=process.platform==='win32';
const script=path.resolve(__dirname,'../scripts',win?'ha-git-sync.ps1':'ha-git-sync.sh');
const have=cmd=>spawnSync(cmd,['--version'],{windowsHide:true}).status===0;
const skip=(win?!have('pwsh'):false)||!have('git');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gslease-'));
const git=(cwd,...a)=>{const r=spawnSync('git',a,{cwd,encoding:'utf8'});if(r.status)throw Error(r.stderr);return r.stdout.trim()};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const nodes={};
function start(name){
 const dir=path.join(tmp,name),env={...process.env,REPO_PATH:dir,BRANCH:'main',APPLY:'1',POLL_INTERVAL:'1',DEBOUNCE:'2',LEASE_TTL:'15',LEASE_GRACE:'2',FOLLOW_INTERVAL:'2',NODE_ID:name};
 const c=spawn(win?'pwsh':'bash',win?['-NoProfile','-File',script]:[script],{cwd:dir,env,windowsHide:true});
 let out='';c.stdout.on('data',d=>out+=d);c.stderr.on('data',d=>out+=d);
 return {c,dir,log:()=>out,stop:async()=>{c.kill('SIGINT');c.kill();await sleep(500)}};
}
async function until(fn,ms,label){const end=Date.now()+ms;while(Date.now()<end){if(fn())return;await sleep(500)}throw Error('Timeout: '+label)}
test('lease: leader pushes, follower fast-forwards, takeover after leader stops',{skip,timeout:120000},async t=>{
 const bare=path.join(tmp,'r.git');git(tmp,'init','-q','--bare','-b','main','r.git');
 for(const n of ['a','b']){git(tmp,'clone','-q',bare,n);git(path.join(tmp,n),'config','user.name','t');git(path.join(tmp,n),'config','user.email','t@t')}
 const a0=path.join(tmp,'a');fs.writeFileSync(path.join(a0,'f.txt'),'0');git(a0,'add','.');git(a0,'commit','-qm','i');git(a0,'push','-q','origin','HEAD:main');git(path.join(tmp,'b'),'pull','-q','origin','main');
 const A=start('a');nodes.a=A;await until(()=>/LEASE ACQUIRED/.test(A.log()),20000,'A lease');
 const B=start('b');nodes.b=B;await sleep(3000);
 fs.writeFileSync(path.join(a0,'f.txt'),'1');
 await until(()=>/PUSH VERIFIED/.test(A.log()),30000,'A push');
 await until(()=>/FOLLOWED/.test(B.log()),30000,'B follow');
 assert.equal(fs.readFileSync(path.join(tmp,'b','f.txt'),'utf8').trim(),'1');
 await A.stop();
 await until(()=>/LEASE ACQUIRED/.test(B.log()),60000,'B takeover');
 fs.writeFileSync(path.join(tmp,'b','f.txt'),'2');
 await until(()=>/PUSH VERIFIED/.test(B.log()),30000,'B push');
 assert.equal(git(tmp,'--git-dir='+bare,'show','main:f.txt'),'2');
 await B.stop();
});
test.after(async()=>{for(const n of Object.values(nodes))await n.stop().catch(()=>{});fs.rmSync(tmp,{recursive:true,force:true})});
