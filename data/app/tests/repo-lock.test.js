'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {withRepoLock,gitDir}=require('../gui/repo-lock');
const {OperationManager}=require('../gui/operation-manager');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gslock-'));
spawnSync('git',['init','-q'],{cwd:dir});
test.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
test('lock is exclusive and released',async()=>{
 const lockDir=path.join(gitDir(dir),'gitsu-op.lock');
 await withRepoLock(dir,async()=>{
  assert.ok(fs.existsSync(lockDir));
  fs.writeFileSync(path.join(lockDir,'pid'),String(process.ppid||1));
 }).catch(()=>{});
 assert.ok(!fs.existsSync(lockDir));
 fs.mkdirSync(lockDir);fs.writeFileSync(path.join(lockDir,'pid'),String(process.ppid));
 await assert.rejects(()=>withRepoLock(dir,async()=>1,{waitMs:600,stepMs:100}),/busy/);
 fs.rmSync(lockDir,{recursive:true});
});
test('stale lock (dead pid) is recovered',async()=>{
 const lockDir=path.join(gitDir(dir),'gitsu-op.lock');fs.mkdirSync(lockDir);fs.writeFileSync(path.join(lockDir,'pid'),'999999');
 assert.equal(await withRepoLock(dir,async()=>'ok'),'ok');
});
test('OperationManager runs inside the lock',async()=>{
 const lockDir=path.join(gitDir(dir),'gitsu-op.lock');let held=false;
 const journal={create:()=>1,set:()=>{},list:()=>[]};
 const m=new OperationManager({journal,execute:async()=>{held=fs.existsSync(lockDir);return {ok:true}},lock:withRepoLock});
 await m.run({dir,action:'push'});assert.equal(held,true);assert.ok(!fs.existsSync(lockDir));
});
