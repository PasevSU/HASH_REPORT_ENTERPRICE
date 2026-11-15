// Acceptance suite for the real 217-page BSI document.
// Inputs are not committed: provide them with CS_GOLDEN_IN / CS_GOLDEN_OUT, or the
// defaults below (the original attachment and the JavaScript output built from it).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { Dict, Name, Stream } from '../lib/objects.mjs';
import { decodeStream } from '../lib/filters.mjs';
import { PdfDocument } from '../lib/parser.mjs';
import { normalize } from '../normalize.mjs';

const INPUT = process.env.CS_GOLDEN_IN
  || 'C:/Users/Pasev/.copilot/workspaces/5b24de32-d812-4779-a690-2da443508bfd/attachments/d3a3a61e-c373-4bd9-82fc-f98a85541967-esig_pdf.pdf';
const OUTPUT = process.env.CS_GOLDEN_OUT || path.join(os.tmpdir(), 'cs_pdfnorm', 'js_pdfa2b.pdf');
const present = fs.existsSync(INPUT) && fs.existsSync(OUTPUT);

const parmsOf = (doc, stream) => (i) => {
  const p = doc.resolve(stream.dict.get('DecodeParms'));
  return Array.isArray(p) ? doc.resolve(p[i]) : p;
};

function contentBytes(doc, page) {
  const contents = doc.resolve(page.get('Contents'));
  const list = Array.isArray(contents) ? contents : [contents];
  return Buffer.concat(list.map((ref) => {
    const stream = doc.resolve(ref);
    return stream instanceof Stream ? Buffer.from(decodeStream(stream, parmsOf(doc, stream))) : Buffer.alloc(0);
  }));
}

function collect(doc) {
  const out = { fonts: [], annots: [], objStm: 0 };
  for (const num of [...new Set([...doc.entries.keys(), ...doc.extra.keys()])].sort((a, b) => a - b)) {
    let value;
    try { value = doc.getObject(num); } catch { continue; }
    const dict = value instanceof Stream ? value.dict : value;
    if (!(dict instanceof Dict)) continue;
    const type = dict.name('Type');
    if (type === 'Font') out.fonts.push(dict);
    else if (type === 'Annot') out.annots.push(dict);
    else if (type === 'ObjStm') out.objStm++;
  }
  return out;
}

let inputDoc;
let outputDoc;
function docs() {
  if (!inputDoc) {
    inputDoc = PdfDocument.load(new Uint8Array(fs.readFileSync(INPUT)));
    outputDoc = PdfDocument.load(new Uint8Array(fs.readFileSync(OUTPUT)));
  }
  return { input: inputDoc, output: outputDoc };
}

test('golden: page tree, page boxes and rotation survive untouched', { skip: !present }, () => {
  const { input, output } = docs();
  assert.equal(input.pages.length, 217);
  assert.equal(output.pages.length, 217);
  for (const index of [0, 100, 216]) {
    const a = input.pages[index];
    const b = output.pages[index];
    assert.deepEqual([...b.get('MediaBox')].map(Number), [...a.get('MediaBox')].map(Number), 'MediaBox page ' + (index + 1));
    assert.equal(b.get('Rotate') ?? 0, a.get('Rotate') ?? 0, 'Rotate page ' + (index + 1));
    assert.equal(output.resolve(b.get('Parent')).name('Type'), 'Pages');
  }
});

test('golden: every page content stream is byte identical to the source', { skip: !present }, () => {
  const { input, output } = docs();
  for (let i = 0; i < input.pages.length; i++) {
    const before = contentBytes(input, input.pages[i]);
    const after = contentBytes(output, output.pages[i]);
    assert.equal(after.length, before.length, 'content length page ' + (i + 1));
    assert.ok(after.equals(before), 'content bytes page ' + (i + 1));
  }
});

test('golden: page labels mirror the printed folios', { skip: !present }, () => {
  const { output } = docs();
  const labels = output.resolve(output.root.get('PageLabels'));
  assert.ok(Array.isArray(labels), 'page labels present');
  assert.deepEqual(labels.map((v) => (typeof v === 'number' ? v : v.name('S'))), [0, 'r', 7, 'D']);
  assert.equal(labels[3].get('St'), 8);
});

test('golden: output intent is sRGB under GTS_PDFA1', { skip: !present }, () => {
  const { output } = docs();
  const intents = output.resolve(output.root.get('OutputIntents'));
  assert.equal(intents.length, 1);
  const intent = output.resolve(intents[0]);
  assert.equal(intent.name('Type'), 'OutputIntent');
  assert.equal(intent.name('S'), 'GTS_PDFA1');
  assert.equal(intent.get('OutputConditionIdentifier').text, 'sRGB IEC61966-2.1');
  const profile = output.resolve(intent.get('DestOutputProfile'));
  assert.equal(profile.dict.get('N'), 3);
  const icc = Buffer.from(decodeStream(profile, parmsOf(output, profile)));
  assert.equal(icc.length, 8708);
  assert.equal(icc.subarray(36, 40).toString('latin1'), 'acsp');
  assert.equal(icc.subarray(16, 20).toString('latin1'), 'RGB ');
});

test('golden: XMP identification and document information agree', { skip: !present }, () => {
  const { output } = docs();
  const meta = output.resolve(output.root.get('Metadata'));
  const xmp = Buffer.from(decodeStream(meta, parmsOf(output, meta))).toString('utf8');
  assert.match(xmp, /<pdfaid:part>2<\/pdfaid:part>/);
  assert.match(xmp, /<pdfaid:conformance>B<\/pdfaid:conformance>/);
  assert.match(xmp, /Basics of Digital Signature Techniques and Trust Services, Version 2\.0/);
  assert.ok(!/pdfaid:part>1</.test(xmp), 'not PDF/A-1');

  const info = output.resolve(output.trailer.get('Info'));
  assert.equal(info.get('Title').text, 'Basics of Digital Signature Techniques and Trust Services, Version 2.0');
  const keywords = info.get('Keywords').text;
  assert.ok(!keywords.includes('"'), 'no stray quotes: ' + keywords);
  assert.match(info.get('CreationDate').text, /^D:\d{14}Z$/);
  assert.match(info.get('ModDate').text, /^D:\d{14}Z$/);
  assert.equal(info.get('Producer').text, info.get('Creator').text);
});

test('golden: no AcroForm, language, tagging and outline survive', { skip: !present }, () => {
  const { input, output } = docs();
  const sourceForm = input.resolve(input.root.get('AcroForm'));
  assert.ok(sourceForm instanceof Dict, 'source declares an AcroForm');
  assert.equal(input.resolve(sourceForm.get('Fields')).length, 0, 'and it has no fields');
  assert.equal(output.root.get('AcroForm'), undefined);
  const lang = output.root.get('Lang');
  assert.ok(lang && String(lang.text ?? lang.raw ?? '').startsWith('en'), 'document language kept');
  assert.equal(output.root.name('PageMode'), 'UseOutlines');
  const markInfo = output.resolve(output.root.get('MarkInfo'));
  assert.equal(markInfo.get('Marked'), true);
  assert.ok(output.root.get('StructTreeRoot') instanceof Object);
});

test('golden: every font object ends up embedded', { skip: !present }, () => {
  const { output } = docs();
  const { fonts } = collect(output);
  assert.ok(fonts.length >= 20, 'font objects: ' + fonts.length);
  for (const font of fonts) {
    const descriptors = [];
    const direct = output.resolve(font.get('FontDescriptor'));
    if (direct instanceof Dict) descriptors.push(direct);
    const kids = output.resolve(font.get('DescendantFonts'));
    if (Array.isArray(kids)) {
      const cid = output.resolve(kids[0]);
      const fd = cid instanceof Dict ? output.resolve(cid.get('FontDescriptor')) : null;
      if (fd instanceof Dict) descriptors.push(fd);
    }
    assert.ok(descriptors.length > 0, 'descriptor for ' + font.name('BaseFont'));
    assert.ok(descriptors.some((fd) => fd.has('FontFile2') || fd.has('FontFile3')), 'embedded ' + font.name('BaseFont'));
  }
});

test('golden: annotations are printable, visible and free of forbidden actions', { skip: !present }, () => {
  const { output } = docs();
  const { annots } = collect(output);
  assert.ok(annots.length > 3000, 'annotations: ' + annots.length);
  for (const annot of annots) {
    const flags = Number(annot.get('F') ?? 0);
    assert.equal(flags & 4, 4, 'printable');
    assert.equal(flags & 2, 0, 'not hidden');
    const action = output.resolve(annot.get('A'));
    if (action instanceof Dict) assert.notEqual(action.name('S'), 'JavaScript');
    assert.equal(annot.get('AA'), undefined, 'no additional actions');
  }
});

test('golden: object streams are used and /Linearized stays out (documented omission)', { skip: !present }, () => {
  const { input, output } = docs();
  const head = Buffer.from(fs.readFileSync(OUTPUT).subarray(0, 4096)).toString('latin1');
  assert.ok(!head.includes('/Linearized'), 'fast web view is out of scope for PDF/A-2b');
  assert.ok(collect(input).objStm > 0, 'source already packs objects');
  assert.ok(collect(output).objStm > 0, 'output packs objects');
  assert.match(head, /^%PDF-1\.7/);
});

test('golden: normalising the source again reproduces the same structure', { skip: !present }, () => {
  const source = new Uint8Array(fs.readFileSync(INPUT));
  const fresh = normalize(source, { quiet: true, sourcePath: INPUT, modifyDate: new Date(Date.UTC(2026, 10, 15, 4, 32, 16)) });
  const doc = PdfDocument.load(fresh.data);
  assert.equal(doc.pages.length, 217);
  assert.equal(doc.root.get('AcroForm'), undefined);
  assert.equal(fresh.stats.steps.iccBytes, 8708);
  assert.equal(fresh.stats.steps.timesRomanFonts, 2);
  assert.equal(fresh.stats.steps.symbolFonts, 7);
  assert.deepEqual(fresh.stats.steps.symbolCids, ['0xb', '0xc', '0xe', '0x10', '0x20', '0x4d', '0x56', '0x7b', '0x85', '0xaa', '0xba']);
  for (let i = 0; i < doc.pages.length; i++) {
    assert.ok(contentBytes(doc, doc.pages[i]).equals(contentBytes(inputDoc, inputDoc.pages[i])), 'content page ' + (i + 1));
  }
});