'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {planCopy,applyCopy}=require('../gui/core');
test('local folder update copies changed files and preserves unrelated destination files and .git',async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-local-'));const src=path.join(tmp,'src'),dst=path.join(tmp,'dst');
 try{fs.mkdirSync(src);fs.mkdirSync(dst);fs.mkdirSync(path.join(src,'.git'));fs.writeFileSync(path.join(src,'.git','config'),'source git');fs.writeFileSync(path.join(src,'a.txt'),'new');fs.writeFileSync(path.join(dst,'a.txt'),'old');fs.writeFileSync(path.join(dst,'extra.txt'),'keep');
 const p=await planCopy(src,dst);assert.deepEqual(p.changes.filter(x=>x.type==='copy').map(x=>x.path),['a.txt']);assert.equal((await applyCopy(p)).copied,1);assert.equal(fs.readFileSync(path.join(dst,'a.txt'),'utf8'),'new');assert.equal(fs.readFileSync(path.join(dst,'extra.txt'),'utf8'),'keep');assert.equal(fs.existsSync(path.join(dst,'.git')),false);assert.equal((await planCopy(src,dst)).changes.filter(x=>x.type==='copy').length,0);
 }finally{fs.rmSync(tmp,{recursive:true,force:true})}
});
test('local folder update rejects overlapping paths',async()=>{const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-local-'));try{await assert.rejects(()=>planCopy(tmp,path.join(tmp,'child')),/overlap/)}finally{fs.rmSync(tmp,{recursive:true,force:true})}});

test('copy refuses a stale preview without overwriting target',async()=>{const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-stale-'));try{const src=path.join(tmp,'src'),dst=path.join(tmp,'dst');fs.mkdirSync(src);fs.mkdirSync(dst);fs.writeFileSync(path.join(src,'a'),'new');fs.writeFileSync(path.join(dst,'a'),'old');const p=await planCopy(src,dst);fs.writeFileSync(path.join(dst,'a'),'third-party');await assert.rejects(()=>applyCopy(p),/stale/);assert.equal(fs.readFileSync(path.join(dst,'a'),'utf8'),'third-party')}finally{fs.rmSync(tmp,{recursive:true,force:true})}});
test('copy refuses a changed source after preview',async()=>{const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-stale-'));try{const src=path.join(tmp,'src'),dst=path.join(tmp,'dst');fs.mkdirSync(src);fs.mkdirSync(dst);fs.writeFileSync(path.join(src,'a'),'new');const p=await planCopy(src,dst);fs.writeFileSync(path.join(src,'a'),'changed');await assert.rejects(()=>applyCopy(p),/stale/);assert.equal(fs.existsSync(path.join(dst,'a')),false)}finally{fs.rmSync(tmp,{recursive:true,force:true})}});
