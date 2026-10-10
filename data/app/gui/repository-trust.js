'use strict';
const path=require('node:path'),fs=require('node:fs'),{spawnSync}=require('node:child_process');
function run(args,cwd){const r=require('./git-trust').gitSync(args,{cwd,encoding:'utf8',windowsHide:true,shell:false,timeout:20000});return {ok:!r.error&&r.status===0,stdout:(r.stdout||'').trim(),stderr:(r.stderr||r.error?.message||'').trim()};}
function probe(dir){const full=path.resolve(dir);if(!fs.existsSync(full)||!fs.statSync(full).isDirectory())throw Error('Directory not found');const r=run(['status','--short'],full);const dubious=/detected dubious ownership/i.test(r.stderr);return {directory:full,ok:r.ok,dubious,diagnostic:r.ok?'Repository accessible':r.stderr.slice(0,3000),requiresApproval:dubious};}
function trust(dir){const before=probe(dir);if(before.ok)return {alreadyTrusted:true,verified:true,directory:before.directory};if(!before.dubious)throw Error('Repository is not blocked by dubious ownership: '+before.diagnostic);
 // Git reads safe.directory from protected global configuration, never from repository-local config.
 const add=run(['config','--global','--add','safe.directory',before.directory],before.directory);
 if(!add.ok)throw Error('Failed to update Git global safe.directory: '+add.stderr);
 const after=probe(before.directory);if(!after.ok)throw Error('Git trust saved, but repository is still inaccessible: '+after.diagnostic);
 return {alreadyTrusted:false,verified:true,directory:before.directory};}
module.exports={probe,trust};
