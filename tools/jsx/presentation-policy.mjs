/**
 * JavaScript port of hash_report_generator/document_presentation_policy.py.
 *
 * Presentation only: nothing here may touch cryptographic bytes. The policy values
 * are read from the same declarative rules (CENTRAL_LAYOUT.document_policy) the
 * Python module reads through style_runtime.layout_rule, so the two implementations
 * cannot drift apart without failing their parity test.
 */
import { layoutRule } from './style-loader.mjs';

/** Python int() for the scalar shapes the policy allows. */
export function pyInt(value) {
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'boolean') return value ? 1 : 0;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('cannot convert float to integer: ' + value);
    return Math.trunc(value);
  }
  if (typeof value === 'string') {
    const text = value.trim();
    if (!/^[+-]?[0-9](?:_?[0-9])*$/.test(text)) {
      throw new Error("invalid literal for int() with base 10: '" + value + "'");
    }
    return Number(text.split('_').join(''));
  }
  throw new TypeError('int() argument must be a string or a number');
}

function pyStr(value) {
  if (typeof value === 'string') return value;
  if (value === null) return 'None';
  if (value === true) return 'True';
  if (value === false) return 'False';
  if (typeof value === 'number' || typeof value === 'bigint') return String(value);
  throw new TypeError('normalize_text expects a scalar; convert containers first');
}

function groupThousands(text) {
  return text.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

/** "1 234 567 bytes" - the only presentation unit the rules currently allow. */
export function formatFileSize(value) {
  if (layoutRule('document_policy', 'file_size_unit') !== 'bytes') {
    throw new Error('Unsupported file size presentation unit');
  }
  const number = pyInt(value);
  if (number < 0) throw new Error('Negative byte count');
  return groupThousands(String(number)) + ' bytes';
}

/** Upper-case hexadecimal digest, exactly as printed in the reports. */
export function formatDigest(value) {
  if (typeof value !== 'string' || !/^[0-9a-fA-F]+$/.test(value)) {
    throw new Error('Digest must be a hexadecimal string');
  }
  if (layoutRule('document_policy', 'hash_display_case') !== 'upper') {
    throw new Error('Unsupported hash presentation case');
  }
  return value.toUpperCase();
}

/** Unicode NFC text under UTF-8; both policies are asserted, not assumed. */
export function normalizeText(value) {
  const form = layoutRule('document_policy', 'unicode_normalization');
  if (form !== 'NFC' || layoutRule('document_policy', 'text_encoding') !== 'UTF-8') {
    throw new Error('Unsupported text policy');
  }
  return pyStr(value).normalize(form);
}

/** Reject a table fragment too small to be laid out without an orphan header. */
export function assertTableFragment(rowCount) {
  if (typeof rowCount !== 'number' || !Number.isFinite(rowCount)) {
    throw new TypeError('assertTableFragment expects a numeric row count');
  }
  const required = pyInt(layoutRule('document_policy', 'minimum_table_fragment_rows'));
  if (rowCount < required) {
    throw new Error('Table fragment has ' + rowCount + ' rows; minimum is ' + required);
  }
  return true;
}

export const format_file_size = formatFileSize;
export const format_digest = formatDigest;
export const normalize_text = normalizeText;
export const assert_table_fragment = assertTableFragment;