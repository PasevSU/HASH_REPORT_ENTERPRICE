'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path'), { spawnSync } = require('node:child_process');
const sync = require('../lib/repo-sync');

const g = (cwd, ...a) => {
  const r = spawnSync('git', a, { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw Error((r.stderr || r.stdout || '').trim() || `git ${a[0]} failed`);
  return r.stdout.trim();
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'reposync-'));
process.env.GIT_CONFIG_GLOBAL = path.join(tmp, 'gitconfig');
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL, '[user]\n name=T\n email=t@t.t\n');

function bare(name) {
  const remote = path.join(tmp, name + '.git');
  g(tmp, 'init', '--bare', '-b', 'main', remote);
  return remote;
}

test('status reports a clean, in-sync repo with upstream', async () => {
  const remote = bare('s1');
  const w = path.join(tmp, 's1');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  g(w, 'push', '-q', '-u', 'origin', 'main');
  const s = await sync.status(w);
  assert.equal(s.dirty, false);
  assert.equal(s.ahead, 0);
  assert.equal(s.behind, 0);
  assert.equal(s.upstreamKnown, true);
  assert.equal(s.remote, 'origin');
});

test('status detects local commits ahead of remote', async () => {
  const remote = bare('s2');
  const w = path.join(tmp, 's2');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  g(w, 'push', '-q', '-u', 'origin', 'main');
  fs.writeFileSync(path.join(w, 'a.txt'), '2');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', '2');
  const s = await sync.status(w);
  assert.equal(s.ahead, 1);
  assert.equal(s.behind, 0);
});

test('status reports null divergence when no upstream is set', async () => {
  const w = path.join(tmp, 's-noup');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  const s = await sync.status(w);
  assert.equal(s.ahead, null);
  assert.equal(s.behind, null);
  assert.equal(s.upstreamKnown, false);
});

test('sync pulls when the remote is ahead', async () => {
  const remote = bare('s3');
  const seed = path.join(tmp, 's3-seed');
  fs.mkdirSync(seed);
  g(seed, 'init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(seed, 'a.txt'), '1');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'i');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  const w = path.join(tmp, 's3');
  g(tmp, 'clone', '-q', remote, w);
  fs.writeFileSync(path.join(seed, 'b.txt'), '2');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'b');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  const before = await sync.status(w, { fetch: true });
  assert.equal(before.behind, 1);
  const r = await sync.sync(w, { apply: true });
  assert.equal(r.pulled, true);
  assert.equal(r.behind, 0);
  assert.equal(fs.existsSync(path.join(w, 'b.txt')), true);
});

test('sync commits and pushes local changes when a message is provided', async () => {
  const remote = bare('s4');
  const w = path.join(tmp, 's4');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  g(w, 'push', '-q', '-u', 'origin', 'main');
  fs.writeFileSync(path.join(w, 'new.txt'), 'x');
  const r = await sync.sync(w, { apply: true, message: 'add new.txt' });
  assert.equal(r.pushed, true);
  assert.equal(r.dirty, false);
  const ls = g(tmp, '--git-dir=' + remote, 'ls-tree', '-r', '--name-only', 'main');
  assert.equal(ls.split('\n').includes('new.txt'), true);
});

test('sync dry-run returns a plan without mutating', async () => {
  const remote = bare('s5');
  const w = path.join(tmp, 's5');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  g(w, 'push', '-q', '-u', 'origin', 'main');
  fs.writeFileSync(path.join(w, 'new.txt'), 'x');
  const r = await sync.sync(w, { apply: false, message: 'x' });
  assert.equal(r.dirty, true);
  assert.equal(r.pulled, false);
  assert.equal(r.pushed, false);
  const ls = g(tmp, '--git-dir=' + remote, 'ls-tree', '-r', '--name-only', 'main');
  assert.equal(ls.split('\n').includes('new.txt'), false);
});

test('sync refuses to pull over a dirty tree when remote is ahead', async () => {
  const remote = bare('s6');
  const seed = path.join(tmp, 's6-seed');
  fs.mkdirSync(seed);
  g(seed, 'init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(seed, 'a.txt'), '1');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'i');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  const w = path.join(tmp, 's6');
  g(tmp, 'clone', '-q', remote, w);
  fs.writeFileSync(path.join(seed, 'b.txt'), '2');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'b');
  g(seed, 'push', '-q', remote, 'HEAD:main');
  fs.writeFileSync(path.join(w, 'local.txt'), 'x');
  await assert.rejects(() => sync.sync(w, { apply: true, message: 'x' }), /uncommitted changes/i);
});

test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
