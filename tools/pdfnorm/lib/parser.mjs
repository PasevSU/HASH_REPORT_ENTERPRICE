// Tokenizer + object parser + cross-reference reader (classic tables, xref streams, object streams).
import { Name, Dict, Ref, PdfString, Stream, encodeName } from './objects.mjs';
import { decodeStream } from './filters.mjs';

const WS = new Set([0x00, 0x09, 0x0a, 0x0c, 0x0d, 0x20]);
const DELIM = new Set([0x28, 0x29, 0x3c, 0x3e, 0x5b, 0x5d, 0x7b, 0x7d, 0x2f, 0x25]);

export class Lexer {
  constructor(buf, pos = 0) { this.buf = buf; this.pos = pos; }
  skipSpace() {
    const b = this.buf;
    while (this.pos < b.length) {
      const c = b[this.pos];
      if (WS.has(c)) { this.pos++; continue; }
      if (c === 0x25) { while (this.pos < b.length && b[this.pos] !== 0x0a && b[this.pos] !== 0x0d) this.pos++; continue; }
      break;
    }
  }
  peekKeyword(kw) {
    const s = Buffer.from(this.buf.subarray(this.pos, this.pos + kw.length)).toString('latin1');
    if (s !== kw) return false;
    const after = this.buf[this.pos + kw.length];
    return after === undefined || WS.has(after) || DELIM.has(after);
  }
  readToken() {
    this.skipSpace();
    const b = this.buf, start = this.pos;
    while (this.pos < b.length && !WS.has(b[this.pos]) && !DELIM.has(b[this.pos])) this.pos++;
    return Buffer.from(b.subarray(start, this.pos)).toString('latin1');
  }
  readName() {
    this.pos++; // '/'
    const b = this.buf, start = this.pos;
    while (this.pos < b.length && !WS.has(b[this.pos]) && !DELIM.has(b[this.pos])) this.pos++;
    let raw = Buffer.from(b.subarray(start, this.pos)).toString('latin1');
    if (raw.includes('#')) raw = raw.replace(/#([0-9A-Fa-f]{2})/g, (m) => m.toUpperCase());
    return new Name(raw);
  }
  readLiteralString() {
    const b = this.buf; this.pos++; // '('
    const out = []; let depth = 1;
    while (this.pos < b.length) {
      let c = b[this.pos++];
      if (c === 0x5c) {
        const n = b[this.pos++];
        const map = { 0x6e: 0x0a, 0x72: 0x0d, 0x74: 0x09, 0x62: 0x08, 0x66: 0x0c };
        if (n in map) out.push(map[n]);
        else if (n >= 0x30 && n <= 0x37) {
          let v = n - 0x30, k = 0;
          while (k < 2 && b[this.pos] >= 0x30 && b[this.pos] <= 0x37) { v = v * 8 + (b[this.pos++] - 0x30); k++; }
          out.push(v & 255);
        } else if (n === 0x0d) { if (b[this.pos] === 0x0a) this.pos++; }
        else if (n === 0x0a) { /* line continuation */ }
        else out.push(n);
        continue;
      }
      if (c === 0x28) { depth++; out.push(c); continue; }
      if (c === 0x29) { depth--; if (depth === 0) break; out.push(c); continue; }
      out.push(c);
    }
    return new PdfString(new Uint8Array(out), false);
  }
  readHexString() {
    const b = this.buf; this.pos++; // '<' (caller guarantees not '<<')
    const out = [];
    let hi = -1;
    while (this.pos < b.length) {
      const c = b[this.pos++];
      if (c === 0x3e) break;
      const v = hexVal(c);
      if (v < 0) continue;
      if (hi < 0) hi = v; else { out.push((hi << 4) | v); hi = -1; }
    }
    if (hi >= 0) out.push(hi << 4);
    return new PdfString(new Uint8Array(out), true);
  }
}

const hexVal = c => (c >= 0x30 && c <= 0x39) ? c - 0x30 : (c >= 0x41 && c <= 0x46) ? c - 55 : (c >= 0x61 && c <= 0x66) ? c - 87 : -1;
const isNumberToken = t => /^[+-]?(\d+\.?\d*|\.\d+)$/.test(t);

export class Parser {
  constructor(buf, doc = null) { this.buf = buf; this.doc = doc; this.lex = new Lexer(buf); }

  /** Parses one object. `allowRefs` enables the "num gen R" lookahead used inside objects. */
  parse(allowRefs = true) {
    this.lex.skipSpace();
    const b = this.buf, c = b[this.lex.pos];
    if (c === 0x2f) return this.lex.readName();
    if (c === 0x28) return this.lex.readLiteralString();
    if (c === 0x3c) {
      if (b[this.lex.pos + 1] === 0x3c) return this.parseDict();
      return this.lex.readHexString();
    }
    if (c === 0x5b) {
      this.lex.pos++;
      const arr = [];
      for (;;) {
        this.lex.skipSpace();
        if (b[this.lex.pos] === 0x5d) { this.lex.pos++; break; }
        if (this.lex.pos >= b.length) break;
        arr.push(this.parse(allowRefs));
      }
      return arr;
    }
    const tok = this.lex.readToken();
    if (tok === 'true') return true;
    if (tok === 'false') return false;
    if (tok === 'null') return null;
    if (isNumberToken(tok)) {
      const num = Number(tok);
      if (allowRefs && Number.isInteger(num) && num >= 0) {
        const save = this.lex.pos;
        this.lex.skipSpace();
        const genTok = this.lex.readToken();
        if (/^\d+$/.test(genTok)) {
          this.lex.skipSpace();
          const r = this.lex.readToken();
          if (r === 'R') return new Ref(num, Number(genTok));
        }
        this.lex.pos = save;
      }
      return num;
    }
    return { keyword: tok };
  }

  parseDict() {
    this.lex.pos += 2; // '<<'
    const d = new Dict();
    for (;;) {
      this.lex.skipSpace();
      if (this.buf[this.lex.pos] === 0x3e && this.buf[this.lex.pos + 1] === 0x3e) { this.lex.pos += 2; break; }
      if (this.lex.pos >= this.buf.length) break;
      const k = this.parse(false);
      if (!(k instanceof Name)) break;
      this.lex.skipSpace();
      if (this.buf[this.lex.pos] === 0x3e && this.buf[this.lex.pos + 1] === 0x3e) { d.set(k.raw, null); break; }
      d.set(k.raw, this.parse(true));
    }
    return d;
  }

  /** Parses "N G obj ... endobj" at `offset`, returning {num, gen, value}. */
  parseIndirectAt(offset) {
    this.lex.pos = offset;
    const num = Number(this.lex.readToken());
    const gen = Number(this.lex.readToken());
    const kw = this.lex.readToken();
    if (kw !== 'obj') throw new Error(`expected obj at ${offset} (got "${kw}")`);
    const value = this.parse(true);
    if (value instanceof Dict) {
      this.lex.skipSpace();
      if (this.lex.peekKeyword('stream')) {
        const start = this.streamDataStart();
        const data = this.extractStreamData(start, value);
        return { num, gen, value: new Stream(value, data) };
      }
    }
    return { num, gen, value };
  }

  streamDataStart() {
    const b = this.buf;
    let p = this.lex.pos + 6; // 'stream'
    if (b[p] === 0x0d) p++;
    if (b[p] === 0x0a) p++;
    return p;
  }

  extractStreamData(start, dict) {
    let len = dict.get('Length');
    if (len instanceof Ref && this.doc) len = this.doc.resolve(len);
    if (typeof len === 'number' && len >= 0 && start + len <= this.buf.length) {
      const tail = Buffer.from(this.buf.subarray(start + Math.max(0, len), start + len + 20)).toString('latin1');
      if (/^\s*endstream/.test(tail)) return this.buf.subarray(start, start + len);
    }
    const idx = Buffer.from(this.buf.subarray(start)).indexOf('endstream');
    if (idx < 0) throw new Error('unterminated stream');
    let end = start + idx;
    if (this.buf[end - 1] === 0x0a) end--;
    if (this.buf[end - 1] === 0x0d) end--;
    return this.buf.subarray(start, end);
  }
}

export class PdfDocument {
  constructor(buf) { this.buf = buf; this.parser = new Parser(buf, this); this.entries = new Map(); this.cache = new Map(); this.objStmCache = new Map(); this.trailer = new Dict(); this.maxGen = new Map(); this.extra = new Map(); this.nextNum = 0; }

  static load(buf) { const d = new PdfDocument(buf); d.readXref(); return d; }

  readXref() {
    const tail = Buffer.from(this.buf.subarray(Math.max(0, this.buf.length - 4096))).toString('latin1');
    const at = tail.lastIndexOf('startxref');
    if (at < 0) throw new Error('no startxref');
    const m = tail.slice(at + 9).match(/\d+/);
    let offset = Number(m[0]);
    const seen = new Set();
    while (offset != null && !seen.has(offset)) {
      seen.add(offset);
      offset = this.readXrefSection(offset);
    }
    if (this.trailer.has('Encrypt') ) throw new Error('encrypted PDFs are not supported');
  }

  readXrefSection(offset) {
    const lex = new Lexer(this.buf, offset);
    lex.skipSpace();
    if (lex.peekKeyword('xref')) return this.readXrefTable(lex);
    const { value } = this.parser.parseIndirectAt(offset);
    if (!(value instanceof Stream)) throw new Error('xref section is neither table nor stream');
    for (const [k, v] of value.dict) if (!this.trailer.has(k)) this.trailer.set(k, v);
    this.readXrefStream(value);
    const xs = value.dict.get('XRefStm');
    if (xs != null) this.readXrefSection(Number(xs));
    return value.dict.get('Prev');
  }

  readXrefTable(lex) {
    lex.pos += 4; // 'xref'
    for (;;) {
      lex.skipSpace();
      if (lex.peekKeyword('trailer')) break;
      const start = Number(lex.readToken());
      const count = Number(lex.readToken());
      if (!Number.isFinite(start) || !Number.isFinite(count)) break;
      for (let i = 0; i < count; i++) {
        const off = Number(lex.readToken());
        const gen = Number(lex.readToken());
        const kind = lex.readToken();
        const num = start + i;
        if (kind === 'n' && off > 0 && !this.entries.has(num)) this.entries.set(num, { type: 1, offset: off, gen });
        else if (kind === 'f' && !this.entries.has(num)) this.entries.set(num, { type: 0, gen });
      }
    }
    lex.skipSpace();
    if (lex.peekKeyword('trailer')) lex.pos += 7;
    this.parser.lex.pos = lex.pos;
    this.parser.lex.skipSpace();
    const trailer = this.parser.parseDict();
    lex.pos = this.parser.lex.pos;
    for (const [k, v] of trailer) if (!this.trailer.has(k)) this.trailer.set(k, v);
    return trailer.get('Prev');
  }

  readXrefStream(stream) {
    const d = stream.dict;
    const w = d.get('W').map(Number);
    const size = Number(d.get('Size'));
    const index = d.get('Index') ? d.get('Index').map(Number) : [0, size];
    const parms = d.get('DecodeParms');
    const data = decodeStream(stream, () => (parms instanceof Ref ? this.resolve(parms) : parms));
    const rowLen = w.reduce((a, b) => a + b, 0);
    let p = 0;
    for (let s = 0; s < index.length; s += 2) {
      const start = index[s], count = index[s + 1];
      for (let i = 0; i < count; i++) {
        if (p + rowLen > data.length) break;
        const fields = [];
        for (const width of w) {
          let v = 0;
          for (let k = 0; k < width; k++) v = v * 256 + data[p++];
          fields.push(v);
        }
        const type = w[0] === 0 ? 1 : fields[0];
        const num = start + i;
        if (this.entries.has(num)) continue;
        if (type === 1) this.entries.set(num, { type: 1, offset: fields[1], gen: fields[2] ?? 0 });
        else if (type === 2) this.entries.set(num, { type: 2, stm: fields[1], idx: fields[2] });
        else this.entries.set(num, { type: 0, gen: 0 });
      }
    }
  }

  loadObjectStream(stmNum) {
    if (this.objStmCache.has(stmNum)) return this.objStmCache.get(stmNum);
    const stm = this.getObject(stmNum);
    const n = Number(this.resolve(stm.dict.get('N')));
    const first = Number(this.resolve(stm.dict.get('First')));
    const parms = stm.dict.get('DecodeParms');
    const data = decodeStream(stm, () => (parms instanceof Ref ? this.resolve(parms) : parms));
    const lex = new Lexer(data, 0);
    const pairs = [];
    for (let i = 0; i < n; i++) pairs.push([Number(lex.readToken()), Number(lex.readToken())]);
    const map = new Map();
    pairs.forEach(([num, off], i) => {
      const p = new Parser(data, this);
      p.lex.pos = first + off;
      map.set(num, p.parse(true));
    });
    this.objStmCache.set(stmNum, map);
    return map;
  }

  addObject(value) {
    if (!this.nextNum) this.nextNum = this.highestObjectNumber();
    const num = ++this.nextNum;
    this.extra.set(num, value);
    return new Ref(num, 0);
  }

  highestObjectNumber() {
    let max = 0;
    for (const num of this.entries.keys()) if (num > max) max = num;
    for (const num of this.extra.keys()) if (num > max) max = num;
    return max;
  }

  getObject(num) {
    if (this.extra.has(num)) return this.extra.get(num);
    if (this.cache.has(num)) return this.cache.get(num);
    const e = this.entries.get(num);
    if (!e) return null;
    let value = null;
    if (e.type === 1) value = this.parser.parseIndirectAt(e.offset).value;
    else if (e.type === 2) { const stm = this.loadObjectStream(e.stm); value = stm.has(num) ? stm.get(num) : null; }
    if (value instanceof Stream) { value.num = num; value.gen = e.gen || 0; }
    this.cache.set(num, value);
    return value;
  }

  resolve(v) {
    let guard = 0;
    while (v instanceof Ref && guard++ < 64) v = this.getObject(v.num);
    return v;
  }

  get root() { return this.resolve(this.trailer.get('Root')); }
  get pages() {
    const out = [];
    const walk = node => {
      const n = this.resolve(node);
      if (!n) return;
      const type = n.name('Type');
      if (type === 'Pages' || !type) for (const kid of this.resolve(n.get('Kids')) || []) walk(kid);
      else if (type === 'Page') out.push(n);
    };
    walk(this.root?.get('Pages'));
    return out;
  }
}