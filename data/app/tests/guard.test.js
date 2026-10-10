'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const guard=require('../gui/guard');
const g=(cwd,...a)=>{const r=spawnSync('git',a,{cwd,encoding:'utf8'});if(r.status!==0)throw Error(r.stderr);return r.stdout.trim()};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'guard-'));
process.env.GIT_CONFIG_GLOBAL=path.join(tmp,'gitconfig');
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL,'[user]\n name=T\n email=t@t.t\n');
const remote=path.join(tmp,'r.git'),work=path.join(tmp,'w');
g(tmp,'init','--bare','-b','main',remote);fs.mkdirSync(work);g(work,'init','-b','main');g(work,'remote','add','origin',remote);

test('commit is blocked with nothing staged and passes with staged file',async()=>{
 await assert.rejects(guard.guarded('commit',{dir:work,message:'x'},async()=>({ok:true})),/staged/);
 fs.writeFileSync(path.join(work,'a.txt'),'1');g(work,'add','.');
 const r=await guard.guarded('commit',{dir:work,message:'x'},async()=>{g(work,'commit','-m','x');return {ok:true}});
 assert.equal(r.guard.verified,true);
});
test('commit blocked on private key',async()=>{
 fs.writeFileSync(path.join(work,'id_rsa'),'k');g(work,'add','-f','id_rsa');
 await assert.rejects(guard.guarded('commit',{dir:work,message:'x'},async()=>({ok:true})),/чувствителни/);
 g(work,'reset','-q','id_rsa');fs.unlinkSync(path.join(work,'id_rsa'));
});
test('push verified against remote by two methods; fake push is detected',async()=>{
 await assert.rejects(guard.guarded('push',{dir:work,apply:true},async()=>({ok:true})),/НЕ потвърди/);
 const r=await guard.guarded('push',{dir:work,apply:true},async()=>{g(work,'push','origin','main');return {ok:true}});
 assert.equal(r.guard.verified,true);assert.ok(r.guard.post.some(x=>/remote = локален HEAD/.test(x)));
});
test('non fast-forward push is blocked before applying',async()=>{
 const other=path.join(tmp,'o');g(tmp,'clone',remote,other);fs.writeFileSync(path.join(other,'b'),'2');g(other,'add','.');g(other,'commit','-m','b');g(other,'push');
 fs.writeFileSync(path.join(work,'c'),'3');g(work,'add','.');g(work,'commit','-m','c');
 let ran=false;
 await assert.rejects(guard.guarded('push',{dir:work,apply:true},async()=>{ran=true;return {ok:true}}),/fast-forward|Обнови/);
 assert.equal(ran,false);
});
test('stale index.lock is repaired, fresh lock blocks',async()=>{
 const lock=path.join(work,'.git','index.lock');fs.writeFileSync(lock,'');
 const old=new Date(Date.now()-1200000);fs.utimesSync(lock,old,old);
 const a=await guard.preflight('commit',{dir:work,message:'m',apply:false});
 assert.ok(!fs.existsSync(lock));assert.ok(a.rep.checks.some(c=>c.name==='index.lock'&&c.level==='warn'));
 fs.writeFileSync(lock,'');
 const b=await guard.preflight('commit',{dir:work,message:'m',apply:false});
 assert.ok(b.rep.blockers.some(c=>c.name==='index.lock'));fs.unlinkSync(lock);
});
test('link/clone: bad URL and unreachable remote are blocked, redundant transport reported',async()=>{
 const bad=await guard.preflight('link',{dir:tmp,url:'nonsense',mayCreate:true});assert.ok(!bad.rep.ok);
 const miss=await guard.preflight('clone',{url:path.join(tmp,'nope.git'),dest:path.join(tmp,'d'),mayCreate:true});assert.ok(!miss.rep.ok);
 const good=await guard.preflight('clone',{url:remote,dest:path.join(tmp,'d2'),mayCreate:true});assert.ok(good.rep.ok,good.rep.summary().join('\n'));
});
test('URL helpers convert between transports',()=>{
 assert.equal(guard.toSsh('https://github.com/a/b'),'git@github.com:a/b.git');
 assert.equal(guard.toHttps('git@github.com:a/b.git'),'https://github.com/a/b.git');
 assert.equal(guard.kindOf('C:\\x\\y'),'local');
});
test.after(()=>fs.rmSync(tmp,{recursive:true,force:true}));
