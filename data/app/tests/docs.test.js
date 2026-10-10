'use strict';
const test = require('node:test');
const assert = require('node:assert');
const docs = require('../lib/docs');

test('readme renders the project identity and mandatory links', () => {
  const out = docs.readme({ name: 'my-app', repo: 'pasevsu-dev/my-app', description: 'Does a thing.' });
  assert.ok(out.startsWith('# my-app\n'), out.slice(0, 40));
  assert.match(out, /\[Contributing\]\(CONTRIBUTING\.md\)/);
  assert.match(out, /\[Security policy\]\(SECURITY\.md\)/);
  assert.match(out, /pasevsu-dev\/my-app/);
  assert.match(out, /PasevSU-DEV/);
});

test('readme falls back to defaults when metadata is missing', () => {
  const out = docs.readme({});
  assert.ok(out.includes('# project\n'));
  assert.ok(out.includes('Denislav Pasev'));
  assert.ok(out.includes('Apache-2.0'));
});

test('contributing includes setup, commands and disclosure redirect', () => {
  const out = docs.contributing({ name: 'my-app', repo: 'pasevsu-dev/my-app', packageManager: 'npm' });
  assert.match(out, /# Contributing to my-app/);
  assert.match(out, /npm install/);
  assert.match(out, /npm test/);
  assert.match(out, /SECURITY\.md/);
});

test('security includes supported versions and reporting channel', () => {
  const out = docs.security({ repo: 'pasevsu-dev/my-app' });
  assert.match(out, /# Security Policy/);
  assert.match(out, /security\/advisories\/new/);
  assert.match(out, /5 business days/);
});

test('generateAll returns all three mandatory documents', () => {
  const out = docs.generateAll({ name: 'x', repo: 'pasevsu-dev/x' });
  assert.deepStrictEqual(Object.keys(out).sort(), ['CONTRIBUTING.md', 'README.md', 'SECURITY.md'].sort());
  for (const f of Object.keys(out)) assert.ok(out[f].length > 0, f);
});

test('render is deterministic and returns null for unknown files', () => {
  const meta = { name: 'x', repo: 'pasevsu-dev/x' };
  assert.strictEqual(docs.render('README.md', meta), docs.readme(meta));
  assert.strictEqual(docs.render('nope.md', meta), null);
  assert.strictEqual(docs.readme(meta), docs.readme(meta));
});

test('normalizeMeta coerces and fills scalar fields', () => {
  const m = docs.normalizeMeta({ name: '  a  ', stack: 'Electron' });
  assert.strictEqual(m.name, 'a');
  assert.deepStrictEqual(m.stack, ['Electron']);
  assert.strictEqual(m.org, 'PasevSU-DEV');
});
