import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { Dict, Name, Ref, Stream, PdfString, serialize, encodeName } from '../lib/objects.mjs';
import { inflate, deflate, asciiHexDecode, ascii85Decode, lzwDecode, runLengthDecode, unpredict, decodeStream } from '../lib/filters.mjs';
import { PdfDocument } from '../lib/parser.mjs';
import { TrueTypeFont, subsetFont, widthsForCodes, descriptorMetrics } from '../lib/fonts.mjs';
import { writePdf } from '../lib/writer.mjs';
import { buildXmp, pdfDate, xmpDate, PDFA } from '../lib/xmp.mjs';
import { normalize, DEFAULTS } from '../normalize.mjs';

const FONTS = 'C:/Windows/Fonts';
const ICC = DEFAULTS.iccPath;
const hasFonts = fs.existsSync(path.join(FONTS, 'times.ttf')) && fs.existsSync(path.join(FONTS, 'symbol.ttf'));
const hasIcc = fs.existsSync(ICC);
const ready = hasFonts && hasIcc;

// ---------------------------------------------------------------- fixtures
function assemble(objects, { root = 1, info = null } = {}) {
  const chunks = [];
  let size = 0;
  const push = (text) => {
    const buffer = Buffer.from(text, 'latin1');
    chunks.push(buffer);
    size += buffer.length;
  };
  push('%PDF-1.6\n%\xe2\xe3\xcf\xd3\n');
  const offsets = [];
  objects.forEach((body, i) => {
    offsets.push(size);
    push(`${i + 1} 0 obj\n${body}\nendobj\n`);
  });
  const xref = size;
  push(`xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`);
  for (const offset of offsets) push(String(offset).padStart(10, '0') + ' 00000 n \n');
  push(`trailer\n<< /Size ${objects.length + 1} /Root ${root} 0 R${info ? ` /Info ${info} 0 R` : ''} >>\nstartxref\n${xref}\n%%EOF\n`);
  return Buffer.concat(chunks);
}

function streamObject(dict, body) {
  return `<< ${dict} /Length ${Buffer.byteLength(body, 'latin1')} >>\nstream\n${body}\nendstream`;
}

function syntheticPdf() {
  const page1 = 'BT /F1 12 Tf 72 720 Td (Hello World) Tj ET\nBT /S1 12 Tf 72 700 Td <000b000c000e> Tj ET';
  const page2 = 'BT /F1 12 Tf 72 720 Td (Second page) Tj ET';
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields [] /DA (/Helv 0 Tf 0 g) /NeedAppearances false >> >>',
    '<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 /MediaBox [0 0 595.28 841.89] >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /Font << /F1 7 0 R /S1 8 0 R >> >> /Contents 4 0 R /Annots [9 0 R] >>',
    streamObject('', page1),
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>',
    streamObject('', page2),
    '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 126 >>',
    '<< /Type /Font /Subtype /Type0 /BaseFont /SymbolMT /Encoding /Identity-H /DescendantFonts [10 0 R] >>',
    '<< /Type /Annot /Subtype /Link /Rect [72 690 200 710] /Border [0 0 0] /A << /S /URI /URI (https://example.org) >> >>',
    '<< /Type /Font /Subtype /CIDFontType2 /BaseFont /SymbolMT /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor 11 0 R /DW 1000 >>',
    '<< /Type /FontDescriptor /FontName /SymbolMT /Flags 4 /FontBBox [0 -220 1113 1005] /ItalicAngle 0 /Ascent 1005 /Descent -220 /CapHeight 1005 /StemV 80 >>',
    '<< /Title (Synthetic source) /Producer (fixture) >>',
  ];
  return assemble(objects, { root: 1, info: 12 });
}

function eachObject(doc, visit) {
  const numbers = [...new Set([...doc.entries.keys(), ...doc.extra.keys()])].sort((a, b) => a - b);
  for (const n of numbers) {
    let value;
    try { value = doc.getObject(n); } catch { continue; }
    if (value !== undefined) visit(value, n);
  }
}

// ---------------------------------------------------------------- objects
test('objects: names, strings, numbers and dictionaries serialise as valid PDF', () => {
  assert.equal(String(new Name('Foo#Bar')), '/Foo#Bar');
  assert.equal(new Name(encodeName('A B#C')).text, 'A B#C');
  assert.equal(new Name('Foo#23Bar').text, 'Foo#Bar');
  assert.equal(String(new Ref(7, 0)), '7 0 R');
  assert.equal(String(PdfString.fromText('a(b)c\\d')), '(a\\(b\\)c\\\\d)');
  assert.equal(PdfString.fromText('a(b)c').text, 'a(b)c');
  assert.equal(String(PdfString.fromText('AB', true)), '<4142>');
  const dict = new Dict();
  dict.set('Type', new Name('Font'));
  assert.equal(dict.get('Type').text, 'Font');
  assert.equal(dict.get('/Type').text, 'Font');
  assert.equal(dict.name('Type'), 'Font');
  assert.equal(serialize(dict), '<</Type /Font>>');
  assert.equal(serialize([1, new Name('A'), false, null]), '[1 /A false null]');
});

// ---------------------------------------------------------------- filters
test('filters: Flate round-trip preserves every byte', () => {
  const source = Buffer.alloc(70000);
  for (let i = 0; i < source.length; i++) source[i] = (i * 37 + (i >> 3)) & 0xff;
  const packed = deflate(new Uint8Array(source));
  assert.ok(packed.length < source.length);
  assert.deepEqual(Buffer.from(inflate(packed)), source);
});

test('filters: ASCIIHex, ASCII85, LZW and RunLength decode the ISO 32000 examples', () => {
  assert.equal(Buffer.from(asciiHexDecode(Buffer.from('48656C6C6F>', 'latin1'))).toString(), 'Hello');
  assert.equal(Buffer.from(asciiHexDecode(Buffer.from('48656C6C6F', 'latin1'))).toString(), 'Hello');
  assert.equal(Buffer.from(ascii85Decode(Buffer.from('<~87cURDZ~>', 'latin1'))).toString(), 'Hello');
  assert.equal(Buffer.from(lzwDecode(new Uint8Array([0x80, 0x0b, 0x60, 0x50, 0x22, 0x0c, 0x0c, 0x85, 0x01]))).toString(), '-----A---B');
  assert.equal(Buffer.from(runLengthDecode(new Uint8Array([2, 97, 98, 99, 1, 100, 101, 128]))).toString(), 'abcde');
});

test('filters: PNG Up and TIFF predictors are undone exactly', () => {
  const up = unpredict(new Uint8Array([2, 10, 20, 30, 2, 1, 1, 1]), { Predictor: 12, Colors: 1, BitsPerComponent: 8, Columns: 3 });
  assert.deepEqual([...up], [10, 20, 30, 11, 21, 31]);
  const none = unpredict(new Uint8Array([0, 10, 20, 30]), { Predictor: 15, Columns: 3 });
  assert.deepEqual([...none], [10, 20, 30]);
  const tiff = unpredict(new Uint8Array([10, 5, 5, 20, 5, 5]), { Predictor: 2, Colors: 1, BitsPerComponent: 8, Columns: 3 });
  assert.deepEqual([...tiff], [10, 15, 20, 20, 25, 30]);
});

test('filters: decodeStream walks a chained /Filter array', () => {
  const dict = new Dict();
  dict.set('Filter', [new Name('ASCIIHexDecode'), new Name('FlateDecode')]);
  const body = Buffer.from('Hello World', 'latin1');
  const chain = Buffer.from(deflate(new Uint8Array(body))).toString('hex').toUpperCase() + '>';
  const stream = new Stream(dict, new Uint8Array(Buffer.from(chain, 'latin1')));
  assert.deepEqual(Buffer.from(decodeStream(stream, () => null)), body);
});

// ---------------------------------------------------------------- parser + writer
test('parser: reads a hand-written file with a classic xref table', () => {
  const doc = PdfDocument.load(syntheticPdf());
  assert.equal(doc.pages.length, 2);
  assert.equal(doc.root.name('Type'), 'Catalog');
  const info = doc.resolve(doc.trailer.get('Info'));
  assert.equal(info.get('Title').text, 'Synthetic source');
});

test('writer: parse, write then re-parse keeps pages and content', () => {
  const source = PdfDocument.load(syntheticPdf());
  const written = writePdf(source, {
    root: source.trailer.get('Root'),
    info: source.trailer.get('Info'),
    compressStreams: true,
    objectStreams: true,
    version: '1.7',
  });
  const again = PdfDocument.load(written.data);
  assert.equal(again.pages.length, 2);
  const contents = again.resolve(again.pages[0].get('Contents'));
  const text = Buffer.from(decodeStream(contents, () => null)).toString('latin1');
  assert.match(text, /Hello World/);
  assert.match(Buffer.from(written.data.subarray(0, 9)).toString('latin1'), /^%PDF-1\.7/);
});

// ---------------------------------------------------------------- xmp
test('xmp: dates and the PDF/A identification block are well formed', () => {
  const d = new Date(Date.UTC(2026, 10, 15, 4, 32, 16));
  assert.equal(pdfDate(d), 'D:20261115043216Z');
  assert.equal(xmpDate(d), '2026-11-15T04:32:16Z');
  assert.deepEqual(PDFA, { part: 2, conformance: 'B' });
  const packet = buildXmp({
    title: 'Basics & <co>', author: 'BSI', subject: 'Legal', keywords: 'a, b',
    creatorTool: 'tool', producer: 'prod', createDate: d, modifyDate: d,
  });
  assert.match(packet, /<pdfaid:part>2<\/pdfaid:part>/);
  assert.match(packet, /<pdfaid:conformance>B<\/pdfaid:conformance>/);
  assert.match(packet, /Basics &amp; &lt;co&gt;/);
  assert.match(packet, /<\?xpacket begin=/);
});

// ---------------------------------------------------------------- fonts
test('fonts: metrics match the platform TrueType tables', { skip: !hasFonts }, () => {
  const font = TrueTypeFont.load(new Uint8Array(fs.readFileSync(path.join(FONTS, 'times.ttf'))));
  assert.equal(font.unitsPerEm, 2048);
  assert.equal(font.numGlyphs, 4731);
  const metrics = descriptorMetrics(font);
  assert.equal(metrics.ascent, 891);
  assert.equal(metrics.descent, -216);
  assert.equal(metrics.capHeight, 662);
  const widths = widthsForCodes(font, 32, 126);
  assert.equal(widths.length, 95);
  assert.ok(widths.every((w) => w > 0));
});

const trim = (bytes) => { let n = bytes.length; while (n > 0 && bytes[n - 1] === 0) n--; return Buffer.from(bytes.subarray(0, n)); };

test('fonts: the subset keeps outlines byte identical under remapped glyph ids', { skip: !hasFonts }, () => {
  const source = TrueTypeFont.load(new Uint8Array(fs.readFileSync(path.join(FONTS, 'times.ttf'))));
  const unicodes = [...'Hello'].map((c) => c.codePointAt(0));
  const subset = subsetFont(source, { unicodes });
  assert.ok(subset.numGlyphs < source.numGlyphs);
  const sourceCmap = source.cmap();
  for (const code of unicodes) {
    const newGid = subset.gidMap.get(sourceCmap.get(code));
    assert.ok(newGid !== undefined, 'mapped ' + code);
    // glyf entries are 4-byte padded, so compare the unpadded outline bytes
    assert.deepEqual(trim(subset.font.glyphData(newGid)), trim(source.glyphData(sourceCmap.get(code))), 'glyph ' + code);
  }
});

// ---------------------------------------------------------------- normalise
test('normalize: a synthetic fixture becomes PDF/A-2b evidence', { skip: !ready }, () => {
  const result = normalize(syntheticPdf(), {
    quiet: true, title: 'Synthetic', author: 'Tester', subject: 'Unit', keywords: 'a, b',
  });
  const doc = PdfDocument.load(result.data);
  const root = doc.root;
  assert.equal(doc.pages.length, 2);
  assert.equal(root.get('AcroForm'), undefined, 'empty AcroForm removed');
  assert.ok(root.has('PageLabels'), 'page labels added');
  assert.ok(root.has('OutputIntents'), 'output intent added');
  assert.ok(root.has('Metadata'), 'xmp written');

  const labels = doc.resolve(root.get('PageLabels'));
  assert.equal(labels.length, 4);
  assert.equal(labels[3].get('St'), 8);
  assert.equal(labels[1].name('S'), 'r');
  assert.equal(labels[3].name('S'), 'D');

  const intents = doc.resolve(root.get('OutputIntents'));
  const intent = doc.resolve(intents[0]);
  assert.equal(intent.name('S'), 'GTS_PDFA1');
  const profile = doc.resolve(intent.get('DestOutputProfile'));
  assert.equal(profile.dict.get('N'), 3);
  assert.equal(decodeStream(profile, () => null).length, result.stats.steps.iccBytes);

  const xmp = Buffer.from(decodeStream(doc.resolve(root.get('Metadata')), () => null)).toString('utf8');
  assert.match(xmp, /<pdfaid:part>2<\/pdfaid:part>/);
  assert.match(xmp, /<pdfaid:conformance>B<\/pdfaid:conformance>/);

  const info = doc.resolve(doc.trailer.get('Info'));
  assert.equal(info.get('Title').text, 'Synthetic');
  assert.equal(info.get('Author').text, 'Tester');

  const annots = doc.resolve(doc.pages[0].get('Annots'));
  assert.equal(doc.resolve(annots[0]).get('F'), 4);
  assert.equal(result.stats.steps.annotations, 1);
  assert.equal(result.stats.steps.acroFormRemoved, true);
  assert.equal(result.stats.pages, 2);
  assert.match(result.stats.sha256, /^[0-9a-f]{64}$/);
  assert.equal(result.stats.bytes, result.data.length);
});

test('normalize: every font object it leaves behind is embedded', { skip: !ready }, () => {
  const result = normalize(syntheticPdf(), { quiet: true, title: 'Synthetic' });
  const doc = PdfDocument.load(result.data);
  const fonts = [];
  eachObject(doc, (value) => {
    if (value instanceof Dict && value.name('Type') === 'Font') fonts.push(value);
  });
  assert.ok(fonts.length >= 3, 'font objects: ' + fonts.length);
  for (const font of fonts) {
    const descriptors = [];
    const direct = doc.resolve(font.get('FontDescriptor'));
    if (direct instanceof Dict) descriptors.push(direct);
    const kids = doc.resolve(font.get('DescendantFonts'));
    if (Array.isArray(kids)) {
      const cid = doc.resolve(kids[0]);
      const fd = cid instanceof Dict ? doc.resolve(cid.get('FontDescriptor')) : null;
      if (fd instanceof Dict) descriptors.push(fd);
    }
    assert.ok(descriptors.length > 0, 'descriptor for ' + font.name('BaseFont'));
    assert.ok(descriptors.some((fd) => fd.has('FontFile2') || fd.has('FontFile3')), 'embedded ' + font.name('BaseFont'));
  }
  assert.ok(result.stats.steps.timesRomanFonts >= 1);
  assert.ok(result.stats.steps.symbolFonts >= 1);
});

test('normalize: re-running on its own output stays stable', { skip: !ready }, () => {
  const once = normalize(syntheticPdf(), { quiet: true, title: 'Synthetic' });
  const twice = normalize(once.data, { quiet: true, title: 'Synthetic' });
  const doc = PdfDocument.load(twice.data);
  assert.equal(doc.pages.length, 2);
  assert.equal(doc.root.get('AcroForm'), undefined);
  const labels = doc.resolve(doc.root.get('PageLabels'));
  assert.equal(labels.length, 4);
  const annots = doc.resolve(doc.pages[0].get('Annots'));
  assert.equal(doc.resolve(annots[0]).get('F'), 4);
  assert.ok(!twice.stats.steps.acroFormRemoved, 'nothing left to remove');
});

test('normalize: /Linearized is deliberately absent (Fast Web View is out of scope)', { skip: !ready }, () => {
  const result = normalize(syntheticPdf(), { quiet: true, title: 'Synthetic' });
  const head = Buffer.from(result.data.subarray(0, 2048)).toString('latin1');
  assert.ok(!head.includes('/Linearized'), 'no linearisation dictionary');
  assert.match(head, /^%PDF-1\.7/);
});