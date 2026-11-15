// PDF object model — lossless enough to re-emit any input byte-for-byte where untouched.
import zlib from 'node:zlib';

export class Name {
  constructor(raw) { this.raw = raw; }              // raw = bytes as written, without leading '/'
  get text() { return decodeNameEscapes(this.raw); }
  toString() { return '/' + this.raw; }
}
export class Ref { constructor(num, gen) { this.num = num; this.gen = gen; } toString() { return this.num + ' ' + this.gen + ' R'; } }
export class PdfString {
  constructor(bytes, hex = false) { this.bytes = bytes; this.hex = hex; }
  get text() { return new TextDecoder('latin1').decode(this.bytes); }
  static fromText(s, hex = false) { return new PdfString(Uint8Array.from(s, c => c.charCodeAt(0) & 0xff), hex); }
  toString() {
    if (this.hex) return '<' + [...this.bytes].map(b => b.toString(16).padStart(2, '0')).join('') + '>';
    let out = '(';
    for (const b of this.bytes) {
      if (b === 0x28 || b === 0x29 || b === 0x5c) out += '\\' + String.fromCharCode(b);
      else if (b === 0x0d) out += '\\r';
      else if (b === 0x0a) out += '\\n';
      else out += String.fromCharCode(b);
    }
    return out + ')';
  }
}
const dictKey = (k) => (k instanceof Name ? k.raw : String(k).replace(/^\//, ''));

export class Dict extends Map {
  constructor(init) { super(); if (init) for (const [k, v] of Object.entries(init)) this.set(k, v); }
  get(k) { return super.get(dictKey(k)); }
  set(k, v) { super.set(dictKey(k), v); return this; }
  has(k) { return super.has(dictKey(k)); }
  del(k) { return super.delete(dictKey(k)); }
  name(k) { const v = super.get(dictKey(k)); return v instanceof Name ? v.text : undefined; }
}
export class Stream {
  constructor(dict, data) { this.dict = dict || new Dict(); this.data = data || new Uint8Array(); this.num = 0; this.gen = 0; }
}

export const isNum = v => typeof v === 'number';
export const isDict = v => v instanceof Dict;
export const isStream = v => v instanceof Stream;

export function decodeNameEscapes(raw) {
  return raw.replace(/#([0-9A-Fa-f]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)));
}
export function encodeName(text) {
  let out = '';
  for (const ch of text) {
    const c = ch.codePointAt(0);
    if (c < 0x21 || c > 0x7e || '#()<>[]{}/%'.includes(ch)) out += '#' + c.toString(16).padStart(2, '0').toUpperCase();
    else out += ch;
  }
  return out;
}

export function formatNumber(n) {
  if (!Number.isFinite(n)) return '0';
  if (Number.isInteger(n)) return String(n);
  const s = String(n);
  if (!/e/i.test(s)) return s;
  return n.toFixed(10).replace(/0+$/, '').replace(/\.$/, '');
}

export function serialize(v) {
  if (v === null || v === undefined) return 'null';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'number') return formatNumber(v);
  if (typeof v === 'string') return v;                     // already-serialized token
  if (v instanceof Name) return v.toString();
  if (v instanceof Ref) return v.toString();
  if (v instanceof PdfString) return v.toString();
  if (Array.isArray(v)) return '[' + v.map(serialize).join(' ') + ']';
  if (v instanceof Dict) return '<<' + [...v].map(([k, x]) => '/' + k + ' ' + serialize(x)).join(' ') + '>>';
  if (v instanceof Stream) return serialize(v.dict);
  throw new Error('cannot serialize ' + Object.prototype.toString.call(v));
}