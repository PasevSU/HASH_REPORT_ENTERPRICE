'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path'), { spawnSync } = require('node:child_process');
const gv = require('../gui/git-view');
const guard = require('../gui/guard');

function mkRepo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gsdel-'));
  const gc = path.join(dir, 'gitconfig');
  fs.writeFileSync(gc, '[user]\n name=T\n email=t@t.t\n');
  process.env.GIT_CONFIG_GLOBAL = gc;
  const g = (cwd, ...a) => {
    const r = spawnSync('git', a, { cwd, encoding: 'utf8' });
    if (r.status !== 0) throw Error((r.stderr || r.stdout || '').trim() || `git ${a[0]} failed`);
    return r.stdout.trim();
  };
  g(dir, 'init', '-q', '-b', 'main');
  const w = (n, t) => fs.writeFileSync(path.join(dir, n), t);
  return { dir, g, w };
}

test('tracked deleted file matching .gitignore is still visible (not ignored)', async () => {
  const { dir, g, w } = mkRepo();
  try {
    w('debug.log', 'log'); w('keep.txt', 'k');
    g(dir, 'add', '.'); g(dir, 'commit', '-qm', 'i');
    w('.gitignore', '*.log\n');
    fs.unlinkSync(path.join(dir, 'debug.log'));
    const s = await gv.status(dir);
    const del = s.files.find((f) => f.path === 'debug.log');
    assert.ok(del, 'deleted tracked file is listed');
    assert.equal(del.worktree, 'D');
    assert.equal(del.ignored, false, 'tracked deleted file must not be flagged ignored');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('tracked modified file matching .gitignore is still visible (not ignored)', async () => {
  const { dir, g, w } = mkRepo();
  try {
    w('debug.log', 'log'); g(dir, 'add', '.'); g(dir, 'commit', '-qm', 'i');
    w('.gitignore', '*.log\n');
    w('debug.log', 'log2');
    const s = await gv.status(dir);
    const mod = s.files.find((f) => f.path === 'debug.log');
    assert.ok(mod, 'tracked modified file is listed');
    assert.equal(mod.worktree, 'M');
    assert.equal(mod.ignored, false, 'tracked modified file must not be flagged ignored');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('deleting a sensitive-named file commits successfully', async () => {
  const { dir, g, w } = mkRepo();
  try {
    w('id_rsa', 'PRIVATE KEY'); w('keep.txt', 'k');
    g(dir, 'add', '.'); g(dir, 'commit', '-qm', 'i');
    fs.unlinkSync(path.join(dir, 'id_rsa'));
    await gv.stage(dir, ['id_rsa']);
    const r = await gv.commit(dir, { message: 'remove id_rsa' });
    assert.equal(r.files, 1, 'deleted id_rsa is committed');
    const s = await gv.status(dir);
    assert.equal(s.files.some((f) => f.path === 'id_rsa'), false, 'id_rsa no longer tracked');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('guard commit preflight allows deleting a sensitive-named file', async () => {
  const { dir, g, w } = mkRepo();
  try {
    w('.env', 'A=1'); w('keep.txt', 'k');
    g(dir, 'add', '.'); g(dir, 'commit', '-qm', 'i');
    fs.unlinkSync(path.join(dir, '.env'));
    await gv.stage(dir, ['.env']);
    const { rep } = await guard.preflight('commit', { dir, message: 'remove .env' });
    assert.equal(rep.ok, true, `guard should not block deletion of .env: ${rep.summary().join(' | ')}`);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
