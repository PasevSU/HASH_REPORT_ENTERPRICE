'use strict';
const path=require('node:path');
class OperationManager {
 constructor({journal,execute,onChange=()=>{},telemetry=null,lock=null}){if(!journal||typeof execute!=='function')throw Error('journal and execute required');this.journal=journal;this.execute=execute;this.onChange=onChange;this.telemetry=telemetry;this.lock=lock;this.active=new Set();}
 async run({dir,action,args=[],apply=false}){
  if(!path.isAbsolute(dir)||!['push','update'].includes(action)||!Array.isArray(args)||args.some(a=>typeof a!=='string'))throw Error('Invalid operation');
  const key=path.resolve(dir);if(this.active.has(key))throw Error('Operation already running for repository');
  this.active.add(key);let id;
  try{
   id=this.journal.create({dir:key,kind:action,args:[action,...args],apply});this.onChange(this.journal.list());
   this.journal.set(id,'running');this.onChange(this.journal.list());
   const exec=()=>this.execute({dir:key,action,args,apply});const perform=this.lock?()=>this.lock(key,exec):exec;const result=this.telemetry?await this.telemetry.measure(`git:${action}`,perform):await perform();
   if(!result||result.ok!==true){this.journal.set(id,'failed',result?.message||`Exit code ${result?.code??'unknown'}`);}else this.journal.set(id,'completed');
   this.onChange(this.journal.list());return {...result,jobId:id};
  }catch(error){if(id){this.journal.set(id,'failed',error.message);this.onChange(this.journal.list());}throw error;}
  finally{this.active.delete(key);}
 }
 list(){return this.journal.list();}
 clear(){this.journal.clear();this.onChange(this.journal.list());return this.journal.list()}
}
module.exports={OperationManager};

