/**
 * Durable report archive - port of chronoseal/report_archive.py.
 *
 * One numbered folder per report plus a SQLite copy of every artifact, so a
 * finished report can be re-verified long after the working files are gone.
 * The folder is published by rename first and the transaction committed second;
 * any failure rolls both back, because a published folder without its database
 * row would permanently block that report number.
 */
import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import {
  ensureDir,
  formatUtc,
  jsonSafe,
  posix,
  sha256Bytes,
  sha256File,
  sleepSync,
  WINDOWS_TRANSIENT,
} from './util.mjs';

export const ARCHIVE_SCHEMA = `
CREATE TABLE IF NOT EXISTS archive_reports (
    report_id TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    report_path TEXT NOT NULL,
    archive_directory TEXT NOT NULL,
    database_path TEXT NOT NULL,
    pdf_sha256 TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS archive_files (
    report_id TEXT NOT NULL REFERENCES archive_reports(report_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content BLOB NOT NULL,
    PRIMARY KEY (report_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_archive_files_sha256 ON archive_files(sha256);
`;

const REPORT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const RENAME_ATTEMPTS = 6;

export function reportIdFromPdf(fileName) {
  const stem = path.parse(String(fileName)).name;
  const reportId = stem.split('_HASHREPORT_TYP_')[0];
  if (!reportId || !REPORT_ID_PATTERN.test(reportId)) {
    throw new Error(`Cannot derive a safe report number from PDF name: ${path.basename(String(fileName))}`);
  }
  return reportId;
}

/** Publish a staged folder, retrying a transient Windows sharing violation. */
export function renameWithRetry(source, destination, attempts = RENAME_ATTEMPTS) {
  let delay = 50;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      fs.renameSync(source, destination);
      return;
    } catch (error) {
      const transient = process.platform === 'win32' && WINDOWS_TRANSIENT.has(error.code);
      if (!transient || attempt === attempts) throw error;
      sleepSync(delay);
      delay = Math.min(delay * 2, 800);
    }
  }
}

function listFilesRecursive(root) {
  const found = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) found.push(full);
    }
  };
  walk(root);
  return found.sort();
}

function copyTree(source, destination) {
  ensureDir(destination);
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else fs.copyFileSync(from, to);
  }
}

function removeTree(target) {
  try {
    fs.rmSync(target, { recursive: true, force: true });
  } catch {
    // Cleanup must never mask the primary failure with a secondary one.
  }
}

/**
 * Publish one immutable report bundle and index all its files in SQLite.
 *
 * `manifest` is mutated with the archive paths on success, mirroring the Python
 * contract that the caller writes the returned manifest afterwards.
 */
export function archiveReport({
  archiveRoot,
  databasePath,
  reportPdf,
  evidenceDirectory,
  runLog = null,
  manifest = {},
  reportName = null,
}) {
  if (!archiveRoot || !databasePath) {
    throw new Error('Report archive is enabled but its archive directory or SQLite database path is empty.');
  }
  const pdf = fs.realpathSync(path.resolve(reportPdf));
  const evidence = fs.realpathSync(path.resolve(evidenceDirectory));
  if (!fs.statSync(pdf).isFile() || !fs.statSync(evidence).isDirectory()) {
    throw new Error('Archive requires a report PDF and its evidence directory');
  }
  let log = null;
  if (runLog) {
    log = fs.realpathSync(path.resolve(runLog));
    if (!fs.statSync(log).isFile()) throw new Error(`Run log is not a file: ${log}`);
  }

  const root = path.resolve(archiveRoot);
  const database = path.resolve(databasePath);
  const archiveName = reportName ? path.basename(reportName) : path.basename(pdf);
  const reportId = reportIdFromPdf(archiveName);
  const destination = path.join(root, reportId);
  if (database === destination || destination === path.dirname(database) || database.startsWith(destination + path.sep)) {
    throw new Error('Archive database must be outside each numbered report folder');
  }
  ensureDir(root);
  ensureDir(path.dirname(database));
  if (fs.existsSync(destination)) {
    throw new Error(`Report archive already exists; refusing overwrite: ${destination}`);
  }

  const stage = path.join(root, `.${reportId}.${randomBytes(8).toString('hex')}.partial`);
  let published = false;
  let db = null;
  try {
    ensureDir(stage);
    fs.copyFileSync(pdf, path.join(stage, archiveName));
    copyTree(evidence, path.join(stage, 'evidence'));
    if (log) fs.copyFileSync(log, path.join(stage, 'run.log'));
    else fs.writeFileSync(path.join(stage, 'run.log'),
      'Session log unavailable; see evidence artifacts and manifest.\n', 'utf8');

    const archiveManifest = jsonSafe({
      ...manifest,
      report_id: reportId,
      archive_directory: destination,
      archive_report_pdf: path.join(destination, archiveName),
      archive_manifest: path.join(destination, 'manifest.json'),
      archive_log: path.join(destination, 'run.log'),
      archive_evidence_directory: path.join(destination, 'evidence'),
      archive_database: database,
    });
    const serialised = JSON.stringify(archiveManifest, null, 2) + '\n';
    fs.writeFileSync(path.join(stage, 'evidence', 'manifest.json'), serialised, 'utf8');
    fs.writeFileSync(path.join(stage, 'manifest.json'), serialised, 'utf8');

    db = new DatabaseSync(database, { timeout: 30000 });
    db.exec('PRAGMA foreign_keys = ON');
    db.exec(ARCHIVE_SCHEMA);
    db.exec('BEGIN IMMEDIATE');
    if (db.prepare('SELECT 1 FROM archive_reports WHERE report_id = ?').get(reportId)) {
      throw new Error(`Report number already exists in archive database: ${reportId}`);
    }
    db.prepare(`INSERT INTO archive_reports (
        report_id, created_utc, report_path, archive_directory,
        database_path, pdf_sha256, manifest_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
      reportId,
      formatUtc(new Date()),
      path.join(destination, archiveName),
      destination,
      database,
      sha256File(path.join(stage, archiveName)),
      JSON.stringify(archiveManifest),
    );
    const insertFile = db.prepare(`INSERT INTO archive_files (
        report_id, relative_path, sha256, size_bytes, content
      ) VALUES (?, ?, ?, ?, ?)`);
    for (const item of listFilesRecursive(stage)) {
      const data = fs.readFileSync(item);
      insertFile.run(reportId, posix(path.relative(stage, item)), sha256Bytes(data), data.length, data);
    }

    if (fs.existsSync(destination)) {
      throw new Error(`Report archive already exists; refusing overwrite: ${destination}`);
    }
    renameWithRetry(stage, destination);
    published = true;
    db.exec('COMMIT');

    for (const key of Object.keys(manifest)) delete manifest[key];
    Object.assign(manifest, archiveManifest);
    return {
      report_id: reportId,
      archive_directory: destination,
      archive_report_pdf: path.join(destination, archiveName),
      archive_manifest: path.join(destination, 'manifest.json'),
      archive_log: path.join(destination, 'run.log'),
      archive_database: database,
    };
  } catch (error) {
    if (db) {
      try { db.exec('ROLLBACK'); } catch { /* transaction already closed */ }
    }
    if (published && fs.existsSync(destination)) removeTree(destination);
    throw error;
  } finally {
    if (db) {
      try { db.close(); } catch { /* already closed */ }
    }
    if (fs.existsSync(stage)) removeTree(stage);
  }
}

/** Read back one archived file, used by tests and by `--verify-archive`. */
export function readArchivedFile(databasePath, reportId, relativePath) {
  const db = new DatabaseSync(path.resolve(databasePath), { timeout: 30000 });
  try {
    const row = db.prepare('SELECT sha256, size_bytes, content FROM archive_files WHERE report_id = ? AND relative_path = ?')
      .get(reportId, relativePath);
    if (!row) return null;
    const data = row.content instanceof Uint8Array ? row.content : new Uint8Array(row.content);
    return { sha256: row.sha256, sizeBytes: Number(row.size_bytes), data };
  } finally {
    db.close();
  }
}
