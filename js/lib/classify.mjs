/**
 * Evidence file type labels, ported one-to-one from the Python generator's
 * HashReportGenerator._classify_artifact_file() (hash_report_combined.py).
 *
 * The label is evidence, not decoration: the report must name an artefact the
 * same way the Python implementation names it, so a reader comparing a clone
 * report with a Python report sees identical Type columns. Order matters -
 * every branch is evaluated top to bottom exactly as in the original.
 */
import path from 'node:path';

const DANGEROUS = ['.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.scr', '.hta'];
const IMAGES = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'];
const OFFICE = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp'];
const ATTACHMENT_TEXT = ['.txt', '.log', '.csv', '.md', '.json', '.xml', '.ini', '.cfg'];

const JSON_LABELS = [
  ['core', 'CORE JSON'],
  ['routing', 'ROUTING'],
  ['attachments', 'ATTACHMENTS JSON'],
  ['deep_forensic', 'DEEP FORENSIC'],
  ['advanced-forensics', 'ADVANCED FORENSICS'],
  ['advanced_forensics', 'ADVANCED FORENSICS'],
  ['filesystem', 'FILESYSTEM'],
  ['preservation', 'PRESERVATION'],
  ['timeline', 'TIMELINE'],
  ['threat-matrix', 'THREAT MATRIX'],
  ['threat_matrix', 'THREAT MATRIX'],
  ['enterprise-summary', 'ENTERPRISE SUMMARY'],
  ['enterprise_summary', 'ENTERPRISE SUMMARY'],
  ['manifest', 'MANIFEST'],
  ['timestamps', 'TIMESTAMPS'],
  ['chain-of-custody', 'CHAIN OF CUSTODY'],
  ['chain_of_custody', 'CHAIN OF CUSTODY'],
  ['anomalies', 'ANOMALIES'],
  ['dns_analysis', 'DNS ANALYSIS'],
  ['dns-analysis', 'DNS ANALYSIS'],
  ['evidence_id', 'EVIDENCE ID'],
  ['forensic_report', 'FORENSIC REPORT'],
  ['batch_forensic', 'BATCH FORENSIC REPORT'],
  ['html_analysis', 'HTML ANALYSIS'],
];

/**
 * Classify one evidence file.
 *
 * @param {string} filename POSIX relative path inside the evidence set.
 * @param {string} baseName Name of the evidence root (the folder or file stem).
 * @returns {string} The Type label printed in the report table.
 */
export function classifyArtifactFile(filename, baseName = '') {
  const name = String(filename || '');
  const lower = name.toLowerCase();
  const base = String(baseName || '').toLowerCase();

  if (name.endsWith('.eml') && !lower.startsWith(`${base}.eml.de`)) return 'ORIGINAL EML';
  if (name.endsWith('.sig')) return 'SIGNATURE';
  if (name.endsWith('.sha256')) return 'SHA256 HASH';

  if (name.endsWith('.pdf')) {
    if (lower.includes('combined')) return 'COMBINED REPORT';
    if (lower.includes('individual')) return 'INDIVIDUAL REPORT';
    if (lower.includes('hash_report')) {
      return lower.includes('combined') ? 'COMBINED REPORT' : 'INDIVIDUAL REPORT';
    }
    return 'PDF PROOF';
  }

  if (name.endsWith('.txt')) {
    if (lower.includes('raw_eml')) return 'RAW EML TEXT';
    if (lower.includes('extracted')) return 'EXTRACTED TEXT';
    if (lower.includes('main.txt')) return 'RAW EML TEXT';
    return 'TEXT';
  }

  if (name.endsWith('.html') && !lower.includes('analysis')) return 'HTML EXTRACTED';

  if (name.endsWith('.bin')) {
    if (lower.includes('raw_headers')) return 'RAW HEADERS';
    if (lower.includes('decoded')) return 'DECODED PART';
    return 'BINARY';
  }

  if (lower.includes('.part_') && (lower.includes('_raw') || lower.endsWith('_raw'))) return 'RAW PART';

  if (name.endsWith('.json')) {
    for (const [needle, label] of JSON_LABELS) {
      if (lower.includes(needle)) return label;
    }
    return 'JSON ARTIFACT';
  }

  if (lower.includes('attachments/') || lower.startsWith('attachments')) {
    const extension = path.posix.extname(lower);
    if (DANGEROUS.includes(extension)) return 'ATTACHMENT (DANGEROUS)';
    if (extension === '.pdf') return 'ATTACHMENT (PDF)';
    if (IMAGES.includes(extension)) return 'ATTACHMENT (IMAGE)';
    if (OFFICE.includes(extension)) return 'ATTACHMENT (OFFICE)';
    if (ATTACHMENT_TEXT.includes(extension)) return 'ATTACHMENT (TEXT)';
    return 'ATTACHMENT';
  }

  return 'OTHER';
}

/** Ordering priority used by the Python report when it groups files by type. */
export const TYPE_PRIORITY = Object.freeze({
  'ORIGINAL EML': 1,
  'RAW EML TEXT': 2,
  'EXTRACTED TEXT': 3,
  'HTML EXTRACTED': 4,
  CORE: 10,
  ROUTING: 11,
  ATTACHMENTS: 12,
  'SHA256 HASH': 30,
  SIGNATURE: 31,
  'ATTACHMENT (DANGEROUS)': 32,
  'ATTACHMENT (PDF)': 33,
  'ATTACHMENT (OFFICE)': 34,
  'ATTACHMENT (IMAGE)': 35,
  'ATTACHMENT (TEXT)': 36,
  ATTACHMENT: 37,
  'JSON ARTIFACT': 40,
  TEXT: 41,
  BINARY: 42,
  OTHER: 99,
});

/** Deterministic type histogram, sorted by label like the Python summary. */
export function typeCounts(rows) {
  const counts = new Map();
  for (const row of rows) {
    const label = String(row.type || 'OTHER');
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
    .map(([label, count]) => ({ label, count }));
}

export default { classifyArtifactFile, typeCounts, TYPE_PRIORITY };