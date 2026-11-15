/**
 * Shared primitives for the pure-JavaScript ChronoSeal clone (js/).
 *
 * Ported semantics from chronoseal/util.py and hash_report_generator/hash_report_core.py:
 *   * sha256 - 1 MiB chunks, never a whole file in memory;
 *   * jsonSafe - a manifest may never carry a non-JSON value (the WindowsPath
 *     blocker of v5.5.x), so every value is normalised before serialisation;
 *   * atomicWrite* - write to a sibling temp file, then rename, retrying the
 *     transient Windows sharing violations that antivirus and the search
 *     indexer produce on SMB shares.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

export const MM = 72 / 25.4;
export const A4_PT = Object.freeze([210 * MM, 297 * MM]);
export const CHUNK_SIZE = 1024 * 1024;

/** Windows sharing/lock errors that a retry can outlive. */
export const WINDOWS_TRANSIENT = new Set(['EPERM', 'EBUSY', 'EACCES', 'EAGAIN']);

const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: false });

export function utf8(text) {
  return encoder.encode(text);
}

export function fromUtf8(bytes) {
  return decoder.decode(bytes);
}

export function pad(value, width = 2) {
  return String(value).padStart(width, '0');
}

export function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

export function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

/** Create one directory that must not exist yet (`Path.mkdir(exist_ok=False)`). */
export function makeDirExclusive(dir) {
  fs.mkdirSync(dir, { recursive: false });
  return dir;
}

export function posix(value) {
  return String(value).split(path.sep).join('/');
}

/** Python str.casefold() approximation used by the hash-table ordering. */
export function casefold(value) {
  return String(value)
    .replace(/\u00df/g, 'ss')
    .replace(/\ufb00/g, 'ff')
    .replace(/\ufb01/g, 'fi')
    .replace(/\ufb02/g, 'fl')
    .replace(/\ufb03/g, 'ffi')
    .replace(/\ufb04/g, 'ffl')
    .replace(/\ufb05/g, 'st')
    .replace(/\ufb06/g, 'st')
    .toLowerCase();
}

export function sha256File(file) {
  const digest = createHash('sha256');
  const buffer = Buffer.allocUnsafe(CHUNK_SIZE);
  const fd = fs.openSync(file, 'r');
  try {
    for (;;) {
      const read = fs.readSync(fd, buffer, 0, CHUNK_SIZE, null);
      if (!read) break;
      digest.update(buffer.subarray(0, read));
    }
  } finally {
    fs.closeSync(fd);
  }
  return digest.digest('hex');
}

export function sha256Bytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

/** SHA-256 over many hex digests in order (the aggregated document proof). */
export function sha256Digests(digests) {
  const digest = createHash('sha256');
  for (const value of digests) digest.update(String(value).toLowerCase(), 'utf8');
  return digest.digest('hex');
}

export function formatUtc(date, { millis = true } = {}) {
  const d = date instanceof Date ? date : new Date(date);
  const base = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
    + ` ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  return millis ? `${base}.${pad(d.getUTCMilliseconds(), 3)}` : base;
}

/** Report stamp: %Y%m%d-%H%M%S + milliseconds. */
export function formatStamp(date) {
  const d = date instanceof Date ? date : new Date(date);
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`
    + `-${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}`
    + pad(d.getUTCMilliseconds(), 3);
}

function isPlainObject(value) {
  if (!value || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

/**
 * Return a JSON-safe copy. Mirrors util.json_safe: path-like values become
 * strings and containers are rebuilt, so a manifest can never fail with
 * "keys must be str, int, float, bool or None".
 */
export function jsonSafe(value, seen = new Set()) {
  if (value === null || value === undefined) return null;
  const type = typeof value;
  if (type === 'string' || type === 'boolean') return value;
  if (type === 'number') return Number.isFinite(value) ? value : String(value);
  if (type === 'bigint') return Number.isSafeInteger(Number(value)) ? Number(value) : String(value);
  if (type === 'function' || type === 'symbol') {
    throw new TypeError(`Manifest value of type ${type} cannot be serialised`);
  }
  if (value instanceof Date) return value.toISOString();
  if (value instanceof URL) return value.href;
  if (Buffer.isBuffer(value) || value instanceof Uint8Array) return `${value.length} bytes`;
  if (seen.has(value)) throw new TypeError('Manifest value contains a cycle');
  seen.add(value);
  try {
    if (Array.isArray(value) || value instanceof Set) {
      return [...value].map((item) => jsonSafe(item, seen));
    }
    if (value instanceof Map) {
      const out = {};
      for (const [key, item] of value) out[String(key)] = jsonSafe(item, seen);
      return out;
    }
    if (isPlainObject(value)) {
      const out = {};
      for (const [key, item] of Object.entries(value)) out[String(key)] = jsonSafe(item, seen);
      return out;
    }
    if (typeof value.toString === 'function' && value.toString !== Object.prototype.toString) {
      return String(value);
    }
    throw new TypeError('Manifest value is not JSON serialisable: ' + Object.prototype.toString.call(value));
  } finally {
    seen.delete(value);
  }
}

function renameWithRetry(source, destination, attempts = 5) {
  let lastError = null;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      fs.renameSync(source, destination);
      return;
    } catch (error) {
      lastError = error;
      if (!WINDOWS_TRANSIENT.has(error.code) || attempt === attempts) throw error;
      sleepSync(200 * attempt);
    }
  }
  throw lastError;
}

export function atomicWriteBytes(target, bytes) {
  const file = path.resolve(String(target));
  ensureDir(path.dirname(file));
  let attempt = 0;
  for (;;) {
    attempt += 1;
    const temp = path.join(
      path.dirname(file),
      `.${path.basename(file)}.${process.pid}.${Date.now().toString(36)}.${attempt}.tmp`,
    );
    try {
      fs.writeFileSync(temp, bytes);
      renameWithRetry(temp, file);
      return file;
    } catch (error) {
      try {
        fs.rmSync(temp, { force: true });
      } catch {
        /* the temp file never became visible evidence */
      }
      if (attempt >= 5 || !WINDOWS_TRANSIENT.has(error.code)) throw error;
      sleepSync(200 * attempt);
    }
  }
}

export function atomicWriteJson(target, data) {
  return atomicWriteBytes(target, `${JSON.stringify(jsonSafe(data), null, 2)}\n`);
}

export function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function statOrNull(target) {
  return fs.statSync(target, { throwIfNoEntry: false }) || null;
}

/** Longest folder containing every path (os.path.commonpath, one drive only). */
export function commonDirectory(paths) {
  const list = paths.map((item) => path.resolve(String(item)));
  if (!list.length) throw new Error('An empty list has no common directory');
  let parts = list[0].split(path.sep);
  for (const item of list.slice(1)) {
    const other = item.split(path.sep);
    let index = 0;
    while (index < parts.length && index < other.length
      && casefold(parts[index]) === casefold(other[index])) index += 1;
    parts = parts.slice(0, index);
  }
  const joined = parts.join(path.sep);
  const absolute = parts.length > 1 || (parts.length === 1 && /^[A-Za-z]:$/.test(joined));
  if (!joined || !absolute) throw new Error('All selected files must live on one drive');
  return path.resolve(joined);
}

/** De-duplicate case-insensitively (Windows) while preserving operator order. */
export function uniquePaths(values) {
  const seen = new Set();
  const out = [];
  for (const value of values) {
    const resolved = path.resolve(String(value));
    const key = casefold(resolved);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(resolved);
  }
  return out;
}
