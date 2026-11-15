/**
 * File selection for the JS clone: an exact operator selection *or* folder
 * discovery narrowed by the shared filter grammar.
 *
 * Port of hash_report_generator/file_selection.py (explicit selection) plus the
 * discovery policy from chronoseal/pipeline.py and hash_report_generator:
 *   * an empty selection means "no explicit selection" - discovery runs;
 *   * discovery never widens a selection: unreadable files are reported and the
 *     caller must fail closed unless the operator allowed them;
 *   * symbolic links are not followed by default;
 *   * the JSON keys of `relative()` are strings, never path objects.
 */
import fs from 'node:fs';
import path from 'node:path';
import { matches as filterMatches, parse as parseFilters, describe as describeFilters } from '../../tools/jsx/file-filters.mjs';
import { casefold, commonDirectory, posix, uniquePaths } from './util.mjs';

export const ENV_FILES = 'CHRONOSEAL_EXPLICIT_FILES';
export const MAX_FILES = 20000;

/** Folders that never belong to an evidence package. */
export const DISCOVERY_SKIP = Object.freeze(new Set([
  '.git', '.hg', '.svn', 'node_modules', '__pycache__', '.chronoseal-venv',
  '.cache', '.pytest_cache', '.venv', 'venv',
]));

function decodeList(value) {
  const text = String(value).trim();
  if (!text) return [];
  if (text.startsWith('[')) {
    let loaded;
    try {
      loaded = JSON.parse(text);
    } catch (error) {
      throw new Error(`${ENV_FILES} is not valid JSON: ${error.message}`);
    }
    if (!Array.isArray(loaded)) throw new Error(`${ENV_FILES} must hold a JSON array of paths.`);
    return loaded;
  }
  return [text];
}

export function parse(values) {
  if (values === null || values === undefined) return [];
  let list;
  if (typeof values === 'string') list = decodeList(values);
  else if (Array.isArray(values) || values instanceof Set) list = [...values];
  else if (typeof values === 'object' && typeof values.path === 'string') list = [values];
  else throw new Error('An explicit file selection must be a path, a list of paths or a JSON array.');

  const ordered = [];
  for (const item of list) {
    if (item === null || item === undefined) continue;
    if (typeof item === 'string' && !item.trim()) continue;
    let resolved;
    try {
      resolved = fs.realpathSync.native(String(item));
    } catch {
      resolved = path.resolve(String(item));
    }
    ordered.push(resolved);
    if (ordered.length > MAX_FILES) throw new Error(`Too many selected files (limit ${MAX_FILES}).`);
  }
  return uniquePaths(ordered);
}

export function fromEnv(environment = process.env) {
  return parse(environment[ENV_FILES]);
}

export function toEnv(values) {
  return JSON.stringify(parse(values));
}

export function missing(values) {
  return parse(values).filter((file) => !fs.statSync(file, { throwIfNoEntry: false })?.isFile());
}

export function root(values) {
  const items = parse(values);
  if (!items.length) throw new Error('The file selection is empty, so it has no common root folder.');
  return commonDirectory(items.map((file) => path.dirname(file)));
}

export function relative(values, base = null) {
  const items = parse(values);
  if (!items.length) return {};
  const anchor = base === null ? root(items) : path.resolve(String(base));
  const mapping = {};
  for (const file of items) {
    const rel = path.relative(anchor, file);
    mapping[file] = rel.startsWith('..') ? posix(file).replace(/^\/+/, '') : posix(rel);
  }
  return mapping;
}

export function entries(values, base = null) {
  const items = parse(values);
  const mapping = relative(items, base);
  return items.map((file) => ({ path: file, rel_path: mapping[file] }));
}

export function describe(values) {
  const items = parse(values);
  if (!items.length) return 'no explicit file selection';
  let names = items.slice(0, 5).map((file) => path.basename(file)).join(', ');
  if (items.length > 5) names += ` and ${items.length - 5} more`;
  return `${items.length} explicitly selected file(s): ${names}`;
}

export function auditPayload(values) {
  const items = parse(values);
  if (!items.length) return { explicit_selection: false };
  const mapping = relative(items);
  return {
    explicit_selection: true,
    selection_root: root(items),
    selection_count: items.length,
    selection_files: items.map((file) => ({ path: file, rel_path: mapping[file] })),
  };
}

function readable(file) {
  try {
    const fd = fs.openSync(file, 'r');
    fs.closeSync(fd);
    return true;
  } catch {
    return false;
  }
}

function walk(folder, recursive, out, audit, { followLinks }) {
  let entriesInFolder;
  try {
    entriesInFolder = fs.readdirSync(folder, { withFileTypes: true });
  } catch {
    audit.unreadable.push(folder);
    return;
  }
  for (const entry of entriesInFolder) {
    const full = path.join(folder, entry.name);
    let stat;
    try {
      stat = fs.lstatSync(full);
    } catch {
      audit.unreadable.push(full);
      continue;
    }
    if (stat.isSymbolicLink()) {
      if (!followLinks) {
        audit.skipped_link_count += 1;
        continue;
      }
      try {
        stat = fs.statSync(full);
      } catch {
        audit.unreadable.push(full);
        continue;
      }
    }
    if (stat.isDirectory()) {
      if (DISCOVERY_SKIP.has(entry.name.toLowerCase())) continue;
      if (recursive) walk(full, recursive, out, audit, { followLinks });
      continue;
    }
    if (stat.isFile()) out.push(full);
  }
}

/**
 * Folder discovery with the shared filter grammar.
 *
 * @returns {{root: string, files: string[], audit: object}}
 */
export function discover({
  source,
  recursive = false,
  filters = [],
  followLinks = false,
  allowUnreadable = false,
}) {
  const start = path.resolve(String(source));
  const stat = fs.statSync(start, { throwIfNoEntry: false });
  if (!stat) throw new Error(`Source does not exist: ${start}`);
  const base = stat.isDirectory() ? start : path.dirname(start);
  const parsedFilters = parseFilters(filters);
  const audit = { unreadable: [], unreadable_count: 0, skipped_link_count: 0, excluded_by_filter_count: 0 };
  let found;
  if (stat.isDirectory()) {
    found = [];
    walk(start, recursive, found, audit, { followLinks });
  } else {
    found = [start];
  }
  const kept = [];
  for (const file of found) {
    const rel = posix(path.relative(base, file));
    const name = path.basename(file);
    if (!readable(file)) {
      audit.unreadable.push(file);
      continue;
    }
    if (!filterMatches(name, rel, parsedFilters)) {
      audit.excluded_by_filter_count += 1;
      continue;
    }
    kept.push(file);
  }
  audit.unreadable_count = audit.unreadable.length;
  if (audit.unreadable_count && !allowUnreadable) {
    throw new Error(`Unreadable file(s) in evidence set: ${audit.unreadable.slice(0, 5).join(', ')}`);
  }
  kept.sort((a, b) => {
    const left = casefold(posix(path.relative(base, a)));
    const right = casefold(posix(path.relative(base, b)));
    if (left === right) return 0;
    return left < right ? -1 : 1;
  });
  return { root: base, files: kept, audit, filters: parsedFilters, filter_note: describeFilters(parsedFilters) };
}

/**
 * One entry point for both routes: an explicit selection wins over discovery.
 *
 * @returns {{files: string[], root: string, explicit: boolean, audit: object|null,
 *            filters: string[], filter_note: string}}
 */
export function resolveSelection({
  files = [],
  source = null,
  recursive = false,
  filters = [],
  followLinks = false,
  allowUnreadable = false,
}) {
  const explicit = parse(files);
  if (explicit.length) {
    const gone = missing(explicit);
    if (gone.length) {
      throw new Error('Selected file(s) are missing or not regular files: ' + gone.slice(0, 5).join(', '));
    }
    const parsedFilters = parseFilters(filters);
    return {
      files: explicit,
      root: root(explicit),
      explicit: true,
      audit: { ...auditPayload(explicit), unreadable_count: 0, skipped_link_count: 0, excluded_by_filter_count: 0 },
      filters: parsedFilters,
      filter_note: describeFilters(parsedFilters),
    };
  }
  if (!source) throw new Error('A source folder is required when no files are selected explicitly.');
  const discovered = discover({ source, recursive, filters, followLinks, allowUnreadable });
  if (!discovered.files.length) {
    throw new Error('No files match the discovery policy in ' + discovered.root);
  }
  return {
    files: discovered.files,
    root: discovered.root,
    explicit: false,
    audit: {
      explicit_selection: false,
      unreadable_count: discovered.audit.unreadable_count,
      skipped_link_count: discovered.audit.skipped_link_count,
      excluded_by_filter_count: discovered.audit.excluded_by_filter_count,
    },
    filters: discovered.filters,
    filter_note: discovered.filter_note,
  };
}
