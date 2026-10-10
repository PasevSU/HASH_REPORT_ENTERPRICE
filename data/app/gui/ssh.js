'use strict';
// SSH key management for GitHub: list, generate (ed25519), publish via gh, test, switch a repo's origin to SSH.
const {execFile}=require('node:child_process');
const fs=require('node:fs'),fsp=fs.promises,os=require('node:os'),path=require('node:path');

const sshDir=()=>path.join(os.homedir(),'.ssh');
const run=(cmd,args,opt={})=>new Promise(res=>execFile(cmd,args,{windowsHide:true,timeout:opt.timeout||20000,cwd:opt.cwd},(err,stdout,stderr)=>res({ok:!err,code:err?.code,stdout:String(stdout||''),stderr:String(stderr||'')})));
const NAME=/^[A-Za-z0-9._-]{1,64}$/;

async function list(){
 const dir=sshDir(),out=[];
 let names=[];try{names=await fsp.readdir(dir)}catch{}
 for(const n of names.filter(x=>x.endsWith('.pub'))){
  const file=path.join(dir,n),fp=await run('ssh-keygen',['-lf',file]);
  const text=(await fsp.readFile(file,'utf8')).trim();
  out.push({name:n.slice(0,-4),file,publicKey:text,fingerprint:fp.ok?fp.stdout.trim():'',hasPrivate:fs.existsSync(file.slice(0,-4))});
 }
 return out;
}

async function status(){
 const v=await run('ssh-keygen',['-?']);
 const available=v.ok||/usage/i.test(v.stderr);
 return {available,dir:sshDir(),keys:available?await list():[]};
}

async function generate({name='id_ed25519',email='',passphrase=''}={}){
 if(!NAME.test(name))throw Error('Невалидно име на ключ.');
 const dir=sshDir();await fsp.mkdir(dir,{recursive:true});
 const file=path.join(dir,name);
 if(fs.existsSync(file)||fs.existsSync(file+'.pub'))throw Error(`Ключ „${name}“ вече съществува — не се презаписва. Изберете друго име.`);
 const r=await run('ssh-keygen',['-t','ed25519','-C',email||`gitsu-${os.userInfo().username}@${os.hostname()}`,'-f',file,'-N',passphrase]);
 if(!r.ok)throw Error((r.stderr||r.stdout||'ssh-keygen неуспешен').trim());
 await ensureConfig(file);
 return {name,file,publicKey:(await fsp.readFile(file+'.pub','utf8')).trim()};
}

// Point github.com at the chosen key unless the config already has a github.com host.
async function ensureConfig(keyFile){
 const cfg=path.join(sshDir(),'config');let text='';
 try{text=await fsp.readFile(cfg,'utf8')}catch{}
 if(/^\s*Host\s+.*github\.com/im.test(text))return false;
 const block=`${text&&!text.endsWith('\n')?'\n':''}\nHost github.com\n  HostName github.com\n  User git\n  IdentityFile ${keyFile.replace(/\\/g,'/')}\n  IdentitiesOnly yes\n`;
 await fsp.appendFile(cfg,block);return true;
}

async function addToGitHub({name,title}){
 if(!NAME.test(name||''))throw Error('Невалидно име на ключ.');
 const file=path.join(sshDir(),name+'.pub');if(!fs.existsSync(file))throw Error('Публичният ключ не е намерен.');
 const r=await run('gh',['ssh-key','add',file,'--title',title||`GitSU ${os.hostname()}`],{timeout:30000});
 const msg=(r.stderr+r.stdout).trim();
 if(!r.ok){
  if(/already|in use/i.test(msg))return {ok:true,message:'Ключът вече е добавен в GitHub.'};
  throw Error(/scope|admin:public_key/i.test(msg)?msg+'\nИзпълнете: gh auth refresh -h github.com -s admin:public_key':msg||'gh ssh-key add неуспешно');
 }
 return {ok:true,message:msg||'Ключът е добавен в GitHub.'};
}

async function test(){
 const r=await run('ssh',['-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','git@github.com'],{timeout:25000});
 const text=(r.stderr+r.stdout).trim(),m=/Hi ([^!]+)! You've successfully authenticated/.exec(text);
 return {ok:!!m,user:m?m[1]:null,message:m?`Свързано като ${m[1]}`:text||'Няма връзка'};
}

const toSsh=url=>{const m=/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?\/?$/.exec(url||'');return m?`git@github.com:${m[1]}/${m[2]}.git`:null};
async function useSshForRepo(dir,remote='origin'){
 const g=await run('git',['-C',dir,'remote','get-url',remote]);
 if(!g.ok)throw Error('Няма remote „'+remote+'“.');
 const cur=g.stdout.trim(),next=toSsh(cur);
 if(!next)throw Error(/^git@github\.com:/.test(cur)?'Remote вече използва SSH.':'Remote не е GitHub HTTPS адрес: '+cur);
 const s=await run('git',['-C',dir,'remote','set-url',remote,next]);
 if(!s.ok)throw Error(s.stderr.trim());
 return {from:cur,to:next};
}

const toHttps=url=>{const m=/^git@github\.com:([\w.-]+)\/([\w.-]+?)(?:\.git)?\/?$/.exec(url||'');return m?`https://github.com/${m[1]}/${m[2]}.git`:null};
async function useHttpsForRepo(dir,remote='origin'){
 const g=await run('git',['-C',dir,'remote','get-url',remote]);
 if(!g.ok)throw Error('Няма remote „'+remote+'“.');
 const cur=g.stdout.trim(),next=toHttps(cur);
 if(!next)throw Error(/^https:\/\/github\.com\//.test(cur)?'Remote вече използва HTTPS.':'Remote не е GitHub SSH адрес: '+cur);
 const s=await run('git',['-C',dir,'remote','set-url',remote,next]);
 if(!s.ok)throw Error(s.stderr.trim());
 return {from:cur,to:next};
}

module.exports={status,generate,addToGitHub,test,useSshForRepo,toSsh,useHttpsForRepo,toHttps};
