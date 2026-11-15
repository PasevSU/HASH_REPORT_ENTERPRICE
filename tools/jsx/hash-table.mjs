// 1:1 JavaScript port of hash_report_generator/hash_table_engine.py.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

export const MODES = ['single_file', 'current_folder', 'recursive_folder'];
const ALGORITHMS = new Set(['sha256', 'sha512', 'sha1', 'md5']);
const CHUNK = 1024 * 1024;

export function casefold(value) {
  // Python str.casefold() differs from toLowerCase() only for a few scalars.
  const folded = String(value).toLowerCase();
  return folded.replace(/\u00df/g, 'ss').replace(/\ufb00/g, 'ff').replace(/\ufb01/g, 'fi')
    .replace(/\ufb02/g, 'fl').replace(/\ufb03/g, 'ffi').replace(/\ufb04/g, 'ffl');
}

function resolveExisting(target) {
  const abs = path.resolve(target);
  try {
    return fs.realpathSync.native ? fs.realpathSync.native(abs) : fs.realpathSync(abs);
  } catch (err) {
    if (err && err.code === 'ENOENT') throw Object.assign(new Error(`No such file or directory: '${target}'`), { code: 'ENOENT' });
    throw err;
  }
}

function toPosix(value) {
  return value.split(path.sep).join('/');
}

function walk(dir, recursive, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    let stat;
    try {
      stat = fs.lstatSync(full, { bigint: true });
    } catch {
      continue;
    }
    if (stat.isSymbolicLink()) continue;
    if (stat.isDirectory()) {
      if (recursive) walk(full, recursive, out);
      continue;
    }
    if (stat.isFile()) out.push(full);
  }
}

export function collectFiles(source, mode, { exclude = [] } = {}) {
  if (!MODES.includes(mode)) throw new Error(`Unsupported scope: ${mode}`);
  const root = resolveExisting(source);
  const ignored = new Set([...exclude].map((p) => resolveExisting(p)));
  const rootStat = fs.statSync(root);
  if (mode === 'single_file') {
    if (!rootStat.isFile()) throw new Error('single_file requires a file');
    return { root: path.dirname(root), files: ignored.has(root) ? [] : [root] };
  }
  if (!rootStat.isDirectory()) throw new Error('folder scope requires a directory');
  const found = [];
  walk(root, mode === 'recursive_folder', found);
  const files = found.filter((p) => !ignored.has(resolveExisting(p)));
  files.sort((a, b) => {
    const ka = casefold(toPosix(path.relative(root, a)));
    const kb = casefold(toPosix(path.relative(root, b)));
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });
  return { root, files };
}

export function formatUtcDate(ns) {
  const big = typeof ns === 'bigint' ? ns : BigInt(Math.round(Number(ns) * 1e9));
  const us = (big + 500n) / 1000n;
  const ms = Number(us / 1000n);
  const d = new Date(ms);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} `
    + `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}.`
    + `${p(d.getUTCMilliseconds(), 3)} UTC`;
}

export const _date = (ts) => formatUtcDate(BigInt(Math.round(Number(ts) * 1e9)));

function statParts(stat) {
  return {
    size: stat.size,
    mtimeNs: stat.mtimeNs,
    ino: stat.ino,
  };
}

export function inspectFile(file, root, algorithms = ['sha256']) {
  const list = [...algorithms];
  if (!list.length || list.some((a) => !ALGORITHMS.has(a))) throw new Error('Invalid hash algorithms');
  const before = fs.statSync(file, { bigint: true });
  const digests = new Map(list.map((a) => [a, createHash(a)]));
  const fd = fs.openSync(file, 'r');
  try {
    const buffer = Buffer.allocUnsafe(CHUNK);
    for (;;) {
      const read = fs.readSync(fd, buffer, 0, CHUNK, null);
      if (!read) break;
      const slice = buffer.subarray(0, read);
      for (const digest of digests.values()) digest.update(slice);
    }
  } finally {
    fs.closeSync(fd);
  }
  const after = fs.statSync(file, { bigint: true });
  const b = statParts(before);
  const a = statParts(after);
  if (b.size !== a.size || b.mtimeNs !== a.mtimeNs || b.ino !== a.ino) {
    throw new Error(`File changed during hashing: ${file}`);
  }
  const suffix = path.extname(file).toLowerCase().replace(/^\./, '');
  const row = {
    path: toPosix(path.relative(root, file)),
    type: suffix || 'file',
    size_bytes: Number(before.size),
    created: formatUtcDate(before.birthtimeNs || before.ctimeNs),
    modified: formatUtcDate(before.mtimeNs),
  };
  for (const [algorithm, digest] of digests) row[algorithm] = digest.digest('hex');
  return row;
}

export const inspect_file = inspectFile;

export function buildRows(source, mode, { algorithms = ['sha256'], exclude = [] } = {}) {
  const { root, files } = collectFiles(source, mode, { exclude });
  return files.map((file, i) => ({ index: i + 1, ...inspectFile(file, root, algorithms) }));
}

export const build_rows = buildRows;