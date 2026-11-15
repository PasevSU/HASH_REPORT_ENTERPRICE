// End-to-end behaviour of the clone: a real report run, the PDF/A-2b stage, the
// layout gate, the evidence folder, the durable archive and the CLI contract.
// Every report is written to the OS temp folder, never into the repository.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { run, parseArgs, EXIT_OK } from '../cli.mjs';
import { archiveReport, readArchivedFile } from '../lib/archive.mjs';
import { inspectPdf } from '../lib/normalize.mjs';
import { fromUtf8 } from '../lib/util.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-run-'));
  const source = path.join(root, 'source');
  const output = path.join(root, 'output');
  fs.mkdirSync(source);
  fs.mkdirSync(output);
  fs.writeFileSync(path.join(source, 'alpha.txt'), 'alpha evidence payload');
  fs.writeFileSync(path.join(source, 'beta.log'), 'beta log line');
  fs.writeFileSync(path.join(source, 'gamma.csv'), 'a,b\n1,2');
  return { root, source, output };
}

test('a folder run publishes a PDF/A-2b report with evidence', async () => {
  const { root, source, output } = fixture();
  const result = await run(['--source', source, '--output', output, '--no-archive', '--quiet'], { repoRoot });
  assert.equal(result.exitCode, EXIT_OK);
  const { summary } = result;
  assert.equal(summary.status, 'PASS');
  assert.deepEqual(summary.pdfa, { part: '2', conformance: 'B' });
  assert.equal(summary.layout.status, 'PASS');
  assert.match(path.basename(summary.published), /^RPT-\d{8}-\d{9}-[0-9A-F]{8}_HASHREPORT_TYP_COMBO\.pdf$/);
  assert.match(summary.aggregate_proof, /^[0-9a-f]{64}$/);
  assert.equal(summary.archive, null, '--no-archive must not create an archive folder');

  const published = path.join(output, path.basename(summary.published));
  const bytes = fs.readFileSync(published);
  assert.equal(bytes.subarray(0, 5).toString('latin1'), '%PDF-');
  const readback = inspectPdf(bytes, { expectedPages: summary.pages });
  assert.equal(readback.pages, summary.pages);
  assert.equal(readback.hasMetadata, true);
  assert.equal(readback.hasOutputIntent, true);

  for (const name of ['manifest.json', 'storage-identity.json', 'layout-audit.json']) {
    assert.ok(fs.existsSync(path.join(summary.evidence_case, name)), `${name} is written`);
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(summary.evidence_case, 'manifest.json'), 'utf8'));
  assert.equal(manifest.report_id, summary.report_id);
  assert.equal(manifest.final_sha256, summary.pdf_sha256);
  assert.equal(manifest.selection_count, 3);
  assert.equal(manifest.signature, 'NOT SIGNED - the JavaScript clone has no DocTimeStamp stage');
  fs.rmSync(root, { recursive: true, force: true });
});

test('filters narrow a folder run and an explicit selection makes a SINGLE report', async () => {
  const { root, source, output } = fixture();
  const filtered = await run(['--source', source, '--filter', '*.txt', '--output', output, '--no-archive', '--quiet'],
    { repoRoot });
  assert.equal(filtered.exitCode, EXIT_OK);
  assert.equal(filtered.summary.rows, undefined);
  assert.match(filtered.summary.aggregate_proof, /^[0-9a-f]{64}$/);

  const single = await run(['--files', path.join(source, 'beta.log'), '--output', output, '--no-archive', '--quiet'],
    { repoRoot });
  assert.equal(single.exitCode, EXIT_OK);
  assert.match(path.basename(single.summary.published), /_HASHREPORT_TYP_SINGLE\.pdf$/);
  assert.deepEqual(fs.readdirSync(output).filter((name) => name.endsWith('.pdf')).length, 2);

  // The same selection keeps the SINGLE profile even when --source names a
  // folder: the folder only anchors the relative paths of the selection.
  const anchored = await run(['--source', source, '--files', path.join(source, 'alpha.txt'),
    '--output', output, '--no-archive', '--quiet'], { repoRoot });
  assert.equal(anchored.exitCode, EXIT_OK);
  assert.equal(anchored.summary.kind, 'SINGLE');
  assert.match(path.basename(anchored.summary.published), /_HASHREPORT_TYP_SINGLE\.pdf$/);
  fs.rmSync(root, { recursive: true, force: true });
});

test('invalid argument combinations are refused before any file is written', async () => {
  const { root, source } = fixture();
  await assert.rejects(run([], { repoRoot }), /--source or --files is required/);
  await assert.rejects(run(['--files', path.join(source, 'alpha.txt'), '--filter', '*.txt'], { repoRoot }),
    /nothing to filter/);
  await assert.rejects(run(['--source', path.join(source, 'alpha.txt'), '--recursive'], { repoRoot }),
    /--recursive needs a folder/);
  await assert.rejects(run(['--source', path.join(root, 'absent')], { repoRoot }), /Source does not exist/);
  assert.throws(() => parseArgs(['--filter']), /--filter requires a value/);
  fs.rmSync(root, { recursive: true, force: true });
});

test('the archive publishes once and then refuses a duplicate report id', async () => {
  const { root, source, output } = fixture();
  const result = await run(['--source', source, '--output', output, '--no-archive', '--quiet'], { repoRoot });
  const archiveRoot = path.join(root, 'archive');
  const databasePath = path.join(root, 'archive', 'archive.sqlite3');
  const pdf = result.summary.published;

  const archived = archiveReport({
    archiveRoot,
    databasePath,
    reportPdf: pdf,
    evidenceDirectory: result.summary.evidence_case,
    manifest: { report_id: 'ignored', status: 'PASS' },
    reportName: path.basename(result.summary.published),
  });
  assert.ok(fs.existsSync(path.join(archived.archive_directory, path.basename(result.summary.published))));
  assert.ok(fs.existsSync(path.join(archived.archive_directory, 'manifest.json')));
  assert.ok(fs.existsSync(path.join(archived.archive_directory, 'run.log')));
  assert.ok(fs.existsSync(path.join(archived.archive_directory, 'evidence', 'manifest.json')));
  const stored = readArchivedFile(databasePath, result.summary.report_id, 'evidence/manifest.json');
  assert.ok(stored, 'the archived evidence manifest is stored in SQLite');
  assert.equal(JSON.parse(fromUtf8(stored.data)).report_id, result.summary.report_id);

  assert.throws(() => archiveReport({
    archiveRoot,
    databasePath,
    reportPdf: pdf,
    evidenceDirectory: result.summary.evidence_case,
    reportName: path.basename(result.summary.published),
  }), /refusing overwrite/);
  fs.rmSync(root, { recursive: true, force: true });
});

test('a second recursive run never hashes the report it produced first', async () => {
  const { root, source, output } = fixture();
  const first = await run(['--source', source, '--recursive', '--output', output, '--no-archive', '--quiet'], { repoRoot });
  assert.equal(first.exitCode, EXIT_OK);
  const second = await run(['--source', source, '--recursive', '--output', output, '--no-archive', '--quiet'], { repoRoot });
  assert.equal(second.exitCode, EXIT_OK);
  const manifest = JSON.parse(fs.readFileSync(path.join(second.summary.evidence_case, 'manifest.json'), 'utf8'));
  assert.ok(manifest.selection_excluded_reports >= 1, 'the previous report is excluded from the evidence set');
  assert.equal(manifest.selection_count, second.summary.files);
  assert.ok(second.summary.files >= 3, 'the real evidence files are still covered');
  fs.rmSync(root, { recursive: true, force: true });
});

test('per-file mode publishes one SINGLE report per selected file', async () => {
  const { root, source, output } = fixture();
  const result = await run(['--source', source, '--output', output, '--per-file', '--no-archive', '--quiet'], { repoRoot });
  assert.equal(result.exitCode, EXIT_OK);
  const { summary } = result;
  assert.equal(summary.mode, 'per_file');
  assert.equal(summary.files, 3);
  assert.equal(summary.failed, 0);
  assert.equal(summary.reports.length, 3);

  const ids = new Set();
  const proofs = new Set();
  const cases = new Set();
  for (const report of summary.reports) {
    assert.equal(report.status, 'PASS');
    assert.equal(report.kind, 'SINGLE', 'every file gets its own SINGLE report');
    assert.equal(report.files, 1, 'a per-file report covers exactly one file');
    assert.match(path.basename(report.published), /_HASHREPORT_TYP_SINGLE\.pdf$/);
    ids.add(report.report_id);
    proofs.add(report.pdf_sha256);
    cases.add(report.evidence_case);
  }
  assert.equal(ids.size, 3, 'report numbers are never shared between files');
  assert.equal(proofs.size, 3, 'each report has its own aggregate proof');
  assert.equal(cases.size, 3, 'each report keeps its own evidence case');
  assert.deepEqual(result.published.sort(), summary.reports.map((r) => r.published).sort());
  assert.equal(fs.readdirSync(output).filter((name) => name.endsWith('.pdf')).length, 3);
  fs.rmSync(root, { recursive: true, force: true });
});

test('per-file mode honours an explicit file list', async () => {
  const { root, source, output } = fixture();
  const selection = [path.join(source, 'alpha.txt'), path.join(source, 'gamma.csv')].join(',');
  const result = await run(['--files', selection, '--output', output, '--per-file', '--no-archive', '--quiet'], { repoRoot });
  assert.equal(result.exitCode, EXIT_OK);
  assert.equal(result.summary.reports.length, 2);
  assert.match(path.basename(result.summary.reports[0].published), /_HASHREPORT_TYP_SINGLE\.pdf$/);
  assert.notEqual(result.summary.reports[0].report_id, result.summary.reports[1].report_id);
  fs.rmSync(root, { recursive: true, force: true });
});

test('per-file mode refuses a forced report profile', async () => {
  const { root, source, output } = fixture();
  await assert.rejects(
    run(['--source', source, '--output', output, '--per-file', '--profile', 'combo', '--quiet'], { repoRoot }),
    /--per-file cannot be combined with --profile/,
  );
  assert.equal(fs.readdirSync(output).length, 0, 'a refused run publishes nothing');
  fs.rmSync(root, { recursive: true, force: true });
});