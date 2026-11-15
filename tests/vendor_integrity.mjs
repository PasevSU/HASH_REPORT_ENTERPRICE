import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const vendorRoot=new URL('../vendor/pdf-rfc3161/',import.meta.url);
const nodeRoot=new URL('../node_modules/pdf-rfc3161/',import.meta.url);
const manifestName='CHRONOSEAL_PATCH_MANIFEST.json';
const manifest=JSON.parse(fs.readFileSync(new URL(manifestName,vendorRoot)));
const walk=(dir,base=dir)=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>{const p=path.join(dir,e.name);return e.isDirectory()?walk(p,base):[path.relative(base,p).split(path.sep).join('/')]});
const actual=walk(fileURLToPath(vendorRoot)).filter(f=>f!==manifestName).sort();
assert.deepEqual(Object.keys(manifest.files_sha256).sort(),actual,'manifest must inventory every vendored file');
for (const [name,sha] of Object.entries(manifest.files_sha256)){
 const vendor=fs.readFileSync(new URL(name,vendorRoot));
 const installed=fs.readFileSync(new URL(name,nodeRoot));
 const digest=crypto.createHash('sha256').update(vendor).digest('hex');
 assert.equal(digest,sha,'vendored package mismatch '+name);
 assert.deepEqual(installed,vendor,'installed package mismatch '+name);
 if(name==='dist/index.js'||name==='dist/index.cjs')assert.equal((vendor.toString().match(/return void 0;\n      }/g)||[]).length >= 2,true);
 console.log('PASS '+name+' '+digest);
}
const pkg=JSON.parse(fs.readFileSync(new URL('../package.json',import.meta.url)));
assert.equal(pkg.dependencies['pdf-rfc3161'],'file:vendor/pdf-rfc3161');
console.log('PASS local dependency pin');
