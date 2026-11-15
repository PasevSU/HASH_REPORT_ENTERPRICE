// Embedded-source-PDF parity: the clone appends the pages of the source PDF and
// attaches the original byte-for-byte, exactly like chronoseal/pipeline.py::_compose.
// Fixtures are written to the OS temp folder, never into the repository.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { run, EXIT_OK } from '../cli.mjs';
import { EMBED_CODES, EmbedError, embedSourcePdf, readAttachment } from '../lib/embed.mjs';
import { inspectPdf } from '../lib/normalize.mjs';
import { PdfReportBuilder } from '../lib/pdf/builder.mjs';
import { sha256Bytes } from '../lib/util.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');

/** A minimal, deliberately non-A4 PDF so a geometry change cannot hide. */
function tinyPdf({ width = 400, height = 300, lines = ['ORIGINAL DOCUMENT'] } = {}) {
  const builder = new PdfReportBuilder({ title: 'source', now: new Date(0), pageWidth: width, pageHeight: height });
  builder.beginPage();
  let y = height - 60;
  for (const text of lines) {
    builder.drawText({ size: 12, x: 40, y, text });
    y -= 20;
  }
  builder.finishPage();
  const { data } = builder.finish();
  return Buffer.from(data instanceof Uint8Array ? data : new Uint8Array(data));
}

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-embed-'));
  const source = path.join(root, 'source');
  const output = path.join(root, 'output');
  fs.mkdirSync(source);
  fs.mkdirSync(output);
  return { root, source, output };
}

test('the source pages are appended with their own geometry and the original is attached', () => {
  const report = tinyPdf({ lines: ['REPORT PAGE'] });
  const source = tinyPdf({ lines: ['ORIGINAL PAGE ONE'] });
  const result = embedSourcePdf(report, { sourceBytes: source, sourceName: 'original.pdf' });

  const readback = inspectPdf(result.bytes, { expectedPages: 2 });
  assert.equal(readback.pages, 2);
  assert.equal(result.audit.source.pages, 1);
  assert.equal(result.audit.report.pages, 1);
  assert.deepEqual(result.audit.source.geometry[0].media, [0, 0, 400, 300]);
  assert.deepEqual(result.audit.checks, {
    page_count: 2,
    geometry_preserved: true,
    attachment_sha256: sha256Bytes(source),
    source_unchanged: false,
  });

  const attachment = readAttachment(result.bytes, 'original.pdf');
  assert.ok(attachment, 'the original is reachable through the catalogue name tree');
  assert.equal(attachment.size, source.length);
  assert.equal(sha256Bytes(attachment.data), sha256Bytes(source));
  assert.match(attachment.checksum, /^[0-9a-f]{32}$/);
  assert.equal(result.audit.composed.sha256, sha256Bytes(result.bytes));
});

test('an embedded report refuses a source that is not a PDF', () => {
  const report = tinyPdf();
  assert.throws(
    () => embedSourcePdf(report, { sourceBytes: Buffer.from('not a pdf'), sourceName: 'notes.txt' }),
    (error) => error instanceof EmbedError && error.code === EMBED_CODES.SOURCE_NOT_PDF,
  );
  assert.throws(
    () => embedSourcePdf(report, { sourceBytes: Buffer.from('not a pdf'), sourceName: 'notes.pdf' }),
    (error) => error instanceof EmbedError && error.code === EMBED_CODES.SOURCE_NOT_PDF,
  );
});

test('--embed-pdf refuses a selection of more than one file', async () => {
  const { source, output } = fixture();
  const first = path.join(source, 'one.pdf');
  const second = path.join(source, 'two.pdf');
  fs.writeFileSync(first, tinyPdf());
  fs.writeFileSync(second, tinyPdf());
  await assert.rejects(
    run(['--files', `${first},${second}`, '--output', output, '--embed-pdf', '--no-archive', '--quiet'], { repoRoot }),
    /--embed-pdf needs exactly one input file/,
  );
});

test('--embed-pdf refuses an input that is not a PDF and a non-single profile', async () => {
  const { source, output } = fixture();
  const text = path.join(source, 'note.txt');
  fs.writeFileSync(text, 'plain text evidence');
  await assert.rejects(
    run(['--files', text, '--output', output, '--embed-pdf', '--no-archive', '--quiet'], { repoRoot }),
    /--embed-pdf needs a PDF input file/,
  );
  const pdf = path.join(source, 'one.pdf');
  fs.writeFileSync(pdf, tinyPdf());
  await assert.rejects(
    run(['--source', pdf, '--output', output, '--embed-pdf', '--profile', 'combo', '--no-archive', '--quiet'], { repoRoot }),
    /--embed-pdf only supports the single report profile/,
  );
});

test('an embedded report type cannot be chosen for a report that embeds nothing', async () => {
  const { source, output } = fixture();
  const pdf = path.join(source, 'one.pdf');
  fs.writeFileSync(pdf, tinyPdf());
  await assert.rejects(
    run(['--source', pdf, '--output', output, '--profile', 'single_pdf', '--no-archive', '--quiet'], { repoRoot }),
    /--profile single_pdf needs --embed-pdf/,
  );
  // The type is accepted as soon as the original really is appended.
  const result = await run(
    ['--source', pdf, '--output', output, '--profile', 'single_pdf', '--embed-pdf', '--no-archive', '--quiet'],
    { repoRoot },
  );
  assert.equal(result.exitCode, EXIT_OK);
  assert.match(path.basename(result.summary.published), /_TYP_SINGLE_PDF\.pdf$/);
});

test('a single PDF source publishes one report with the original embedded', async () => {
  const { source, output } = fixture();
  const pdf = path.join(source, 'signed.pdf');
  const original = tinyPdf({ lines: ['SIGNED ORIGINAL'] });
  fs.writeFileSync(pdf, original);

  const result = await run(['--source', pdf, '--output', output, '--embed-pdf', '--no-archive', '--quiet'], { repoRoot });
  assert.equal(result.exitCode, EXIT_OK);
  const { summary } = result;
  assert.equal(summary.status, 'PASS');
  assert.equal(summary.kind, 'SINGLE_PDF');
  assert.equal(summary.pdf_pages, summary.pages + 1);
  assert.equal(summary.embedded_pdf.source, 'signed.pdf');
  assert.equal(summary.embedded_pdf.sha256, sha256Bytes(original));
  assert.equal(summary.embedded_pdf.attachment_sha256, sha256Bytes(original));

  const published = fs.readFileSync(summary.published);
  assert.equal(inspectPdf(published, { expectedPages: summary.pdf_pages }).pages, summary.pdf_pages);
  const attachment = readAttachment(published, 'signed.pdf');
  assert.ok(attachment, 'the ORIGINAL PDF travels inside the report');
  assert.equal(sha256Bytes(attachment.data), sha256Bytes(original));

  const audit = JSON.parse(fs.readFileSync(summary.embedded_pdf.audit, 'utf8'));
  assert.equal(audit.status, 'PASS');
  assert.equal(audit.source.sha256, sha256Bytes(original));
  assert.equal(audit.composed.pages, summary.pdf_pages);
  assert.equal(audit.checks.attachment_sha256, sha256Bytes(original));
  assert.equal(audit.checks.source_unchanged, true);

  const manifest = JSON.parse(fs.readFileSync(path.join(summary.evidence_case, 'manifest.json'), 'utf8'));
  assert.equal(manifest.embedded_source_pdf.source.sha256, sha256Bytes(original));
  assert.equal(manifest.source_pdf_audit, summary.embedded_pdf.audit);
});

test('per-file mode can embed every selected PDF', async () => {
  const { source, output } = fixture();
  const first = path.join(source, 'one.pdf');
  const second = path.join(source, 'two.pdf');
  fs.writeFileSync(first, tinyPdf({ lines: ['FIRST'] }));
  fs.writeFileSync(second, tinyPdf({ lines: ['SECOND'] }));

  const result = await run([
    '--files', `${first},${second}`, '--output', output, '--per-file', '--embed-pdf', '--no-archive', '--quiet',
  ], { repoRoot });
  assert.equal(result.exitCode, EXIT_OK);
  assert.equal(result.summary.mode, 'per_file');
  assert.equal(result.summary.reports.length, 2);
  for (const report of result.summary.reports) {
    assert.equal(report.status, 'PASS');
    assert.equal(report.pdf_pages, report.pages + 1);
    assert.equal(report.embedded_pdf.attachment_sha256, report.embedded_pdf.sha256);
  }
  assert.notEqual(result.summary.reports[0].report_id, result.summary.reports[1].report_id);
});