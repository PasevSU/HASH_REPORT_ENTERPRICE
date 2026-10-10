'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path'), { spawnSync } = require('node:child_process');
const gitops = require('../lib/gitops');

const g = (cwd, ...a) => {
  const r = spawnSync('git', a, { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw Error((r.stderr || r.stdout || '').trim() || `git ${a[0]} failed`);
  return r.stdout.trim();
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'gitops-'));
process.env.GIT_CONFIG_GLOBAL = path.join(tmp, 'gitconfig');
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL, '[user]\n name=T\n email=t@t.t\n');

function bare(name) {
  const remote = path.join(tmp, name + '.git');
  g(tmp, 'init', '--bare', '-b', 'main', remote);
  return remote;
}

function seedPush(remote) {
  const seed = path.join(tmp, path.basename(remote, '.git') + '-seed');
  fs.mkdirSync(seed);
  g(seed, 'init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(seed, 'a.txt'), '1');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'i');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  return seed;
}

test('push with no upstream sets -u and succeeds', async () => {
  const remote = bare('push1');
  const w = path.join(tmp, 'push1');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  const r = await gitops.push(w, { apply: true, message: 'initial' });
  assert.equal(r.pushed, true);
  assert.equal(r.branch, 'main');
  assert.equal(g(w, 'config', '--get', 'branch.main.remote'), 'origin');
  assert.equal(g(w, 'config', '--get', 'branch.main.merge'), 'refs/heads/main');
  assert.equal(g(w, 'rev-parse', 'HEAD'), g(tmp, '--git-dir=' + remote, 'rev-parse', 'main'));
});

test('push after prior commit with no working-tree changes still sets upstream', async () => {
  const remote = bare('push2');
  const w = path.join(tmp, 'push2');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'b.txt'), '2');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'b');
  // Reproduce the broken state: remote set but no merge (upstream) configured.
  g(w, 'config', 'branch.main.remote', 'origin');
  const r = await gitops.push(w, { apply: true });
  assert.equal(r.pushed, true);
  assert.equal(g(w, 'config', '--get', 'branch.main.merge'), 'refs/heads/main');
  assert.equal(g(w, 'rev-parse', 'HEAD'), g(tmp, '--git-dir=' + remote, 'rev-parse', 'main'));
});

test('pull with no upstream falls back to origin and sets tracking', async () => {
  const remote = bare('pull1');
  const seed = seedPush(remote);
  const w = path.join(tmp, 'pull1');
  g(tmp, 'clone', '-q', remote, w);
  g(w, 'branch', '--unset-upstream');
  fs.writeFileSync(path.join(seed, 'b.txt'), '2');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'b');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  const r = await gitops.pull(w, { apply: true });
  assert.equal(r.updated, true);
  assert.equal(g(w, 'config', '--get', 'branch.main.remote'), 'origin');
  assert.equal(g(w, 'config', '--get', 'branch.main.merge'), 'refs/heads/main');
  assert.equal(g(w, 'rev-parse', 'HEAD'), g(tmp, '--git-dir=' + remote, 'rev-parse', 'main'));
});

test('missing identity produces a clear error', async () => {
  const w = path.join(tmp, 'noid');
  fs.mkdirSync(w);
  const empty = path.join(tmp, 'noid-gitconfig');
  fs.writeFileSync(empty, '');
  const prevG = process.env.GIT_CONFIG_GLOBAL;
  const prevS = process.env.GIT_CONFIG_NOSYSTEM;
  process.env.GIT_CONFIG_GLOBAL = empty;
  process.env.GIT_CONFIG_NOSYSTEM = '1';
  try {
    g(w, 'init', '-q', '-b', 'main');
    fs.writeFileSync(path.join(w, 'a.txt'), '1');
    await assert.rejects(() => gitops.push(w, { apply: true, message: 'x' }), /user\.name/);
  } finally {
    process.env.GIT_CONFIG_GLOBAL = prevG;
    if (prevS === undefined) delete process.env.GIT_CONFIG_NOSYSTEM; else process.env.GIT_CONFIG_NOSYSTEM = prevS;
  }
});

test('link always sets upstream', async () => {
  const remote = bare('link1');
  seedPush(remote);
  const d = path.join(tmp, 'link1');
  fs.mkdirSync(d);
  fs.writeFileSync(path.join(d, 'mine.txt'), 'x');
  const r = await gitops.link(d, remote, { branch: 'main' });
  assert.equal(r.linked, true);
  assert.equal(g(d, 'remote', 'get-url', 'origin'), remote);
  assert.equal(g(d, 'config', '--get', 'branch.main.remote'), 'origin');
  assert.equal(g(d, 'config', '--get', 'branch.main.merge'), 'refs/heads/main');
  assert.equal(g(d, 'rev-parse', 'HEAD'), g(tmp, '--git-dir=' + remote, 'rev-parse', 'main'));
  assert.match(g(d, 'status', '--porcelain'), /mine\.txt/);
});

test('link sets upstream when local branch differs from remote default', async () => {
  const remote = bare('link2');
  seedPush(remote);
  const w = path.join(tmp, 'link2');
  g(tmp, 'clone', '-q', remote, w);
  g(w, 'branch', '-m', 'master');
  g(w, 'branch', '--unset-upstream', 'master');
  const r = await gitops.link(w, remote, {});
  assert.equal(r.linked, true);
  assert.equal(r.branch, 'master');
  assert.equal(g(w, 'config', '--get', 'branch.master.remote'), 'origin');
  assert.equal(g(w, 'config', '--get', 'branch.master.merge'), 'refs/heads/main');
});

test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
