'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const {probe,trust}=require('../gui/repository-trust');
test('probe recognizes ordinary git repository without changing global config',()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-trust-'));try{const r=spawnSync('git',['init'],{cwd:dir,encoding:'utf8'});assert.equal(r.status,0);const p=probe(dir);assert.equal(p.ok,true);assert.equal(p.dubious,false);assert.equal(p.requiresApproval,false);assert.equal(trust(dir).alreadyTrusted,true);}finally{fs.rmSync(dir,{recursive:true,force:true})}});
test('probe does not trust an invalid directory',()=>{assert.throws(()=>probe(path.join(os.tmpdir(),'gitsu-nonexistent-directory-xyz')))});
