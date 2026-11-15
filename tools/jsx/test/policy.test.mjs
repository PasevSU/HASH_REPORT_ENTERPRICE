import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import {
  DEFAULT_PROFILE,
  PROFILE_FIELDS,
  auditOptions,
  toDict,
} from '../report-profile.mjs';
import {
  assertTableFragment,
  formatDigest,
  formatFileSize,
  normalizeText,
  pyInt,
} from '../presentation-policy.mjs';
import {
  keepHeadingWithFirstParagraph,
  keepShortSection,
  paginationConfig,
} from '../pagination-policy.mjs';

const REF = JSON.parse(fs.readFileSync(new URL('./fixtures/styles.json', import.meta.url), 'utf8'));

/** Python reference errors are recorded as "<ExceptionType>: <message>". */
function referenceError(reference) {
  const text = String(reference.error);
  const cut = text.indexOf(': ');
  return { kind: text.slice(0, cut), message: text.slice(cut + 2) };
}

function check(fn, reference) {
  if (Object.hasOwn(reference, 'expect')) {
    assert.deepEqual(fn(reference.input), reference.expect, JSON.stringify(reference.input));
    return;
  }
  const expected = referenceError(reference);
  assert.throws(() => fn(reference.input), (error) => {
    if (expected.kind === 'ValueError') {
      assert.equal(error.message, expected.message);
    } else {
      assert.ok(error instanceof TypeError, 'expected TypeError, got ' + error.constructor.name);
    }
    return true;
  });
}

test('presentation: formatFileSize matches every reference case', () => {
  assert.equal(REF.presentation.file_size.length, 13);
  for (const reference of REF.presentation.file_size) check(formatFileSize, reference);
});

test('presentation: formatDigest matches every reference case', () => {
  for (const reference of REF.presentation.digest) check(formatDigest, reference);
});

test('presentation: normalizeText matches every reference case', () => {
  for (const reference of REF.presentation.text) check(normalizeText, reference);
});

test('presentation: assertTableFragment matches every reference case', () => {
  for (const reference of REF.presentation.fragment) check(assertTableFragment, reference);
});

test('presentation: pyInt reproduces Python int() on the recorded inputs', () => {
  assert.equal(pyInt(3.9), 3);
  assert.equal(pyInt('5_000'), 5000);
  assert.throws(() => pyInt(null), TypeError);
  assert.equal(formatFileSize('5_000'), '5 000 bytes');
});

test('profile: defaults serialise exactly like the Python dataclass', () => {
  assert.deepEqual(toDict(), REF.profile.default.to_dict);
  assert.deepEqual(auditOptions(), REF.profile.default.audit_options);
  assert.deepEqual(toDict(DEFAULT_PROFILE), REF.profile.default.to_dict);
  assert.equal(PROFILE_FIELDS.length, Object.keys(REF.profile.default.to_dict).length);
});

test('profile: audit options honour overridden margins and word floor', () => {
  const custom = { ...DEFAULT_PROFILE, name: 'Custom', version: '9.9', left_mm: 15, min_body_words: 30 };
  assert.deepEqual(toDict(custom), REF.profile.custom.to_dict);
  assert.deepEqual(auditOptions(custom), REF.profile.custom.audit_options);
});

test('profile: unknown profile objects are rejected instead of guessed', () => {
  assert.throws(() => toDict(null), TypeError);
  assert.throws(() => auditOptions({}), /missing: /);
  assert.throws(() => auditOptions({ ...DEFAULT_PROFILE, left_mm: '20' }), /must be a number: left_mm/);
  assert.throws(() => toDict({ ...DEFAULT_PROFILE, name: null }), /must be a string: name/);
});

test('pagination: config is the raw PAGINATION block', () => {
  assert.deepEqual(paginationConfig(), REF.pagination.config);
  assert.equal(paginationConfig().short_table_max_rows, 8);
});

test('pagination: short sections stay together, long ones must be split', () => {
  for (const reference of REF.pagination.keep) {
    const { rows } = reference;
    if (Object.hasOwn(reference, 'expect')) {
      assert.deepEqual(reference.expect, ['KeepTogether']);
      assert.deepEqual(keepShortSection(rows), { strategy: 'keep', gapPt: 4 }, 'rows=' + rows);
    } else {
      const expected = referenceError(reference);
      assert.equal(expected.kind, 'ValueError');
      assert.throws(() => keepShortSection(rows), (error) => {
        assert.equal(error.message, expected.message);
        return true;
      });
    }
  }
});

test('pagination: heading keeps with the first paragraph', () => {
  assert.deepEqual(REF.pagination.heading.expect, ['KeepTogether']);
  assert.deepEqual(keepHeadingWithFirstParagraph(), { strategy: 'keep', gapPt: 4 });
});

test('pagination: a non-table argument is a type error, not a silent split', () => {
  assert.equal(referenceError(REF.pagination.non_table).kind, 'TypeError');
  assert.throws(() => keepShortSection('3'), TypeError);
  assert.throws(() => keepShortSection(Number.NaN), TypeError);
  assert.throws(() => keepShortSection(3.5), TypeError);
});

test('pagination: zero-row and boundary counts are handled deterministically', () => {
  assert.deepEqual(keepShortSection(0), { strategy: 'keep', gapPt: 4 });
  assert.deepEqual(keepShortSection(8), { strategy: 'keep', gapPt: 4 });
  assert.throws(() => keepShortSection(9), /Long table must be placed as separate splittable flowables/);
});