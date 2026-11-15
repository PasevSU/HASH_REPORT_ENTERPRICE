// PDF writer: reachability renumbering, object streams, xref streams, linearisation.
import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import { Dict, Name, Ref, Stream, PdfString, formatNumber } from './objects.mjs';

const ascii = (s) => new Uint8Array(Buffer.from(s, 'latin1'));

class Out {
  constructor() { this.parts = []; this.length = 0; }
  push(x) { const b = x instanceof Uint8Array ? x : ascii(String(x)); this.parts.push(b); this.length += b.length; return this; }
  get offset() { return this.length; }
  bytes() {
    const out = new Uint8Array(this.length);
    let o = 0;
    for (const p of this.parts) { out.set(p, o); o += p.length; }
    return out;
  }
}

export function emitValue(value, map) {
  if (value === null || value === undefined) return 'null';
  if (value instanceof Ref) return (map.get(value.num) ?? 0) + ' 0 R';
  if (value instanceof Dict) {
    const parts = [];
    for (const [k, v] of value) parts.push('/' + k + ' ' + emitValue(v, map));
    return '<< ' + parts.join(' ') + ' >>';
  }
  if (Array.isArray(value)) return '[' + value.map((v) => emitValue(v, map)).join(' ') + ']';
  if (typeof value === 'number') return formatNumber(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (value instanceof Name) return value.toString();
  if (value instanceof PdfString) return value.toString();
  if (value instanceof Stream) throw new Error('stream must be emitted by the writer');
  return String(value);
}

function streamDict(stream, length) {
  const dict = new Dict();
  for (const [k, v] of stream.dict) if (k !== 'Length') dict.set(k, v);
  dict.set('Length', length);
  return dict;
}

function plainDictOf(dict, extra) {
  const d = new Dict();
  for (const [k, v] of dict) if (k !== 'Length') d.set(k, v);
  for (const [k, v] of Object.entries(extra || {})) d.set(k, v);
  return d;
}

function collectReachable(doc, roots) {
  const seen = new Set();
  const emitted = new Set();
  const order = [];
  const stack = [];
  const note = (v) => {
    if (v instanceof Ref) { if (!seen.has(v.num)) { seen.add(v.num); stack.push(v.num); } }
    else if (v instanceof Dict) for (const [, x] of v) note(x);
    else if (v instanceof Stream) note(v.dict);
    else if (Array.isArray(v)) for (const x of v) note(x);
  };
  roots.forEach(note);
  while (stack.length) {
    const num = stack.pop();
    if (emitted.has(num)) continue;
    emitted.add(num);
    order.push(num);
    note(doc.getObject(num));
  }
  return order;
}

function pngUpPredict(rows, columns) {
  const out = new Uint8Array(rows.length * (columns + 1));
  let prev = new Uint8Array(columns);
  let o = 0;
  for (const row of rows) {
    out[o++] = 2;
    for (let i = 0; i < columns; i++) out[o++] = (row[i] - prev[i]) & 0xff;
    prev = row;
  }
  return out;
}

function idFor(seed) {
  const h = createHash('sha256').update(seed).digest();
  return [new PdfString(h.subarray(0, 16), true), new PdfString(new Uint8Array(h.subarray(0, 16)).map((b) => b ^ 0xff), true)];
}

export function writePdf(doc, opts = {}) {
  const rootRef = opts.root ?? doc.trailer.get('Root');
  const infoRef = opts.info ?? doc.trailer.get('Info') ?? null;
  const compressStreams = opts.compressStreams !== false;
  const useObjectStreams = opts.objectStreams !== false;
  const chunkSize = opts.chunkSize ?? 128;
  const version = opts.version ?? '1.6';

  const order = collectReachable(doc, infoRef ? [rootRef, infoRef] : [rootRef]);
  const map = new Map();
  order.forEach((num, i) => map.set(num, i + 1));

  const plain = [];
  const packable = [];
  for (const num of order) {
    const value = doc.getObject(num);
    const newNum = map.get(num);
    if (value instanceof Stream || !useObjectStreams) plain.push({ newNum, value });
    else packable.push({ newNum, value });
  }
  plain.sort((a, b) => a.newNum - b.newNum);
  packable.sort((a, b) => a.newNum - b.newNum);

  const out = new Out();
  out.push('%PDF-' + version + '\n');
  out.push('\x25\xe2\xe3\xcf\xd3\n');

  const xref = new Map();
  for (const item of plain) {
    xref.set(item.newNum, { type: 1, offset: out.offset });
    out.push(item.newNum + ' 0 obj\n');
    let body;
    if (item.value instanceof Stream) {
      let data = item.value.data;
      const dict = streamDict(item.value, data.length);
      if (compressStreams && !dict.has('Filter') && data.length > 64) {
        const packed = new Uint8Array(deflateSync(Buffer.from(data)));
        if (packed.length < data.length - 8) {
          dict.set('Filter', new Name('FlateDecode'));
          data = packed;
          dict.set('Length', data.length);
        }
      }
      body = emitValue(dict, map) + '\nstream\n';
      out.push(body).push(data).push('\nendstream');
    } else {
      out.push(emitValue(item.value, map));
    }
    out.push('\nendobj\n');
  }

  let nextNum = order.length + 1;
  const objStmNums = [];
  for (let i = 0; i < packable.length; i += chunkSize) {
    const group = packable.slice(i, i + chunkSize);
    const stmNum = nextNum++;
    let header = '';
    let body = '';
    group.forEach((item, idx) => {
      header += item.newNum + ' ' + body.length + ' ';
      body += emitValue(item.value, map) + '\n';
      xref.set(item.newNum, { type: 2, stm: stmNum, index: idx });
    });
    const headerBytes = ascii(header);
    const bodyBytes = ascii(body);
    const raw = new Uint8Array(headerBytes.length + bodyBytes.length);
    raw.set(headerBytes, 0);
    raw.set(bodyBytes, headerBytes.length);
    const packed = new Uint8Array(deflateSync(Buffer.from(raw)));
    const dict = new Dict();
    dict.set('Type', new Name('ObjStm'));
    dict.set('N', group.length);
    dict.set('First', headerBytes.length);
    dict.set('Filter', new Name('FlateDecode'));
    dict.set('Length', packed.length);
    xref.set(stmNum, { type: 1, offset: out.offset });
    out.push(stmNum + ' 0 obj\n');
    out.push(emitValue(dict, map)).push('\nstream\n').push(packed).push('\nendstream\nendobj\n');
    objStmNums.push(stmNum);
  }

  const id = opts.id ?? idFor(Buffer.concat([Buffer.from(out.bytes()), Buffer.from([order.length & 0xff])]));
  const xrefNum = nextNum++;
  const size = xrefNum + 1;
  const xrefOffset = out.offset;
  xref.set(xrefNum, { type: 1, offset: xrefOffset });

  const rows = [];
  for (let num = 0; num < size; num++) {
    const row = new Uint8Array(7);
    const e = num === 0 ? { type: 0, offset: 0, gen: 65535 } : xref.get(num);
    if (!e) { row[0] = 0; }
    else if (e.type === 1) {
      row[0] = 1;
      row[1] = (e.offset >>> 24) & 0xff; row[2] = (e.offset >>> 16) & 0xff;
      row[3] = (e.offset >>> 8) & 0xff; row[4] = e.offset & 0xff;
    } else if (e.type === 2) {
      row[0] = 2;
      row[1] = (e.stm >>> 24) & 0xff; row[2] = (e.stm >>> 16) & 0xff;
      row[3] = (e.stm >>> 8) & 0xff; row[4] = e.stm & 0xff;
      row[5] = (e.index >>> 8) & 0xff; row[6] = e.index & 0xff;
    } else {
      row[0] = 0;
      row[5] = (e.gen >> 8) & 0xff; row[6] = e.gen & 0xff;
    }
    rows.push(row);
  }
  const xrefData = new Uint8Array(deflateSync(Buffer.from(pngUpPredict(rows, 7))));
  const xrefDict = new Dict();
  xrefDict.set('Type', new Name('XRef'));
  xrefDict.set('Size', size);
  xrefDict.set('W', [1, 4, 2]);
  xrefDict.set('Root', rootRef);
  if (infoRef) xrefDict.set('Info', infoRef);
  xrefDict.set('ID', id);
  xrefDict.set('Filter', new Name('FlateDecode'));
  const parms = new Dict();
  parms.set('Predictor', 12);
  parms.set('Columns', 7);
  xrefDict.set('DecodeParms', parms);
  xrefDict.set('Length', xrefData.length);
  out.push(xrefNum + ' 0 obj\n');
  out.push(emitValue(xrefDict, map)).push('\nstream\n').push(xrefData).push('\nendstream\nendobj\n');
  out.push('startxref\n' + xrefOffset + '\n%%EOF\n');

  return { data: out.bytes(), stats: { objects: order.length, packed: packable.length, objectStreams: objStmNums.length, xrefOffset, size } };
}

export const writeDocument = writePdf;