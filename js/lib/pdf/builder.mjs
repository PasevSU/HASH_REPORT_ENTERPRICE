/**
 * Minimal PDF authoring layer for the JS clone.
 *
 * The repository already ships a lossless PDF object model, a TrueType subsetter
 * and a serialiser (tools/pdfnorm/lib/*). Instead of adding a native PDF library
 * this builder reuses them, so a clone report is produced and normalised by the
 * same pure-JavaScript code that keeps PDF/A-2b compliance.
 *
 * Every text run is written twice on purpose:
 *   * as Identity-H glyph codes (CID = retained glyph id) so CJK/Cyrillic text and
 *     the embedded program always agree;
 *   * in a /ToUnicode CMap so the text stays extractable and auditable - a report
 *     whose text cannot be extracted fails its own layout gate.
 */
import { Dict, Name, PdfString, Stream } from '../../../tools/pdfnorm/lib/objects.mjs';
import { PdfDocument } from '../../../tools/pdfnorm/lib/parser.mjs';
import { writePdf } from '../../../tools/pdfnorm/lib/writer.mjs';
import { subsetFont, descriptorMetrics } from '../../../tools/pdfnorm/lib/fonts.mjs';
import { resolveFont, glyphId, advanceWidth } from '../fonts.mjs';

export const PDF_VERSION = '1.7';

function colorParts(value) {
  if (Array.isArray(value)) return value.slice(0, 3).map(Number);
  const text = String(value || '#000000').replace('#', '');
  if (!/^[0-9a-fA-F]{6}$/.test(text)) throw new Error('Invalid colour: ' + value);
  return [0, 2, 4].map((index) => parseInt(text.slice(index, index + 2), 16) / 255);
}

function formatFloat(value) {
  const rounded = Math.round(Number(value) * 1000) / 1000;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
}

/** Latin-1 when possible, UTF-16BE with BOM otherwise (legal in any PDF text string). */
function pdfText(value) {
  const text = String(value ?? '');
  if (/^[\u0000-\u00ff]*$/.test(text)) {
    return PdfString.fromText(text);
  }
  const bytes = new Uint8Array(2 + text.length * 2);
  bytes[0] = 0xfe;
  bytes[1] = 0xff;
  let offset = 2;
  for (let index = 0; index < text.length; index += 1) {
    const unit = text.charCodeAt(index);
    bytes[offset++] = (unit >> 8) & 0xff;
    bytes[offset++] = unit & 0xff;
  }
  return new PdfString(bytes, true);
}

function pdfDate(date) {
  const d = date instanceof Date ? date : new Date(date);
  const p = (value, width = 2) => String(value).padStart(width, '0');
  const offsetMinutes = -d.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absolute = Math.abs(offsetMinutes);
  return `D:${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`
    + `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
    + `${sign}${p(Math.floor(absolute / 60))}'${p(absolute % 60)}'`;
}

function utf16Hex(codePoint) {
  const value = codePoint > 0xffff
    ? (() => {
      const adjusted = codePoint - 0x10000;
      return [0xd800 + (adjusted >> 10), 0xdc00 + (adjusted & 0x3ff)];
    })()
    : [codePoint];
  return value.map((unit) => unit.toString(16).padStart(4, '0')).join('').toUpperCase();
}

export class PdfReportBuilder {
  constructor({
    title = 'ChronoSeal HASH REPORT',
    author = 'ChronoSeal Enterprise (JavaScript clone)',
    subject = '',
    keywords = '',
    creator = 'ChronoSeal JS clone',
    producer = 'ChronoSeal JS clone (pure JavaScript)',
    now = new Date(),
    pageWidth = 595.276,
    pageHeight = 841.89,
  } = {}) {
    this.metadata = { title, author, subject, keywords, creator, producer, now };
    this.pageWidth = pageWidth;
    this.pageHeight = pageHeight;
    this.fonts = new Map();
    this.pages = [];
    this.current = null;
  }

  /** Register (once) the typographic role and return its resource name. */
  fontResource(role) {
    const existing = this.fonts.get(role);
    if (existing) return existing.resource;
    const resolved = resolveFont(role);
    const handle = {
      role,
      resource: `F${this.fonts.size + 1}`,
      family: resolved.family,
      file: resolved.file,
      font: resolved.font,
      used: new Set([0]),
      cmapByGid: new Map(),
    };
    this.fonts.set(role, handle);
    return handle.resource;
  }

  beginPage() {
    if (this.current) throw new Error('A page is already open');
    this.current = { ops: [], items: [], graphics: 0 };
    this.pages.push(this.current);
    return this.pages.length;
  }

  finishPage() {
    if (!this.current) throw new Error('No page is open');
    this.current = null;
  }

  get pageIndex() {
    return this.pages.length;
  }

  encode(handle, text) {
    let hex = '';
    for (const character of String(text)) {
      const codePoint = character.codePointAt(0);
      const gid = glyphId(handle.font, codePoint);
      handle.used.add(gid);
      if (!handle.cmapByGid.has(gid)) handle.cmapByGid.set(gid, codePoint);
      hex += gid.toString(16).padStart(4, '0');
    }
    return hex;
  }

  /**
   * Draw one line of text with its baseline at `y` (PDF user space, origin
   * bottom-left). Returns the measured width so the layout can align columns.
   */
  drawText({ role = 'regular', size = 9, x, y, text, color = '#000000', band = 'body' }) {
    if (!this.current) throw new Error('drawText requires an open page');
    const content = String(text ?? '');
    if (!content) return 0;
    const resource = this.fontResource(role);
    const handle = this.fonts.get(role);
    const hex = this.encode(handle, content);
    const [r, g, b] = colorParts(color);
    this.current.ops.push(
      `BT /${resource} ${formatFloat(size)} Tf ${formatFloat(r)} ${formatFloat(g)} ${formatFloat(b)} rg `
      + `1 0 0 1 ${formatFloat(x)} ${formatFloat(y)} Tm <${hex}> Tj ET`,
    );
    let width = 0;
    for (const character of content) {
      width += advanceWidth(handle.font, glyphId(handle.font, character.codePointAt(0)));
    }
    width = (width * size) / 1000;
    this.current.items.push({ role, size, x, y, width, text: content, band });
    return width;
  }

  drawRect({ x, y, width, height, color = '#ffffff', stroke = null, lineWidth = 0.5 }) {
    if (!this.current) throw new Error('drawRect requires an open page');
    const [r, g, b] = colorParts(color);
    this.current.ops.push(
      `${formatFloat(r)} ${formatFloat(g)} ${formatFloat(b)} rg `
      + `${formatFloat(x)} ${formatFloat(y)} ${formatFloat(width)} ${formatFloat(height)} re f`,
    );
    if (stroke) {
      const [sr, sg, sb] = colorParts(stroke);
      this.current.ops.push(
        `${formatFloat(sr)} ${formatFloat(sg)} ${formatFloat(sb)} RG ${formatFloat(lineWidth)} w `
        + `${formatFloat(x)} ${formatFloat(y)} ${formatFloat(width)} ${formatFloat(height)} re S`,
      );
    }
    this.current.graphics += 1;
  }

  drawLine({ x1, y1, x2, y2, color = '#d4dce4', width = 0.5 }) {
    if (!this.current) throw new Error('drawLine requires an open page');
    const [r, g, b] = colorParts(color);
    this.current.ops.push(
      `${formatFloat(r)} ${formatFloat(g)} ${formatFloat(b)} RG ${formatFloat(width)} w `
      + `${formatFloat(x1)} ${formatFloat(y1)} m ${formatFloat(x2)} ${formatFloat(y2)} l S`,
    );
    this.current.graphics += 1;
  }

  /** Word boxes for the layout gate: body words are separated by whitespace. */
  wordBoxes(page) {
    const words = [];
    for (const item of page.items) {
      const handle = this.fonts.get(item.role);
      // Exact advance widths per word: the margin audit must not inherit an average.
      const widthOf = (chunk) => {
        let total = 0;
        for (const character of chunk) {
          total += advanceWidth(handle.font, glyphId(handle.font, character.codePointAt(0)));
        }
        return (total * item.size) / 1000;
      };
      let cursor = item.x;
      for (const chunk of item.text.split(/(\s+)/)) {
        if (!chunk) continue;
        const width = widthOf(chunk);
        if (!/^\s+$/.test(chunk)) {
          words.push({
            text: chunk,
            x0: cursor,
            x1: cursor + width,
            // Approximation of an ascender/descender band; only margins matter here.
            y0: item.y - item.size * 0.25,
            y1: item.y + item.size * 0.8,
            band: item.band || 'body',
          });
        }
        cursor += width;
      }
    }
    return words;
  }

  toUnicodeCMap(handle) {
    const entries = [...handle.used]
      .filter((gid) => handle.cmapByGid.has(gid))
      .sort((a, b) => a - b)
      .map((gid) => [gid, handle.cmapByGid.get(gid)]);
    const chunks = [];
    for (let index = 0; index < entries.length; index += 100) {
      const slice = entries.slice(index, index + 100);
      chunks.push(`${slice.length} beginbfchar\n`
        + slice.map(([gid, code]) => `<${gid.toString(16).padStart(4, '0')}> <${utf16Hex(code)}>`).join('\n')
        + '\nendbfchar');
    }
    const body = [
      '/CIDInit /ProcSet findresource begin',
      '12 dict begin',
      'begincmap',
      '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
      '/CMapName /Adobe-Identity-UCS def',
      '/CMapType 2 def',
      '1 begincodespacerange',
      '<0000> <FFFF>',
      'endcodespacerange',
      ...chunks,
      'endcmap',
      'CMapName currentdict /CMap defineresource pop',
      'end',
      'end',
    ].join('\n');
    return new TextEncoder().encode(body + '\n');
  }

  buildFont(doc, handle) {
    const subset = subsetFont(handle.font, { gids: [...handle.used], retainGids: true });
    const metrics = descriptorMetrics(handle.font);
    const baseName = handle.family.replace(/[^A-Za-z0-9]/g, '') || 'ChronoUnicode';

    const fileDict = new Dict();
    fileDict.set('Length1', subset.data.length);
    const fileStream = new Stream(fileDict, subset.data);
    const fileRef = doc.addObject(fileStream);

    const descriptor = new Dict();
    descriptor.set('Type', new Name('FontDescriptor'));
    descriptor.set('FontName', new Name(baseName));
    descriptor.set('Flags', 32);
    descriptor.set('FontBBox', metrics.bbox);
    descriptor.set('ItalicAngle', metrics.italicAngle);
    descriptor.set('Ascent', metrics.ascent);
    descriptor.set('Descent', metrics.descent);
    descriptor.set('CapHeight', metrics.capHeight);
    descriptor.set('StemV', 80);
    descriptor.set('FontFile2', fileRef);
    const descriptorRef = doc.addObject(descriptor);

    const widths = [];
    for (const gid of [...handle.used].sort((a, b) => a - b)) {
      widths.push(gid, [advanceWidth(handle.font, gid)]);
    }
    const cidFont = new Dict();
    cidFont.set('Type', new Name('Font'));
    cidFont.set('Subtype', new Name('CIDFontType2'));
    cidFont.set('BaseFont', new Name(baseName));
    const systemInfo = new Dict();
    systemInfo.set('Registry', PdfString.fromText('Adobe'));
    systemInfo.set('Ordering', PdfString.fromText('Identity'));
    systemInfo.set('Supplement', 0);
    cidFont.set('CIDSystemInfo', systemInfo);
    cidFont.set('FontDescriptor', descriptorRef);
    cidFont.set('CIDToGIDMap', new Name('Identity'));
    cidFont.set('DW', 1000);
    cidFont.set('W', widths);
    const cidRef = doc.addObject(cidFont);

    const toUnicode = new Stream(new Dict(), this.toUnicodeCMap(handle));
    const toUnicodeRef = doc.addObject(toUnicode);

    const type0 = new Dict();
    type0.set('Type', new Name('Font'));
    type0.set('Subtype', new Name('Type0'));
    type0.set('BaseFont', new Name(baseName));
    type0.set('Encoding', new Name('Identity-H'));
    type0.set('DescendantFonts', [cidRef]);
    type0.set('ToUnicode', toUnicodeRef);
    return doc.addObject(type0);
  }

  /** Serialise the document; returns {data, stats} from the shared writer. */
  finish() {
    if (this.current) this.finishPage();
    if (!this.pages.length) throw new Error('A PDF report needs at least one page');
    const doc = new PdfDocument(new Uint8Array(0));

    const fontRefs = new Map();
    for (const [role, handle] of this.fonts) fontRefs.set(handle.resource, this.buildFont(doc, handle));

    const pagesRef = doc.addObject(new Dict());
    const pageRefs = [];
    for (const page of this.pages) {
      const content = new Stream(new Dict(), new TextEncoder().encode(page.ops.join('\n') + '\n'));
      const contentRef = doc.addObject(content);
      const resources = new Dict();
      const fontDict = new Dict();
      for (const [resource, ref] of fontRefs) fontDict.set(resource, ref);
      resources.set('Font', fontDict);
      resources.set('ProcSet', [new Name('PDF'), new Name('Text')]);
      const pageDict = new Dict();
      pageDict.set('Type', new Name('Page'));
      pageDict.set('Parent', pagesRef);
      pageDict.set('MediaBox', [0, 0, Math.round(this.pageWidth * 100) / 100, Math.round(this.pageHeight * 100) / 100]);
      pageDict.set('Resources', resources);
      pageDict.set('Contents', contentRef);
      pageRefs.push(doc.addObject(pageDict));
    }

    const pagesDict = doc.getObject(pagesRef.num);
    pagesDict.set('Type', new Name('Pages'));
    pagesDict.set('Kids', pageRefs);
    pagesDict.set('Count', pageRefs.length);

    const catalog = new Dict();
    catalog.set('Type', new Name('Catalog'));
    catalog.set('Pages', pagesRef);
    catalog.set('Lang', PdfString.fromText('de-DE'));
    const catalogRef = doc.addObject(catalog);

    const info = new Dict();
    info.set('Title', pdfText(this.metadata.title));
    info.set('Author', pdfText(this.metadata.author));
    info.set('Subject', pdfText(this.metadata.subject));
    info.set('Keywords', pdfText(this.metadata.keywords));
    info.set('Creator', pdfText(this.metadata.creator));
    info.set('Producer', pdfText(this.metadata.producer));
    info.set('CreationDate', pdfText(pdfDate(this.metadata.now)));
    info.set('ModDate', pdfText(pdfDate(this.metadata.now)));
    const infoRef = doc.addObject(info);

    return writePdf(doc, {
      root: catalogRef,
      info: infoRef,
      version: PDF_VERSION,
      compressStreams: true,
      objectStreams: true,
    });
  }
}
