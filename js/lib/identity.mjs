/**
 * Report identity and environment facts for the JS clone.
 *
 * The identifiers are byte-compatible with hash_report_core.py: name, stamp and
 * the self-exclusion pattern must agree, otherwise a clone report would be
 * hashed into the next clone report as evidence.
 */
import fs from 'node:fs';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { formatUtc, pad } from './util.mjs';

export const REPORT_PREFIX = 'RPT';

/** Generation kinds the pipeline recognises (the SINGLE/COMBO marker in the name). */
export const KINDS = Object.freeze([
  'SINGLE', 'SINGLE_PDF',
  'COMBO', 'COMBO_ALL', 'COMBO_PDF', 'COMBO_ALL_PDF',
  'VOLUME', 'FILE_INFORMATION',
]);

/** RPT-YYYYMMDD-HHMMSSmmm-XXXXXXXX, local time, as hash_report_core.py builds it. */
export function reportId(now = new Date()) {
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
    + `-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
    + pad(now.getMilliseconds(), 3);
  const suffix = randomBytes(4).toString('hex').toUpperCase();
  return `${REPORT_PREFIX}-${stamp}-${suffix}`;
}

export function reportFileName(id) {
  if (!/^RPT-\d{8}-\d{9}-[0-9A-F]{8}$/.test(id)) throw new Error('Invalid report id: ' + id);
  return `${id}_HASHREPORT.pdf`;
}

/**
 * Published document name used by Pipeline.run(): the marker tells a verifier
 * whether the evidence set is one file or a package, and `_ALL` marks recursion.
 */
export function documentName({ id, kind, recursive = false }) {
  if (!KINDS.includes(kind)) throw new Error('Unsupported report kind: ' + kind);
  // `_ALL` records recursion and `_PDF` records an embedded document. A recursive
  // report carries both markers, and Python splices `_ALL` between the type and
  // `_PDF`, so a recursive COMBO_PDF publishes as COMBO_ALL_PDF, never COMBO_PDF_ALL.
  const marker = recursive && kind === 'COMBO' ? 'COMBO_ALL'
    : recursive && kind === 'COMBO_PDF' ? 'COMBO_ALL_PDF'
      : kind;
  return `${id}_HASHREPORT_TYP_${marker}.pdf`;
}

const MODERN_REPORT = new RegExp(
  '(?:\\d{4}-\\d{2}-\\d{2}-\\d{9}_-_)?'
  + 'RPT-\\d{8}-\\d{9}-[0-9A-Fa-f]{8}'
  + '(?:-HASHREPORT|_HASHREPORT_TYP_(?:COMBO_ALL_PDF|COMBO_ALL|COMBO_PDF|COMBO|SINGLE_PDF|SINGLE'
  + '|VOLUME|FILE_INFORMATION))\\.pdf$',
  'i',
);

const LEGACY_REPORT = /_hash_report_(?:combined|individual)\.pdf$/i;
const LEGACY_EXPLANATION = /_-_ERLAEUTERUNG\.pdf$/i;
const EVIDENCE_FILES = new Set([
  'discovery-unreadable.json',
  'hash_report_evidence.sqlite3',
  'hash_report_evidence.sqlite3-shm',
  'hash_report_evidence.sqlite3-wal',
  'hash_report_evidence.sqlite3-journal',
]);

/**
 * True for anything this program produced itself. A report must never hash its
 * own previous output, and neither must a discovery run pick up its own log.
 */
export function isGeneratedHashReport(nameOrPath) {
  const name = path.basename(String(nameOrPath));
  if (EVIDENCE_FILES.has(name.toLowerCase())) return true;
  return MODERN_REPORT.test(name) || LEGACY_REPORT.test(name) || LEGACY_EXPLANATION.test(name);
}

export function systemInformation(now = new Date()) {
  const cpus = os.cpus() || [];
  return {
    generated: formatUtc(now),
    hostname: os.hostname(),
    platform: `${os.platform()} ${os.release()}`,
    architecture: os.arch(),
    node_version: process.version,
    v8_version: process.versions.v8,
    cpu_model: cpus.length ? String(cpus[0].model || '').trim() : 'unknown',
    cpu_count: cpus.length,
    memory_total_bytes: os.totalmem(),
    uptime_seconds: Math.round(os.uptime()),
  };
}

export function userInformation() {
  const info = os.userInfo();
  const [domain, name] = String(info.username || '').includes('\\')
    ? String(info.username).split('\\', 2)
    : [os.hostname(), info.username];
  return {
    user: name || String(info.username || ''),
    domain: domain || os.hostname(),
    home_directory: info.homedir || os.homedir(),
    host: os.hostname(),
  };
}

/** Volume identity for the hashed location, from fs.statfs (no external tool). */
const VOLUME_PROBE_CACHE = new Map();

function runProbe(file, args) {
  try {
    return String(
      execFileSync(file, args, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
        timeout: 6000,
        windowsHide: true,
        cwd: os.tmpdir(),
      }),
    );
  } catch {
    return '';
  }
}

/**
 * Windows volume header data, cached per volume root. `fsutil` needs elevation and
 * `wmic` is gone from current builds, so the serial comes from `vol`, the volume GUID
 * from `mountvol` and the filesystem name from CIM.
 */
function probeWindowsVolume(root) {
  if (VOLUME_PROBE_CACHE.has(root)) return VOLUME_PROBE_CACHE.get(root);
  const drive = root.replace(/[\\/]+$/, '');
  const serialMatch = /Volume Serial Number is\s*([0-9A-Fa-f-]+)/.exec(runProbe('cmd', ['/c', 'vol', drive]));
  const guidMatch = /\\\\\?\\Volume\{([0-9a-fA-F-]+)\}/.exec(runProbe('mountvol', [root, '/L']));
  let filesystem = '';
  if (drive) {
    const cim = runProbe('powershell', [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      `(Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='${drive}'").FileSystem`,
    ]);
    filesystem = cim.trim().split(/\r?\n/).pop().trim();
  }
  const probe = {
    serial: serialMatch ? serialMatch[1].replace(/-/g, '').toUpperCase() : '',
    filesystem,
    guid: guidMatch ? guidMatch[1] : '',
  };
  VOLUME_PROBE_CACHE.set(root, probe);
  return probe;
}

/** Hardware ID as the Python generator reports it: uuid.getnode() (the MAC integer). */
export function hardwareId() {
  const interfaces = os.networkInterfaces();
  const names = Object.keys(interfaces).sort();
  for (const name of names) {
    for (const address of interfaces[name] || []) {
      const mac = String(address.mac || '');
      if (address.internal || !/^[0-9a-f]{2}(:[0-9a-f]{2}){5}$/i.test(mac) || mac === '00:00:00:00:00:00') {
        continue;
      }
      return BigInt(`0x${mac.replace(/:/g, '')}`).toString();
    }
  }
  return '';
}

/** `Windows 11` on Win11 (Node only exposes the kernel version) and `type release` elsewhere. */
export function operatingSystemName() {
  if (process.platform === 'win32') {
    const build = Number((os.release() || '').split('.')[2] || 0);
    if (build >= 22000) return 'Windows 11';
    if (build >= 10240) return 'Windows 10';
    return `Windows ${os.release()}`;
  }
  return `${os.type()} ${os.release()}`.trim();
}

export function volumeInformation(folder) {
  const target = path.resolve(String(folder));
  let stats = null;
  if (typeof fs.statfsSync === 'function') {
    try {
      stats = fs.statfsSync(target);
    } catch {
      stats = null;
    }
  }
  const blockSize = stats ? Number(stats.bsize) : 0;
  const root = path.parse(target).root || target;
  const probe = process.platform === 'win32' ? probeWindowsVolume(root) : { serial: '', filesystem: '', guid: '' };
  const parent = path.dirname(target);
  const shortPath = root && path.basename(target) ? `${root.replace(/[\\/]+$/, '')}\\...\\${path.basename(target)}` : target;
  return {
    path: target,
    volume_root: root,
    short_path: shortPath,
    parent,
    volumes: [target, parent],
    guid: probe.guid,
    serial: probe.serial,
    mount_point: root,
    filesystem: probe.filesystem || (stats ? String(stats.type) : 'unknown'),
    total_bytes: stats ? blockSize * Number(stats.blocks) : null,
    free_bytes: stats ? blockSize * Number(stats.bavail) : null,
    available_bytes: stats ? blockSize * Number(stats.bfree) : null,
  };
}
