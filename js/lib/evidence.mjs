/**
 * Evidence capture for one report run (port of chronoseal/storage_identity.py and
 * the evidence part of chronoseal/pipeline.py).
 *
 * Provenance is never guessed: a value Node cannot read without a native call is
 * recorded as null together with the reason, exactly like the Python module.
 */
import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { atomicWriteJson, ensureDir, formatUtc, jsonSafe, makeDirExclusive } from './util.mjs';

export const DEFAULT_MIN_FREE_BYTES = 512 * 1024 * 1024;

function nearestExisting(target) {
  let probe = path.resolve(target);
  while (!fs.existsSync(probe)) {
    const parent = path.dirname(probe);
    if (parent === probe) break;
    probe = parent;
  }
  return probe;
}

/** Read-only filesystem provenance for one path. */
export function inspectStorage(target) {
  const requested = path.resolve(target);
  const probe = nearestExisting(requested);
  const stats = fs.statSync(probe);
  const volume = fs.statfsSync(probe);
  const blockSize = Number(volume.bsize) * Number(volume.blocks);
  const free = Number(volume.bsize) * Number(volume.bavail);
  return {
    requested_path: requested,
    probed_directory: probe,
    device_id_st_dev: Number(stats.dev),
    directory_inode_st_ino: Number(stats.ino),
    bytes_total: blockSize,
    bytes_used: blockSize - free,
    bytes_available: free,
    capacity_percent_used: blockSize ? Math.round((100 * (blockSize - free) / blockSize) * 100) / 100 : null,
    // Node exposes neither the Windows volume GUID nor its serial without a
    // native addon; recording a guess would be worse than recording null.
    volume_guid_path: null,
    volume_mount_point: process.platform === 'win32' ? path.parse(probe).root : null,
    filesystem_name: null,
    volume_serial_number: null,
    captured_utc: formatUtc(new Date()),
  };
}

export function inspectWorkspaces(inputPath, evidencePath, outputPath) {
  return {
    input: inspectStorage(inputPath),
    evidence: inspectStorage(evidencePath),
    output: inspectStorage(outputPath),
  };
}

/** Advisory only: a nearly full volume must not silently truncate a report. */
export function lowSpaceWarning(identity, minimum = null) {
  const limit = minimum === null || minimum === undefined ? DEFAULT_MIN_FREE_BYTES : Number(minimum);
  if (!limit || limit <= 0) return null;
  const free = identity?.bytes_available;
  if (free === null || free === undefined || free >= limit) return null;
  const where = identity.probed_directory || identity.requested_path || 'the target volume';
  const mib = (value) => Math.round(value / 1048576);
  return `Low free space on ${where}: ${mib(free)} MiB available, ${mib(limit)} MiB expected; `
    + 'the report, its evidence copy and the archive may not fit.';
}

/** `YYYYmmdd_HHMMSS_<12 hex>` case folder, created exclusively. */
export function caseDirectory(evidenceBase, { now = new Date(), suffix = null } = {}) {
  const pad = (value) => String(value).padStart(2, '0');
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
    + `_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const unique = suffix || randomBytes(6).toString('hex');
  const caseDir = path.join(evidenceBase, `${stamp}_${unique}`);
  try {
    ensureDir(path.dirname(caseDir));
    makeDirExclusive(caseDir);
  } catch (error) {
    throw new Error(`Cannot create the evidence case ${caseDir}: ${error.message}. `
      + 'The input location must be writable; read-only media, a full volume or a file named '
      + 'ChronoSeal_Evidence block evidence capture, so choose a writable output directory.');
  }
  return caseDir;
}

export const MANIFEST_SCHEMA = 'chronoseal.onebutton/v4-dualstamp';

/**
 * Write the evidence artifacts of a run. The manifest is written last so it can
 * reference every file that exists next to it.
 */
export function writeEvidence({ caseDir, storage, layout, manifest }) {
  const files = {};
  if (storage) {
    files.storageIdentity = path.join(caseDir, 'storage-identity.json');
    atomicWriteJson(files.storageIdentity, jsonSafe(storage));
  }
  if (layout) {
    files.layoutAudit = path.join(caseDir, 'layout-audit.json');
    atomicWriteJson(files.layoutAudit, jsonSafe(layout));
  }
  const payload = jsonSafe({ ...manifest });
  if (files.storageIdentity) payload.storage_identity = files.storageIdentity;
  if (files.layoutAudit) {
    payload.layout_audit = files.layoutAudit;
    payload.layout_status = layout.status;
  }
  files.manifest = path.join(caseDir, 'manifest.json');
  atomicWriteJson(files.manifest, payload);
  return { files, manifest: payload };
}
