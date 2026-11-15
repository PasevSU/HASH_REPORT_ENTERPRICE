/**
 * In-process replacement for hash_report_generator/style_loader.py together with
 * js_rules.py and js_rules_runner.cjs.
 *
 * The Python implementation spawns a Node child process (capped at 64 MB) for every
 * style load, and the generator loads styles four times per run. This module reads
 * and evaluates the same declarative rule files inside the process that already runs
 * Node, so one loadStyles() costs a handful of file reads instead of a process spawn.
 *
 * Everything observable is kept identical to Python: discovery order, merge order,
 * duplicate detection, mandatory-section validation, error text, and the JSON-shaped
 * result (the Python side only ever sees the runner's JSON payload, so a JSON
 * round-trip reproduces its semantics exactly - including dropped undefined values).
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { fnmatchcase } from './lib/glob.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');

export const STYLE_DIR = path.join(REPO_ROOT, 'hash_report_generator', 'style');
export const DEFAULT_PATTERN = '*.js';
export const MAX_RULE_BYTES = 200000;
export const RULE_TIMEOUT_MS = 1000;
export const REQUIRED = Object.freeze([
  'PAGE', 'COLORS', 'FONTS', 'LEADING', 'TABLE', 'COLUMNS', 'OBJECTS',
  'LEGAL_CONTAINER', 'KEY_VALUE', 'SIZE_UNIT', 'TITLE_HIERARCHY', 'FONT_FAMILIES',
  'FONT_FILES', 'FONT_POLICY', 'BRIDGE_LAYOUT', 'REPORT_BLOCK_CONTRACT',
]);

const CACHE = new Map();
const LAZY = { visual: null, layout: null };

export function invalidate(directory = null, pattern = DEFAULT_PATTERN) {
  if (directory === null && pattern === DEFAULT_PATTERN) {
    CACHE.clear();
    LAZY.visual = null;
    LAZY.layout = null;
    return;
  }
  const folder = directory === null ? STYLE_DIR : String(directory);
  CACHE.delete(cacheKey(folder, pattern, directory === null));
}

function cacheKey(folder, pattern, isDefault) {
  return folder + '\u0000' + pattern + '\u0000' + (isDefault ? '1' : '0');
}

function plainCopy(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function pyRepr(value) {
  const text = String(value);
  const escaped = text
    .split(String.fromCharCode(92)).join(String.fromCharCode(92, 92))
    .split("'").join(String.fromCharCode(92) + "'");
  return "'" + escaped + "'";
}

function pyListRepr(values) {
  return '[' + values.map(pyRepr).join(', ') + ']';
}

function ruleError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function missingDirectory(folder) {
  const error = new Error('Style directory missing: ' + folder);
  error.code = 'ENOENT';
  return error;
}

function canonical(folder) {
  try {
    return fs.realpathSync(folder);
  } catch {
    return path.resolve(folder);
  }
}

function isDir(target) {
  const stat = fs.statSync(target, { throwIfNoEntry: false });
  return Boolean(stat && stat.isDirectory());
}

/**
 * Sorted rule files under `folder`, mirroring pathlib's Windows ordering: the sort
 * key is the lower-cased absolute path, so `str(p).lower()` ordering is preserved
 * and the list is stable for equal keys.
 */
export function discoverRuleFiles(folder, pattern = DEFAULT_PATTERN) {
  const root = String(folder);
  if (!isDir(root)) throw missingDirectory(root);
  const found = [];
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && fnmatchcase(entry.name.toLowerCase(), pattern.toLowerCase())) {
        found.push(full);
      }
    }
  };
  walk(root);
  if (found.length === 0) throw new Error('No style definitions found in ' + root);
  return found.sort((a, b) => {
    const left = a.toLowerCase();
    const right = b.toLowerCase();
    return left < right ? -1 : left > right ? 1 : 0;
  });
}

/** Read and evaluate one declarative rule file, applying the runner's hardening. */
export function readRuleDocument(base, file) {
  const requested = path.resolve(file);
  let entry;
  try {
    entry = fs.lstatSync(requested);
  } catch {
    throw ruleError('MISSING_FILE', 'JS rule file is missing: ' + requested);
  }
  if (entry.isSymbolicLink()) throw ruleError('SYMLINK', 'Invalid JS rule path: ' + requested);
  let real;
  try {
    real = fs.realpathSync(requested);
  } catch {
    throw ruleError('UNREADABLE', 'JS rule file is missing: ' + requested);
  }
  if (real !== base && !real.startsWith(base + path.sep)) {
    throw ruleError('OUTSIDE', 'Invalid JS rule path: ' + requested);
  }
  if (!real.endsWith('.js')) throw ruleError('SUFFIX', 'Invalid JS rule path: ' + requested);
  if (!entry.isFile()) throw ruleError('NOT_FILE', 'JS rule file is missing: ' + requested);

  let source;
  try {
    source = fs.readFileSync(real, 'utf8');
  } catch {
    throw ruleError('UNREADABLE', 'JS rule file is missing: ' + real);
  }
  if (source.length > MAX_RULE_BYTES) throw ruleError('TOO_LARGE', 'JS rule is too large: ' + real);

  const sandbox = vm.createContext(
    { module: { exports: null } },
    { codeGeneration: { strings: false, wasm: false } },
  );
  try {
    new vm.Script(source, { filename: real }).runInContext(sandbox, { timeout: RULE_TIMEOUT_MS });
  } catch (error) {
    throw ruleError('EVALUATION', 'JS rules failed to load: ' + real + ': ' + (error && error.message));
  }
  const data = sandbox.module.exports;
  if (!data || Array.isArray(data) || typeof data !== 'object') {
    throw ruleError('NOT_OBJECT', 'Style root must be an object: ' + requested);
  }
  return plainCopy(data);
}

function merge(target, source, origin) {
  for (const key of Object.keys(source)) {
    if (Object.prototype.hasOwnProperty.call(target, key)) {
      const mine = target[key];
      const theirs = source[key];
      if (isPlainObject(mine) && isPlainObject(theirs)) {
        merge(mine, theirs, origin);
      } else {
        throw new Error('Duplicate style rule ' + pyRepr(key) + ' in ' + origin);
      }
    } else {
      target[key] = plainCopy(source[key]);
    }
  }
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Merge every rule file in `directory` (default: the packaged style folder).
 *
 * @param {{directory?: string|null, pattern?: string}} [options]
 * @returns {object} fresh deep copy; callers may mutate it freely.
 */
export function loadStyles({ directory = null, pattern = DEFAULT_PATTERN } = {}) {
  const isDefault = directory === null;
  const folder = isDefault ? STYLE_DIR : String(directory);
  const key = cacheKey(folder, pattern, isDefault);
  const cached = CACHE.get(key);
  if (cached !== undefined) return plainCopy(cached);

  if (!isDir(folder)) throw missingDirectory(folder);
  const base = canonical(folder);
  const merged = {};
  for (const file of discoverRuleFiles(folder, pattern)) {
    merge(merged, readRuleDocument(base, file), path.resolve(file));
  }
  if (isDefault) validateRequiredSections(merged);
  CACHE.set(key, merged);
  return plainCopy(merged);
}

function visualRules() {
  if (LAZY.visual === null) LAZY.visual = loadStyles().MIGRATED_VISUAL_LITERALS;
  return LAZY.visual;
}

function layoutRules() {
  if (LAZY.layout === null) LAZY.layout = loadStyles().CENTRAL_LAYOUT;
  return LAZY.layout;
}

/** Mandatory-section gate; Python applies it only for the packaged rule folder. */
export function validateRequiredSections(payload) {
  const missing = REQUIRED
    .filter((name) => !Object.prototype.hasOwnProperty.call(payload || {}, name))
    .sort();
  if (missing.length) throw new Error('Missing mandatory style sections: ' + pyListRepr(missing));
  return true;
}

/** Port of style_runtime.visual(key): strict, no local defaults. */
export function visual(key) {
  const table = visualRules();
  if (!Object.prototype.hasOwnProperty.call(table, key)) {
    throw new Error('Missing migrated visual literal: ' + key);
  }
  return plainCopy(table[key]);
}

/** Port of style_runtime.layout_rule(*path): strict path walk. */
export function layoutRule(...keys) {
  let node = layoutRules();
  const walked = [];
  for (const key of keys) {
    walked.push(key);
    if (!isPlainObject(node) && !Array.isArray(node)) {
      throw new Error('Missing layout rule: ' + walked.join('/'));
    }
    if (!Object.prototype.hasOwnProperty.call(node, key)) {
      throw new Error('Missing layout rule: ' + walked.join('/'));
    }
    node = node[key];
  }
  return plainCopy(node);
}

export const load_styles = loadStyles;
export const layout_rule = layoutRule;