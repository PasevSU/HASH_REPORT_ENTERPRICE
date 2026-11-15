// 1:1 JavaScript port of hash_report_generator/file_filters.py (v5.5.0).
import { fnmatchcase } from './lib/glob.mjs';

export const ENV_FILTERS = 'CHRONOSEAL_INCLUDE_PATTERNS';
export const ENV_CASE = 'CHRONOSEAL_FILTER_CASE_SENSITIVE';
export const MAX_FILTER_LENGTH = 512;

const SPLIT_RE = /[,;\r\n]+/;
const WILDCARD_RE = /[*?\[\]]/;
const TRUE_WORDS = new Set(['1', 'true', 'yes', 'on']);

function env(name, fallback = '') {
  return process.env[name] ?? fallback;
}

export function normalize(field) {
  if (field === null || field === undefined) return [];
  let text = String(field);
  if (text.length > MAX_FILTER_LENGTH * 4) text = text.slice(0, MAX_FILTER_LENGTH * 4);
  const out = [];
  for (const chunk of text.split(SPLIT_RE)) {
    const item = chunk.trim();
    if (item && item.length <= MAX_FILTER_LENGTH) out.push(item);
  }
  return out;
}

export function parse(values) {
  if (values === null || values === undefined) return [];
  const list = typeof values === 'string' ? [values] : values;
  const seen = new Set();
  const result = [];
  for (const value of list) {
    for (const item of normalize(value)) {
      const key = item.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(item);
    }
  }
  return result;
}

export function caseSensitive() {
  return TRUE_WORDS.has(String(env(ENV_CASE, '')).trim().toLowerCase());
}

export const case_sensitive = caseSensitive;

function matchOne(candidate, pattern, sensitive) {
  let cand = candidate;
  let pat = pattern;
  if (!sensitive) {
    cand = cand.toLowerCase();
    pat = pat.toLowerCase();
  }
  if (WILDCARD_RE.test(pat)) return fnmatchcase(cand, pat);
  return cand.includes(pat);
}

export function matches(name, relPath, filters, sensitive) {
  const items = filters || [];
  if (!items.length) return true;
  const useSensitive = sensitive === undefined || sensitive === null ? caseSensitive() : sensitive;
  const candidates = [String(name || '')];
  const rel = String(relPath || '').split('\\').join('/');
  if (rel && !candidates.includes(rel)) candidates.push(rel);
  for (const pattern of items) {
    for (const candidate of candidates) {
      if (candidate && matchOne(candidate, pattern, useSensitive)) return true;
    }
  }
  return false;
}

export function describe(filters) {
  const items = parse(filters) || [];
  return items.length ? items.join(', ') : 'none';
}

export function fromEnv() {
  const raw = String(env(ENV_FILTERS, '')).trim();
  if (!raw) return [];
  let value;
  try {
    value = JSON.parse(raw);
  } catch {
    return parse(raw);
  }
  if (typeof value === 'string') return parse(value);
  if (Array.isArray(value)) return parse(value.map((item) => String(item)));
  return [];
}

export const from_env = fromEnv;

export function toEnv(filters) {
  // Python json.dumps default separator is `, ` - match it byte for byte.
  return '[' + parse(filters).map((item) => JSON.stringify(item)).join(', ') + ']';
}

export const to_env = toEnv;

export function auditPayload(filters) {
  const items = parse(filters) || [];
  return {
    filters: items,
    filter_count: items.length,
    filter_case_sensitive: caseSensitive(),
    filter_description: describe(items),
  };
}

export const audit_payload = auditPayload;