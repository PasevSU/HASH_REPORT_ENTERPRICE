import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as ff from '../file-filters.mjs';
import { fnmatchcase, translate } from '../lib/glob.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(fs.readFileSync(path.join(here, 'fixtures', 'parity.json'), 'utf8'));

function withEnvCase(flag, fn) {
  const previous = process.env[ff.ENV_CASE];
  if (flag === null || flag === undefined) delete process.env[ff.ENV_CASE];
  else process.env[ff.ENV_CASE] = flag;
  try {
    return fn();
  } finally {
    if (previous === undefined) delete process.env[ff.ENV_CASE];
    else process.env[ff.ENV_CASE] = previous;
  }
}

test('glob: * spans path separators like Python fnmatch', () => {
  assert.equal(fnmatchcase('invoices/2026/scan_0001.eml.pdf', '*eml.pdf'), true);
  assert.equal(fnmatchcase('invoices/2026/scan_0001.pdf', '*eml.pdf'), false);
  assert.equal(translate('*.pdf').source, '^(?:[\\s\\S]*\\.pdf)$');
});

test('glob: character sets, ranges and negation follow fnmatchcase', () => {
  assert.equal(fnmatchcase('a1.pdf', 'a[0-9].pdf'), true);
  assert.equal(fnmatchcase('ab.pdf', 'a[0-9].pdf'), false);
  assert.equal(fnmatchcase('ab.pdf', 'a[!0-9].pdf'), true);
  assert.equal(fnmatchcase('a1.pdf', 'a[!0-9].pdf'), false);
  assert.equal(fnmatchcase('a[', 'a['), true);
  assert.equal(fnmatchcase('a$', 'a$'), true);
});

test('normalize splits on , ; and newlines and trims', () => {
  for (const item of fixture.file_filters.normalize) {
    assert.deepEqual(ff.normalize(item.input), item.expect, JSON.stringify(item.input));
  }
});

test('parse de-duplicates case-insensitively across fields', () => {
  for (const item of fixture.file_filters.parse) {
    assert.deepEqual(ff.parse(item.input), item.expect, JSON.stringify(item.input));
  }
});

test('matches matches the Python reference on every recorded case', () => {
  for (const item of fixture.file_filters.matches) {
    const actual = withEnvCase(item.env_case, () => ff.matches(item.name, item.rel, item.filters));
    assert.equal(actual, item.expect,
      `${JSON.stringify(item.name)} rel=${JSON.stringify(item.rel)} filters=${JSON.stringify(item.filters)} env=${item.env_case}`);
  }
});

test('matches keeps the chainable *eml.pdf behaviour from the brief', () => {
  assert.equal(ff.matches('scan_0001.eml.pdf', 'invoices/2026/scan_0001.eml.pdf', ['*eml.pdf']), true);
  assert.equal(ff.matches('scan_0001.pdf', 'invoices/2026/scan_0001.pdf', ['*eml.pdf']), false);
  assert.equal(ff.matches('anything.txt', '', []), true);
  assert.equal(ff.matches('anything.txt', '', ['*.pdf', '*.eml']), false);
});

test('describe summarises filters as a comma list or "none"', () => {
  for (const item of fixture.file_filters.describe) {
    assert.equal(ff.describe(item.input), item.expect, JSON.stringify(item.input));
  }
});

test('audit payload is byte-identical to the Python reference', () => {
  for (const item of fixture.file_filters.audit) {
    withEnvCase(null, () => {
      assert.deepEqual(ff.auditPayload(item.input), item.expect, JSON.stringify(item.input));
    });
  }
});

test('to_env round-trips through JSON exactly', () => {
  for (const item of fixture.file_filters.to_env) {
    assert.equal(ff.toEnv(item.input), item.expect, JSON.stringify(item.input));
  }
});

test('from_env accepts JSON lists, bare strings and malformed JSON', () => {
  withEnvCase(null, () => {
    process.env[ff.ENV_FILTERS] = '["*.pdf","*.eml"]';
    assert.deepEqual(ff.fromEnv(), ['*.pdf', '*.eml']);
    process.env[ff.ENV_FILTERS] = '*.pdf;*.eml';
    assert.deepEqual(ff.fromEnv(), ['*.pdf', '*.eml']);
    process.env[ff.ENV_FILTERS] = '["*.pdf"';
    assert.deepEqual(ff.fromEnv(), [parseBracket('["*.pdf"')]);
    process.env[ff.ENV_FILTERS] = '';
    assert.deepEqual(ff.fromEnv(), []);
    delete process.env[ff.ENV_FILTERS];
  });
});

function parseBracket(raw) {
  return ff.normalize(raw)[0];
}

test('case sensitive switch honours 1/true/yes/on', () => {
  for (const flag of ['1', 'true', 'YES', 'on']) {
    withEnvCase(flag, () => assert.equal(ff.caseSensitive(), true, flag));
  }
  for (const flag of ['0', 'false', '', 'off']) {
    withEnvCase(flag, () => assert.equal(ff.caseSensitive(), false, flag));
  }
});