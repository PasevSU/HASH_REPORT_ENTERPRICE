import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as hte from '../hash-table.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'parity.json'), 'utf8'));
const ref = fixture.hash_table;

function makeCorpus() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cs-jsx-'));
  for (const [rel, text] of Object.entries(ref.corpus)) {
    const target = path.join(base, ...rel.split('/'));
    fs.mkdirSync(path.dirname(target), { recursive: true });
    // Python Path.write_text uses universal newlines: '\n' becomes os.linesep.
    fs.writeFileSync(target, text.split('\n').join(os.EOL), 'utf8');
  }
  return base;
}

const base = makeCorpus();
test.after(() => fs.rmSync(base, { recursive: true, force: true }));

test('collectFiles reproduces Python collect_files for every mode', () => {
  for (const item of ref.modes) {
    const source = path.join(base, ...item.source.split('/'));
    const { root, files } = hte.collectFiles(source, item.mode);
    assert.equal(path.basename(root), item.root, item.mode);
    const rels = files.map((p) => path.relative(root, p).split(path.sep).join('/'));
    assert.deepEqual(rels, item.files, item.mode);
  }
});

test('collectFiles honours the exclude list', () => {
  const { root, files } = hte.collectFiles(base, 'recursive_folder', { exclude: [path.join(base, 'sub', 'd.md')] });
  const rels = files.map((p) => path.relative(root, p).split(path.sep).join('/'));
  assert.deepEqual(rels, ref.exclude);
});

test('buildRows hashes the corpus exactly like the Python engine', () => {
  const rows = hte.buildRows(base, 'recursive_folder', { algorithms: ['sha256', 'sha512', 'sha1', 'md5'] });
  const trimmed = rows.map((row) => ({
    index: row.index, path: row.path, type: row.type, size_bytes: row.size_bytes,
    sha256: row.sha256, sha512: row.sha512, sha1: row.sha1, md5: row.md5,
  }));
  assert.deepEqual(trimmed, ref.rows);
});

test('buildRows single_file reports the bare file name', () => {
  const rows = hte.buildRows(path.join(base, 'sub', 'd.md'), 'single_file');
  const trimmed = rows.map((row) => ({
    index: row.index, path: row.path, type: row.type, size_bytes: row.size_bytes, sha256: row.sha256,
  }));
  assert.deepEqual(trimmed, ref.single);
});

test('UTC date formatting matches Python datetime strftime', () => {
  for (const item of ref.dates) {
    assert.equal(hte.formatUtcDate(BigInt(item.ns)), item.expect, String(item.ns));
  }
});

test('inspectFile reports the documented row shape', () => {
  const row = hte.inspectFile(path.join(base, 'b.PDF'), base, ['sha256', 'sha512', 'sha1', 'md5']);
  assert.deepEqual(Object.keys(row).sort(), ['created', 'md5', 'modified', 'path', 'sha1', 'sha256', 'sha512', 'size_bytes', 'type']);
  assert.equal(row.type, 'pdf');
  assert.match(row.modified, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} UTC$/);
  const reference = ref.rows.find((item) => item.path === 'b.PDF');
  assert.equal(row.size_bytes, reference.size_bytes);
  assert.equal(row.sha256, reference.sha256);
});

test('empty files hash to the well-known digests', () => {
  const row = hte.inspectFile(path.join(base, 'empty.bin'), base, ['sha256', 'md5']);
  assert.equal(row.sha256, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
  assert.equal(row.md5, 'd41d8cd98f00b204e9800998ecf8427e');
  assert.equal(row.type, 'bin');
});

test('rejects invalid scopes and algorithms', () => {
  assert.throws(() => hte.collectFiles(base, 'everything'), /Unsupported scope: everything/);
  assert.throws(() => hte.inspectFile(path.join(base, 'a.txt'), base, ['sha3']), /Invalid hash algorithms/);
  assert.throws(() => hte.inspectFile(path.join(base, 'a.txt'), base, []), /Invalid hash algorithms/);
  assert.throws(() => hte.collectFiles(path.join(base, 'missing'), 'current_folder'), /ENOENT|no such file/i);
});

test('casefold folds the scalars where Python differs from toLowerCase', () => {
  assert.equal(hte.casefold('STRASSE'), hte.casefold('straße'.replace('ß', 'ß')));
  assert.equal(hte.casefold('ß'), 'ss');
  assert.equal(hte.casefold(String.fromCharCode(0xfb03)), 'ffi');
  assert.equal(hte.casefold('ПРАЗЕН'), 'празен');
});

test('symlinks are skipped like the Python walker', () => {
  const linkDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cs-jsx-link-'));
  fs.writeFileSync(path.join(linkDir, 'real.txt'), 'real\n');
  let linked = true;
  try {
    fs.symlinkSync(path.join(linkDir, 'real.txt'), path.join(linkDir, 'alias.txt'));
  } catch {
    linked = false;
  }
  if (linked) {
    const { files } = hte.collectFiles(linkDir, 'current_folder');
    assert.deepEqual(files.map((p) => path.basename(p)), ['real.txt']);
  }
  fs.rmSync(linkDir, { recursive: true, force: true });
});