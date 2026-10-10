'use strict';
// gitops — the single source of truth for Git plumbing.
//
// Promise-based primitives that reuse git-trust for dubious-ownership healing and always set
// GIT_TERMINAL_PROMPT=0 so git never blocks on a credential prompt. Every mutating primitive
// returns a structured result and throws a clear error on failure; push additionally verifies
// that the remote SHA equals the local HEAD before reporting success.
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const trust = require('../gui/git-trust');
const { filterSensitive } = require('../gui/sensitive');

const DEFAULT_TIMEOUT = 60000;
const FETCH_TIMEOUT = 300000;
const PUSH_TIMEOUT = 300000;
const CLONE_TIMEOUT = 600000;

const GIT_ENV = { GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'never' };

// ---------- process runner ----------
function runProc(cmd, args, { cwd, timeout = DEFAULT_TIMEOUT, env = {} } = {}) {
  return new Promise((resolve) => {
    let out = '';
    let err = '';
    let done = false;
    const child = spawn(cmd, args, {
      cwd,
      shell: false,
      windowsHide: true,
      env: { ...process.env, ...env }
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

async function runGit(dir, args, { timeout = DEFAULT_TIMEOUT } = {}) {
  const root = path.resolve(dir);
  const r = await runProc('git', args, { cwd: root, timeout, env: GIT_ENV });
  if (!r.ok && trust.isDubious(r.stderr)) {
    const healed = trust.ensureSafe(root);
    if (healed.ok) return runProc('git', args, { cwd: root, timeout, env: GIT_ENV });
  }
  return r;
}

async function must(dir, args, { timeout = DEFAULT_TIMEOUT } = {}) {
  const r = await runGit(dir, args, { timeout });
  if (!r.ok) {
    const detail = (r.stderr || r.stdout || '').trim();
    throw new Error(`git ${args[0]} failed${r.timedOut ? ' (timeout)' : ''}${detail ? `: ${detail}` : ''}`);
  }
  return r.stdout;
}

async function ghRun(args, { timeout = 60000 } = {}) {
  return runProc('gh', args, { timeout, env: { GH_PROMPT_DISABLED: '1', GIT_TERMINAL_PROMPT: '0' } });
}

async function ghMust(args, opts) {
  const r = await ghRun(args, opts);
  if (!r.ok) throw new Error((r.stderr || r.stdout || 'gh failed').trim());
  return r.stdout;
}

function identityError() {
  return new Error(
    'Няма зададена Git идентичност (user.name/user.email) — задайте я преди да се създаде commit.\n' +
    'Git-Identität (user.name/user.email) ist nicht konfiguriert — bitte vor dem Commit setzen.'
  );
}

// ---------- read primitives ----------
async function ensureIdentity(dir) {
  const name = (await runGit(dir, ['config', '--get', 'user.name'])).stdout.trim();
  const email = (await runGit(dir, ['config', '--get', 'user.email'])).stdout.trim();
  if (!name || !email) throw identityError();
  return { name, email };
}

async function currentBranch(dir) {
  const r = await runGit(dir, ['symbolic-ref', '--quiet', '--short', 'HEAD']);
  if (!r.ok || !r.stdout.trim()) throw new Error('Detached HEAD is not supported.');
  return r.stdout.trim();
}

async function hasUpstream(dir, branch) {
  const remote = (await runGit(dir, ['config', '--get', `branch.${branch}.remote`])).stdout.trim();
  const merge = (await runGit(dir, ['config', '--get', `branch.${branch}.merge`])).stdout.trim();
  return !!(remote && remote !== '.' && merge.startsWith('refs/heads/'));
}

async function resolveRemote(dir) {
  const origin = await runGit(dir, ['remote', 'get-url', 'origin']);
  if (origin.ok && origin.stdout.trim()) return { name: 'origin', url: origin.stdout.trim() };
  const remotes = (await runGit(dir, ['remote'])).stdout.split(/\r?\n/).filter(Boolean);
  if (!remotes.length) return null;
  const name = remotes[0];
  const url = await runGit(dir, ['remote', 'get-url', name]);
  return { name, url: url.ok ? url.stdout.trim() : '' };
}

async function hasWorkingTreeChanges(dir) {
  const r = await runGit(dir, ['status', '--porcelain', '--untracked-files=all']);
  return !!r.stdout.trim();
}

async function hasHead(dir) {
  return (await runGit(dir, ['rev-parse', '--verify', 'HEAD'])).ok;
}

async function upstreamRef(dir, branch) {
  const remote = (await runGit(dir, ['config', '--get', `branch.${branch}.remote`])).stdout.trim();
  const merge = (await runGit(dir, ['config', '--get', `branch.${branch}.merge`])).stdout.trim();
  if (remote && remote !== '.' && merge.startsWith('refs/heads/')) {
    return `${remote}/${merge.slice('refs/heads/'.length)}`;
  }
  return null;
}

async function remoteDefaultBranch(dir, url) {
  const r = await runGit(dir, ['ls-remote', '--symref', url, 'HEAD'], { timeout: 60000 });
  if (!r.ok) return null;
  const m = /^ref: refs\/heads\/(\S+)\s+HEAD/m.exec(r.stdout || '');
  return m ? m[1] : null;
}

// ---------- mutating primitives ----------
async function stageAll(dir) {
  return must(dir, ['add', '--all']);
}

async function commit(dir, message) {
  if (!message || !String(message).trim()) throw new Error('A non-empty commit message is required.');
  await ensureIdentity(dir);
  return must(dir, ['commit', '-q', '-m', String(message).trim()]);
}

async function verifyRemoteSha(dir, remote, branch, local) {
  const r = await runGit(dir, ['ls-remote', remote.name, `refs/heads/${branch}`], { timeout: 60000 });
  if (!r.ok) {
    throw new Error('Push could not be verified: ' + (r.stderr || r.stdout || 'ls-remote failed').split('\n')[0]);
  }
  const remoteSha = (r.stdout || '').split(/\s+/)[0] || '';
  if (remoteSha !== local) {
    throw new Error(`Push could not be verified (local ${local}, remote ${remoteSha || 'none'})`);
  }
}

async function push(dir, options = {}) {
  const root = path.resolve(dir);
  const branch = await currentBranch(root);
  const changes = await hasWorkingTreeChanges(root);
  const upstream = await hasUpstream(root, branch);
  const remote = await resolveRemote(root);
  const headOk = await hasHead(root);
  const sha = headOk ? (await runGit(root, ['rev-parse', 'HEAD'])).stdout.trim() : '';
  const plan = {
    ok: true, dir: root, branch, changes, hasUpstream: upstream,
    remote: remote ? remote.name : null, sha: sha || null, pushed: false
  };
  if (!options.apply) return plan;

  if (changes) {
    if (!options.message || !String(options.message).trim()) {
      throw new Error('A non-empty commit message is required when committing local changes.');
    }
    await stageAll(root);
    await commit(root, options.message);
  }
  if (!(await hasHead(root))) {
    throw new Error('Nothing to push: repository has no commits.');
  }
  if (upstream) {
    await must(root, ['push'], { timeout: PUSH_TIMEOUT });
  } else {
    if (!remote) throw new Error('No upstream or origin remote is configured.');
    await must(root, ['push', '--set-upstream', remote.name, 'HEAD'], { timeout: PUSH_TIMEOUT });
  }
  const local = (await runGit(root, ['rev-parse', 'HEAD'])).stdout.trim();
  await verifyRemoteSha(root, remote, branch, local);
  return { ...plan, pushed: true, sha: local };
}

async function pull(dir, options = {}) {
  const root = path.resolve(dir);
  const branch = await currentBranch(root);
  const dirty = await hasWorkingTreeChanges(root);
  const upstream = await hasUpstream(root, branch);
  const remote = await resolveRemote(root);
  const plan = {
    ok: true, dir: root, branch, dirty, hasUpstream: upstream,
    remote: remote ? remote.name : null, updated: false
  };
  if (!options.apply) return plan;

  if (dirty) throw new Error('Working tree is not clean; commit or stash changes before updating.');
  if (!remote) throw new Error('No upstream or origin remote is configured.');
  await must(root, ['fetch', '--prune', remote.name], { timeout: FETCH_TIMEOUT });
  const target = (await upstreamRef(root, branch)) || `${remote.name}/${branch}`;
  await must(root, ['merge', '--ff-only', target], { timeout: FETCH_TIMEOUT });
  if (!upstream) {
    await must(root, ['branch', '--set-upstream-to=' + target, branch]);
  }
  const sha = (await runGit(root, ['rev-parse', 'HEAD'])).stdout.trim();
  return { ...plan, updated: true, sha };
}

async function link(dir, url, options = {}) {
  const root = path.resolve(dir);
  const remoteDefault = await remoteDefaultBranch(root, url);
  const branch = options.branch || remoteDefault || 'main';
  const isRepo = (await runGit(root, ['rev-parse', '--is-inside-work-tree'])).ok;
  if (!isRepo) await must(root, ['init', '-b', branch]);
  const existing = (await runGit(root, ['remote', 'get-url', 'origin'])).stdout.trim();
  if (existing && existing !== url) throw new Error('Origin already exists with a different URL: ' + existing);
  if (!existing) await must(root, ['remote', 'add', 'origin', url]);

  const lsr = await runGit(root, ['ls-remote', '--heads', 'origin'], { timeout: 60000 });
  if (!lsr.ok) {
    return { ok: true, dir: root, url, branch, linked: true, remoteEmpty: true, warning: 'Remote is not reachable yet; origin was set and push will configure upstream.' };
  }
  if (!lsr.stdout.trim()) {
    return { ok: true, dir: root, url, branch, linked: true, remoteEmpty: true };
  }

  await must(root, ['fetch', '--no-tags', 'origin'], { timeout: FETCH_TIMEOUT });
  const current = (await runGit(root, ['branch', '--show-current'])).stdout.trim() || branch;
  const hasCommits = await hasHead(root);
  const defaultRef = `refs/remotes/origin/${remoteDefault || current}`;
  const defaultExists = (await runGit(root, ['rev-parse', '--verify', defaultRef])).ok;
  const targetBranch = defaultExists ? (remoteDefault || current) : current;
  const targetRef = `refs/remotes/origin/${targetBranch}`;
  const targetExists = (await runGit(root, ['rev-parse', '--verify', targetRef])).ok;
  if (!targetExists) throw new Error('Remote has no branch to link against.');

  let localBranch;
  if (!hasCommits) {
    await must(root, ['symbolic-ref', 'HEAD', `refs/heads/${targetBranch}`]);
    await must(root, ['reset', '-q', targetRef]);
    localBranch = targetBranch;
  } else {
    const related = (await runGit(root, ['merge-base', 'HEAD', targetRef])).ok;
    if (!related) throw new Error('Local and remote histories are unrelated; refusing to link');
    localBranch = current;
  }
  // Always set the upstream branch so a later push never hits "no upstream branch".
  await must(root, ['branch', '--set-upstream-to=origin/' + targetBranch, localBranch]);
  return { ok: true, dir: root, url, branch: localBranch, linked: true };
}

async function clone(url, dest) {
  const root = path.resolve(dest);
  await must(path.dirname(root), ['clone', '--', url, root], { timeout: CLONE_TIMEOUT });
  const branch = (await runGit(root, ['branch', '--show-current'])).stdout.trim() || null;
  return { ok: true, dir: root, url, branch };
}

function validateRepositoryName(name) {
  if (typeof name !== 'string' || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(name)) {
    throw new Error('Repository name must use OWNER/REPOSITORY format.');
  }
  return name;
}

async function ghProtocol() {
  const p = await ghRun(['config', 'get', 'git_protocol'], { timeout: 10000 });
  return p.ok && p.stdout.trim() === 'ssh' ? 'ssh' : 'https';
}

async function scanStagedSensitive(root) {
  const staged = (await runGit(root, ['diff', '--cached', '--name-only', '-z'])).stdout.split('\0').filter(Boolean);
  const deleted = new Set((await runGit(root, ['diff', '--cached', '--diff-filter=D', '--name-only', '-z'])).stdout.split('\0').filter(Boolean));
  const bad = await filterSensitive(staged, async (f) => {
    const r = await runGit(root, ['show', ':' + f]);
    return r.stdout;
  }, (f) => deleted.has(f));
  return { staged, bad };
}

async function publish(dir, options = {}) {
  if (!options.apply) throw new Error('Publishing creates a GitHub repository and pushes files; pass apply to confirm.');
  const root = path.resolve(dir);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) throw new Error(`Directory not found: ${root}`);
  const repository = validateRepositoryName(options.repo);
  const visibility = options.visibility || 'private';
  if (!['private', 'public'].includes(visibility)) throw new Error('Visibility must be private or public.');
  if (!(await ghRun(['auth', 'status'], { timeout: 20000 })).ok) {
    throw new Error('GitHub CLI is not authenticated. Use "GitHub · Login" first.');
  }

  const isRepo = (await runGit(root, ['rev-parse', '--is-inside-work-tree'])).ok;
  if (isRepo) {
    const top = (await runGit(root, ['rev-parse', '--show-toplevel'])).stdout.trim();
    if (path.resolve(top).toLowerCase() !== root.toLowerCase()) {
      throw new Error('Folder is inside another repository; select its root');
    }
    const origin = await runGit(root, ['remote', 'get-url', 'origin']);
    if (origin.ok) throw new Error('Origin already exists (' + origin.stdout.trim() + '); use "GitHub connection" instead');
  } else {
    await must(root, ['init', '-b', 'main']);
  }

  if (await hasWorkingTreeChanges(root)) {
    if (options.ensureRules) await options.ensureRules(root);
    await stageAll(root);
    const { staged, bad } = await scanStagedSensitive(root);
    if (bad.length) {
      await runGit(root, ['reset', '-q']);
      throw new Error('Sensitive files staged, aborted: ' + bad.join(', '));
    }
    if (!staged.length) throw new Error('Nothing to commit: folder is empty');
    await commit(root, (options.message || 'Initial commit').trim());
  } else if (!(await hasHead(root))) {
    throw new Error('Nothing to commit: folder is empty');
  }

  const exists = await ghRun(['repo', 'view', repository, '--json', 'name'], { timeout: 20000 });
  if (exists.ok) throw new Error(`Repository ${repository} already exists on GitHub`);

  const createArgs = ['repo', 'create', repository, `--${visibility}`];
  if (options.description) createArgs.push('--description', String(options.description));
  const made = await ghRun(createArgs, { timeout: 60000 });
  if (!made.ok) {
    if (!/not accessible|createRepository/i.test(made.stderr || made.stdout)) {
      throw new Error(made.stderr || made.stdout || 'gh repo create failed');
    }
    const [own, nm] = repository.split('/');
    const me = (await ghRun(['api', 'user', '-q', '.login'], { timeout: 20000 })).stdout.trim();
    const rest = ['api', '-X', 'POST', own === me ? 'user/repos' : `orgs/${own}/repos`, '-f', 'name=' + nm, '-F', 'private=' + (visibility === 'private')];
    if (options.description) rest.push('-f', 'description=' + String(options.description));
    const alt = await ghRun(rest, { timeout: 60000 });
    if (!alt.ok) {
      throw new Error('GitHub refused to create the repository with this token (no createRepository permission). Use a classic token with "repo" scope. Detail: ' + (alt.stderr || alt.stdout).split('\n')[0]);
    }
  }

  const protocol = await ghProtocol();
  const cloneUrl = protocol === 'ssh' ? `git@github.com:${repository}.git` : `https://github.com/${repository}.git`;
  try {
    await must(root, ['remote', 'add', 'origin', cloneUrl]);
    const result = await push(root, { apply: true });
    return { ok: true, dir: root, repository, url: cloneUrl, branch: result.branch, verifiedSha: result.sha, published: true };
  } catch (e) {
    throw new Error(`The GitHub repository ${repository} was created, but linking/push failed: ${e.message} — use Connect → link with ${cloneUrl} to finish.`);
  }
}

module.exports = {
  runGit,
  ensureIdentity,
  currentBranch,
  hasUpstream,
  resolveRemote,
  stageAll,
  commit,
  push,
  pull,
  link,
  clone,
  publish,
  validateRepositoryName
};
