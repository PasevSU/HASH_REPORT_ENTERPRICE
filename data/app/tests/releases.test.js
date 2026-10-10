'use strict';
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs'), os = require('node:os'), path = require('node:path'), { spawnSync } = require('node:child_process');
const releases = require('../lib/releases');

const g = (cwd, ...a) => {
  const r = spawnSync('git', a, { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw Error((r.stderr || r.stdout || '').trim() || `git ${a[0]} failed`);
  return r.stdout.trim();
};

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'releases-'));
process.env.GIT_CONFIG_GLOBAL = path.join(tmp, 'gitconfig');
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL, '[user]\n name=T\n email=t@t.t\n');

test('create requires a tag before touching gh', async () => {
  await assert.rejects(() => releases.create(tmp, { title: 'no tag' }), /tag is required/i);
});

test('remove requires a tag before touching gh', async () => {
  await assert.rejects(() => releases.remove(tmp, '   '), /tag is required/i);
});

test('tags lists local tags and empty remote when unlinked', async () => {
  const w = path.join(tmp, 'w');
  fs.mkdirSync(w);
  g(w, 'init', '-q', '-b', 'main');
  fs.writeFileSync(path.join(w, 'a.txt'), '1');
  g(w, 'add', '.');
  g(w, 'commit', '-qm', 'i');
  g(w, 'tag', 'v1.0.0');
  g(w, 'tag', 'v1.1.0');
  const t = await releases.tags(w);
  assert.deepStrictEqual([...t.local].sort(), ['v1.0.0', 'v1.1.0']);
  assert.deepStrictEqual(t.remote, []);
});

test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
