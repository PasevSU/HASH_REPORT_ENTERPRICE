'use strict';
// Sensitive-file detection shared by publish and commit. Public certificates (.pem/.crt/.cer
// without a private key) are allowed; everything else on the list is blocked by name.
const fsp=require('node:fs').promises,path=require('node:path');
const SENSITIVE=/(^|[\\/])(\.env(\..*)?|id_(rsa|ed25519|ecdsa|dsa)|secrets\.ya?ml|.*\.(pem|key|pfx|p12|kdbx))$/i;
const CERT_LIKE=/\.(pem|crt|cer)$/i;
const SECRET_BODY=/PRIVATE KEY|ENCRYPTED/;
const SKIP_DIRS=new Set(['.git','node_modules']);

// read(name) -> string content; unreadable files are treated as sensitive.
async function filterSensitive(names,read,isDeleted){
 const bad=[];
 for(const n of names){
  if(!SENSITIVE.test(n))continue;
  if(isDeleted&&isDeleted(n))continue;
  if(CERT_LIKE.test(n)){
   const body=await Promise.resolve().then(()=>read(n)).then(x=>String(x).slice(0,200000),()=>'PRIVATE KEY');
   if(!SECRET_BODY.test(body))continue;
  }
  bad.push(n);
 }
 return bad;
}

// Recursive listing for folders that are not yet repositories (relative paths, '/' separated).
async function walk(dir,limit=20000){
 const out=[];
 async function rec(abs,rel){
  if(out.length>=limit)return;
  for(const e of await fsp.readdir(abs,{withFileTypes:true})){
   if(SKIP_DIRS.has(e.name))continue;
   const r=rel?rel+'/'+e.name:e.name;
   if(e.isDirectory())await rec(path.join(abs,e.name),r);else out.push(r);
   if(out.length>=limit)return;
  }
 }
 await rec(dir,'');
 return out;
}
module.exports={SENSITIVE,filterSensitive,walk};
