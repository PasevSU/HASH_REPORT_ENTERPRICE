/**
 * Report generation for the JS clone: selection -> hashes -> PDF bytes.
 *
 * The digest basis is deliberately identical to hash_report_core.py, so a clone
 * report's aggregate proof can be recomputed by the Python verifier: for every
 * entry in report order, concatenate the hexadecimal SHA-256 digest and the
 * displayed relative name, UTF-8 encode, then digest the whole stream.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { PdfReportBuilder } from './pdf/builder.mjs';
import { ReportLayout } from './pdf/layout.mjs';
import {
  loadModule,
  loadProfile,
  renderReport,
  reportType,
  timezoneText,
} from './report.mjs';
import {
  hardwareId,
  operatingSystemName,
  reportId as newReportId,
  reportFileName,
  userInformation,
  volumeInformation,
} from './identity.mjs';
import { casefold, pad, posix, sha256File, sha256Bytes } from './util.mjs';
import { loadStyles } from '../../tools/jsx/style-loader.mjs';
import {
  ALL_TEXT_ALGORITHMS,
  PAGE_TEXT_ALGORITHMS,
  documentDigests,
  footerHashLines,
  normalisePageText,
  pageDigests,
  placeholderDigests,
} from './reports/checksums.mjs';
import { loadReportModule, renderReportSections } from './reports/index.mjs';

/** The eleven evidence algorithms hash_report_core.py refuses to substitute. */
export const COURT_ALGORITHMS = Object.freeze([
  ['MD5', 'md5'], ['SHA-1', 'sha1'], ['SHA-224', 'sha224'], ['SHA-256', 'sha256'],
  ['SHA-384', 'sha384'], ['SHA-512', 'sha512'], ['SHA3-224', 'sha3-224'],
  ['SHA3-256', 'sha3-256'], ['SHA3-384', 'sha3-384'], ['SHA3-512', 'sha3-512'],
  ['RIPEMD-160', 'ripemd160'],
]);

export const AGGREGATION_METHOD =
  'Per entry in report order: lowercase SHA-256 digest followed by the displayed relative name, '
  + 'concatenated without separators, UTF-8 encoded, then digested.';

export function courtHashes(data) {
  const out = {};
  for (const [label, algorithm] of COURT_ALGORITHMS) {
    try {
      out[label] = createHash(algorithm).update(data).digest('hex');
    } catch (error) {
      throw new Error(`Required hash algorithm unavailable: ${label}; report blocked (${error.message})`);
    }
  }
  return out;
}

export function aggregatePayload(rows) {
  return Buffer.from(rows.map((row) => `${row.sha256}${row.name}`).join(''), 'utf8');
}

export function aggregateProof(rows) {
  return sha256Bytes(aggregatePayload(rows));
}

/** Local wall-clock timestamp: the report records when the operator ran it. */
export function localStamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + ` ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function describeFile(file, root) {
  const stats = fs.statSync(file);
  const relative = posix(path.relative(root, file));
  const created = stats.birthtimeMs ? stats.birthtime : stats.ctime;
  return {
    path: file,
    name: relative || path.basename(file),
    size_bytes: stats.size,
    created_at: created,
    modified_at: stats.mtime,
    created: localStamp(created),
    modified: localStamp(stats.mtime),
    sha256: sha256File(file),
  };
}

/** Hash the selection in deterministic order (case-folded POSIX relative path). */
export function hashSelection(files, root) {
  const rows = files.map((file) => describeFile(file, root));
  rows.sort((a, b) => (casefold(a.name) < casefold(b.name) ? -1 : casefold(a.name) > casefold(b.name) ? 1 : 0));
  return rows;
}

/**
 * Build the report document.
 *
 * @returns {{bytes: Uint8Array, pageCount: number, sections: string[],
 *            reportId: string, fileName: string, kind: string, rows: object[],
 *            documentProof: string, courtHashes: object, generatedAt: string}}
 */
export function generateReport({
  files,
  root,
  selection = {},
  profileId = 'combo',
  reportId: requestedId = null,
  generatedAt = new Date(),
  styles = null,
  hardwareId: requestedHardwareId = '',
  author = 'ChronoSeal Enterprise (JavaScript clone)',
  embeddedPdf = null,
  textChecksums = true,
} = {}) {
  if (!Array.isArray(files) || !files.length) throw new Error('A report needs at least one input file');
  const hardware = requestedHardwareId || hardwareId();
  const resolvedStyles = styles || loadStyles();
  const profile = loadProfile(profileId);
  const recursive = selection.recursive === true;
  const kind = reportType(profile, { recursive });
  const id = requestedId || newReportId(generatedAt);
  const rows = hashSelection(files, root || path.dirname(files[0]));
  const documentProof = aggregateProof(rows);
  const hashes = courtHashes(aggregatePayload(rows));

  const modules = new Map();
  for (const moduleId of profile.modules) modules.set(moduleId, loadModule(moduleId));

  const filters = selection.filters || [];
  const sourceFolder = root || path.dirname(files[0]);
  const user = userInformation();
  const context = {
    reportId: id,
    reportType: kind,
    generatedAt: localStamp(generatedAt),
    timezone: timezoneText(generatedAt),
    source: selection.source || sourceFolder,
    inputKind: selection.kind || 'current_folder',
    mode: selection.mode || (files.length > 1 ? 'combo' : 'single'),
    recursive,
    filters,
    filterText: filters.length ? filters.join(', ') : 'none - every file in the folder',
    files: rows,
    totalSizeKb: (rows.reduce((total, row) => total + row.size_bytes, 0) / 1024).toFixed(3),
    unreadable: selection.unreadable || [],
    documentProof,
    aggregationMethod: AGGREGATION_METHOD,
    courtHashes: hashes,
    hardwareId: hardware,
    volume: volumeInformation(sourceFolder),
    embeddedPdf: embeddedPdf || null,
    checksums: null,
    user: {
      user: user.user,
      host: user.host,
      operating_system: operatingSystemName(),
      hardware_id: hardware,
    },
  };

  // The type module owns the sections printed after the declarative profile, so
  // every report type has its own file instead of a shared switch here.
  const typeModule = loadReportModule(profile.id);
  let resolvedChecksums = null;

  const renderOnce = ({ totalPages = 0, checksums = null, hashes = null } = {}) => {
    const builder = new PdfReportBuilder({
      title: profile.title || 'ChronoSeal HASH REPORT',
      author,
      subject: `${kind} report ${id}`,
      keywords: 'SHA-256, hash report, evidence, ChronoSeal',
      now: generatedAt,
    });
    const layout = new ReportLayout({
      styles: resolvedStyles,
      builder,
      title: profile.title || '',
      totalPages,
      footerHashes: hashes,
      reportId: id,
    });
    const base = renderReport({
      builder, layout, profile, modules, context, styles: resolvedStyles,
    });
    const bodyTexts = layout.pageTextLines().map(normalisePageText);
    // The appendix hashes the pages that already exist, so the scope snapshot is
    // taken before the type sections are drawn; the appendix never hashes itself.
    context.checksums = checksums || {
      scope: { pageCount: bodyTexts.length },
      document: placeholderDigests(ALL_TEXT_ALGORITHMS),
      pages: bodyTexts.map((text, index) => ({
        index: index + 1,
        digests: placeholderDigests(PAGE_TEXT_ALGORITHMS),
      })),
      placeholder: true,
    };
    const extra = renderReportSections(typeModule, layout, context);
    layout.finish();
    const allTexts = layout.pageTextLines().map(normalisePageText);
    return {
      builder,
      sections: [...base.sections, ...extra],
      pageCount: layout.pageCount,
      bodyTexts,
      allTexts,
    };
  };

  // Pass 1 is a rehearsal with X-filled digests: same widths, same page count.
  // Pass 2 prints the real values. Pass 3 adds the per-page footer hashes of the
  // exact text pass 2 drew; a changed page count restarts that last step once.
  const runPass = () => {
    const rehearsal = renderOnce({ totalPages: 0 });
    if (!textChecksums || !typeModule) {
      return rehearsal.pageCount > 1 ? renderOnce({ totalPages: rehearsal.pageCount }) : rehearsal;
    }
    resolvedChecksums = {
      scope: { pageCount: rehearsal.bodyTexts.length },
      document: documentDigests(rehearsal.bodyTexts),
      pages: rehearsal.bodyTexts.map((text, index) => ({
        index: index + 1,
        digests: pageDigests(text),
      })),
      placeholder: false,
    };
    const hashed = renderOnce({ totalPages: rehearsal.pageCount, checksums: resolvedChecksums });
    let hashes = hashed.allTexts.map((text) => footerHashLines(pageDigests(text)));
    let final = renderOnce({ totalPages: hashed.pageCount, checksums: resolvedChecksums, hashes });
    if (final.pageCount !== hashed.pageCount) {
      hashes = final.allTexts.map((text) => footerHashLines(pageDigests(text)));
      const pageCount = final.pageCount;
      final = renderOnce({ totalPages: pageCount, checksums: resolvedChecksums, hashes });
    }
    return final;
  };

  // The footer label and the embedded-source note both print the page count, so
  // a pass that changes the count is repeated until the document is stable.
  let pass = runPass();
  for (let attempt = 0; context.embeddedPdf && attempt < 3; attempt += 1) {
    if (context.embeddedPdf.reportPages === pass.pageCount) break;
    context.embeddedPdf.reportPages = pass.pageCount;
    pass = runPass();
  }
  const { builder, sections } = pass;
  const { data } = builder.finish();

  return {
    bytes: data instanceof Uint8Array ? data : new Uint8Array(data),
    pageCount: builder.pages.length,
    sections,
    reportId: id,
    fileName: reportFileName(id),
    kind,
    profile: profile.id,
    reportModule: typeModule ? typeModule.id : null,
    textChecksums: resolvedChecksums
      ? {
        scopePages: resolvedChecksums.scope.pageCount,
        pages: resolvedChecksums.pages.length,
        document: resolvedChecksums.document,
      }
      : null,
    rows,
    documentProof,
    courtHashes: hashes,
    generatedAt: localStamp(generatedAt),
    aggregationMethod: AGGREGATION_METHOD,
    builder,
    pages: builder.pages,
  };
}
