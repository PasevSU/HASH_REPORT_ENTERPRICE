'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {AutoSyncManager}=require('../gui/auto-sync-manager');
test('watcher rejects relative and unsafe branch paths',()=>{
 const m=new AutoSyncManager();
 assert.throws(()=>m.start({dir:'relative',branch:'main'}),/Absolute/);
 assert.throws(()=>m.start({dir:process.cwd(),branch:'--upload-pack'}),/Invalid branch/);
 assert.throws(()=>m.start({dir:process.cwd(),branch:'../main'}),/Invalid branch/);
 assert.throws(()=>m.start({dir:process.cwd(),branch:'main',poll:0}),/intervals/);
 assert.deepEqual(m.status(),[]);
});
test('stopping inactive watcher does not kill unrelated process',()=>{
 const m=new AutoSyncManager();assert.equal(m.stop(process.cwd()),false);
});
