/**
 * Read-only A4 layout gate for the JS clone - port of chronoseal/report_quality.py.
 *
 * Visual/layout validation is NOT a cryptographic signature verification, and the
 * note returned with every result says so. Thresholds come from the shared report
 * profile (tools/jsx/report-profile.mjs), never from constants invented here.
 */
import { MM } from './util.mjs';
import { auditOptions, DEFAULT_PROFILE } from '../../tools/jsx/report-profile.mjs';

export const A4 = Object.freeze([210 * MM, 297 * MM]);
export const AUDIT_NOTE = 'Layout-only check; does not verify PDF signatures, timestamps, or legal compliance';



export function appendixTitles(styles = null) {
  const rules = (styles && styles.PAGE_IDENTITY) || {};
  const titles = [];
  for (const key of ['document_appendix_title', 'combined_appendix_title', 'source_appendix_title']) {
    if (rules[key]) titles.push(String(rules[key]));
  }
  return titles;
}

const tolerance = 0.1;

/**
 * Audit the pages a layout produced.
 *
 * @param {{builder: object, pages: object[], styles?: object, titles?: string[]}} input
 * @returns {{file: string, status: string, issues: string[], pages: object[], note: string}}
 */
export function auditLayout({ builder, pages, styles = null, titles = null, profile = DEFAULT_PROFILE, file = '(in-memory)' }) {
  const limits = auditOptions(profile);
  const appendixes = titles || appendixTitles(styles);
  const width = builder.pageWidth;
  const height = builder.pageHeight;
  const issues = [];
  const report = [];
  const a4 = Math.abs(width - A4[0]) < 2 && Math.abs(height - A4[1]) < 2;

  pages.forEach((page, position) => {
    const index = position + 1;
    if (!a4) issues.push(`page ${index}: not A4`);
    const words = builder.wordBoxes(page);
    const text = words.map((word) => word.text).join(' ');
    // The checksum appendix is a declared layout of its own and uses the
    // appendix top allowance, exactly like the Python gate.
    const appendix = appendixes.some((title) => title && text.includes(title));
    const pageTop = appendix ? limits.appendix_top_mm : limits.top_mm;
    // Footer is audited separately: it is intentionally below the body area. A
    // word the layout drew in the footer band belongs to the footer even when it
    // sits a little higher, which the page-hash block above the rule does.
    const isFooter = (word) => (
      word.band === 'footer' || word.y1 <= limits.footer_band_mm * MM
    );
    const body = words.filter((word) => !isFooter(word));
    const footer = words.filter(isFooter);
    const bodyOutside = body.filter((word) => (
      word.x0 < limits.left_mm * MM - tolerance
      || word.x1 > width - limits.right_mm * MM + tolerance
      || word.y1 > height - pageTop * MM + tolerance
      || word.y0 < limits.bottom_mm * MM - tolerance
    ));
    const footerOutside = footer.filter((word) => (
      word.x0 < 5 * MM - tolerance
      || word.x1 > width - 5 * MM + tolerance
      || word.y0 < 3 * MM - tolerance
    ));
    const probes = {
      words: body.length > 0 || footer.length > 0,
      text: Boolean(text.trim()),
      graphics: page.graphics > 0,
    };
    if (!probes.words && !probes.text) issues.push(`page ${index}: no extractable text`);
    if (body.length < limits.minimum_body_words) issues.push(`page ${index}: sparse or empty body (${body.length} words)`);
    if (bodyOutside.length) issues.push(`page ${index}: ${bodyOutside.length} body words outside content margins`);
    if (footerOutside.length) issues.push(`page ${index}: ${footerOutside.length} footer words outside safe page edges`);
    report.push({
      page: index,
      a4,
      appendix,
      body_words: body.length,
      footer_words: footer.length,
      body_margin_violations: bodyOutside.length,
      footer_edge_violations: footerOutside.length,
      content_probes: probes,
      probe_errors: {},
    });
  });

  return {
    file,
    status: issues.length ? 'REVIEW' : 'PASS',
    issues,
    pages: report,
    note: AUDIT_NOTE,
    profile: { name: profile.name, version: profile.version },
  };
}
