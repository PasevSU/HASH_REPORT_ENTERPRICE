'use strict';
// End-to-end integration test for the IPC "operation" path WITHOUT Electron.
// It mirrors gui/main.js exactly:
//   operation handler (main.js:35) -> guard.guarded(action, {needCommit:false}, ...)
//     -> OperationManager.run({dir,action,args,apply})
//       -> execute closure (main.js:20) -> gitops.push / gitops.pull
// This proves that "Качи/Upload" (push) and "Обнови/Pull" actually work end-to-end,
// including the first-ever push into an empty repo (the earlier reported bug).
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const { spawnSync } = require('node:child_process');

const gitops = require('../lib/gitops');
const guard = require('../gui/guard');
const { OperationManager } = require('../gui/operation-manager');
const { JobJournal } = require('../gui/job-journal');
const { withRepoLock } = require('../gui/repo-lock');

const g = (cwd, ...a) => {
  const r = spawnSync('git', a, { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw Error((r.stderr || r.stdout || '').trim() || `git ${a[0]} failed`);
  return r.stdout.trim();
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'op-'));
process.env.GIT_CONFIG_GLOBAL = path.join(tmp, 'gitconfig');
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL, '[user]\n name=T\n email=t@t.t\n');

function bare(name) {
  const remote = path.join(tmp, name + '.git');
  g(tmp, 'init', '--bare', '-b', 'main', remote);
  return remote;
}

// Faithful copy of the execute closure built in main.js:20.
function makeExecute() {
  return ({ dir, action, args, apply }) => {
    const message = args.includes('--message') ? args[args.indexOf('--message') + 1] : undefined;
    return action === 'push' ? gitops.push(dir, { message, apply }) : gitops.pull(dir, { apply });
  };
}

// Faithful copy of the operation handler in main.js:35.
function makeOperation(manager) {
  return async (dir, action, message, apply) => {
    const args = message && action === 'push' ? ['--message', message] : [];
    return guard.guarded(action, { dir, apply: !!apply, message, needCommit: false },
      () => manager.run({ dir, action, args, apply: !!apply }));
  };
}

function makeManager() {
  const journal = new JobJournal(path.join(tmp, 'journal-' + Math.random().toString(36).slice(2) + '.json'));
  const manager = new OperationManager({ journal, lock: withRepoLock, execute: makeExecute(), onChange: () => {} });
  return { manager, journal };
}

test('upload (push) creates the first commit and pushes a brand-new empty repo end-to-end', async () => {
  const remote = bare('up1');
  const w = path.join(tmp, 'up1');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), 'hello');

  const { manager } = makeManager();
  const operation = makeOperation(manager);
  const r = await operation(w, 'push', 'initial upload', true);

  assert.equal(r.ok, true);
  assert.equal(r.pushed, true);
  assert.equal(g(w, 'rev-parse', 'HEAD'), g(tmp, '--git-dir=' + remote, 'rev-parse', 'main'));
  assert.equal(g(tmp, '--git-dir=' + remote, 'show', 'main:a.txt'), 'hello');
  assert.equal(g(w, 'config', '--get', 'branch.main.remote'), 'origin');
});

test('upload propagates the commit message through the full operation chain', async () => {
  const remote = bare('up2');
  const w = path.join(tmp, 'up2');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'f.txt'), 'x');

  const { manager } = makeManager();
  await makeOperation(manager)(w, 'push', 'release notes v1.2.3', true);

  assert.equal(g(tmp, '--git-dir=' + remote, 'log', '-1', '--format=%s', 'main'), 'release notes v1.2.3');
});

test('upload propagates a deleted file (deletion is pushed)', async () => {
  const remote = bare('up3');
  const w = path.join(tmp, 'up3');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'gone.txt'), 'bye');
  const { manager } = makeManager();
  const operation = makeOperation(manager);
  await operation(w, 'push', 'add file', true);

  fs.unlinkSync(path.join(w, 'gone.txt'));
  const r = await operation(w, 'push', 'remove file', true);

  assert.equal(r.ok, true);
  assert.equal(g(w, 'status', '--porcelain'), '');
  const remoteTree = g(tmp, '--git-dir=' + remote, 'ls-tree', '-r', '--name-only', 'main');
  assert.equal(remoteTree.includes('gone.txt'), false, 'deleted file must no longer exist on remote');
});

test('update (pull) fetches and merges a remote commit end-to-end', async () => {
  const remote = bare('pl1');
  const seed = path.join(tmp, 'pl1-seed');
  fs.mkdirSync(seed);
  g(seed, 'init', '-q', '-b', 'main');
  g(seed, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(seed, 'a.txt'), '1');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'seed');
  g(seed, 'push', '-q', '-u', 'origin', 'main');

  const w = path.join(tmp, 'pl1-work');
  g(tmp, 'clone', '-q', '-b', 'main', remote, w);

  fs.writeFileSync(path.join(seed, 'b.txt'), '2');
  g(seed, 'add', '.');
  g(seed, 'commit', '-qm', 'second');
  g(seed, 'push', '-q', 'origin', 'main');

  const { manager } = makeManager();
  const operation = makeOperation(manager);
  const r = await operation(w, 'update', undefined, true);

  assert.equal(r.ok, true);
  assert.equal(r.updated, true);
  assert.equal(fs.readFileSync(path.join(w, 'b.txt'), 'utf8'), '2');
  assert.equal(g(w, 'rev-parse', 'HEAD'), g(seed, 'rev-parse', 'HEAD'));
});

test('operation records a completed job in the journal', async () => {
  const remote = bare('j1');
  const w = path.join(tmp, 'j1');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  g(w, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(w, 'a.txt'), '1');

  const { manager, journal } = makeManager();
  await makeOperation(manager)(w, 'push', 'journal push', true);

  const jobs = journal.list();
  assert.equal(jobs.length, 1);
  assert.equal(jobs[0].kind, 'push');
  assert.equal(jobs[0].status, 'completed');
  assert.equal(jobs[0].apply, true);
});
