const test=require('node:test'),assert=require('node:assert');
const {filterSensitive}=require('../gui/sensitive.js');
test('public cert allowed, private key and .env blocked',async()=>{
 const files={'a/cert.pem':'-----BEGIN CERTIFICATE-----','b/k.pem':'-----BEGIN PRIVATE KEY-----','.env':'x','n/.env.local':'x','ok.txt':'x'};
 const bad=await filterSensitive(Object.keys(files),n=>files[n]);
 assert.deepEqual(bad.sort(),['.env','b/k.pem','n/.env.local']);
});
test('unreadable cert is sensitive',async()=>{
 assert.deepEqual(await filterSensitive(['c.pem'],()=>{throw new Error('x')}),['c.pem']);
});