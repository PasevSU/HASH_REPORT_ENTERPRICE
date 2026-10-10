'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const {diagnose}=require('../gui/repository-diagnostics');
test('nonexistent repository returns blocked without throwing',()=>{
 const result=diagnose(path.join(os.tmpdir(),'gitsu-not-existent-1234567890'));
 assert.equal(result.ready,false);
 assert.equal(result.checks[0].status,'BLOCKED');
});
test('git repository preflight distinguishes missing origin and gh authentication',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-diagnose-'));
 try{
  const init=spawnSync('git',['init',dir],{encoding:'utf8'});
  assert.equal(init.status,0,init.stderr);
  const result=diagnose(dir,{run:(bin,args,cwd)=>{
   if(bin==='gh')return {ok:false,error:'not signed in'};
   const r=spawnSync(bin,args,{cwd,encoding:'utf8'});
   return {ok:r.status===0,output:(r.stdout||'').trim(),error:(r.stderr||'').trim()};
  }});
  assert.equal(result.ready,true);
  assert.equal(result.checks.find(c=>c.id==='origin').status,'BLOCKED');
  assert.equal(result.checks.find(c=>c.id==='githubAuth').status,'BLOCKED');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
