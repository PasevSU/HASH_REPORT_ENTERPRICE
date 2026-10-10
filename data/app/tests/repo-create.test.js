'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const rc=require('../gui/repo-create');
const sh=(cwd,...a)=>{const r=spawnSync('git',a,{cwd,encoding:'utf8'});assert.equal(r.status,0,r.stderr);return r.stdout.trim()};
const tmp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-rc-'));

test('name and source validation',()=>{
 assert.throws(()=>rc.validName('../x'),/Invalid/);
 assert.throws(()=>rc.validName('-rf'),/Invalid/);
 assert.throws(()=>rc.validName('a b'),/Invalid/);
 assert.equal(rc.validName('ok-name_1.x'),'ok-name_1.x');
 assert.throws(()=>rc.validSource('ext::sh -c evil'),/GitHub URL/);
 assert.throws(()=>rc.validSource('relative/path'),/GitHub URL/);
 assert.equal(rc.validSource('https://github.com/o/r.git'),'https://github.com/o/r.git');
 assert.equal(rc.validSource('git@github.com:o/r.git'),'git@github.com:o/r.git');
});

test('clone from a local bare repository and refuse non-empty destination',async()=>{
 const root=tmp(),bare=path.join(root,'remote.git'),seed=path.join(root,'seed');
 sh(root,'init','-q','--bare','-b','main',bare);
 sh(root,'clone','-q',bare,seed);fs.writeFileSync(path.join(seed,'a.txt'),'x');
 sh(seed,'-c','user.name=t','-c','user.email=t@t','commit','-q','--allow-empty','-m','i');
 sh(seed,'add','.');sh(seed,'-c','user.name=t','-c','user.email=t@t','commit','-q','-m','f');sh(seed,'push','-q','origin','HEAD:main');
 const dest=path.join(root,'clone');
 const plan=await rc.planClone({url:bare,dest});assert.equal(plan.defaultBranch,'main');
 const r=await rc.applyClone({url:bare,dest});
 assert.equal(r.branch,'main');assert.ok(fs.existsSync(path.join(dest,'a.txt')));
 await assert.rejects(rc.planClone({url:bare,dest}),/not empty/);
 await assert.rejects(rc.planClone({url:path.join(root,'missing.git'),dest:path.join(root,'c2')}),/not reachable/);
});

test('create new local repository',async()=>{
 const root=tmp();
 const r=await rc.applyNewLocal({parent:root,name:'proj'},async d=>{fs.writeFileSync(path.join(d,'.gitignore'),'');return ['.gitignore']});
 assert.equal(sh(r.dir,'branch','--show-current'),'main');
 assert.ok(fs.existsSync(path.join(r.dir,'.git')));
 await assert.rejects(rc.planNewLocal({parent:root,name:'proj'}),/not empty/);
 await assert.rejects(rc.planNewLocal({parent:root,name:'..'}),/Invalid/);
});
