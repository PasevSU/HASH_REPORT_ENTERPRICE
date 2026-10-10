'use strict';
const fs=require('node:fs'),path=require('node:path');
const WORKFLOW='.github/workflows/gitsu-validation.yml';
const WORKFLOW_TEXT=`name: GitSU Validation
on:
  push:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate repository
        shell: bash
        run: |
          git status --porcelain
          git fsck --no-reflogs
`;
function noLinks(root,rel){let p=root;for(const part of rel.split('/')){p=path.join(p,part);try{if(fs.lstatSync(p).isSymbolicLink())throw Error('Symbolic link blocked: '+p)}catch(e){if(e.code!=='ENOENT')throw e}}}
function planWorkflow(dir){const root=path.resolve(dir);if(!fs.statSync(root).isDirectory())throw Error('Not a directory');noLinks(root,WORKFLOW);const file=path.join(root,WORKFLOW);const exists=fs.existsSync(file);return {dir:root,path:WORKFLOW,exists,willCreate:!exists,content:WORKFLOW_TEXT};}
function applyWorkflow(dir){const p=planWorkflow(dir);if(!p.willCreate)return {created:false,path:p.path};const file=path.join(p.dir,p.path);fs.mkdirSync(path.dirname(file),{recursive:true});noLinks(p.dir,p.path);try{fs.writeFileSync(file,WORKFLOW_TEXT,{flag:'wx'});return {created:true,path:p.path}}catch(e){if(e.code==='EEXIST')return {created:false,path:p.path};throw e}}
function exportRepositoryIndex(dirs,output){if(!Array.isArray(dirs)||!dirs.every(x=>typeof x==='string'))throw Error('Invalid repository list');const out=path.resolve(output);if(path.basename(out).toLowerCase()!=='repositories.json')throw Error('Output must be repositories.json');const parent=path.dirname(out);if(!fs.statSync(parent).isDirectory())throw Error('Output directory missing');if(fs.existsSync(out))throw Error('repositories.json exists; refusing overwrite');const items=dirs.map(dir=>({path:path.resolve(dir),name:path.basename(dir)}));const payload={schemaVersion:1,generatedAt:new Date().toISOString(),repositories:items};fs.writeFileSync(out,JSON.stringify(payload,null,2)+'\n',{flag:'wx'});return {file:out,count:items.length};}
module.exports={WORKFLOW,WORKFLOW_TEXT,planWorkflow,applyWorkflow,exportRepositoryIndex};
