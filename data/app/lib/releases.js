'use strict';
// releases — GitHub Release + git tag management for a repository folder.
//
// Uses the official `gh` CLI for GitHub Releases (never collects credentials in GitSU) and
// `git tag` via gitops.runGit for local/remote tag introspection. Release commands run from the
// repository directory so `gh` infers the repo from the origin remote.
const path = require('node:path');
const { spawn } = require('node:child_process');
const gitops = require('./gitops');

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

async function list(dir, { limit = 100 } = {}) {
  const r = await gh(
    ['release', 'list', '--limit', String(limit), '--json', 'tagName,name,publishedAt,isDraft,isPrerelease'],
    { cwd: path.resolve(dir) }
  );
  if (!r.ok) throw new Error((r.stderr || r.stdout || 'gh release list failed').trim());
  let items = [];
  try { items = JSON.parse(r.stdout); } catch { items = []; }
  return items.map((x) => ({
    tag: x.tagName,
    title: x.name || x.tagName,
    publishedAt: x.publishedAt,
    draft: !!x.isDraft,
    prerelease: !!x.isPrerelease,
    url: null
  }));
}

async function latest(dir) {
  const r = await gh(['release', 'view', '--json', 'tagName,name,publishedAt,isDraft,isPrerelease,url,body'], { cwd: path.resolve(dir) });
  if (!r.ok) return null; // no releases yet
  let x;
  try { x = JSON.parse(r.stdout); } catch { return null; }
  return {
    tag: x.tagName,
    title: x.name || x.tagName,
    publishedAt: x.publishedAt,
    draft: !!x.isDraft,
    prerelease: !!x.isPrerelease,
    url: x.url,
    body: x.body || ''
  };
}

async function create(dir, { tag, title, notes, target, prerelease = false, draft = false } = {}) {
  const root = path.resolve(dir);
  const t = String(tag || '').trim();
  if (!t) throw new Error('A tag is required to create a release.');
  const args = ['release', 'create', t];
  if (String(title || '').trim()) args.push('--title', String(title).trim());
  if (String(notes || '').trim()) args.push('--notes', String(notes).trim());
  if (String(target || '').trim()) args.push('--target', String(target).trim());
  if (prerelease) args.push('--prerelease');
  if (draft) args.push('--draft');
  const out = await ghMust(args, { cwd: root, timeout: 120000 });
  return { ok: true, tag: t, url: (out || '').trim() || null };
}

async function remove(dir, tag) {
  const t = String(tag || '').trim();
  if (!t) throw new Error('A tag is required to delete a release.');
  await ghMust(['release', 'delete', t, '--yes'], { cwd: path.resolve(dir) });
  return { ok: true, tag: t };
}

async function tags(dir) {
  const root = path.resolve(dir);
  const local = (await gitops.runGit(root, ['tag', '--list'])).stdout.split(/\r?\n/).filter(Boolean);
  let remoteTags = [];
  const remote = await gitops.resolveRemote(root);
  if (remote) {
    const r = await gitops.runGit(root, ['ls-remote', '--tags', '--refs', remote.name], { timeout: 60000 });
    remoteTags = (r.stdout || '').split(/\r?\n/).map((l) => l.replace(/^.*refs\/tags\//, '')).filter(Boolean);
  }
  return { local, remote: remoteTags };
}

module.exports = { list, latest, create, remove, tags };
