'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),child=require('node:child_process');
test('inspect refuses dubious Git ownership rather than silently treating repo as non-repository',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-ownership-'));
 const original=child.spawnSync;
 try{
  child.spawnSync=(bin,args)=>({status:128,stdout:'',stderr:"fatal: detected dubious ownership in repository at '/test'"});
  const filename=require.resolve('../gui/core');delete require.cache[filename];
  const {inspect}=require('../gui/core');
  assert.throws(()=>inspect(dir),e=>e.code==='GIT_DUBIOUS_OWNERSHIP'&&/Git trust/.test(e.message));
  delete require.cache[filename];
 }finally{child.spawnSync=original;fs.rmSync(dir,{recursive:true,force:true});}
});
