#!/usr/bin/env node
/**
 * ChronoSeal HASH REPORT - JavaScript clone (command line only).
 *
 * Same configuration, same style rules, same digest basis and the same evidence
 * layout as the Python program, but every stage is JavaScript:
 *
 *   1 preflight      config, storage identity, free-space advisory
 *   2 selection      folder discovery with the shared filter grammar, or an
 *                    explicit file list (never both)
 *   3 report         SHA-256 hashes, aggregate proof, eleven court algorithms,
 *                    multi-page A4 PDF built from hash_report_generator/style
 *   4 layout gate    read-only check of margins, footer and content probes
 *   5 PDF/A-2b       embedded subsets, sRGB output intent, XMP, repaired xref
 *   6 evidence       case folder, storage identity, layout audit, manifest,
 *                    optional immutable archive folder plus SQLite copy
 *
 * The program never signs, so it never claims a signature: the manifest records
 * exactly what was produced.
 */
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { archiveSettings, evidencePolicy, generatorSettings, loadConfig, REPO_ROOT } from './lib/config.mjs';
import { describe, parse, resolveSelection } from './lib/selection.mjs';
import { aggregatePayload, generateReport } from './lib/generate.mjs';
import { auditLayout } from './lib/quality.mjs';
import { inspectPdf, normalizeReport } from './lib/normalize.mjs';
import { describeSourcePdf, embedSourcePdf } from './lib/embed.mjs';
import {
  caseDirectory,
  inspectStorage,
  inspectWorkspaces,
  lowSpaceWarning,
  MANIFEST_SCHEMA,
  writeEvidence,
} from './lib/evidence.mjs';
import { archiveReport } from './lib/archive.mjs';
import {
  documentName,
  isGeneratedHashReport,
  systemInformation,
  userInformation,
  volumeInformation,
} from './lib/identity.mjs';
import { atomicWriteBytes, formatUtc, jsonSafe, posix, sha256Bytes } from './lib/util.mjs';
import { loadStyles, STYLE_DIR } from '../tools/jsx/style-loader.mjs';

export const EXIT_OK = 0;
export const EXIT_ERROR = 1;
export const EXIT_BLOCKED = 2;
export const CLONE_VERSION = '1.0.0';

const USAGE = `ChronoSeal HASH REPORT - JavaScript clone ${CLONE_VERSION}

  node js/cli.mjs --source <folder> [--recursive] [--filter PATTERN]...
  node js/cli.mjs --files <file[,file...]> [--output <folder>]

Options
  --source <folder|file>  Folder to report on, or one file for a SINGLE report.
  --recursive             Include subfolders (marks a COMBO report as _ALL).
  --filter <pattern>      Repeatable file filter, same grammar as the GUI
                          (for example "*.pdf" or "*eml.pdf").
  --files <list>          Explicit selection; comma or newline separated. Filters
                          do not apply to an explicit selection.
  --output <folder>       Where the finished report is published (default: source).
  --profile <id>          Report profile from hash_report_generator/report_profiles
                          (default: single for one file, combo otherwise).
  --archive / --no-archive
                          Force the durable archive on or off (default: config).
  --per-file              One SINGLE report per file instead of one combined report.
                          Each report gets its own report number, evidence case and
                          archive row.
  --embed-pdf             Only for one PDF input: append the pages of that PDF and
                          attach the original file byte-for-byte (single_pdf parity).
  --no-normalise          Keep the generated PDF without the PDF/A-2b stage.
  --require-layout-pass   Block publication when the layout gate reports REVIEW.
  --json                  Print a machine-readable summary on stdout.
  --quiet                 Only print warnings and errors.
  --version, --help
`;

/** Minimal, allocation-light argument reader: the clone adds no dependency. */
export function parseArgs(argv) {
  const options = {
    source: null,
    recursive: false,
    filters: [],
    files: [],
    output: null,
    profile: null,
    archive: null,
    normalise: true,
    requireLayoutPass: false,
    perFile: false,
    embedPdf: false,
    json: false,
    quiet: false,
    help: false,
    version: false,
  };
  const take = (index, flag) => {
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) throw new Error(`${flag} requires a value`);
    return value;
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case '--source': options.source = take(index, arg); index += 1; break;
      case '--recursive': case '-r': options.recursive = true; break;
      case '--filter': options.filters.push(take(index, arg)); index += 1; break;
      case '--files': options.files.push(...String(take(index, arg)).split(/[,\r\n]+/).filter(Boolean)); index += 1; break;
      case '--output': options.output = take(index, arg); index += 1; break;
      case '--profile': options.profile = take(index, arg); index += 1; break;
      case '--archive': options.archive = true; break;
      case '--no-archive': options.archive = false; break;
      case '--no-normalise': options.normalise = false; break;
      case '--per-file': options.perFile = true; break;
      case '--embed-pdf': options.embedPdf = true; break;
      case '--require-layout-pass': options.requireLayoutPass = true; break;
      case '--json': options.json = true; break;
      case '--quiet': options.quiet = true; break;
      case '--version': options.version = true; break;
      case '--help': case '-h': options.help = true; break;
      default: throw new Error(`Unknown option: ${arg}`);
    }
  }
  return options;
}

/** Rule files that produced the layout, recorded so the manifest is auditable. */
export function styleRuleFiles(repoRoot = REPO_ROOT) {
  const directory = repoRoot === REPO_ROOT ? STYLE_DIR : path.join(repoRoot, 'hash_report_generator', 'style');
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory)
    .filter((name) => name.toLowerCase().endsWith('.js'))
    .sort()
    .map((name) => posix(path.relative(repoRoot, path.join(directory, name))));
}
function makeLogger(quiet) {
  const lines = [];
  const emit = (level, message) => {
    const line = `${formatUtc(new Date(), { millis: false })} ${level} ${message}`;
    lines.push(line);
    if (level === 'INFO' && quiet) return;
    process.stdout.write(line + '\n');
  };
  return {
    lines,
    log: (message) => emit('INFO', message),
    warn: (message) => emit('WARNING', message),
    step: (index, total, message) => emit('INFO', `${index}/${total} ${message}`),
    text: () => lines.join('\n') + '\n',
  };
}

function publishReport(bytes, destination, fileName) {
  fs.mkdirSync(destination, { recursive: true });
  const target = path.join(destination, fileName);
  // COPYFILE_EXCL makes publication exclusive: an existing report is never
  // silently overwritten, because the name carries the report number.
  fs.writeFileSync(target, bytes, { flag: 'wx' });
  return target;
}

/**
 * Run one generation.
 *
 * @returns {Promise<object>} summary object
 */
export async function run(argv, { repoRoot = REPO_ROOT } = {}) {
  const started = Date.now();
  const options = parseArgs(argv);
  if (options.help) return { help: USAGE, exitCode: EXIT_OK };
  if (options.version) return { version: CLONE_VERSION, exitCode: EXIT_OK };
  if (!options.files.length && !options.source) throw new Error('Either --source or --files is required');

  const logger = makeLogger(options.quiet);
  const config = loadConfig(path.join(repoRoot, 'config', 'config.json'));
  const policy = evidencePolicy(config);
  const settings = generatorSettings(config, repoRoot);
  let archive = archiveSettings(config, repoRoot);
  if (options.archive === false) archive = { enabled: false, directory: null, database: null };
  if (options.archive === true && !archive.enabled) {
    throw new Error('--archive was requested but config/config.json has no archive directory and database.');
  }

  const sourcePath = options.source ? path.resolve(options.source) : path.resolve(options.files[0]);
  if (!fs.existsSync(sourcePath)) throw new Error('Source does not exist: ' + sourcePath);
  const sourceIsFolder = fs.statSync(sourcePath).isDirectory();
  // --source may name one document, which is how the GUI's "report a single file"
  // entry point behaves: that is an explicit selection of one file, not a folder scan.
  if (!options.files.length && !sourceIsFolder) options.files.push(sourcePath);
  if (options.files.length && options.filters.length) {
    throw new Error('File type filters only apply to a folder (combined) report; '
      + 'an explicit file selection has nothing to filter.');
  }
  if (options.recursive && !sourceIsFolder) {
    throw new Error('--recursive needs a folder; ' + sourcePath + ' is a file');
  }

  logger.step(1, 6, 'Preflight');
  logger.log('config: ' + config.__path);
  const preflight = inspectStorage(sourceIsFolder ? sourcePath : path.dirname(sourcePath));
  logger.log('storage: ' + preflight.probed_directory
    + ` (${Math.round(preflight.bytes_available / 1048576)} MiB free)`);
  const spaceWarning = lowSpaceWarning(preflight, (config.storage || {}).min_free_bytes);
  if (spaceWarning) logger.warn(spaceWarning);
  logger.log('evidence retention: ' + Object.keys(policy).join(', '));

  logger.step(2, 6, 'Selection');
  const selection = resolveSelection({
    files: options.files,
    source: sourceIsFolder ? sourcePath : null,
    recursive: options.recursive,
    filters: options.filters,
    followLinks: settings.follow_links === true,
    allowUnreadable: settings.allow_unreadable_files === true,
  });
  // A report must never hash a previous report: the evidence set would then grow
  // with the program's own output on every run.
  const candidates = selection.files.filter((file) => !isGeneratedHashReport(file));
  const selfExcluded = selection.files.length - candidates.length;
  if (!candidates.length) throw new Error('Every candidate is a generated report; nothing to hash in ' + selection.root);
  logger.log(`${candidates.length} file(s) from ${selection.root}`
    + (selfExcluded ? `; ${selfExcluded} generated report(s) excluded` : '')
    + (selection.filter_note && selection.filter_note !== 'none' ? `; ${selection.filter_note}` : ''));

  // --per-file turns the selection into one independent report per file. Each
  // report is a separate run: own report number, own evidence case, own archive
  // row, so one damaged file cannot silently swallow the rest of the selection.
  if (options.perFile) {
    if (options.profile) {
      throw new Error('--per-file cannot be combined with --profile: every file gets its own SINGLE report');
    }
    const perFileOutput = options.output
      ? path.resolve(options.output)
      : (sourceIsFolder ? sourcePath : path.dirname(sourcePath));
    if (!fs.existsSync(perFileOutput) || !fs.statSync(perFileOutput).isDirectory()) {
      throw new Error('Output directory does not exist: ' + perFileOutput);
    }
    const oneArgv = (file) => {
      const args = ['--files', file, '--output', perFileOutput];
      if (options.archive === true) args.push('--archive');
      if (options.archive === false) args.push('--no-archive');
      if (!options.normalise) args.push('--no-normalise');
      if (options.requireLayoutPass) args.push('--require-layout-pass');
      if (options.embedPdf) args.push('--embed-pdf');
      args.push('--quiet');
      return args;
    };
    const reports = [];
    let failed = 0;
    for (const file of candidates) {
      const label = posix(path.relative(selection.root, file)) || path.basename(file);
      try {
        const one = await run(oneArgv(file), { repoRoot });
        reports.push(one.summary);
        logger.log(`${label}: ${one.summary.status} ${one.summary.report_id} `
          + `(${one.summary.pages} page(s), ${one.summary.pdf_bytes} bytes)`);
      } catch (error) {
        failed += 1;
        reports.push({ status: 'ERROR', file: label, error: error.message });
        logger.warn(`${label}: ${error.message}`);
      }
    }
    const elapsed = Math.round((Date.now() - started) / 10) / 100;
    const summary = {
      status: failed ? 'ERROR' : 'PASS',
      mode: 'per_file',
      reports,
      files: candidates.length,
      failed,
      elapsed_seconds: elapsed,
    };
    if (options.json) process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
    else logger.log(`done in ${elapsed}s - ${summary.status} `
      + `(${reports.length - failed}/${reports.length} report(s))`);
    return {
      exitCode: failed ? EXIT_ERROR : EXIT_OK,
      summary,
      published: reports.map((report) => report.published).filter(Boolean),
    };
  }

  // An explicit --files selection is always a SINGLE report when it names one file,
  // even though --source may still point at a folder that only anchors the root.
  const explicit = options.files.length > 0;
  if (options.embedPdf) {
    if (candidates.length !== 1) {
      throw new Error(`--embed-pdf needs exactly one input file (the selection has ${candidates.length})`);
    }
    if (!/\.pdf$/i.test(candidates[0])) {
      throw new Error('--embed-pdf needs a PDF input file: ' + candidates[0]);
    }
    if (options.profile && options.profile !== 'single' && options.profile !== 'single_pdf') {
      throw new Error('--embed-pdf only supports the single report profile');
    }
  }
  // The embedded type promises an appended source PDF; renaming a plain report to
  // it would make the file name describe something the document does not contain.
  if (!options.embedPdf && options.profile === 'single_pdf') {
    throw new Error('--profile single_pdf needs --embed-pdf: that type documents an embedded source PDF');
  }
  // The embedded original is a single-document feature: the report type is the
  // one that documents an appended source PDF.
  const profileId = options.profile
    || (options.embedPdf
      ? 'single_pdf'
      : (candidates.length === 1 && (!sourceIsFolder || explicit) ? 'single' : 'combo'));
  // Facts the report body prints about the appended original; they are known
  // before composition because the attachment is the source bytes unchanged.
  const embedSourceFacts = options.embedPdf ? describeSourcePdf(candidates[0]) : null;
  // loadStyles() validates the mandatory sections of the packaged rule folder.
  const styles = loadStyles();
  const outputDir = options.output ? path.resolve(options.output) : (sourceIsFolder ? sourcePath : path.dirname(sourcePath));
  if (!fs.existsSync(outputDir) || !fs.statSync(outputDir).isDirectory()) {
    throw new Error('Output directory does not exist: ' + outputDir);
  }

  logger.step(3, 6, 'Report');
  const generatedAt = new Date();
  const report = generateReport({
    files: candidates,
    root: selection.root,
    profileId,
    generatedAt,
    styles,
    selection: {
      source: selection.explicit ? null : sourcePath,
      kind: selection.explicit ? 'explicit_files' : (sourceIsFolder ? 'folder' : 'single_file'),
      mode: candidates.length > 1 ? 'combo' : 'single',
      recursive: options.recursive,
      filters: options.filters,
    },
    embeddedPdf: embedSourceFacts
      ? {
        name: embedSourceFacts.name,
        source: embedSourceFacts.path,
        bytes: embedSourceFacts.bytes,
        sha256: embedSourceFacts.sha256,
        pages: embedSourceFacts.pages,
        attachment: embedSourceFacts.name,
        attachmentSha256: embedSourceFacts.sha256,
        auditStatus: 'composition audit written after the PDF/A-2b and embed stages',
      }
      : null,
  });
  logger.log(`report ${report.reportId} (${report.kind}) pages=${report.pageCount} rows=${report.rows.length}`);
  logger.log('aggregate proof: ' + report.documentProof);

  logger.step(4, 6, 'Layout gate');
  const layout = auditLayout({ builder: report.builder, pages: report.pages, styles, file: '(generated)' });
  if (layout.status === 'PASS') logger.log('layout: PASS (' + layout.pages.length + ' pages)');
  else logger.warn('LAYOUT REVIEW: ' + layout.issues.join('; '));
  if (layout.status !== 'PASS' && options.requireLayoutPass) {
    return { exitCode: EXIT_BLOCKED, layout, summary: { status: 'LAYOUT REVIEW', issues: layout.issues } };
  }

  logger.step(5, 6, 'PDF/A-2b');
  let finalBytes = report.bytes;
  let normaliseStats = null;
  if (options.normalise) {
    const normalised = normalizeReport(report.bytes, {
      title: `ChronoSeal HASH REPORT ${report.reportId}`,
      author: 'ChronoSeal Enterprise (JavaScript clone)',
      subject: `${report.kind} hash report for ${selection.root}`,
      keywords: 'SHA-256, hash report, evidence, ChronoSeal',
      sourcePath: path.join(selection.root, report.fileName),
      createDate: generatedAt,
      modifyDate: generatedAt,
    });
    finalBytes = normalised.bytes;
    normaliseStats = normalised.stats;
    logger.log(`normalised: ${finalBytes.length} bytes sha256=${normalised.sha256.slice(0, 16)}…`);
  } else {
    logger.warn('PDF/A-2b stage skipped (--no-normalise): the published file is not PDF/A-2b');
  }
  let embeddedSource = null;
  if (options.embedPdf) {
    const source = candidates[0];
    const embedded = embedSourcePdf(finalBytes, {
      sourcePath: source,
      sourceName: path.basename(source),
      description: 'Original document ' + path.basename(source) + ', attached unchanged',
      expectedReportPages: report.pageCount,
      now: generatedAt,
    });
    finalBytes = embedded.bytes;
    embeddedSource = embedded.audit;
    logger.log(`embed: ${embeddedSource.source.pages} source page(s), `
      + `${embeddedSource.attachment.bytes} bytes attached byte-for-byte`);
    logger.log('embed: attachment sha256 ' + embeddedSource.attachment.sha256);
  }
  const pdfPages = report.pageCount + (embeddedSource ? embeddedSource.source.pages : 0);
  const readback = inspectPdf(finalBytes, { expectedPages: pdfPages });
  logger.log(`read-back: ${readback.pages} page(s), metadata=${readback.hasMetadata}, `
    + `output-intent=${readback.hasOutputIntent}`);

  logger.step(6, 6, 'Evidence');
  const evidenceBase = path.join(sourceIsFolder ? sourcePath : path.dirname(sourcePath), 'ChronoSeal_Evidence');
  const caseDir = caseDirectory(evidenceBase);
  // The published marker is always SINGLE or COMBO; recursion is the separate
  // _ALL suffix, exactly as Pipeline.run() builds it.
  const baseKind = String(report.kind).replace(/_ALL$/, '');
  const fileName = documentName({ id: report.reportId, kind: baseKind, recursive: options.recursive });
  const staged = path.join(caseDir, fileName);
  atomicWriteBytes(staged, finalBytes);
  let sourcePdfAudit = null;
  if (embeddedSource) {
    sourcePdfAudit = path.join(caseDir, 'source-pdf-signature-audit.json');
    fs.writeFileSync(sourcePdfAudit, JSON.stringify(jsonSafe(embeddedSource), null, 2) + '\n', 'utf8');
  }
  const workspace = inspectWorkspaces(
    sourceIsFolder ? sourcePath : path.dirname(sourcePath),
    caseDir,
    outputDir,
  );
  const finalHash = sha256Bytes(finalBytes);
  const manifest = {
    schema: MANIFEST_SCHEMA,
    implementation: `chronoseal-js-clone/${CLONE_VERSION}`,
    report_id: report.reportId,
    report_kind: report.kind,
    generated_utc: formatUtc(generatedAt),
    source: sourcePath,
    input_kind: selection.explicit ? 'explicit_files' : (sourceIsFolder ? 'folder' : 'single_file'),
    mode: report.kind.toLowerCase(),
    recursive: Boolean(options.recursive),
    selection_filters: options.filters.length ? parse(options.filters) : null,
    selection_root: selection.root,
    selection_files: selection.explicit ? candidates : null,
    selection_paths: selection.explicit ? candidates.map((file) => posix(path.relative(selection.root, file))) : null,
    selection_count: candidates.length,
    selection_excluded_reports: selfExcluded,
    output_directory: outputDir,
    published_name: fileName,
    generated_report: staged,
    report_sha256: sha256Bytes(report.bytes),
    final_pdf: staged,
    final_sha256: finalHash,
    pdfa: options.normalise ? { part: '2', conformance: 'B' } : null,
    normalise_stats: normaliseStats,
    embedded_source_pdf: embeddedSource,
    source_pdf_audit: sourcePdfAudit,
    aggregation_method: report.aggregationMethod,
    aggregation_payload_sha256: sha256Bytes(aggregatePayload(report.rows)),
    aggregate_proof: report.documentProof,
    court_algorithms: report.courtHashes,
    system: systemInformation(generatedAt),
    user: userInformation(),
    volume: volumeInformation(selection.root),
    style_rules: styleRuleFiles(repoRoot),
    report_profile: report.profile,
    hardware_id: null,
    rfc3161_audit: null,
    signature: 'NOT SIGNED - the JavaScript clone has no DocTimeStamp stage',
    elapsed_seconds: null,
    status: layout.status === 'PASS' ? 'PASS' : 'LAYOUT REVIEW',
  };
  const evidence = writeEvidence({ caseDir, storage: workspace, layout, manifest });
  logger.log('evidence: ' + caseDir);

  // The run log is written before the archive so the archived copy is the log of
  // the run that produced it, and it is appended to after publication.
  const logFile = path.join(caseDir, 'run.log');
  fs.writeFileSync(logFile, logger.text(), 'utf8');

  let archiveInfo = null;
  if (archive.enabled) {
    archiveInfo = archiveReport({
      archiveRoot: archive.directory,
      databasePath: archive.database,
      reportPdf: staged,
      evidenceDirectory: caseDir,
      runLog: logFile,
      manifest,
      reportName: fileName,
    });
    logger.log('archive: ' + archiveInfo.archive_directory);
  }

  const published = publishReport(finalBytes, outputDir, fileName);
  logger.log('published: ' + published);
  // Only the case copy is extended after publication: the archived log is the
  // snapshot of the run that the SQLite blob stores, so the two must not drift.
  fs.appendFileSync(logFile, `${formatUtc(new Date(), { millis: false })} INFO published: ${published}\n`, 'utf8');

  const summary = {
    status: manifest.status,
    report_id: report.reportId,
    kind: report.kind,
    files: report.rows.length,
    pages: report.pageCount,
    aggregate_proof: report.documentProof,
    pdf_sha256: finalHash,
    pdf_bytes: finalBytes.length,
    pdfa: manifest.pdfa,
    pdf_pages: pdfPages,
    embedded_pdf: embeddedSource
      ? {
        source: embeddedSource.source.name,
        sha256: embeddedSource.source.sha256,
        pages: embeddedSource.source.pages,
        attachment_sha256: embeddedSource.attachment.sha256,
        audit: sourcePdfAudit,
      }
      : null,
    layout: { status: layout.status, issues: layout.issues },
    published,
    evidence_case: caseDir,
    archive: archiveInfo ? archiveInfo.archive_directory : null,
    elapsed_seconds: Math.round((Date.now() - started) / 10) / 100,
  };
  fs.writeFileSync(path.join(caseDir, 'manifest.json'),
    JSON.stringify(jsonSafe({ ...manifest, elapsed_seconds: summary.elapsed_seconds, run_log: logFile }), null, 2) + '\n',
    'utf8');

  if (options.json) process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
  else logger.log(`done in ${summary.elapsed_seconds}s - ${summary.status}`);
  return { exitCode: EXIT_OK, summary, layout, published, evidenceDirectory: caseDir, archive: archiveInfo };
}

// fileURLToPath, not a hand-rolled URL decode: on a UNC share the pathname keeps the
// host in the authority. Case also differs (`pasevclaud` vs `PASEVCLAUD`), and Windows
// paths are case-insensitive, so compare through one normaliser.
const asKey = (value) => {
  const resolved = path.resolve(value);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
};
const isMain = Boolean(process.argv[1]) && asKey(process.argv[1]) === asKey(fileURLToPath(import.meta.url));
if (isMain) {
  try {
    const result = await run(process.argv.slice(2));
    if (result.help) process.stdout.write(result.help);
    else if (result.version) process.stdout.write(result.version + '\n');
    process.exitCode = result.exitCode;
  } catch (error) {
    process.stderr.write('BLOCKED\n\n' + (error && error.message ? error.message : String(error)) + '\n');
    if (process.env.CHRONOSEAL_DEBUG) process.stderr.write((error && error.stack) || '');
    process.exitCode = EXIT_ERROR;
  }
}
