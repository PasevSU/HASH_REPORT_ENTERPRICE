/**
 * PDF/A-2b stage for the JS clone.
 *
 * The repository already ships a dependency-free normaliser (tools/pdfnorm) that
 * the project uses to produce a compliant PDF/A-2b file: embedded TrueType
 * subsets, sRGB output intent, XMP metadata and a repaired cross-reference table.
 * The clone reuses it instead of re-implementing PDF/A, and only overrides the
 * document metadata and the page-label scheme, because a report prints its own
 * "Page N" folios.
 */
import { PdfDocument } from '../../tools/pdfnorm/lib/parser.mjs';
import { normalize } from '../../tools/pdfnorm/normalize.mjs';
import { sha256Bytes } from './util.mjs';

export const CREATOR_TOOL = 'ChronoSeal Enterprise JS clone';
export const PRODUCER = 'ChronoSeal Enterprise JS clone PDF/A-2b normaliser';

/**
 * Normalise report bytes to PDF/A-2b.
 *
 * @returns {{bytes: Uint8Array, sha256: string, stats: object}}
 */
export function normalizeReport(bytes, {
  title = 'ChronoSeal HASH REPORT',
  author = 'ChronoSeal Enterprise (JavaScript clone)',
  subject = '',
  keywords = '',
  sourcePath = null,
  createDate = null,
  modifyDate = null,
} = {}) {
  const result = normalize(bytes, {
    title,
    author,
    subject,
    keywords,
    creatorTool: CREATOR_TOOL,
    producer: PRODUCER,
    pageLabels: false,
    quiet: true,
    sourcePath,
    createDate,
    modifyDate,
  });
  const data = result.data instanceof Uint8Array ? result.data : new Uint8Array(result.data);
  return { bytes: data, sha256: sha256Bytes(data), stats: result.stats };
}

/**
 * Structural read-back of a produced PDF: the file must parse again, keep its
 * page count, and give every page a content stream.
 */
export function inspectPdf(bytes, { expectedPages = null } = {}) {
  const doc = PdfDocument.load(Buffer.from(bytes));
  const pages = doc.pages || [];
  if (!doc.root) throw new Error('Produced PDF has no document catalog');
  if (expectedPages !== null && pages.length !== expectedPages) {
    throw new Error(`Produced PDF has ${pages.length} pages, expected ${expectedPages}`);
  }
  const missing = [];
  pages.forEach((page, index) => {
    const dict = doc.resolve(page);
    if (!dict || !dict.get('Contents')) missing.push(index + 1);
  });
  if (missing.length) throw new Error('Pages without a content stream: ' + missing.join(', '));
  return {
    pages: pages.length,
    objects: doc.entries.size + doc.extra.size,
    hasMetadata: Boolean(doc.root.get('Metadata')),
    hasOutputIntent: Boolean(doc.root.get('OutputIntents')),
  };
}
