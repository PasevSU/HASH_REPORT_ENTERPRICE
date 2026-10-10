'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const c=require('../gui/connect');
const g=(cwd,...a)=>{const r=spawnSync('git',a,{cwd,encoding:'utf8'});if(r.status)throw Error(r.stderr);return r.stdout.trim()};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gsconn-'));
const bare=path.join(tmp,'r.git');
test.before(()=>{g(tmp,'init','-q','--bare','-b','main','r.git');const s=path.join(tmp,'seed');fs.mkdirSync(s);g(s,'init','-q','-b','main');g(s,'config','user.name','t');g(s,'config','user.email','t@t');fs.writeFileSync(path.join(s,'a.txt'),'1');g(s,'add','.');g(s,'commit','-qm','i');g(s,'push','-q',bare,'HEAD:main')});
test.after(()=>fs.rmSync(tmp,{recursive:true,force:true}));
test('normalizeRepo',()=>{assert.equal(c.normalizeRepo('a/b'),'https://github.com/a/b.git');assert.equal(c.normalizeRepo(''),'');assert.throws(()=>c.normalizeRepo('ftp://x/y'))});
test('inspect suggests actions',async()=>{
 const e=path.join(tmp,'empty');fs.mkdirSync(e);
 assert.equal((await c.inspectFolder(e,bare)).defaultAction,'clone');
 assert.equal((await c.inspectFolder(e,'')).defaultAction,'create');
 assert.equal((await c.inspectFolder(path.join(tmp,'missing'),'')).exists,false);
});
test('clone into empty folder',async()=>{
 const d=path.join(tmp,'cl');const r=await c.apply({dir:d,repo:bare,mode:'clone'});
 assert.equal(r.dir,d);assert.ok(fs.existsSync(path.join(d,'a.txt')));
});
test('link non-git folder keeps files and aligns to remote',async()=>{
 const d=path.join(tmp,'ln');fs.mkdirSync(d);fs.writeFileSync(path.join(d,'mine.txt'),'x');
 await c.apply({dir:d,repo:bare,mode:'link'});
 assert.equal(g(d,'remote','get-url','origin'),bare);
 assert.ok(fs.existsSync(path.join(d,'mine.txt')));
 assert.equal(g(d,'rev-parse','HEAD'),g(tmp,'--git-dir='+bare,'rev-parse','main'));
 assert.match(g(d,'status','--porcelain'),/mine\.txt/);
});
test('link refuses unrelated histories and rolls back',async()=>{
 const d=path.join(tmp,'un');fs.mkdirSync(d);g(d,'init','-q','-b','main');g(d,'config','user.name','t');g(d,'config','user.email','t@t');fs.writeFileSync(path.join(d,'z'),'z');g(d,'add','.');g(d,'commit','-qm','z');
 await assert.rejects(()=>c.apply({dir:d,repo:bare,mode:'link'}),/unrelated/);
 assert.throws(()=>g(d,'remote','get-url','origin'));
});
test('local mode creates repo',async()=>{
 const d=path.join(tmp,'loc');await c.apply({dir:d,mode:'local'},{ensureRules:async()=>[]});
 assert.equal(g(d,'rev-parse','--is-inside-work-tree'),'true');
});
test('wrong action rejected',async()=>{await assert.rejects(()=>c.plan({dir:path.join(tmp,'cl'),mode:'clone',repo:bare}),/not possible/)});

