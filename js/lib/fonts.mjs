/**
 * Unicode font resolution and text measurement for the JS clone.
 *
 * The rule files declare the policy (style/25_font_families.js): embedded
 * Unicode TrueType only, never a builtin fallback, resolved from the operating
 * system. This module therefore fails loudly when a candidate is missing instead
 * of silently degrading to a non-embedded standard font.
 */
import fs from 'node:fs';
import path from 'node:path';
import { TrueTypeFont } from '../../tools/pdfnorm/lib/fonts.mjs';
import { loadStyles } from '../../tools/jsx/style-loader.mjs';

export const ROLES = Object.freeze([
  'regular', 'bold', 'italic', 'bold_italic', 'monospace', 'monospace_bold',
]);

const CACHE = new Map();
let POLICY = null;

function policy() {
  if (POLICY === null) {
    const styles = loadStyles();
    POLICY = {
      families: styles.FONT_FAMILIES,
      files: styles.FONT_FILES || {},
      policy: styles.FONT_POLICY,
    };
  }
  return POLICY;
}

export function invalidate() {
  CACHE.clear();
  POLICY = null;
}

function candidateFiles(role) {
  const { files, policy: rules } = policy();
  const configured = files[role] || files[policy().families[role]] || null;
  const list = [];
  if (configured) {
    for (const item of Array.isArray(configured) ? configured : [configured]) list.push(String(item));
  }
  const system = (rules.system_font_candidates || {})[role] || [];
  for (const item of system) list.push(String(item));
  return list;
}

/**
 * Resolve and parse the TrueType program for one typographic role.
 *
 * @returns {{role: string, family: string, file: string, font: TrueTypeFont}}
 */
export function resolveFont(role) {
  if (!ROLES.includes(role)) throw new Error('Unknown font role: ' + role);
  const cached = CACHE.get(role);
  if (cached) return cached;
  const rules = policy().policy || {};
  if (rules.require_embedded_unicode !== true) {
    throw new Error('FONT_POLICY.require_embedded_unicode must stay true');
  }
  const tried = [];
  for (const candidate of candidateFiles(role)) {
    tried.push(candidate);
    const stat = fs.statSync(candidate, { throwIfNoEntry: false });
    if (!stat || !stat.isFile()) continue;
    const font = TrueTypeFont.load(new Uint8Array(fs.readFileSync(candidate)));
    const resolved = {
      role,
      family: policy().families[role] || path.basename(candidate, path.extname(candidate)),
      file: candidate,
      font,
    };
    CACHE.set(role, resolved);
    return resolved;
  }
  if (rules.fallback_to_builtin === true) {
    throw new Error('FONT_POLICY.fallback_to_builtin cannot be honoured: no embedded Unicode TrueType available for ' + role);
  }
  throw new Error(`No embedded Unicode font found for role ${role}. Tried: ${tried.join(', ')}`);
}

/** Glyph id for one code point (0 = .notdef, exactly like the Python side). */
export function glyphId(font, codePoint) {
  return font.cmap().get(codePoint) || 0;
}

/** Advance width in text space units (1/1000 em), the unit PDF expects in /W. */
export function advanceWidth(font, gid) {
  return Math.round((font.advance(gid) * 1000) / font.unitsPerEm);
}

const WIDTH_CACHE = new Map();

/** Width of a string in points at `size`, measured with the embedded program. */
export function measureText(role, text, size) {
  const resolved = resolveFont(role);
  const key = role + '\u0000' + size + '\u0000' + text;
  const cached = WIDTH_CACHE.get(key);
  if (cached !== undefined) return cached;
  let total = 0;
  for (const character of String(text)) {
    const codePoint = character.codePointAt(0);
    total += advanceWidth(resolved.font, glyphId(resolved.font, codePoint));
  }
  const points = (total * size) / 1000;
  if (WIDTH_CACHE.size > 20000) WIDTH_CACHE.clear();
  WIDTH_CACHE.set(key, points);
  return points;
}

/** Greedy word wrap into lines that fit `maxWidth` points. */
export function wrapText(role, text, size, maxWidth) {
  const source = String(text);
  if (maxWidth <= 0) return [source];
  if (!source) return [''];
  const words = source.split(/\s+/).filter((word) => word.length > 0);
  if (!words.length) return [''];
  const lines = [];
  let current = words[0];
  for (const word of words.slice(1)) {
    const candidate = `${current} ${word}`;
    if (measureText(role, candidate, size) <= maxWidth) {
      current = candidate;
      continue;
    }
    lines.push(current);
    current = word;
  }
  lines.push(current);
  return lines;
}

/**
 * Break one long token (a path or a digest without separators) so it never
 * overflows its column: the report must stay inside the audited margins.
 */
export function wrapToken(role, token, size, maxWidth) {
  const text = String(token);
  if (!text) return [''];
  if (measureText(role, text, size) <= maxWidth) return [text];
  const parts = [];
  let current = '';
  for (const character of text) {
    const candidate = current + character;
    if (current && measureText(role, candidate, size) > maxWidth) {
      parts.push(current);
      current = character;
    } else {
      current = candidate;
    }
  }
  if (current) parts.push(current);
  return parts;
}

/** Wrap a paragraph, breaking over-long tokens inside each line. */
export function wrapParagraph(role, text, size, maxWidth) {
  const out = [];
  for (const line of wrapText(role, text, size, maxWidth)) {
    if (measureText(role, line, size) <= maxWidth) {
      out.push(line);
      continue;
    }
    const pieces = [];
    for (const word of line.split(' ')) pieces.push(...wrapToken(role, word, size, maxWidth));
    out.push(...pieces);
  }
  return out;
}
