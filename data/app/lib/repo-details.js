'use strict';
// repo-details — read and edit GitHub repository metadata (description, homepage, topics,
// visibility, default branch) through the official `gh` CLI. Commands run from the repository
// directory so `gh` infers the repo from the origin remote; no credentials are collected here.
const path = require('node:path');
const { spawn } = require('node:child_process');

const DEFAULT_TIMEOUT = 60000;

function gh(args, { timeout = DEFAULT_TIMEOUT, cwd } = {}) {
  return new Promise((resolve) => {
    let out = '';
    let err = '';
    let done = false;
    const child = spawn('gh', args, {
      cwd,
      shell: false,
      windowsHide: true,
      env: { ...process.env, GH_PROMPT_DISABLED: '1', GIT_TERMINAL_PROMPT: '0' }
    });
    const finish = (r) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve({ ok: r.code === 0, code: r.code, stdout: out, stderr: err, timedOut: !!r.timedOut });
    };
    const timer = setTimeout(() => {
      try { child.kill(); } catch {}
      finish({ code: null, timedOut: true });
    }, timeout);
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('error', (e) => { err += (err ? '\n' : '') + e.message; finish({ code: null }); });
    child.on('close', (code) => finish({ code }));
    child.stdin.end();
  });
}

async function ghMust(args, opts) {
  const r = await gh(args, opts);
  if (!r.ok) throw new Error((r.stderr || r.stdout || 'gh failed').trim());
  return r.stdout;
}

// Read repository metadata. Returns null when the folder is not a GitHub repository.
async function get(dir) {
  const r = await gh(
    ['repo', 'view', '--json', 'nameWithOwner,name,description,homepageUrl,isPrivate,defaultBranchRef,repositoryTopics,url,sshUrl'],
    { cwd: path.resolve(dir) }
  );
  if (!r.ok) {
    const msg = (r.stderr || r.stdout || '').trim();
    if (/not a git repository|could not resolve|no repository|does not exist/i.test(msg)) return null;
    throw new Error(msg || 'gh repo view failed');
  }
  let x;
  try { x = JSON.parse(r.stdout); } catch { return null; }
  const defaultBranch = x.defaultBranchRef && x.defaultBranchRef.name ? x.defaultBranchRef.name : '';
  return {
    fullName: x.nameWithOwner || '',
    name: x.name || '',
    description: x.description || '',
    homepage: x.homepageUrl || '',
    topics: Array.isArray(x.repositoryTopics) ? x.repositoryTopics.map((t) => t.name) : [],
    isPrivate: !!x.isPrivate,
    defaultBranch,
    url: x.url || '',
    sshUrl: x.sshUrl || ''
  };
}

// Edit repository metadata. Only supplied fields are changed.
async function edit(dir, opts = {}) {
  const args = ['repo', 'edit'];
  const s = (v) => String(v ?? '').trim();
  if (s(opts.description) !== '' && opts.description !== undefined) args.push('--description', s(opts.description));
  if (opts.homepage !== undefined) args.push('--homepage', s(opts.homepage));
  const topics = Array.isArray(opts.topics) ? opts.topics.map(s).filter(Boolean) : [];
  if (topics.length) args.push('--add-topic', topics.join(','));
  if (opts.removeTopics && Array.isArray(opts.removeTopics) && opts.removeTopics.length) {
    args.push('--remove-topic', opts.removeTopics.map(s).filter(Boolean).join(','));
  }
  if (opts.visibility === 'public' || opts.visibility === 'private' || opts.visibility === 'internal') {
    args.push('--visibility', opts.visibility);
  }
  if (s(opts.defaultBranch)) args.push('--default-branch', s(opts.defaultBranch));
  if (args.length === 2) throw new Error('Nothing to update — provide at least one field.');
  await ghMust(args, { cwd: path.resolve(dir), timeout: 120000 });
  return { ok: true };
}

module.exports = { get, edit };
