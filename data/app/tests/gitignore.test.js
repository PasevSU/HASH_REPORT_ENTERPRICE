'use strict';
const test = require('node:test');
const assert = require('node:assert');
const gi = require('../lib/gitignore');

test('serialize produces grouped, deterministic output for every category', () => {
  const model = {
    files: ['secret.txt', 'config.local.json'],
    patterns: ['*.log', '*.tmp'],
    dirs: ['node_modules/', 'dist/'],
    subdirs: ['**/logs', '**/*.pdf'],
    exceptions: ['!important.log'],
    rootOnly: ['/TODO.txt'],
    presets: [],
    custom: []
  };
  const out = gi.serialize(model);
  assert.match(out, /# Specific files\nsecret\.txt\nconfig\.local\.json\n/);
  assert.match(out, /# Wildcard patterns\n\*\.log\n\*\.tmp\n/);
  assert.match(out, /# Whole directories\nnode_modules\/\ndist\/\n/);
  assert.match(out, /# In all subdirectories\n\*\*\/logs\n\*\*\/\*\.pdf\n/);
  assert.match(out, /# Exceptions \(negation\)\n!important\.log\n/);
  assert.match(out, /# Only in root\n\/TODO\.txt\n/);
  // deterministic
  assert.strictEqual(out, gi.serialize(model));
});

test('presets emit their entry groups', () => {
  const out = gi.serialize({ presets: ['dependencies', 'secrets'] });
  assert.match(out, /# Dependencies\nnode_modules\/\nvendor\/\n__pycache__\/\n\*\.pyc\n\.venv\/\nvenv\/\n/);
  assert.match(out, /# Secrets & local config\n\.env\n\.env\.local\n\*\.key\n\*\.pem\nsecrets\.yml\n/);
});

test('empty model serializes to empty string', () => {
  assert.strictEqual(gi.serialize({}), '');
  assert.strictEqual(gi.serialize(gi.emptyModel()), '');
});

test('parse classifies classic gitignore lines into the structured model', () => {
  const m = gi.parse([
    'node_modules/',
    'dist/',
    '*.log',
    'temp*',
    '**/logs',
    '**/*.pdf',
    '!important.log',
    '/TODO.txt',
    'secret.txt'
  ].join('\n'));
  assert.deepStrictEqual(m.dirs, ['node_modules/', 'dist/']);
  assert.deepStrictEqual(m.patterns, ['*.log', 'temp*']);
  assert.deepStrictEqual(m.subdirs, ['**/logs', '**/*.pdf']);
  assert.deepStrictEqual(m.exceptions, ['!important.log']);
  assert.deepStrictEqual(m.rootOnly, ['/TODO.txt']);
  assert.deepStrictEqual(m.files, ['secret.txt']);
});

test('parse preserves comments and blank lines in custom', () => {
  const m = gi.parse('# keep me\n\nweird-custom-rule\n');
  assert.ok(m.custom.includes('# keep me'));
  assert.ok(m.custom.includes(''));
  // A bare token is a "specific file" entry (the catch-all category), not custom.
  assert.ok(m.files.includes('weird-custom-rule'));
});

test('round-trip: serialize(parse(x)) preserves every rule line', () => {
  const src = [
    'node_modules/',
    'dist/',
    '*.log',
    '**/logs',
    '!important.log',
    '/TODO.txt',
    'secret.txt',
    '# a comment'
  ].join('\n') + '\n';
  const out = gi.serialize(gi.parse(src));
  for (const line of ['node_modules/', 'dist/', '*.log', '**/logs', '!important.log', '/TODO.txt', 'secret.txt', '# a comment']) {
    assert.ok(out.includes(line), `expected "${line}" in output:\n${out}`);
  }
});

test('splitEntries splits commas and newlines and trims', () => {
  assert.deepStrictEqual(gi.splitEntries('a.txt, b.txt\nc.txt'), ['a.txt', 'b.txt', 'c.txt']);
  assert.deepStrictEqual(gi.splitEntries('  '), []);
});

test('presetEntries returns the preset list or empty', () => {
  assert.deepStrictEqual(gi.presetEntries('dependencies'), gi.PRESETS.dependencies.entries);
  assert.deepStrictEqual(gi.presetEntries('nope'), []);
});

test('classify orders negations, root, subdirs, dirs, patterns, files', () => {
  assert.strictEqual(gi.classify('!x').key, 'exceptions');
  assert.strictEqual(gi.classify('/x').key, 'rootOnly');
  assert.strictEqual(gi.classify('**/x').key, 'subdirs');
  assert.strictEqual(gi.classify('x/').key, 'dirs');
  assert.strictEqual(gi.classify('*.x').key, 'patterns');
  assert.strictEqual(gi.classify('x').key, 'files');
});

test('isIgnoredPath matches files, globs, dirs, subdirs and root-only rules', () => {
  const content = [
    'secret.txt',
    '*.log',
    'node_modules/',
    '**/*.pdf',
    '/TODO.txt',
    'src/config.local.json'
  ].join('\n');
  assert.strictEqual(gi.isIgnoredPath('secret.txt', content), true);
  assert.strictEqual(gi.isIgnoredPath('sub/secret.txt', content), true);
  assert.strictEqual(gi.isIgnoredPath('app.log', content), true);
  assert.strictEqual(gi.isIgnoredPath('deep/nested/x.log', content), true);
  assert.strictEqual(gi.isIgnoredPath('node_modules/x/y.js', content), true);
  assert.strictEqual(gi.isIgnoredPath('docs/report.pdf', content), true);
  assert.strictEqual(gi.isIgnoredPath('TODO.txt', content), true);
  assert.strictEqual(gi.isIgnoredPath('sub/TODO.txt', content), false);
  assert.strictEqual(gi.isIgnoredPath('src/config.local.json', content), true);
  assert.strictEqual(gi.isIgnoredPath('src/other.json', content), false);
});

test('isIgnoredPath honors negation and backslash escapes', () => {
  const content = [
    '*.log',
    '!important.log',
    '\\*.literal'
  ].join('\n');
  assert.strictEqual(gi.isIgnoredPath('app.log', content), true);
  assert.strictEqual(gi.isIgnoredPath('important.log', content), false);
  assert.strictEqual(gi.isIgnoredPath('*.literal', content), true);
  assert.strictEqual(gi.isIgnoredPath('x.literal', content), false);
});

test('isIgnoredPath ignores comments/blank lines and normalizes separators', () => {
  const content = '# comment\n\n*.tmp\n';
  assert.strictEqual(gi.isIgnoredPath('a.tmp', content), true);
  assert.strictEqual(gi.isIgnoredPath('a\\b\\c.tmp', content), true);
  assert.strictEqual(gi.isIgnoredPath('a.txt', content), false);
});

test('isIgnoredPath returns false for empty or invalid input', () => {
  assert.strictEqual(gi.isIgnoredPath('x', ''), false);
  assert.strictEqual(gi.isIgnoredPath(null, '*.log'), false);
  assert.strictEqual(gi.isIgnoredPath('x', null), false);
});
