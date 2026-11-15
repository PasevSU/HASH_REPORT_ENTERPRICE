import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  DEFAULT_PATTERN,
  REQUIRED,
  STYLE_DIR,
  discoverRuleFiles,
  invalidate,
  layoutRule,
  loadStyles,
  readRuleDocument,
  validateRequiredSections,
  visual,
} from '../style-loader.mjs';

const REF = JSON.parse(fs.readFileSync(new URL('./fixtures/styles.json', import.meta.url), 'utf8'));
const TOKEN = '<DIR>';

/** Mirrors the reference generator: base/<case name>/<rule files>. */
function caseDir(name, files) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'cs_style_'));
  const dir = path.join(base, name);
  fs.mkdirSync(dir, { recursive: true });
  for (const [fileName, body] of Object.entries(files || {})) {
    const target = path.join(dir, ...fileName.split('/'));
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, body, 'utf8');
  }
  return { base, dir };
}

function scrub(message, base) {
  return String(message).split(base).join(TOKEN);
}

function unwrap(reference) {
  const text = String(reference.error || reference.expect);
  const cut = text.indexOf(': ');
  return { kind: text.slice(0, cut), message: text.slice(cut + 2) };
}

function withCase(name, body) {
  const { base, dir } = caseDir(name, REF.cases.files[name]);
  try {
    body(dir, base);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
}

test('loader: merged payload is byte-identical to the Python reference', () => {
  const merged = loadStyles();
  assert.deepEqual(merged, REF.loader.payload);
  assert.equal(Object.keys(merged).length, REF.loader.sections.length);
});

test('loader: every mandatory section survives the merge', () => {
  const merged = loadStyles();
  assert.deepEqual([...REQUIRED].sort(), REF.loader.required);
  assert.equal(REQUIRED.length, 16);
  for (const name of REF.loader.required) assert.ok(name in merged, name);
});

test('loader: mandatory-section gate reports the Python list message', () => {
  const expected = unwrap(REF.cases.missing_sections);
  assert.throws(() => validateRequiredSections(REF.cases.merge.expect), (error) => {
    assert.equal(error.message, expected.message);
    return true;
  });
  assert.throws(() => validateRequiredSections({}), /Missing mandatory style sections/);
});

test('loader: packaged rule folder passes the gate', () => {
  assert.equal(validateRequiredSections(loadStyles()), true);
  assert.ok(fs.statSync(STYLE_DIR).isDirectory());
  assert.equal(DEFAULT_PATTERN, '*.js');
});

test('loader: visual() resolves every reference literal', () => {
  assert.equal(REF.visual.length, 12);
  for (const { key, expect } of REF.visual) assert.deepEqual(visual(key), expect, key);
  assert.throws(() => visual('no.such.literal'), /no\.such\.literal/);
});

test('loader: layoutRule() walks every reference path', () => {
  for (const { path: keys, expect } of REF.layout.paths) {
    assert.deepEqual(layoutRule(...keys), expect, JSON.stringify(keys));
  }
  assert.deepEqual(layoutRule(), loadStyles().CENTRAL_LAYOUT);
});

test('loader: PAGINATION is not reachable through layoutRule, only the merged root', () => {
  const merged = loadStyles();
  assert.deepEqual(merged[REF.layout.merged_root.key], REF.layout.merged_root.expect);
  assert.throws(() => layoutRule(...REF.layout.out_of_scope.path), /Missing layout rule: PAGINATION/);
});

test('loader: duplicate rule in one file is rejected with the key name', () => {
  const expected = unwrap(REF.cases.duplicate);
  withCase('duplicate', (dir, base) => {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(scrub(error.message, base), expected.message);
      assert.match(error.message, /SAME/);
      return true;
    });
  });
});

test('loader: duplicate rule across nested folders names the second file', () => {
  const expected = unwrap(REF.cases.nested_duplicate);
  withCase('nested_duplicate', (dir, base) => {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(scrub(error.message, base), expected.message);
      assert.match(error.message, /'width'/);
      assert.match(error.message, /02_second\.js$/);
      return true;
    });
  });
});

test('loader: missing directory raises ENOENT with the Python wording', () => {
  const expected = unwrap(REF.cases.missing_dir);
  const { base, dir } = caseDir('does_not_exist', {});
  fs.rmSync(dir, { recursive: true, force: true });
  try {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(error.code, 'ENOENT');
      assert.equal(scrub(error.message, base), expected.message);
      return true;
    });
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('loader: empty rule folder is reported, not silently accepted', () => {
  const expected = unwrap(REF.cases.empty_dir);
  withCase('empty', (dir, base) => {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(scrub(error.message, base), expected.message);
      return true;
    });
  });
});

test('loader: deep merge of a custom folder matches Python', () => {
  withCase('merge', (dir) => {
    const merged = loadStyles({ directory: dir });
    assert.deepEqual(merged, REF.cases.merge.expect);
    assert.deepEqual(merged.PAGE, { paper: 'A4', width: 595.28, height: 841.89 });
    assert.deepEqual(merged.COLORS, { ink: '#111' });
    assert.deepEqual(merged.NESTED, { list: [1, 2, { deep: true }] });
    assert.deepEqual(merged.EXTRA, { zero: 0, flag: false, text: 'é' });
  });
});

test('loader: non-object rule root is rejected without a subprocess repr', () => {
  const entry = REF.cases.array_root;
  withCase('array_root', (dir) => {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(error.code, entry.expected_code);
      assert.match(error.message, /Style root must be an object/);
      assert.doesNotMatch(error.message, /Command '/);
      assert.doesNotMatch(error.message, /returned non-zero exit status/);
      return true;
    });
  });
  assert.ok(entry.leaks_subprocess_repr, 'Python reference leaks a subprocess repr here');
  assert.match(entry.detail_suffix, /01_array\.js$/);
});

test('loader: a throwing rule file reports evaluation failure', () => {
  const entry = REF.cases.throwing;
  withCase('throwing', (dir) => {
    assert.throws(() => loadStyles({ directory: dir }), (error) => {
      assert.equal(error.code, entry.expected_code);
      assert.match(error.message, /JS rules failed to load: .*01_boom\.js: boom/);
      assert.doesNotMatch(error.message, /Command '/);
      assert.doesNotMatch(error.message, /returned non-zero exit status/);
      return true;
    });
  });
  assert.ok(entry.leaks_subprocess_repr, 'Python reference leaks a subprocess repr here');
});

test('loader: cache returns independent copies and honours invalidate()', () => {
  const first = loadStyles();
  first.CENTRAL_LAYOUT.paper = 'Letter';
  const second = loadStyles();
  assert.notEqual(second.CENTRAL_LAYOUT.paper, 'Letter');
  assert.equal(Object.keys(second).length, REF.loader.sections.length);
  assert.notStrictEqual(first, second);
  invalidate();
  assert.deepEqual(loadStyles(), REF.loader.payload);
});

test('loader: invalidate() forces a genuine re-read of the rule folder', () => {
  const { base, dir } = caseDir('reread', { 'only.js': 'module.exports = { VERSION: 1 };' });
  try {
    assert.deepEqual(loadStyles({ directory: dir }), { VERSION: 1 });
    fs.writeFileSync(path.join(dir, 'only.js'), 'module.exports = { VERSION: 2 };', 'utf8');
    assert.deepEqual(loadStyles({ directory: dir }), { VERSION: 1 }, 'cache must still hold');
    invalidate();
    assert.deepEqual(loadStyles({ directory: dir }), { VERSION: 2 });
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test('loader: discovery is recursive, sorted, and skips non-JS entries', () => {
  const { base, dir } = caseDir('discovery', {
    'zeta.js': 'module.exports = { Z: 1 };',
    'alpha.js': 'module.exports = { A: 1 };',
    '.hidden.js': 'module.exports = { H: 1 };',
    'notes.txt': 'ignored',
    'nested/inner.js': 'module.exports = { I: 1 };',
  });
  try {
    const found = discoverRuleFiles(dir).map((file) => path.relative(dir, file).split(path.sep).join('/'));
    assert.deepEqual(found, ['alpha.js', 'nested/inner.js', 'zeta.js']);
    for (const file of discoverRuleFiles(dir)) {
      assert.equal(Object.keys(readRuleDocument(dir, file)).length, 1);
    }
    assert.throws(() => readRuleDocument(dir, path.join(dir, 'notes.txt')), (error) => {
      assert.equal(error.code, 'SUFFIX');
      return true;
    });
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});