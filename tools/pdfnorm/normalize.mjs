#!/usr/bin/env node
// PDF/A-2b normaliser: pure JavaScript, no native dependencies.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { Dict, Name, Ref, Stream, PdfString } from './lib/objects.mjs';
import { PdfDocument } from './lib/parser.mjs';
import { decodeStream } from './lib/filters.mjs';
import { TrueTypeFont, subsetFont, widthsForCodes, descriptorMetrics } from './lib/fonts.mjs';
import { writePdf } from './lib/writer.mjs';
import { buildXmp, pdfDate } from './lib/xmp.mjs';

export const DEFAULTS = {
  title: 'Basics of Digital Signature Techniques and Trust Services, Version 2.0',
  author: 'Federal Office for Information Security (BSI)',
  subject: 'Legal Framework, Technical Aspects',
  keywords: 'electronic Signatures, electronic Seals, ETSI, RFC, eIDAS-Standards, '
    + 'Cryptography, Signature Algorithms, Evidence Record',
  producer: 'ChronoSeal Enterprise 5.6.0 PDF normalizer (pure JavaScript)',
  creatorTool: 'ChronoSeal Enterprise 5.6.0',
  fontDir: process.env.CS_FONT_DIR || 'C:/Windows/Fonts',
  iccPath: process.env.CS_ICC || 'C:/Windows/System32/spool/drivers/color/ewsrgb.icm',
  pageLabels: true,
  pageLabelRoman: 7,
  pageLabelStart: 8,
  subsetPrefixes: { times: 'CHRNSP', arial: 'CHRNSQ', ariaBold: 'CHRNSQ', symbol: 'CHRNSB' },
  pdfVersion: '1.7',
};

const isName = (v, n) => v instanceof Name && v.text === n;

function dictDelete(dict, key) {
  if (typeof dict.del === 'function') dict.del(key);
  else dict.delete(key);
}

function objectNumbers(doc) {
  const nums = new Set();
  for (const n of doc.entries.keys()) nums.add(n);
  for (const n of doc.extra.keys()) nums.add(n);
  return [...nums].sort((a, b) => a - b);
}

function streamBytes(doc, stream) {
  const filters = doc.resolve(stream.dict.get('Filter'));
  if (!filters) return stream.data;
  return decodeStream(stream, (i) => {
    const p = doc.resolve(stream.dict.get('DecodeParms'));
    return Array.isArray(p) ? doc.resolve(p[i]) : p;
  });
}

function contentBytes(doc, contents) {
  const c = doc.resolve(contents);
  if (!c) return new Uint8Array(0);
  const list = Array.isArray(c) ? c.map((x) => doc.resolve(x)) : [c];
  const parts = list.filter((s) => s instanceof Stream).map((s) => streamBytes(doc, s));
  const total = parts.reduce((a, p) => a + p.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

function makeStream(doc, dict, data) {
  return doc.addObject(new Stream(dict, data));
}

function embeddedFont(doc, { file, unicodeCodes, gids, retainGids, fontName, flags }) {
  const raw = new Uint8Array(fs.readFileSync(file));
  const source = TrueTypeFont.load(raw);
  const sub = subsetFont(source, gids ? { gids, retainGids: true } : { unicodes: unicodeCodes });
  const metrics = descriptorMetrics(source);
  const fileStream = new Stream(new Dict(), sub.data);
  fileStream.dict.set('Type', new Name('EmbeddedFile'));
  fileStream.dict.set('Length1', sub.data.length);
  const fileRef = doc.addObject(fileStream);
  const fd = new Dict();
  fd.set('Type', new Name('FontDescriptor'));
  fd.set('FontName', new Name(fontName));
  fd.set('Flags', flags);
  fd.set('FontBBox', metrics.bbox);
  fd.set('ItalicAngle', 0);
  fd.set('Ascent', metrics.ascent);
  fd.set('Descent', metrics.descent);
  fd.set('CapHeight', metrics.capHeight);
  fd.set('StemV', 80);
  fd.set('FontFile2', fileRef);
  return { source, subset: sub, descriptorRef: doc.addObject(fd), descriptor: fd, bytes: sub.data };
}

export function normalize(srcBytes, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  const log = [];
  const say = (m) => { log.push(m); if (!o.quiet) console.log(m); };
  const stat = { steps: {}, log };

  const doc = PdfDocument.load(srcBytes);
  const root = doc.root;
  if (!root) throw new Error('document has no catalog');
  const pages = doc.pages;
  say('source: ' + pages.length + ' pages, ' + doc.entries.size + ' objects');

  const existing = () => objectNumbers(doc);

  // ---- 1. Times-Roman -> embedded TrueType subset
  const ascii = [...Array(95).keys()].map((i) => 32 + i);
  const times = embeddedFont(doc, {
    file: path.join(o.fontDir, 'times.ttf'),
    unicodeCodes: ascii,
    fontName: o.subsetPrefixes.times + '+Times-Roman',
    flags: 32,
  });
  const timesWidths = widthsForCodes(times.source, 32, 126);
  let nTimes = 0;
  for (const num of existing()) {
    const v = doc.getObject(num);
    if (!(v instanceof Dict) || !isName(v.get('Type'), 'Font')) continue;
    if (!isName(v.get('BaseFont'), 'Times-Roman')) continue;
    v.set('Subtype', new Name('TrueType'));
    v.set('BaseFont', new Name(o.subsetPrefixes.times + '+Times-Roman'));
    v.set('Encoding', new Name('WinAnsiEncoding'));
    v.set('FirstChar', 32);
    v.set('LastChar', 126);
    v.set('Widths', timesWidths.slice());
    v.set('FontDescriptor', times.descriptorRef);
    nTimes++;
  }
  stat.steps.timesRomanFonts = nTimes;
  say('Times-Roman fonts embedded: ' + nTimes);

  // ---- 1b. Arial family -> embedded TrueType, original /Widths retained
  for (const [baseFont, file, prefix] of [['Arial', 'arial.ttf', 'Arial'], ['Arial,Bold', 'arialbd.ttf', 'Arial-Bold']]) {
    const targets = [];
    for (const num of existing()) {
      const v = doc.getObject(num);
      if (!(v instanceof Dict) || !isName(v.get('Type'), 'Font')) continue;
      if (!isName(v.get('BaseFont'), baseFont)) continue;
      targets.push(v);
    }
    if (!targets.length) continue;
    const first = Math.min(...targets.map((t) => Number(t.get('FirstChar') ?? 32)));
    const last = Math.max(...targets.map((t) => Number(t.get('LastChar') ?? 126)));
    const probe = TrueTypeFont.load(new Uint8Array(fs.readFileSync(path.join(o.fontDir, file))));
    const cmap = probe.cmap();
    const codes = [];
    for (let c = first; c <= last; c++) if (cmap.has(c)) codes.push(c);
    const embed = embeddedFont(doc, {
      file: path.join(o.fontDir, file),
      unicodeCodes: codes,
      fontName: o.subsetPrefixes.arial + '+' + prefix,
      flags: 32,
    });
    for (const t of targets) {
      t.set('Subtype', new Name('TrueType'));
      t.set('BaseFont', new Name(o.subsetPrefixes.arial + '+' + prefix));
      t.set('Encoding', new Name('WinAnsiEncoding'));
      t.set('FirstChar', first);
      t.set('LastChar', last);
      t.set('FontDescriptor', embed.descriptorRef);
    }
    stat.steps[baseFont + 'Fonts'] = targets.length;
    say(baseFont + ' fonts embedded (kept original /Widths): ' + targets.length);
  }

  // ---- 2. SymbolMT (Type0) -> embedded TrueType with retained glyph ids
  const scanRe = /\/([A-Za-z0-9#_.+-]+)\s+[-\d.]+\s+Tf|<([0-9A-Fa-f\s]*)>\s*(?:Tj|TJ|'|")?/g;
  const cids = new Set();

  const scanContent = (data, fonts) => {
    let current = null;
    const text = Buffer.from(data).toString('latin1');
    scanRe.lastIndex = 0;
    let m;
    while ((m = scanRe.exec(text)) !== null) {
      if (m[1] !== undefined) {
        const font = fonts.get(m[1]);
        current = font && String(font.get('BaseFont') ?? '').includes('SymbolMT') ? font : null;
        continue;
      }
      if (!current) continue;
      const hex = (m[2] || '').replace(/\s+/g, '');
      for (let i = 0; i + 4 <= hex.length; i += 4) cids.add(parseInt(hex.slice(i, i + 4), 16));
    }
  };

  const fontsOf = (res) => {
    const out = new Map();
    const fonts = res ? doc.resolve(res.get('Font')) : null;
    if (fonts instanceof Dict) for (const [k, v] of fonts) out.set(k, doc.resolve(v));
    return out;
  };

  const seenForms = new Set();
  const walkResources = (res, data) => {
    const r = doc.resolve(res);
    if (!r) return;
    scanContent(data, fontsOf(r));
    const xobjects = doc.resolve(r.get('XObject'));
    if (!(xobjects instanceof Dict)) return;
    for (const [, raw] of xobjects) {
      const x = doc.resolve(raw);
      if (!(x instanceof Stream) || !isName(x.dict.get('Subtype'), 'Form')) continue;
      const key = x.num ?? raw.num;
      if (seenForms.has(key)) continue;
      seenForms.add(key);
      const sub = doc.resolve(x.dict.get('Resources')) || r;
      walkResources(sub, streamBytes(doc, x));
    }
  };

  for (const page of pages) {
    const res = page.get('Resources');
    walkResources(res, contentBytes(doc, page.get('Contents')));
  }

  const symbolPath = path.join(o.fontDir, 'symbol.ttf');
  const symbolSource = TrueTypeFont.load(new Uint8Array(fs.readFileSync(symbolPath)));
  const cidList = [...cids].filter((c) => c < symbolSource.numGlyphs).sort((a, b) => a - b);
  stat.steps.symbolCids = cidList.map((c) => '0x' + c.toString(16));
  say('SymbolMT CIDs to embed: ' + cidList.map((c) => '0x' + c.toString(16)).join(' '));

  let nSymbol = 0;
  if (cidList.length) {
    const embed = embeddedFont(doc, {
      file: symbolPath,
      gids: cidList,
      retainGids: true,
      fontName: o.subsetPrefixes.symbol + '+SymbolMT',
      flags: 4,
    });
    const bits = new Uint8Array(Math.ceil(symbolSource.numGlyphs / 8));
    for (const c of cidList) bits[c >> 3] |= 0x80 >> (c & 7);
    const cidSet = new Stream(new Dict(), bits);
    cidSet.dict.set('Type', new Name('CIDSet'));
    const cidSetRef = doc.addObject(cidSet);
    for (const num of existing()) {
      const v = doc.getObject(num);
      if (!(v instanceof Dict) || !isName(v.get('Type'), 'Font')) continue;
      if (!String(v.get('BaseFont') ?? '').includes('SymbolMT')) continue;
      const desc = doc.resolve(v.get('DescendantFonts'));
      if (!desc || !desc.length) continue;
      const cidFont = doc.resolve(desc[0]);
      if (!(cidFont instanceof Dict)) continue;
      const fd = doc.resolve(cidFont.get('FontDescriptor'));
      if (fd instanceof Dict) {
        fd.set('FontName', new Name(o.subsetPrefixes.symbol + '+SymbolMT'));
        for (const [k, val] of embed.descriptor) {
          if (['Ascent', 'Descent', 'CapHeight', 'StemV', 'Flags', 'FontBBox'].includes(k)) fd.set(k, val);
        }
        fd.set('FontFile2', embed.descriptor.get('FontFile2'));
        if (fd.has('FontFile')) dictDelete(fd, 'FontFile');
        if (fd.has('FontFile3')) dictDelete(fd, 'FontFile3');
        if (!fd.has('CIDSet')) fd.set('CIDSet', cidSetRef);
      } else {
        const clone = new Dict(embed.descriptor);
        clone.set('CIDSet', cidSetRef);
        cidFont.set('FontDescriptor', doc.addObject(clone));
      }
      cidFont.set('FontName', new Name(o.subsetPrefixes.symbol + '+SymbolMT'));
      cidFont.set('BaseFont', new Name(o.subsetPrefixes.symbol + '+SymbolMT'));
      cidFont.set('CIDToGIDMap', new Name('Identity'));
      v.set('BaseFont', new Name(o.subsetPrefixes.symbol + '+SymbolMT'));
      nSymbol++;
    }
  }
  stat.steps.symbolFonts = nSymbol;
  say('SymbolMT fonts embedded: ' + nSymbol);

  // ---- 3. remove the empty interactive form
  const acro = doc.resolve(root.get('AcroForm'));
  if (acro instanceof Dict) {
    const fields = doc.resolve(acro.get('Fields'));
    if (!fields || !fields.length) {
      dictDelete(root, 'AcroForm');
      stat.steps.acroFormRemoved = true;
      say('AcroForm removed (0 fields)');
    } else {
      stat.steps.acroFormRemoved = false;
      say('AcroForm kept (' + fields.length + ' fields)');
    }
  }

  // ---- 3b. annotation flags: printable, never hidden
  let nAnn = 0;
  for (const page of pages) {
    const annots = doc.resolve(page.get('Annots'));
    if (!Array.isArray(annots)) continue;
    for (const raw of annots) {
      const a = doc.resolve(raw);
      if (!(a instanceof Dict)) continue;
      const flags = Number(doc.resolve(a.get('F')) ?? 0);
      a.set('F', (flags & ~3) | 4);
      nAnn++;
    }
  }
  stat.steps.annotations = nAnn;
  say('annotations flagged printable (/F 4): ' + nAnn);

  // ---- 3c. strip actions that PDF/A forbids
  const forbidden = new Set(['Launch', 'Sound', 'Movie', 'JavaScript', 'Rendition', 'ImportData', 'SetOCGState', 'GoTo3DView', 'Trans']);
  let nActions = 0;
  for (const num of existing()) {
    const v = doc.getObject(num);
    if (!(v instanceof Dict)) continue;
    const action = doc.resolve(v.get('A'));
    if (action instanceof Dict && isName(action.get('S'), 'JavaScript')) nActions++;
    if (action instanceof Dict && forbidden.has(action.get('S')?.text)) {
      dictDelete(v, 'A');
      nActions++;
    }
    if (v.has('AA')) { dictDelete(v, 'AA'); nActions++; }
  }
  stat.steps.removedActions = nActions;
  if (nActions) say('forbidden actions removed: ' + nActions);

  // ---- 4. output intent (sRGB ICC)
  const icc = new Uint8Array(fs.readFileSync(o.iccPath));
  const iccStream = new Stream(new Dict(), icc);
  iccStream.dict.set('N', 3);
  const iccRef = doc.addObject(iccStream);
  const intent = new Dict();
  intent.set('Type', new Name('OutputIntent'));
  intent.set('S', new Name('GTS_PDFA1'));
  intent.set('OutputConditionIdentifier', PdfString.fromText('sRGB IEC61966-2.1'));
  intent.set('OutputCondition', PdfString.fromText('sRGB IEC61966-2.1'));
  intent.set('Info', PdfString.fromText('sRGB IEC61966-2.1 (ECI, ewsrgb.icm)'));
  intent.set('RegistryName', PdfString.fromText('http://www.color.org'));
  intent.set('DestOutputProfile', iccRef);
  root.set('OutputIntents', doc.addObject([doc.addObject(intent)]));
  stat.steps.iccBytes = icc.length;
  say('output intent: sRGB, ' + icc.length + ' ICC bytes');

  // ---- 5. page labels mirroring the printed folios
  // Callers that print their own folios (the report generator prints "Page N")
  // pass pageLabels: false; the default stays the BSI front-matter scheme.
  if (o.pageLabels === false) {
    stat.steps.pageLabels = null;
    say('page labels: left to the printed folios');
  } else {
    const roman = new Dict(); roman.set('S', new Name('r'));
    const arabic = new Dict(); arabic.set('S', new Name('D')); arabic.set('St', o.pageLabelStart);
    root.set('PageLabels', doc.addObject([0, roman, o.pageLabelRoman, arabic]));
    stat.steps.pageLabels = [[0, 'r'], [o.pageLabelRoman, 'D', o.pageLabelStart]];
    say('page labels: i..vii then ' + o.pageLabelStart + '..' + (o.pageLabelStart + pages.length - o.pageLabelRoman - 1));
  }

  // ---- 6. metadata (DocInfo + XMP)
  let mtime = new Date();
  try { mtime = o.modifyDate || fs.statSync(o.sourcePath).mtime; } catch { /* keep now */ }
  const created = o.createDate || mtime;
  const modified = o.modifyDate || new Date();
  const infoRef = doc.trailer.get('Info');
  let info = doc.resolve(infoRef);
  if (!(info instanceof Dict)) {
    info = new Dict();
    doc.trailer.set('Info', doc.addObject(info));
  }
  info.set('Title', PdfString.fromText(o.title));
  info.set('Author', PdfString.fromText(o.author));
  info.set('Subject', PdfString.fromText(o.subject));
  info.set('Keywords', PdfString.fromText(o.keywords));
  info.set('Creator', PdfString.fromText(o.producer));
  info.set('Producer', PdfString.fromText(o.producer));
  info.set('CreationDate', PdfString.fromText(pdfDate(created)));
  info.set('ModDate', PdfString.fromText(pdfDate(modified)));

  const xmp = buildXmp({
    title: o.title, author: o.author, subject: o.subject, keywords: o.keywords,
    creatorTool: o.creatorTool, producer: o.producer, createDate: created, modifyDate: modified,
  });
  const metaStream = new Stream(new Dict(), new Uint8Array(Buffer.from(xmp, 'utf8')));
  metaStream.dict.set('Type', new Name('Metadata'));
  metaStream.dict.set('Subtype', new Name('XML'));
  root.set('Metadata', doc.addObject(metaStream));
  say('metadata written; created ' + created.toISOString() + ', modified ' + modified.toISOString());

  // ---- 7. serialise
  const written = writePdf(doc, {
    root: doc.trailer.get('Root'),
    info: doc.trailer.get('Info'),
    compressStreams: true,
    objectStreams: true,
    version: o.pdfVersion,
  });
  stat.bytes = written.data.length;
  stat.pdfa = { part: 2, conformance: 'B' };
  stat.sha256 = createHash('sha256').update(Buffer.from(written.data)).digest('hex');
  stat.write = written.stats;
  stat.pages = pages.length;
  say('saved: ' + written.data.length + ' bytes');
  say('sha256: ' + stat.sha256);
  return { data: written.data, stats: stat };
}

const isMain = Boolean(process.argv[1] && process.argv[1].split(String.fromCharCode(92)).join("/").endsWith("normalize.mjs"));
if (isMain) {
  const [src, dst] = process.argv.slice(2);
  if (!src || !dst) {
    console.error('usage: node tools/pdfnorm/normalize.mjs <input.pdf> <output.pdf>');
    process.exit(2);
  }
  const res = normalize(new Uint8Array(fs.readFileSync(src)), { sourcePath: src });
  fs.writeFileSync(dst, res.data);
  const sidecar = dst + '.sha256';
  fs.writeFileSync(sidecar, res.stats.sha256 + '  ' + path.basename(dst) + '\n');
  console.log('wrote ' + dst + ' and ' + sidecar);
}