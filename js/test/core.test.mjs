// Core contracts of the JavaScript clone: filter grammar, selection, digest basis,
// type classification, report identity, cell formatters and the evidence policy.
// Every fixture lives in the OS temp folder so nothing lands in the repository.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { resolveSelection } from '../lib/selection.mjs';
import { describe as describeFilters, matches, parse as parseFilters } from '../../tools/jsx/file-filters.mjs';
import { aggregatePayload, aggregateProof, hashSelection, localStamp } from '../lib/generate.mjs';
import { classifyArtifactFile, typeCounts } from '../lib/classify.mjs';
import { documentName, isGeneratedHashReport, reportId } from '../lib/identity.mjs';
import { digestGroup, sizeKb, timestampCell, timezoneText } from '../lib/report.mjs';
import { evidencePolicy } from '../lib/config.mjs';
import { sha256File } from '../lib/util.mjs';

const REPORT = 'RPT-20260101-000000000-AAAAAAAA_HASHREPORT_TYP_COMBO.pdf';

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-clone-'));
  fs.writeFileSync(path.join(root, 'alpha.txt'), 'alpha evidence payload');
  fs.writeFileSync(path.join(root, 'beta.log'), 'beta log line');
  fs.writeFileSync(path.join(root, 'gamma.csv'), 'a,b\n1,2');
  fs.mkdirSync(path.join(root, 'sub'));
  fs.writeFileSync(path.join(root, 'sub', 'delta.md'), 'delta');
  return root;
}

test('the filter grammar takes the GUI patterns and dedupes them', () => {
  assert.deepEqual(parseFilters(['*.pdf']), ['*.pdf']);
  assert.deepEqual(parseFilters('*.pdf;*.txt'), ['*.pdf', '*.txt']);
  assert.deepEqual(parseFilters('*eml.pdf'), ['*eml.pdf']);
  assert.deepEqual(parseFilters(['*.PDF', '*.pdf']), ['*.PDF'], 'case-insensitive dedupe');
  assert.deepEqual(parseFilters([null, '   ', '']), []);
  assert.equal(describeFilters([]), 'none');
  assert.equal(describeFilters(['*.pdf', '*.txt']), '*.pdf, *.txt');
  assert.equal(matches('mail.eml.pdf', 'mail.eml.pdf', ['*eml.pdf'], false), true);
  assert.equal(matches('mail.txt', 'mail.txt', ['*.pdf'], false), false);
  assert.equal(matches('anything.bin', 'anything.bin', [], false), true, 'no filter takes everything');
});

test('discovery honours filters and recursion, and report detection is separate', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, REPORT), 'prior report');
  const flat = resolveSelection({ source: root, filters: ['*.txt', '*.log'] });
  assert.deepEqual(flat.files.map((file) => path.basename(file)).sort(), ['alpha.txt', 'beta.log']);
  assert.equal(flat.filter_note, '*.txt, *.log');
  const deep = resolveSelection({ source: root, recursive: true });
  assert.ok(deep.files.some((file) => file.endsWith('delta.md')), 'recursion reaches subfolders');
  // Selection is raw; the CLI drops generated reports so a report never hashes itself.
  assert.deepEqual(deep.files.filter((file) => isGeneratedHashReport(file)), [path.join(root, REPORT)]);
  assert.throws(() => resolveSelection({ source: root, filters: ['*.nope'] }), /No files match/);
  assert.throws(() => resolveSelection({ files: [path.join(root, 'absent.txt')] }), /missing or not regular/);
  fs.rmSync(root, { recursive: true, force: true });
});

test('the aggregation proof matches an independent Python computation', () => {
  const root = fixture();
  const rows = hashSelection(['alpha.txt', 'beta.log', 'gamma.csv'].map((name) => path.join(root, name)), root);
  assert.deepEqual(rows.map((row) => row.name), ['alpha.txt', 'beta.log', 'gamma.csv']);
  for (const row of rows) assert.equal(row.sha256, sha256File(path.join(root, row.name)));
  // sha256("".join(sha256(bytes).hexlower + name)), recomputed with hashlib.
  assert.equal(aggregateProof(rows), '554fb5f2c3a9dc212a23f76531bf0b67c8825336843347e8b83755f111c84e96');
  const payload = aggregatePayload(rows).toString('utf8');
  assert.equal(payload, rows.map((row) => row.sha256 + row.name).join(''));
  fs.rmSync(root, { recursive: true, force: true });
});

test('artifact classification follows the Python branch order', () => {
  assert.equal(classifyArtifactFile('message.eml'), 'ORIGINAL EML');
  assert.equal(classifyArtifactFile('message.eml.sig'), 'SIGNATURE');
  assert.equal(classifyArtifactFile('message.eml.sha256'), 'SHA256 HASH');
  assert.equal(classifyArtifactFile('report.pdf'), 'PDF PROOF');
  assert.equal(classifyArtifactFile('beta.log'), 'OTHER', 'a .log file has no dedicated branch');
  assert.equal(classifyArtifactFile('raw_headers.bin'), 'RAW HEADERS');
  assert.equal(classifyArtifactFile('headers.bin'), 'BINARY');
  assert.equal(classifyArtifactFile('transport.json'), 'JSON ARTIFACT');
  assert.equal(classifyArtifactFile('gamma.csv'), 'OTHER');
  assert.deepEqual(typeCounts([{ type: 'TEXT' }, { type: 'TEXT' }, { type: 'OTHER' }]),
    [{ label: 'OTHER', count: 1 }, { label: 'TEXT', count: 2 }]);
});

test('report identity keeps the _ALL marker a suffix and stays detectable', () => {
  const now = new Date(2026, 10, 15, 8, 30, 12, 456);
  assert.match(reportId(now), /^RPT-20261115-\d{9}-[0-9A-F]{8}$/);
  const id = 'RPT-20261115-093012456-ABCDEF12';
  assert.equal(documentName({ id, kind: 'COMBO' }), `${id}_HASHREPORT_TYP_COMBO.pdf`);
  assert.equal(documentName({ id, kind: 'COMBO', recursive: true }), `${id}_HASHREPORT_TYP_COMBO_ALL.pdf`);
  assert.equal(documentName({ id, kind: 'SINGLE' }), `${id}_HASHREPORT_TYP_SINGLE.pdf`);
  assert.throws(() => documentName({ id, kind: 'FOLDER' }), /Unsupported report kind/);
  for (const name of [`${id}_HASHREPORT_TYP_COMBO_ALL.pdf`, `${id}_HASHREPORT_TYP_SINGLE.pdf`,
    `${id}-HASHREPORT.pdf`, `2026-01-01-000000000_-_${id}-HASHREPORT.pdf`]) {
    assert.ok(isGeneratedHashReport(name), `${name} is a generated report`);
  }
  for (const name of ['evidence.pdf', 'esig_pdf.pdf', 'RPT-not-a-report.pdf']) {
    assert.ok(!isGeneratedHashReport(name), `${name} is not a generated report`);
  }
});

test('cell formatters mirror the reference layout', () => {
  assert.equal(sizeKb(49), '0.048');
  assert.equal(sizeKb(1024), '1.000');
  assert.equal(digestGroup(0), 8);
  assert.equal(digestGroup(10_000), 32);
  for (const width of [0, 60, 120, 400, 999, 2000]) assert.equal(digestGroup(width) % 4, 0, `width ${width}`);
  const cell = timestampCell(new Date(2026, 10, 15, 9, 30, 12, 7));
  assert.equal(cell.split('\n').length, 2);
  assert.match(cell.split('\n')[0], /^2026-11-15$/);
  assert.match(cell.split('\n')[1], /^09:30:12/);
  assert.match(timezoneText(new Date()), /^([A-Za-z]{2,5} )?[+-]\d{2}:\d{2}$/);
  assert.match(localStamp(new Date(2026, 0, 2, 3, 4, 5)), /^2026-01-02 03:04:05$/);
});

test('evidence retention flags cannot be switched off', () => {
  assert.deepEqual(Object.keys(evidencePolicy({ evidence: {} })).sort(),
    ['keep_certificates', 'keep_tsr', 'keep_validation_json']);
  assert.throws(() => evidencePolicy({ evidence: { keep_tsr: false } }), /cannot be disabled/);
  assert.throws(() => evidencePolicy({ evidence: [] }), /JSON object/);
});
