/**
 * JavaScript port of hash_report_generator/pagination_policy.py, minus ReportLab.
 *
 * The Python module makes the decision *and* builds Platypus flowables; only the
 * decision is portable, so this module returns a plan object instead:
 *
 *   keepShortSection(6) -> { strategy: 'keep',  gapPt: 4 }
 *   keepShortSection(9) -> throws, exactly like the Python original
 *
 * There are no hard-coded CondPageBreak thresholds: the numbers come from
 * style/90_pagination.js through the same strict rule loader.
 */
import { loadStyles } from './style-loader.mjs';
import { pyInt } from './presentation-policy.mjs';

/** Central pagination rules; refuses anything but the A4 paper policy. */
export function paginationConfig(styles = null) {
  const source = styles === null ? loadStyles() : styles;
  const config = (source && source.PAGINATION) || {};
  if (config.paper !== 'A4') throw new Error('Central pagination requires A4');
  return config;
}

/**
 * Should a heading and its table travel together?
 *
 * @param {number} rowCount rows in the table (ReportLab's len(table._cellvalues))
 * @returns {{strategy: 'keep'|'split', gapPt: number}}
 */
export function keepShortSection(rowCount, { gapPt = 4, config = null } = {}) {
  const settings = config === null ? paginationConfig() : config;
  if (!Number.isInteger(rowCount) || rowCount < 0) {
    throw new TypeError('Expected a table with a non-negative row count');
  }
  if (!(settings.short_tables_keep_together ?? true)) return { strategy: 'split', gapPt };
  const maxRows = pyInt(settings.short_table_max_rows ?? 8);
  if (rowCount <= maxRows) return { strategy: 'keep', gapPt };
  // Long tables must be placed as separate splittable flowables.
  throw new Error('Long table must be placed as separate splittable flowables');
}

/** Keep a heading with its first real paragraph, never with a blank spacer. */
export function keepHeadingWithFirstParagraph({ gapPt = 4, config = null } = {}) {
  const settings = config === null ? paginationConfig() : config;
  const keep = (settings.no_orphan_section_headings ?? true)
    && (settings.heading_first_paragraph_keep_together ?? true);
  return { strategy: keep ? 'keep' : 'split', gapPt };
}

export const pagination_config = paginationConfig;
export const keep_short_section = keepShortSection;
export const keep_heading_with_first_paragraph = keepHeadingWithFirstParagraph;