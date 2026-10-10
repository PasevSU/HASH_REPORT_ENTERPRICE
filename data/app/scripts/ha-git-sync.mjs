#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { platform } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const home = path.dirname(fileURLToPath(import.meta.url));
const win = platform() === 'win32';
const script = path.join(home, win ? 'ha-git-sync.ps1' : 'ha-git-sync.sh');
const args = win ? ['-NoProfile','-NonInteractive','-File',script] : [script];
const env = { ...process.env, REPO_PATH:process.env.REPO_PATH || process.cwd(), BRANCH:process.env.BRANCH || 'main' };
const child = spawn(win ? 'pwsh.exe' : 'bash', args, {stdio:'inherit',env,shell:false});
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>child.kill(signal));
child.on('error', e=>{console.error('Watcher startup failed:',e.message);process.exitCode=1;});
child.on('exit',(code,signal)=>{process.exitCode=code ?? (signal ? 130 : 1);});
