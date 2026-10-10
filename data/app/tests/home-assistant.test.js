'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const ha=require('../gui/home-assistant');
function tmp(){return fs.mkdtempSync(path.join(os.tmpdir(),'gitsu-ha-'))}
test('scaffold plan is nonmutating',()=>{const root=tmp();try{const p=ha.scaffoldPlan(root,'demo_integration');assert.equal(p.collisions.length,0);assert.equal(fs.readdirSync(root).length,0)}finally{fs.rmSync(root,{recursive:true,force:true})}});
test('scaffold creates and validates minimum structure',()=>{const root=tmp();try{const r=ha.scaffoldApply(root,'demo_integration');assert.ok(r.created.length);assert.equal(r.validation.valid,true);assert.equal(r.validation.type,'integration')}finally{fs.rmSync(root,{recursive:true,force:true})}});
test('never overwrites existing scaffold',()=>{const root=tmp();try{ha.scaffoldApply(root,'demo');assert.throws(()=>ha.scaffoldApply(root,'demo'),/Existing files/)}finally{fs.rmSync(root,{recursive:true,force:true})}});
test('rejects invalid domain',()=>{assert.throws(()=>ha.scaffoldPlan(tmp(),'../escape'),/Domain/)});
test('detects broken manifest',()=>{const root=tmp();try{ha.scaffoldApply(root,'demo');fs.writeFileSync(path.join(root,'custom_components/demo/manifest.json'),'{');const r=ha.validate(root);assert.equal(r.valid,false);assert.ok(r.issues.some(x=>String(x.reason).includes('Invalid JSON')))}finally{fs.rmSync(root,{recursive:true,force:true})}});
test('requires frontend JS',()=>{const root=tmp();try{fs.mkdirSync(path.join(root,'www'));assert.equal(ha.validate(root,'plugin').valid,false);fs.writeFileSync(path.join(root,'www','card.js'),'class Card {}');assert.equal(ha.validate(root,'plugin').valid,true)}finally{fs.rmSync(root,{recursive:true,force:true})}});
