const test=require('node:test'),assert=require('node:assert');
const {ResourceController}=require('../gui/resource-controller.js');
test('urgent run is not blocked while throttled',async()=>{
 const rc=new ResourceController({sample:()=>({free:0.01,cpu:0.99}),intervalMs:10});rc.start();
 await new Promise(r=>setTimeout(r,50));
 assert.equal(rc.last.mode,'throttled');
 assert.equal(await rc.run(async()=>42,{urgent:true}),42);rc.close();
});