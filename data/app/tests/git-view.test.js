'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const gv=require('../gui/git-view');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gsgv-'));
const g=(...a)=>{const r=spawnSync('git',a,{cwd:dir,encoding:'utf8'});if(r.status)throw Error(r.stderr);return r.stdout.trim()};
g('init','-q','-b','main');g('config','user.name','t');g('config','user.email','t@t');
test.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
const w=(n,t)=>fs.writeFileSync(path.join(dir,n),t);
test('status lists untracked, stage, unstage before first commit',async()=>{
 w('a.txt','1');let s=await gv.status(dir);
 assert.equal(s.branch,'main');assert.deepEqual(s.files.map(f=>[f.path,f.untracked]),[['a.txt',true]]);
 await gv.stage(dir,['a.txt']);s=await gv.status(dir);assert.equal(s.files[0].index,'A');
 await gv.unstage(dir,['a.txt']);s=await gv.status(dir);assert.equal(s.files[0].untracked,true);
});
test('diff of untracked and staged files',async()=>{
 assert.match((await gv.diff(dir,{file:'a.txt'})).text,/\+1/);
 await gv.stage(dir,['a.txt']);assert.match((await gv.diff(dir,{file:'a.txt',staged:true})).text,/\+1/);
});
test('commit, log, show',async()=>{
 const r=await gv.commit(dir,{message:'first'});assert.equal(r.files,1);
 const l=await gv.log(dir);assert.equal(l.length,1);assert.equal(l[0].subject,'first');
 assert.match((await gv.show(dir,l[0].sha)).text,/a\.txt/);
 w('a.txt','2');assert.match((await gv.diff(dir,{file:'a.txt'})).text,/\+2/);
});
test('commit blocks secrets and empty stage',async()=>{
 await assert.rejects(()=>gv.commit(dir,{message:'x'}),/Nothing staged/);
 w('.env','A=1');await gv.stage(dir,['.env']);
 await assert.rejects(()=>gv.commit(dir,{message:'x'}),/Sensitive/);
 await gv.unstage(dir,['.env']);
 w('k.txt','ghp_'+'a'.repeat(36));await gv.stage(dir,['k.txt']);
 await assert.rejects(()=>gv.commit(dir,{message:'x'}),/token/);
});
test('rejects bad paths',async()=>{
 await assert.rejects(()=>gv.stage(dir,['../x']),/Invalid path/);
 await assert.rejects(()=>gv.stage(dir,['-A']),/Invalid path/);
 await assert.rejects(()=>gv.show(dir,'--output=x'),/Invalid commit/);
});
