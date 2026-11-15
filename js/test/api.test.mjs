// Contract of the programmatic API: the helpers must produce exactly the same
// reports as the CLI, and a failing file must never hide the other reports.
// Everything is written to the OS temp folder, never into the repository.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import {
  CLONE_VERSION,
  buildArgv,
  prepareOutput,
  reportForFile,
  reportForFolder,
  reportForFiles,
} from '../api.mjs';
import { EXIT_ERROR, EXIT_OK } from '../cli.mjs';
import { readAttachment } from '../lib/embed.mjs';
import { PdfReportBuilder } from '../lib/pdf/builder.mjs';

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-api-'));
  const source = path.join(root, 'source');
  const output = path.join(root, 'output');
  fs.mkdirSync(source);
  fs.writeFileSync(path.join(source, 'alpha.txt'), 'alpha evidence payload');
  fs.writeFileSync(path.join(source, 'beta.log'), 'beta log line');
  return { root, source, output };
}

test('buildArgv maps every option onto the CLI grammar', () => {
  assert.deepEqual(buildArgv({
    source: 'D:\\case',
    files: ['a.txt', 'b.txt'],
    filters: ['*.pdf', '*eml.pdf'],
    recursive: true,
    output: 'D:\\out',
    profile: 'combo',
    archive: true,
    normalise: false,
    requireLayoutPass: true,
    perFile: true,
    quiet: true,
  }), [
    '--source', 'D:\\case',
    '--files', 'a.txt,b.txt',
    '--recursive',
    '--filter', '*.pdf',
    '--filter', '*eml.pdf',
    '--output', 'D:\\out',
    '--profile', 'combo',
    '--archive',
    '--no-normalise',
    '--require-layout-pass',
    '--per-file',
    '--quiet',
  ]);
  assert.deepEqual(buildArgv({ archive: false }), ['--no-archive']);
  assert.deepEqual(buildArgv(), [], 'no options means no arguments');
  assert.equal(typeof CLONE_VERSION, 'string');
});

test('prepareOutput creates a nested output folder the CLI would refuse', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-api-'));
  const nested = path.join(root, 'a', 'b', 'c');
  const resolved = prepareOutput(nested);
  assert.equal(resolved, path.resolve(nested));
  assert.ok(fs.statSync(resolved).isDirectory());
  assert.equal(prepareOutput(nested), resolved, 'calling twice is harmless');
  fs.rmSync(root, { recursive: true, force: true });
});

test('reportForFile publishes one SINGLE report', async () => {
  const { root, source, output } = fixture();
  const result = await reportForFile(path.join(source, 'alpha.txt'), { output, archive: false });
  assert.equal(result.exitCode, EXIT_OK);
  assert.equal(result.summary.kind, 'SINGLE');
  assert.equal(result.summary.files, 1);
  assert.match(path.basename(result.published), /^RPT-\d{8}-\d{9}-[0-9A-F]{8}_HASHREPORT_TYP_SINGLE\.pdf$/);
  assert.ok(fs.existsSync(result.published));
  const manifest = JSON.parse(fs.readFileSync(path.join(result.evidenceDirectory, 'manifest.json'), 'utf8'));
  assert.equal(manifest.report_id, result.summary.report_id);
  fs.rmSync(root, { recursive: true, force: true });
});

test('reportForFolder publishes one COMBO report', async () => {
  const { root, source, output } = fixture();
  const result = await reportForFolder(source, { output, archive: false });
  assert.equal(result.exitCode, EXIT_OK);
  assert.equal(result.summary.kind, 'COMBO');
  assert.equal(result.summary.files, 2);
  assert.match(path.basename(result.published), /_HASHREPORT_TYP_COMBO\.pdf$/);
  fs.rmSync(root, { recursive: true, force: true });
});

test('reportForFiles keeps the good reports when one file cannot be read', async () => {
  const { root, source, output } = fixture();
  const missing = path.join(source, 'missing.txt');
  const result = await reportForFiles(
    [path.join(source, 'alpha.txt'), missing, path.join(source, 'beta.log')],
    { output, archive: false },
  );
  assert.equal(result.status, 'ERROR');
  assert.equal(result.files, 3);
  assert.equal(result.failed, 1);
  assert.equal(result.exitCode, EXIT_ERROR);
  assert.equal(result.reports.length, 3);

  const good = result.reports.filter((report) => report.summary);
  assert.equal(good.length, 2, 'the two readable files still produced reports');
  assert.notEqual(good[0].summary.report_id, good[1].summary.report_id);
  for (const report of good) assert.ok(fs.existsSync(report.published));
  const failed = result.reports.find((report) => !report.summary);
  assert.equal(failed.file, path.resolve(missing));
  assert.match(failed.error, /does not exist/);
  assert.equal(fs.readdirSync(output).filter((name) => name.endsWith('.pdf')).length, 2);

  await assert.rejects(
    reportForFiles([missing], { output, archive: false, continueOnError: false }),
    /does not exist/,
  );
  fs.rmSync(root, { recursive: true, force: true });
});

test('the API validates its inputs instead of publishing an empty report', async () => {
  const { root, source, output } = fixture();
  const missing = path.join(source, 'nope.txt');
  await assert.rejects(reportForFile(missing), /File does not exist/);
  await assert.rejects(reportForFolder(missing), /Folder does not exist/);
  await assert.rejects(reportForFolder(path.join(source, 'alpha.txt')), /Not a folder/);
  await assert.rejects(reportForFile(source), /Not a regular file/);
  await assert.rejects(reportForFiles([], { output }), /at least one file/);
  fs.rmSync(root, { recursive: true, force: true });
});
function tinyPdf() {
  const builder = new PdfReportBuilder({ title: 'src' });
  builder.beginPage();
  builder.drawText({ size: 12, x: 40, y: 700, text: 'ORIGINAL' });
  builder.finishPage();
  return Buffer.from(builder.finish().data);
}

test('embedPdf maps onto --embed-pdf and reportForFile embeds the original', async () => {
  assert.deepEqual(
    buildArgv({ files: ['a.pdf'], output: 'o', embedPdf: true }),
    ['--files', 'a.pdf', '--output', 'o', '--embed-pdf'],
  );
  const { source, output } = fixture();
  const pdf = path.join(source, 'original.pdf');
  const original = tinyPdf();
  fs.writeFileSync(pdf, original);

  const result = await reportForFile(pdf, { output, embedPdf: true, archive: false });
  assert.equal(result.exitCode, EXIT_OK);
  assert.equal(result.summary.pdf_pages, result.summary.pages + 1);
  assert.equal(result.summary.embedded_pdf.attachment_sha256, result.summary.embedded_pdf.sha256);

  const published = fs.readFileSync(result.summary.published);
  const attachment = readAttachment(published, 'original.pdf');
  assert.ok(attachment);
  assert.equal(Buffer.compare(attachment.data, original), 0);
});
