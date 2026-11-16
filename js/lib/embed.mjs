/**
 * Embedded-source-PDF stage for the JS clone.
 *
 * Python's `single_pdf` profile publishes a SINGLE report, then appends the pages
 * of the source PDF unchanged and attaches the original file byte-for-byte so a
 * reviewer can open the signed document from inside the report. `chronoseal/
 * pipeline.py::_compose` is the reference implementation; this module ports its
 * three guarantees to the JavaScript clone:
 *
 *   1. imported pages keep their original geometry (no rescaling, no footer);
 *   2. the attachment is byte-identical to the source file;
 *   3. both facts are verified after serialisation and recorded in an audit.
 *
 * The stage runs after PDF/A-2b normalisation, so the repository normaliser never
 * rewrites foreign page content or foreign fonts. That also means the PDF/A-2b
 * claim covers the pages the clone authored; an attached original that was not
 * PDF/A stays exactly as it was signed, which is the point of attaching it.
 */
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { PdfDocument } from '../../tools/pdfnorm/lib/parser.mjs';
import { Dict, Name, PdfString, Ref, Stream } from '../../tools/pdfnorm/lib/objects.mjs';
import { decodeStream } from '../../tools/pdfnorm/lib/filters.mjs';
import { writePdf } from '../../tools/pdfnorm/lib/writer.mjs';
import { sha256Bytes } from './util.mjs';

const CODE_SUFFIXES = Object.freeze({
  SOURCE_NOT_PDF: 'SOURCE_NOT_PDF',
  SOURCE_ENCRYPTED: 'SOURCE_ENCRYPTED',
  SOURCE_EMPTY: 'SOURCE_EMPTY',
  EMBED_HASH_MISMATCH: 'EMBED_HASH_MISMATCH',
  SOURCE_GEOMETRY_CHANGED: 'SOURCE_GEOMETRY_CHANGED',
  SOURCE_CHANGED: 'SOURCE_CHANGED_DURING_COMPOSE',
  SOURCE_MISSING: 'SOURCE_MISSING',
});

/** The only two documented placements of the included document. */
export const EMBED_POSITIONS = Object.freeze(['before', 'after']);

/**
 * Codes carry the report type, so an operator reads COMBO_PDF_SOURCE_MISSING and
 * knows which report failed without opening the log.
 */
export function embedCodes(kind = 'SINGLE_PDF') {
  const prefix = String(kind || 'SINGLE_PDF').toUpperCase();
  const codes = {
    POSITION_INVALID: 'EMBED_POSITION_INVALID',
    SOURCE_INVALID: 'EMBED_PDF_SOURCE_INVALID',
  };
  for (const [key, suffix] of Object.entries(CODE_SUFFIXES)) codes[key] = `${prefix}_${suffix}`;
  return Object.freeze(codes);
}

/** Single-document codes; kept for callers that embed the input file itself. */
export const EMBED_CODES = embedCodes('SINGLE_PDF');

export class EmbedError extends Error {
  constructor(code, detail) {
    super(code + ': ' + detail);
    this.name = 'EmbedError';
    this.code = code;
  }
}

const INHERITABLE = ['Resources', 'MediaBox', 'CropBox', 'Rotate'];

/** `D:YYYYMMDDHHmmSS+HH'mm'`, the PDF text-date form the rest of the clone emits. */
function pdfDate(value) {
  const pad = (n) => String(Math.floor(Math.abs(n))).padStart(2, '0');
  const offset = -value.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  return `D:${value.getFullYear()}${pad(value.getMonth() + 1)}${pad(value.getDate())}`
    + `${pad(value.getHours())}${pad(value.getMinutes())}${pad(value.getSeconds())}`
    + `${sign}${pad(offset / 60)}'${pad(offset % 60)}'`;
}

/** Page references in document order; refs are kept so /Annots /P can be remapped. */
function pageRefs(doc) {
  const out = [];
  const seen = new Set();
  const walk = (node) => {
    const key = node instanceof Ref ? node.num : null;
    if (key !== null) {
      if (seen.has(key)) return;
      seen.add(key);
    }
    const dict = doc.resolve(node);
    if (!dict || typeof dict.get !== 'function') return;
    const type = typeof dict.name === 'function' ? dict.name('Type') : null;
    const kids = doc.resolve(dict.get('Kids'));
    if (type === 'Pages' || (Array.isArray(kids) && type !== 'Page')) {
      for (const kid of kids || []) walk(kid);
      return;
    }
    const target = node instanceof Ref ? node : doc.addObject(dict);
    out.push(target);
  };
  walk(doc.root.get('Pages'));
  return out;
}

function deepCopy(source, target) {
  const map = new Map();
  const copy = (value) => {
    if (value instanceof Ref) {
      if (map.has(value.num)) return map.get(value.num);
      const ref = new Ref(target.addObject(new Dict()).num, 0);
      map.set(value.num, ref);
      target.extra.set(ref.num, copy(source.getObject(value.num)));
      return ref;
    }
    if (value instanceof Stream) return new Stream(copy(value.dict), value.data);
    if (value instanceof Dict) {
      const dict = new Dict();
      for (const [key, item] of value) dict.set(key, copy(item));
      return dict;
    }
    if (Array.isArray(value)) return value.map(copy);
    return value;
  };
  return { copy, map };
}

/** Inherited page attributes live on ancestor /Pages nodes, not on the page itself. */
function inherited(doc, pageRef, key) {
  const seen = new Set();
  let node = doc.resolve(pageRef);
  while (node && !seen.has(node)) {
    seen.add(node);
    const direct = node.get(key);
    if (direct !== undefined && direct !== null) return direct;
    const parent = node.get('Parent');
    if (!parent) return null;
    node = doc.resolve(parent);
  }
  return null;
}

function geometryOf(doc, page) {
  const read = (key) => {
    const raw = doc.resolve(page.get(key));
    if (!Array.isArray(raw) || raw.length !== 4) return null;
    return raw.map((value) => Math.round(Number(doc.resolve(value)) * 100) / 100);
  };
  return {
    media: read('MediaBox'),
    crop: read('CropBox'),
    rotate: Number(doc.resolve(page.get('Rotate')) || 0),
  };
}

function sameGeometry(a, b) {
  const same = (left, right) => {
    if (left === null || right === null) return left === right;
    return left.length === right.length && left.every((value, i) => Math.abs(value - right[i]) < 0.01);
  };
  return same(a.media, b.media) && same(a.crop, b.crop) && (a.rotate || 0) === (b.rotate || 0);
}

/**
 * Copy every page of `source` into `target`, preserving geometry and annotations.
 *
 * `at === null` appends the pages; an index inserts them, which is how the
 * "source document first" placement is built.
 */
export function importPages(target, source, { at = null } = {}) {
  const pagesRef = target.root.get('Pages');
  const pagesDict = target.resolve(pagesRef);
  const existing = Array.isArray(pagesDict.get('Kids')) ? [...pagesDict.get('Kids')] : [];
  const { copy, map } = deepCopy(source, target);
  const imported = [];
  for (const pageRef of pageRefs(source)) {
    const page = source.resolve(pageRef);
    const clone = new Dict();
    const ref = new Ref(target.addObject(new Dict()).num, 0);
    // Register before copying so /Annots -> /P resolves to the new page, not the old one.
    map.set(pageRef.num, ref);
    for (const [key, value] of page) {
      if (key === 'Parent') continue;
      clone.set(key, copy(value));
    }
    for (const key of INHERITABLE) {
      if (clone.has(key)) continue;
      const value = inherited(source, pageRef, key);
      if (value !== null && value !== undefined) clone.set(key, copy(value));
    }
    clone.set('Parent', pagesRef);
    target.extra.set(ref.num, clone);
    imported.push({ ref, page, geometry: geometryOf(source, page) });
  }
  const index = at === null
    ? existing.length
    : Math.max(0, Math.min(Math.trunc(Number(at) || 0), existing.length));
  const kids = [...existing];
  kids.splice(index, 0, ...imported.map((entry) => entry.ref));
  pagesDict.set('Kids', kids);
  pagesDict.set('Count', kids.length);
  return imported;
}

function nameTreeArray(doc) {
  const catalog = doc.root;
  let names = doc.resolve(catalog.get('Names'));
  if (!names) {
    names = new Dict();
    catalog.set('Names', doc.addObject(names));
  }
  let tree = doc.resolve(names.get('EmbeddedFiles'));
  if (!tree) {
    tree = new Dict();
    names.set('EmbeddedFiles', doc.addObject(tree));
  }
  if (!Array.isArray(tree.get('Names'))) tree.set('Names', []);
  return tree;
}

/** Attach `bytes` under `name` through the catalogue name tree (PDF/A-2 style). */
export function attachFile(doc, { name, bytes, description = '', now = new Date() }) {
  const checksum = createHash('md5').update(Buffer.from(bytes)).digest();
  const params = new Dict();
  params.set('Size', bytes.length);
  params.set('ModDate', PdfString.fromText(pdfDate(now)));
  params.set('CheckSum', new PdfString(new Uint8Array(checksum), true));
  const streamDict = new Dict();
  streamDict.set('Type', new Name('EmbeddedFile'));
  streamDict.set('Subtype', new Name('application#2Fpdf'));
  streamDict.set('Params', params);
  const streamRef = doc.addObject(new Stream(streamDict, new Uint8Array(bytes)));
  const ef = new Dict();
  ef.set('F', streamRef);
  const spec = new Dict();
  spec.set('Type', new Name('Filespec'));
  spec.set('F', PdfString.fromText(name));
  spec.set('UF', PdfString.fromText(name));
  spec.set('Desc', PdfString.fromText(description));
  spec.set('EF', ef);
  spec.set('AFRelationship', new Name('Supplement'));
  const specRef = doc.addObject(spec);
  const tree = nameTreeArray(doc);
  tree.set('Names', [...tree.get('Names'), PdfString.fromText(name), specRef]);
  return { specRef, streamRef, checksum: Buffer.from(checksum).toString('hex') };
}

/** Read an attachment back out of serialised bytes, so the guard tests the real file. */
export function readAttachment(bytes, name) {
  const doc = PdfDocument.load(Buffer.from(bytes));
  const names = doc.resolve(doc.root.get('Names'));
  const tree = names ? doc.resolve(names.get('EmbeddedFiles')) : null;
  const entries = tree && Array.isArray(tree.get('Names')) ? tree.get('Names') : [];
  for (let i = 0; i < entries.length; i += 2) {
    const label = doc.resolve(entries[i]);
    const labelText = typeof label === 'string' ? label : (label && label.text) || String(label);
    if (labelText !== name) continue;
    const spec = doc.resolve(entries[i + 1]);
    const ef = doc.resolve(spec.get('EF'));
    const stream = doc.resolve(ef.get('F'));
    const parms = doc.resolve(stream.dict.get('DecodeParms'));
    const data = decodeStream(stream, () => (parms instanceof Ref ? doc.resolve(parms) : parms));
    const params = doc.resolve(stream.dict.get('Params')) || new Map();
    const checksum = params.get('CheckSum');
    return {
      name,
      data: Buffer.from(data),
      size: data.length,
      checksum: checksum instanceof PdfString
        ? Buffer.from(checksum.bytes).toString('hex')
        : String(checksum || ''),
    };
  }
  return null;
}

function fail(code, detail) {
  throw new EmbedError(code, detail);
}

function loadSource(bytes, codes, name) {
  try {
    return PdfDocument.load(Buffer.from(bytes));
  } catch (error) {
    const code = /encrypt/i.test(error.message) ? codes.SOURCE_ENCRYPTED : codes.SOURCE_NOT_PDF;
    fail(code, name + ': ' + error.message);
  }
  return null;
}

/**
 * Facts about a source PDF that are known before composition: name, byte size,
 * SHA-256 and page count. The report body needs them while it is being drawn,
 * the way the Python report describes the file it includes.
 */
export function describeSourcePdf(sourcePath, { sourceName = null, kind = 'SINGLE_PDF' } = {}) {
  const codes = embedCodes(kind);
  const name = sourceName || path.basename(sourcePath);
  if (!/\.pdf$/i.test(name)) fail(codes.SOURCE_NOT_PDF, 'not a PDF file: ' + name);
  if (!fs.existsSync(sourcePath)) fail(codes.SOURCE_MISSING, sourcePath);
  const bytes = fs.readFileSync(sourcePath);
  const doc = loadSource(bytes, codes, name);
  const pages = pageRefs(doc).length;
  if (!pages) fail(codes.SOURCE_EMPTY, name + ' has no pages');
  return { name, path: sourcePath, bytes: bytes.length, sha256: sha256Bytes(bytes), pages };
}

/**
 * Compose `reportBytes` + the included document + optional attachment.
 *
 * @param {object} options
 * @param {'before'|'after'} [options.position] where the source pages go.
 * @param {string} [options.kind] report type, so the audit and the codes name it.
 * @returns {{bytes: Uint8Array, sha256: string, audit: object}}
 */
export function embedSourcePdf(reportBytes, {
  sourcePath = null,
  sourceBytes = null,
  sourceName = null,
  includePages = true,
  attach = true,
  description = 'Original document, attached unchanged',
  now = new Date(),
  expectedReportPages = null,
  position = 'after',
  kind = 'SINGLE_PDF',
} = {}) {
  const codes = embedCodes(kind);
  const place = String(position || 'after').trim().toLowerCase();
  if (!EMBED_POSITIONS.includes(place)) {
    fail(codes.POSITION_INVALID, 'expected before or after, got ' + JSON.stringify(position));
  }
  const name = sourceName || (sourcePath ? path.basename(sourcePath) : 'source.pdf');
  let bytes = sourceBytes;
  let before = null;
  if (!bytes) {
    if (!sourcePath) throw new Error('embedSourcePdf needs sourcePath or sourceBytes');
    if (!fs.existsSync(sourcePath)) fail(codes.SOURCE_MISSING, sourcePath);
    before = fs.statSync(sourcePath);
    bytes = fs.readFileSync(sourcePath);
  }
  if (!/\.pdf$/i.test(name)) fail(codes.SOURCE_NOT_PDF, 'not a PDF file: ' + name);

  const sourceDoc = loadSource(bytes, codes, name);
  const sourcePages = pageRefs(sourceDoc);
  if (!sourcePages.length) fail(codes.SOURCE_EMPTY, name + ' has no pages');

  const target = PdfDocument.load(Buffer.from(reportBytes));
  const reportPages = target.pages.length;
  if (expectedReportPages !== null && reportPages !== expectedReportPages) {
    throw new Error(`Report has ${reportPages} pages, expected ${expectedReportPages}`);
  }

  const imported = includePages ? importPages(target, sourceDoc, { at: place === 'before' ? 0 : null }) : [];
  const attachment = attach ? attachFile(target, { name, bytes, description, now }) : null;

  const written = writePdf(target, {
    root: target.trailer.get('Root'),
    info: target.trailer.get('Info') || null,
    version: '1.7',
    compressStreams: true,
    objectStreams: true,
  });
  const data = written.data instanceof Uint8Array ? written.data : new Uint8Array(written.data);

  // Verification runs on the serialised file, exactly like _compose() does.
  const check = PdfDocument.load(Buffer.from(data));
  const expectedPages = reportPages + imported.length;
  if (check.pages.length !== expectedPages) {
    throw new Error(`Composed PDF has ${check.pages.length} pages, expected ${expectedPages}`);
  }
  const checkPages = pageRefs(check);
  // Where the source pages start depends on the chosen placement, so the geometry
  // audit reads the position that was actually written.
  const sourceFirstIndex = place === 'before' ? 0 : reportPages;
  imported.forEach((entry, index) => {
    const geometry = geometryOf(check, check.resolve(checkPages[sourceFirstIndex + index]));
    if (!sameGeometry(geometry, entry.geometry)) {
      fail(codes.SOURCE_GEOMETRY_CHANGED,
        `${name} page ${index + 1} changed geometry: ${JSON.stringify(geometry)} vs ${JSON.stringify(entry.geometry)}`);
    }
  });

  let attachmentAudit = null;
  if (attachment) {
    const read = readAttachment(data, name);
    if (!read) fail(codes.EMBED_HASH_MISMATCH, `attachment ${name} is missing from the composed PDF`);
    const digest = sha256Bytes(read.data);
    if (digest !== sha256Bytes(bytes)) {
      fail(codes.EMBED_HASH_MISMATCH, `attachment sha256 ${digest} does not match the source`);
    }
    attachmentAudit = {
      name,
      bytes: read.size,
      sha256: digest,
      md5: attachment.checksum,
      subtype: 'application/pdf',
      relationship: 'Supplement',
    };
  }

  if (before && sourcePath) {
    const after = fs.statSync(sourcePath);
    if (after.size !== before.size || after.mtimeMs !== before.mtimeMs) {
      fail(codes.SOURCE_CHANGED, sourcePath + ' changed while the report was composed');
    }
  }

  const audit = {
    schema: 'chronoseal-source-pdf-audit/1',
    status: 'PASS',
    report_kind: String(kind || 'SINGLE_PDF').toUpperCase(),
    generated_utc: now.toISOString(),
    source: {
      name,
      path: sourcePath,
      bytes: bytes.length,
      sha256: sha256Bytes(bytes),
      pages: sourcePages.length,
      first_visible_page: imported.length ? sourceFirstIndex + 1 : null,
      geometry: imported.map((entry, index) => ({ page: index + 1, ...entry.geometry })),
    },
    report: { pages: reportPages, sha256: sha256Bytes(reportBytes) },
    composed: { pages: expectedPages, bytes: data.length, sha256: sha256Bytes(data) },
    include_pages: Boolean(includePages),
    embed_position: place,
    attachment: attachmentAudit,
    checks: {
      page_count: expectedPages,
      geometry_preserved: true,
      attachment_sha256: attachmentAudit ? attachmentAudit.sha256 : null,
      source_unchanged: Boolean(before),
    },
  };
  return { bytes: data, sha256: audit.composed.sha256, audit };
}

export default {
  EMBED_CODES,
  EMBED_POSITIONS,
  EmbedError,
  describeSourcePdf,
  embedCodes,
  embedSourcePdf,
  importPages,
  attachFile,
  readAttachment,
};
