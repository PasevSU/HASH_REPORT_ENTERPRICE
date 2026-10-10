'use strict';
const {spawnSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
function probe(command,args=['--version']) {const r=spawnSync(command,args,{encoding:'utf8',shell:false,windowsHide:true,timeout:8000});return {available:!r.error&&r.status===0,detail:(r.stdout||r.stderr||r.error?.message||'').trim().slice(0,400)}}
function health(root){return {node:{available:true,detail:process.version},git:probe('git'),github:probe('gh'),cli:{available:fs.existsSync(path.join(root,'cli.js'))},configuration:{available:fs.existsSync(path.join(root,'configuration.yaml'))},checkedAt:new Date().toISOString()}}
async function healthAsync(root){
  const {run}=require('./repo-create');
  const p=async(c)=>{const r=await run(c,['--version'],{timeout:8000});return {available:r.ok,detail:(r.stdout||r.stderr||'').trim().slice(0,400)}};
  const [git,github]=await Promise.all([p('git'),p('gh')]);
  return {node:{available:true,detail:process.version},git,github,cli:{available:fs.existsSync(path.join(root,'cli.js'))},configuration:{available:fs.existsSync(path.join(root,'configuration.yaml'))},checkedAt:new Date().toISOString()};
}
module.exports={probe,health,healthAsync};
