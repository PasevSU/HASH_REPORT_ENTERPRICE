'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
class JobJournal {
 constructor(file){this.file=path.resolve(file);this.records=new Map();this.load();}
 load(){try{const raw=JSON.parse(fs.readFileSync(this.file,'utf8'));if(!Array.isArray(raw.jobs))throw Error('Invalid journal');for(const j of raw.jobs){if(!j||typeof j.id!=='string'||typeof j.status!=='string')continue;this.records.set(j.id,j)}for(const j of this.records.values()){if(['queued','running'].includes(j.status)){j.status='interrupted';j.updatedAt=new Date().toISOString();j.reason='Application restarted; operation not replayed automatically';}}if(this.records.size>200){this.records=new Map([...this.records.values()].sort((a,b)=>(b.createdAt||'').localeCompare(a.createdAt||'')).slice(0,200).map(j=>[j.id,j]))}this.flush()}catch(e){if(e.code==='ENOENT')return;throw e}}
 flush(){fs.mkdirSync(path.dirname(this.file),{recursive:true});const tmp=this.file+'.'+process.pid+'.tmp';fs.writeFileSync(tmp,JSON.stringify({schema:1,jobs:[...this.records.values()]},null,2),{encoding:'utf8',mode:0o600});fs.renameSync(tmp,this.file)}
 create({dir,kind,args,apply=false}){const id=crypto.randomUUID();const now=new Date().toISOString();const item={id,dir,kind,args,apply:Boolean(apply),status:'queued',createdAt:now,updatedAt:now};this.records.set(id,item);this.flush();return id}
 set(id,status,reason){const item=this.records.get(id);if(!item)throw Error('Unknown job');if(!['running','completed','failed','interrupted'].includes(status))throw Error('Invalid status');item.status=status;item.updatedAt=new Date().toISOString();if(reason)item.reason=String(reason).slice(0,2000);this.flush();return item}
 list(){return [...this.records.values()].map(x=>({...x,args:[...x.args]}))}
 clear(){const n=this.records.size;this.records.clear();this.flush();return n}
}
module.exports={JobJournal};
