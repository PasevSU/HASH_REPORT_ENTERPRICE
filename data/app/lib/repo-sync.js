'use strict';
// repo-sync — the single communication layer between a local folder and its remote repository.
//
// High-level orchestration over gitops (which stays the low-level Git plumbing). This package is
// the only entry point the UI/IPC needs for folder<->repository communication:
//   status() — local state + remote divergence (ahead/behind)
//   fetch()  — download remote refs without touching the working tree
//   push()   — stage + commit + push (upload), via gitops.push
//   pull()   — fetch + merge (update), via gitops.pull
//   sync()   — bidirectional reconcile: pull if behind, then push if ahead/dirty
const path = require('node:path');
const gitops = require('./gitops');

async function localState(dir) {
  const root = path.resolve(dir);
  const branch = await gitops.currentBranch(root);
  const dirty = (await gitops.runGit(root, ['status', '--porcelain', '--untracked-files=all'])).stdout.trim() !== '';
  const remote = await gitops.resolveRemote(root);
  const upstream = await gitops.hasUpstream(root, branch);
  const headOk = (await gitops.runGit(root, ['rev-parse', '--verify', 'HEAD'])).ok;
  const sha = headOk ? (await gitops.runGit(root, ['rev-parse', 'HEAD'])).stdout.trim() : null;
  return {
    dir: root,
    branch,
    dirty,
    remote: remote ? remote.name : null,
    remoteUrl: remote ? remote.url : null,
    upstream,
    sha
  };
}

async function divergence(dir) {
  const r = await gitops.runGit(dir, ['rev-list', '--left-right', '--count', 'HEAD...@{upstream}']);
  const m = /^\s*(\d+)\s+(\d+)\s*$/.exec(r.stdout || '');
  return { ahead: m ? Number(m[1]) : null, behind: m ? Number(m[2]) : null, upstreamKnown: !!m };
}

async function status(dir, options = {}) {
  const s = await localState(dir);
  // Behind/ahead must be measured against a current remote-tracking ref, otherwise "behind"
  // is always 0 on a stale clone. Fetching is opt-in so a plain status stays a fast read.
  if (options.fetch && s.remote) {
    await fetch(s.dir);
  }
  const d = (s.upstream && s.remote)
    ? await divergence(s.dir).catch(() => ({ ahead: null, behind: null, upstreamKnown: false }))
    : { ahead: null, behind: null, upstreamKnown: false };
  return { ...s, ahead: d.ahead, behind: d.behind, upstreamKnown: d.upstreamKnown };
}

async function fetch(dir) {
  const s = await localState(dir);
  if (!s.remote) throw new Error('No remote configured; cannot fetch.');
  const r = await gitops.runGit(s.dir, ['fetch', '--prune', s.remote], { timeout: 300000 });
  if (!r.ok) throw new Error(r.stderr || r.stdout || 'git fetch failed');
  return { ok: true, dir: s.dir, remote: s.remote };
}

async function push(dir, options = {}) {
  return gitops.push(dir, options);
}

async function pull(dir, options = {}) {
  return gitops.pull(dir, options);
}

async function sync(dir, options = {}) {
  const apply = !!options.apply;
  const s = await status(dir, { fetch: true });
  const plan = {
    ok: true,
    dir: s.dir,
    branch: s.branch,
    dirty: s.dirty,
    ahead: s.ahead,
    behind: s.behind,
    remote: s.remote,
    pulled: false,
    pushed: false
  };
  if (!apply) return plan;

  // Behind first: update local with remote (requires a clean tree).
  if (s.behind > 0) {
    if (s.dirty) {
      throw new Error('Cannot sync: working tree has uncommitted changes while remote is ahead. Commit or stash first.');
    }
    await gitops.pull(s.dir, { apply: true });
    plan.pulled = true;
  }

  // Ahead or local changes: upload (stages+commits when a message is provided).
  const after = await status(s.dir);
  if (after.ahead > 0 || after.dirty) {
    if (after.dirty && (!options.message || !String(options.message).trim())) {
      throw new Error('A commit message is required to commit local changes during sync.');
    }
    await gitops.push(s.dir, { apply: true, message: options.message });
    plan.pushed = true;
  }

  const final = await status(s.dir);
  return { ...plan, ahead: final.ahead, behind: final.behind, dirty: final.dirty, sha: final.sha };
}

module.exports = { status, fetch, push, pull, sync, localState };
