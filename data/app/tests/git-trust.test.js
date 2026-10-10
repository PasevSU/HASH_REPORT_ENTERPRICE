'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {isDubious,safeDirectoryValue,ensureSafe}=require('../gui/git-trust');

const DUBIOUS_ERR="fatal: detected dubious ownership in repository at 'X'\nTo add an exception ... safe.directory";

test('isDubious matches git message only',()=>{
 assert.equal(isDubious(DUBIOUS_ERR),true);
 assert.equal(isDubious('fatal: not a git repository'),false);
});

test('safeDirectoryValue uses git spelling for UNC and plain paths otherwise',()=>{
 assert.equal(safeDirectoryValue('\\\\NAS\\HDD (at HDD)\\PROJECT\\repo\\'),'%(prefix)///NAS/HDD (at HDD)/PROJECT/repo');
 assert.equal(safeDirectoryValue('E:\\Downloads\\x'),'E:/Downloads/x');
});

test('ensureSafe adds exactly one exact path, never a wildcard, and verifies',()=>{
 const calls=[];let fixed=false;
 const spawn=(cmd,args)=>{
  calls.push(args.join(' '));
  if(args[0]==='rev-parse')return fixed?{status:0,stdout:'.git'}:{status:128,stderr:DUBIOUS_ERR};
  if(args.includes('--get-all'))return {status:0,stdout:''};
  if(args.includes('--add')){fixed=true;return {status:0}}
  return {status:1};
 };
 const r=ensureSafe('\\\\NAS\\share\\repo',{spawn});
 assert.equal(r.ok,true);assert.equal(r.added,true);
 const add=calls.find(c=>c.includes('--add'));
 assert.match(add,/safe\.directory %\(prefix\)\/\/\/NAS\/share\/repo$/);
 assert.ok(!calls.some(c=>/safe\.directory \*/.test(c)));
});

test('ensureSafe does nothing for healthy repo and for non-ownership errors',()=>{
 assert.deepEqual(ensureSafe('C:\\r',{spawn:()=>({status:0,stdout:'.git'})}),{ok:true,added:false});
 const r=ensureSafe('C:\\r',{spawn:()=>({status:128,stderr:'fatal: not a git repository'})});
 assert.equal(r.ok,false);assert.equal(r.reason,'not-dubious');
});

test('ensureSafe does not add a duplicate for an existing bare-UNC entry',()=>{
 const calls=[];let probes=0;
 const spawn=(cmd,args)=>{
  calls.push(args.join(' '));
  if(args[0]==='rev-parse'){probes++;return probes===1?{status:128,stderr:DUBIOUS_ERR}:{status:0,stdout:'.git'};}
  if(args.includes('--get-all'))return {status:0,stdout:'//NAS/share/repo\n'};
  if(args.includes('--add'))return {status:0};
  return {status:1};
 };
 const r=ensureSafe('\\\\NAS\\share\\repo',{spawn});
 assert.equal(r.ok,true);
 assert.ok(!calls.some(c=>c.includes('--add')));
});
