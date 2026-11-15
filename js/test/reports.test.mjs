// One module per report type. These tests pin the registry, the section order
// each type prints, and the page-text checksums that make every page of every
// type self-verifying: a footer hash must equal a fresh recomputation over the
// body text the renderer actually drew for that page.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { generateReport } from '../lib/generate.mjs';
import { listProfiles, loadProfile, reportType } from '../lib/report.mjs';
import { documentName, isGeneratedHashReport } from '../lib/identity.mjs';
import { REPORT_MODULES, loadReportModule, reportModuleIds } from '../lib/reports/index.mjs';
import { getSection, sectionIds } from '../lib/reports/sections.mjs';
import {
  ALL_TEXT_ALGORITHMS,
  PAGE_TEXT_ALGORITHMS,
  documentDigests,
  normalisePageText,
  pageDigests,
} from '../lib/reports/checksums.mjs';

const HEADING = 'PAGE TEXT HASHES (UTF-8 / NFC; footer excluded)';

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'chronoseal-types-'));
  const source = path.join(root, 'source');
  fs.mkdirSync(path.join(source, 'nested'), { recursive: true });
  fs.writeFileSync(path.join(source, 'alpha.txt'), 'alpha evidence payload');
  fs.writeFileSync(path.join(source, 'beta.log'), 'beta log line');
  fs.writeFileSync(path.join(source, 'nested', 'gamma.csv'), 'a,b\n1,2');
  return { root, source };
}

/** Body text of one drawn page, captured exactly as the hashing pass saw it. */
function bodyTextsOf(result) {
  return result.builder.pages.map((page) => normalisePageText(
    page.items.filter((item) => item.band !== 'footer').map((item) => item.text),
  ));
}

function footerTexts(page) {
  return page.items.filter((item) => item.band === 'footer').map((item) => item.text);
}

/** Generate one report of the given profile over the shared fixture folder. */
function build(profileId, extra = {}) {
  const { root, source } = fixture();
  const files = [
    path.join(source, 'alpha.txt'),
    path.join(source, 'beta.log'),
    path.join(source, 'nested', 'gamma.csv'),
  ];
  const result = generateReport({
    files: profileId === 'single_pdf' ? files.slice(0, 1) : files,
    root: source,
    profileId,
    selection: { source, kind: 'current_folder', recursive: true, filters: [] },
    generatedAt: new Date('2026-08-04T09:15:00Z'),
    ...extra,
  });
  fs.rmSync(root, { recursive: true, force: true });
  return result;
}

test('every report profile has its own module and every section resolves', () => {
  const profiles = listProfiles().sort();
  assert.deepEqual(reportModuleIds().sort(), profiles, 'one module per profile, no orphans');

  for (const id of profiles) {
    const module = loadReportModule(id);
    assert.equal(module.id, id);
    assert.ok(module.title.length > 0, `${id} has a title`);
    assert.ok(['single_file', 'current_folder', 'recursive_folder'].includes(module.input_scope));
    assert.ok(module.sections.length > 0, `${id} prints at least one section`);
    for (const sectionId of module.sections) {
      assert.ok(sectionIds().includes(sectionId), `${id} references a known section: ${sectionId}`);
      assert.equal(typeof getSection(sectionId).build, 'function');
    }
  }

  assert.notEqual(REPORT_MODULES.get('single'), REPORT_MODULES.get('volume'), 'types are not aliases');
  assert.equal(loadReportModule('does_not_exist'), null);
  assert.throws(() => getSection('does_not_exist'), /unknown/i);
});

test('every report type prints its declared sections in order', () => {
  for (const id of reportModuleIds()) {
    const result = build(id);
    const module = loadReportModule(id);
    assert.equal(result.reportModule, id, `${id} is rendered by its own module`);
    assert.equal(result.profile, id);
    assert.ok(result.pageCount >= 2, `${id} produces a multi-page document`);

    const printed = result.sections.filter((section) => module.sections.includes(section));
    assert.deepEqual(printed, [...module.sections], `${id} prints its sections in declaration order`);
  }
});

test('every page of every type carries verifiable page-text hashes', () => {
  for (const id of reportModuleIds()) {
    const result = build(id);
    const bodies = bodyTextsOf(result);
    assert.equal(bodies.length, result.pageCount, `${id}: every drawn page is hashed`);

    for (const [index, page] of result.builder.pages.entries()) {
      const footer = footerTexts(page);
      assert.ok(footer.includes(HEADING), `${id} page ${index + 1}: footer hash heading`);

      const digests = pageDigests(bodies[index]);
      for (const label of PAGE_TEXT_ALGORITHMS) {
        const expected = `${label}: ${digests[label].toUpperCase()}`;
        assert.ok(
          footer.includes(expected),
          `${id} page ${index + 1}: ${label} matches its recomputed body digest`,
        );
      }
    }
  }
});

test('the document digest covers the same body texts the pages hash', () => {
  for (const id of ['single', 'combo_all']) {
    const result = build(id);
    assert.ok(result.textChecksums, `${id} reports its text checksums`);
    assert.deepEqual(
      Object.keys(result.textChecksums.document).sort(),
      [...ALL_TEXT_ALGORITHMS].sort(),
      `${id} hashes the document with all eleven algorithms`,
    );
    assert.deepEqual(
      result.textChecksums.document,
      documentDigests(bodyTextsOf(result).slice(0, result.textChecksums.scopePages)),
      `${id}: published document digests recompute from the pages in scope`,
    );
  }
});

test('the checksum appendix never hashes itself', () => {
  for (const id of reportModuleIds()) {
    const result = build(id);
    const { scopePages } = result.textChecksums;
    assert.ok(scopePages >= 1, `${id}: at least one page is in scope`);
    assert.ok(
      scopePages < result.pageCount,
      `${id}: the appendix is outside the hashed scope (${scopePages}/${result.pageCount})`,
    );
    for (const page of result.builder.pages.slice(scopePages)) {
      assert.ok(
        footerTexts(page).includes(HEADING),
        `${id}: appendix pages still carry footer hashes`,
      );
    }
  }
});

test('the single PDF type documents the embedded source before the note', () => {
  const result = build('single_pdf');
  const module = loadReportModule('single_pdf');
  assert.deepEqual([...module.sections], [
    'timestamp_record',
    'source_pdf_evidence',
    'generation_note',
    'legal_documentation',
    'text_checksums',
  ]);
  assert.equal(result.kind, 'SINGLE_PDF');
  assert.ok(result.sections.includes('source_pdf_evidence'));
});

test('the file information report prints evidence without the legal reprint', () => {
  const result = build('file_information_report');
  assert.ok(result.sections.includes('text_checksums'));
  assert.ok(result.sections.includes('file_information'));
  assert.ok(!result.sections.includes('legal_documentation'));
  assert.equal(result.kind, 'FILE_INFORMATION');
});

test('every type publishes under its own marker and never becomes evidence', () => {
  const sampleId = 'RPT-20260804-091500000-ABCDEF12';
  const kinds = reportModuleIds().map((id) => reportType(loadProfile(id)));
  assert.deepEqual([...kinds].sort(), [
    'COMBO', 'COMBO_ALL', 'FILE_INFORMATION', 'SINGLE', 'SINGLE_PDF', 'VOLUME',
  ]);
  for (const kind of kinds) {
    const recursive = kind === 'COMBO_ALL';
    const name = documentName({ id: sampleId, kind: kind.replace(/_ALL$/, ''), recursive });
    assert.equal(name, `${sampleId}_HASHREPORT_TYP_${kind}.pdf`);
    assert.ok(isGeneratedHashReport(name), `${name} is never hashed as evidence`);
  }
});
test('text checksums can be turned off for a lightweight document', () => {
  const result = build('single', { textChecksums: false });
  assert.equal(result.textChecksums, null);
  for (const page of result.builder.pages) {
    assert.ok(!footerTexts(page).includes(HEADING), 'no footer hash block was drawn');
  }
});