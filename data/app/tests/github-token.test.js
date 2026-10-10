'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {GitHubBrowserAuth}=require('../gui/github-auth');
const token='github_pat_TESTTOKEN123456789012345678901';
function fakeSpawn(command,args,options){const c=new EventEmitter();c.stdout=new EventEmitter();c.stderr=new EventEmitter();let data='';c.stdin={on:()=>{},end:x=>{data=x;process.nextTick(()=>c.emit('close',0))}};c.kill=()=>c.emit('close',1);c.record=()=>({command,args,options,data});fakeSpawn.child=c;return c;}
test('PAT login passes secret via stdin only',async()=>{const events=[];const auth=new GitHubBrowserAuth({spawnImpl:fakeSpawn,emit:x=>events.push(x)});const result=await auth.loginWithToken(token);assert.equal(result.ok,true);const c=fakeSpawn.child.record();assert.equal(c.command,'gh');assert.ok(c.args.includes('--with-token'));assert.equal(c.args.join(' ').includes(token),false);assert.equal(c.data,token+'\n');assert.equal(JSON.stringify(events).includes(token),false)});
test('PAT rejects empty and newline input',async()=>{const auth=new GitHubBrowserAuth({spawnImpl:fakeSpawn});assert.equal((await auth.loginWithToken('')).ok,false);assert.equal((await auth.loginWithToken(token+'\nEXTRA')).ok,false)});
test('PAT login blocks parallel attempts',async()=>{let child;const spawnImpl=()=>{child=new EventEmitter();child.stdin={on:()=>{},end:()=>{}};child.kill=()=>{};return child};const auth=new GitHubBrowserAuth({spawnImpl});const first=auth.loginWithToken(token);assert.equal((await auth.loginWithToken(token)).ok,false);child.emit('close',0);assert.equal((await first).ok,true)});
