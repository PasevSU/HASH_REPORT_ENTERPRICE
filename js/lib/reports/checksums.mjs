/**
 * Text checksums for the JS clone (port of chronoseal/page_identity.py).
 *
 * The checksummed text is the text the layout actually drew: every body draw
 * call records its string, footer draws are excluded, and each page is
 * normalised once (trailing blanks removed, empty lines dropped, NFC) before the
 * digests are taken. Per-page framing is an 8-byte big-endian length followed by
 * the UTF-8 page text, which is what the Python report publishes, so the scope
 * of a value is reproducible from the report itself.
 *
 * The checksum appendix is excluded from the scope: it publishes numbers about
 * pages that were hashed before the appendix existed, so it never hashes itself.
 */
import { createHash } from 'node:crypto';

/** The six algorithms printed in every page footer. */
export const PAGE_TEXT_ALGORITHMS = Object.freeze([
  'MD5', 'SHA-1', 'SHA-224', 'SHA-256', 'SHA-384', 'SHA-512',
]);

/** The eleven algorithms hash_report_core.py never substitutes. */
export const ALL_TEXT_ALGORITHMS = Object.freeze([
  ...PAGE_TEXT_ALGORITHMS, 'SHA3-224', 'SHA3-256', 'SHA3-384', 'SHA3-512', 'RIPEMD-160',
]);

const CRYPTO_NAMES = Object.freeze({
  'MD5': 'md5',
  'SHA-1': 'sha1',
  'SHA-224': 'sha224',
  'SHA-256': 'sha256',
  'SHA-384': 'sha384',
  'SHA-512': 'sha512',
  'SHA3-224': 'sha3-224',
  'SHA3-256': 'sha3-256',
  'SHA3-384': 'sha3-384',
  'SHA3-512': 'sha3-512',
  'RIPEMD-160': 'ripemd160',
});

function hasher(label) {
  const name = CRYPTO_NAMES[label];
  if (!name) throw new Error(`Unknown text checksum algorithm: ${label}`);
  return createHash(name);
}

/** Lowercase hexadecimal digest; display code upper-cases, verification does not. */
export function digestText(label, text) {
  return hasher(label).update(String(text), 'utf8').digest('hex');
}

export function digestBytes(label, bytes) {
  return hasher(label).update(bytes).digest('hex');
}

const DIGEST_LENGTHS = new Map();

/** Hex length per algorithm, used to reserve a stable slot in the appendix. */
export function digestLength(label) {
  if (!DIGEST_LENGTHS.has(label)) DIGEST_LENGTHS.set(label, digestText(label, '').length);
  return DIGEST_LENGTHS.get(label);
}

/**
 * Canonical page text: trailing blanks removed per line, empty lines dropped,
 * lines joined with LF, then Unicode NFC.
 */
export function normalisePageText(lines) {
  return (lines || [])
    .map((line) => String(line).replace(/[ \t]+$/, ''))
    .filter((line) => line.length > 0)
    .join('\n')
    .normalize('NFC');
}

/** Eight-byte big-endian framing of the page texts, concatenated. */
export function framePageTexts(texts) {
  const chunks = [];
  for (const text of texts) {
    const encoded = Buffer.from(text, 'utf8');
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(encoded.length));
    chunks.push(length, encoded);
  }
  return Buffer.concat(chunks);
}

function digestsFor(labels, text) {
  const out = {};
  for (const label of labels) out[label] = digestText(label, text);
  return out;
}

/** All six footer algorithms for one page. */
export function pageDigests(text) {
  return digestsFor(PAGE_TEXT_ALGORITHMS, text);
}

/** All eleven algorithms over the framed document text. */
export function documentDigests(texts) {
  return digestsFor(ALL_TEXT_ALGORITHMS, framePageTexts(texts));
}

/** Footer lines for one page: heading plus the six page algorithms. */
export function footerHashLines(digests) {
  const lines = ["PAGE TEXT HASHES (UTF-8 / NFC; footer excluded)"];
  for (const label of PAGE_TEXT_ALGORITHMS) {
    const value = (digests || {})[label];
    if (!value) continue;
    lines.push(`${label}: ${String(value).toUpperCase()}`);
  }
  return lines;
}

/**
 * Placeholder with the exact width of a real digest: a rehearsal pass can run
 * with unknown values and still produce the very same line breaks and page
 * count, so the pass that prints the real values stays byte-stable.
 */
export function placeholderDigests(labels = ALL_TEXT_ALGORITHMS) {
  const out = {};
  for (const label of labels) out[label] = 'X'.repeat(digestLength(label));
  return out;
}