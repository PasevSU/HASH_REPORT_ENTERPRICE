// TrueType/OpenType (sfnt) parsing, metrics and subsetting - dependency free.

const tagOf = (buf, off) => String.fromCharCode(buf[off], buf[off + 1], buf[off + 2], buf[off + 3]);
const u8 = (b, o) => b[o];
const u16 = (b, o) => (b[o] << 8) | b[o + 1];
const i16 = (b, o) => { const v = (b[o] << 8) | b[o + 1]; return v & 0x8000 ? v - 0x10000 : v; };
const u32 = (b, o) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;

// Python's round() is round-half-to-even; PDF metrics were generated with it.
export const bankRound = (x) => {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
};

class Buf {
  constructor(size) { this.b = new Uint8Array(size); this.o = 0; }
  u8(v) { this.b[this.o++] = v & 0xff; return this; }
  u16(v) { this.b[this.o++] = (v >> 8) & 0xff; this.b[this.o++] = v & 0xff; return this; }
  i16(v) { return this.u16(v & 0xffff); }
  u32(v) { this.b[this.o++] = (v >>> 24) & 0xff; this.b[this.o++] = (v >>> 16) & 0xff; this.b[this.o++] = (v >>> 8) & 0xff; this.b[this.o++] = v & 0xff; return this; }
  bytes(src) { this.b.set(src, this.o); this.o += src.length; return this; }
  get length() { return this.o; }
}

const KEEP_TABLES = new Set(['head', 'hhea', 'maxp', 'hmtx', 'loca', 'glyf', 'cmap', 'name', 'OS/2', 'post', 'cvt ', 'fpgm', 'prep', 'gasp']);

export class TrueTypeFont {
  constructor(buf) {
    this.buf = buf;
    this.tables = new Map();
    const numTables = u16(buf, 4);
    for (let i = 0; i < numTables; i++) {
      const rec = 12 + i * 16;
      const tag = tagOf(buf, rec);
      this.tables.set(tag, { offset: u32(buf, rec + 8), length: u32(buf, rec + 12) });
    }
    const head = this.table('head');
    if (!head) throw new Error('not an sfnt font: missing head');
    this.headOffset = head.offset;
    this.unitsPerEm = u16(buf, head.offset + 18);
    this.bbox = [i16(buf, head.offset + 36), i16(buf, head.offset + 38), i16(buf, head.offset + 40), i16(buf, head.offset + 42)];
    this.indexToLocFormat = i16(buf, head.offset + 50);
    const hhea = this.table('hhea');
    this.ascent = hhea ? i16(buf, hhea.offset + 4) : this.bbox[3];
    this.descent = hhea ? i16(buf, hhea.offset + 6) : this.bbox[1];
    this.numberOfHMetrics = hhea ? u16(buf, hhea.offset + 34) : 0;
    const maxp = this.table('maxp');
    this.numGlyphs = maxp ? u16(buf, maxp.offset + 4) : 0;
    const os2 = this.table('OS/2');
    this.capHeight = os2 && os2.length >= 90 ? i16(buf, os2.offset + 88) : 0;
    if (!this.capHeight) this.capHeight = this.ascent;
    this._loca = null;
    this._cmap = null;
  }

  static load(buf) { return new TrueTypeFont(buf instanceof Uint8Array ? buf : new Uint8Array(buf)); }

  table(tag) { return this.tables.get(tag) || null; }

  loca() {
    if (this._loca) return this._loca;
    const loca = this.table('loca');
    if (!loca) throw new Error('missing loca');
    const n = this.numGlyphs + 1;
    const out = new Uint32Array(n);
    const long = this.indexToLocFormat === 1;
    for (let i = 0; i < n; i++) {
      out[i] = long ? u32(this.buf, loca.offset + i * 4) : u16(this.buf, loca.offset + i * 2) * 2;
    }
    this._loca = out;
    return out;
  }

  glyphData(gid) {
    if (gid < 0 || gid >= this.numGlyphs) return new Uint8Array(0);
    const loca = this.loca();
    const glyf = this.table('glyf');
    if (!glyf) return new Uint8Array(0);
    const start = loca[gid], end = loca[gid + 1];
    if (end <= start) return new Uint8Array(0);
    return this.buf.subarray(glyf.offset + start, glyf.offset + end);
  }

  advance(gid) {
    if (gid < 0) return 0;
    const hmtx = this.table('hmtx');
    if (!hmtx) return 0;
    const n = this.numberOfHMetrics;
    const idx = gid < n ? gid : Math.max(0, n - 1);
    return u16(this.buf, hmtx.offset + idx * 4);
  }

  lsb(gid) {
    const hmtx = this.table('hmtx');
    if (!hmtx) return 0;
    const n = this.numberOfHMetrics;
    if (gid < n) return i16(this.buf, hmtx.offset + gid * 4 + 2);
    const off = hmtx.offset + n * 4 + (gid - n) * 2;
    return off + 1 < hmtx.offset + hmtx.length ? i16(this.buf, off) : 0;
  }

  cmap() {
    if (this._cmap) return this._cmap;
    const map = new Map();
    const tbl = this.table('cmap');
    if (tbl) {
      const count = u16(this.buf, tbl.offset + 2);
      let best = null;
      for (let i = 0; i < count; i++) {
        const rec = tbl.offset + 4 + i * 8;
        const platform = u16(this.buf, rec), encoding = u16(this.buf, rec + 2);
        const sub = tbl.offset + u32(this.buf, rec + 4);
        const score = (platform === 3 && encoding === 10) ? 4 : (platform === 3 && encoding === 1) ? 3
          : (platform === 0) ? 2 : (platform === 3 && encoding === 0) ? 1 : 0;
        if (score && (!best || score > best.score)) best = { score, sub };
      }
      if (best) this.readCmapSubtable(best.sub, map);
    }
    this._cmap = map;
    return map;
  }

  readCmapSubtable(off, map) {
    const b = this.buf;
    const format = u16(b, off);
    if (format === 4) {
      const segX2 = u16(b, off + 6);
      const seg = segX2 / 2;
      const endBase = off + 14;
      const startBase = endBase + segX2 + 2;
      const deltaBase = startBase + segX2;
      const rangeBase = deltaBase + segX2;
      for (let s = 0; s < seg; s++) {
        const end = u16(b, endBase + s * 2);
        const start = u16(b, startBase + s * 2);
        const delta = u16(b, deltaBase + s * 2);
        const ro = u16(b, rangeBase + s * 2);
        for (let c = start; c <= end && c !== 0xffff; c++) {
          let gid;
          if (ro === 0) gid = (c + delta) & 0xffff;
          else {
            const gi = rangeBase + s * 2 + ro + (c - start) * 2;
            gid = u16(b, gi);
            if (gid) gid = (gid + delta) & 0xffff;
          }
          if (gid && !map.has(c)) map.set(c, gid);
        }
      }
    } else if (format === 12) {
      const groups = u32(b, off + 12);
      for (let g = 0; g < groups; g++) {
        const rec = off + 16 + g * 12;
        const start = u32(b, rec), end = u32(b, rec + 4), startGid = u32(b, rec + 8);
        for (let c = start; c <= end; c++) if (!map.has(c)) map.set(c, startGid + (c - start));
      }
    } else if (format === 6) {
      const first = u16(b, off + 6), n = u16(b, off + 8);
      for (let i = 0; i < n; i++) map.set(first + i, u16(b, off + 10 + i * 2));
    } else if (format === 0) {
      for (let c = 0; c < 256; c++) map.set(c, b[off + 6 + c]);
    }
  }

  components(gid) {
    const data = this.glyphData(gid);
    if (data.length < 10 || i16(data, 0) >= 0) return [];
    const out = [];
    let o = 10;
    for (;;) {
      if (o + 4 > data.length) break;
      const flags = u16(data, o);
      const comp = u16(data, o + 2);
      out.push(comp);
      o += 4;
      o += (flags & 0x0001) ? 4 : 2;
      if (flags & 0x0008) o += 2;
      else if (flags & 0x0040) o += 4;
      else if (flags & 0x0080) o += 8;
      if (!(flags & 0x0020)) break;
    }
    return out;
  }
}

export function descriptorMetrics(font) {
  const s = (v) => bankRound(v * 1000 / font.unitsPerEm);
  return {
    bbox: font.bbox.map(s),
    ascent: s(font.ascent),
    descent: s(font.descent),
    capHeight: s(font.capHeight || font.ascent),
    italicAngle: 0,
  };
}

export function widthsForCodes(font, first, last) {
  const cmap = font.cmap();
  const out = [];
  for (let code = first; code <= last; code++) {
    const gid = cmap.get(code);
    const adv = gid ? font.advance(gid) : 0;
    out.push(bankRound(adv * 1000 / font.unitsPerEm));
  }
  return out;
}

const pad4 = (n) => (n + 3) & ~3;

function checksum(buf, off, len) {
  let s = 0;
  for (let i = 0; i < len; i += 4) {
    const a = buf[off + i] || 0, b = buf[off + i + 1] || 0, c = buf[off + i + 2] || 0, d = buf[off + i + 3] || 0;
    s = (s + (((a << 24) | (b << 16) | (c << 8) | d) >>> 0)) >>> 0;
  }
  return s >>> 0;
}

function rewriteComposite(data, mapGid) {
  const out = new Uint8Array(data);
  let o = 10;
  for (;;) {
    if (o + 4 > out.length) break;
    const flags = (out[o] << 8) | out[o + 1];
    const comp = (out[o + 2] << 8) | out[o + 3];
    const mapped = mapGid(comp);
    out[o + 2] = (mapped >> 8) & 0xff;
    out[o + 3] = mapped & 0xff;
    o += 4;
    o += (flags & 0x0001) ? 4 : 2;
    if (flags & 0x0008) o += 2;
    else if (flags & 0x0040) o += 4;
    else if (flags & 0x0080) o += 8;
    if (!(flags & 0x0020)) break;
  }
  return out;
}

function buildCmap(pairs) {
  if (!pairs.length) return null;
  const entries = [...pairs].sort((a, b) => a[0] - b[0]);
  const segs = entries.map(([code, gid]) => ({ end: code, start: code, delta: (gid - code) & 0xffff }));
  segs.push({ end: 0xffff, start: 0xffff, delta: 1 });
  const segCount = segs.length;
  const length = 16 + segCount * 8;
  const w = new Buf(length);
  w.u16(4).u16(length).u16(0);
  let pow = 1, sel = 0;
  while (pow * 2 <= segCount) { pow *= 2; sel++; }
  w.u16(segCount * 2).u16(pow * 2).u16(sel).u16(segCount * 2 - pow * 2);
  for (const s of segs) w.u16(s.end);
  w.u16(0);
  for (const s of segs) w.u16(s.start);
  for (const s of segs) w.u16(s.delta);
  for (let i = 0; i < segCount; i++) w.u16(0);
  // cmap header: version 0, one subtable (3,1) format 4
  const head = new Buf(12);
  head.u16(0).u16(1).u16(3).u16(1).u32(12);
  const out = new Uint8Array(12 + length);
  out.set(head.b, 0);
  out.set(w.b, 12);
  return out;
}

export function subsetFont(font, { unicodes = null, gids = null, retainGids = false } = {}) {
  const cmap = font.cmap();
  const keep = new Set([0]);
  const codePairs = new Map();
  if (unicodes) {
    for (const code of unicodes) {
      const gid = cmap.get(code);
      if (gid === undefined) continue;
      keep.add(gid);
      codePairs.set(code, gid);
    }
  }
  if (gids) for (const g of gids) if (g >= 0 && g < font.numGlyphs) keep.add(g);

  const queue = [...keep];
  while (queue.length) {
    const gid = queue.pop();
    for (const comp of font.components(gid)) if (!keep.has(comp) && comp < font.numGlyphs) { keep.add(comp); queue.push(comp); }
  }

  const order = [...keep].sort((a, b) => a - b);
  const newGidOf = new Map();
  if (retainGids) order.forEach((g) => newGidOf.set(g, g));
  else order.forEach((g, i) => newGidOf.set(g, i));

  const numGlyphs = retainGids ? font.numGlyphs : order.length;

  const glyfParts = [];
  const locaOffsets = new Uint32Array(numGlyphs + 1);
  let cursor = 0;
  for (let gid = 0; gid < numGlyphs; gid++) {
    locaOffsets[gid] = cursor;
    const srcGid = retainGids ? gid : order[gid];
    if (keep.has(srcGid)) {
      let data = font.glyphData(srcGid);
      if (data.length) {
        if (i16(data, 0) < 0) data = rewriteComposite(data, (c) => newGidOf.get(c) ?? 0);
        const padded = new Uint8Array(pad4(data.length));
        padded.set(data, 0);
        glyfParts.push(padded);
        cursor += padded.length;
      }
    }
  }
  locaOffsets[numGlyphs] = cursor;

  const glyf = new Uint8Array(cursor);
  let go = 0;
  for (const p of glyfParts) { glyf.set(p, go); go += p.length; }

  const w = new Buf((numGlyphs + 1) * 4);
  for (let i = 0; i <= numGlyphs; i++) w.u32(locaOffsets[i]);
  const loca = w.b;

  const h = new Buf(numGlyphs * 4);
  for (let gid = 0; gid < numGlyphs; gid++) {
    const src = retainGids ? gid : order[gid];
    h.u16(font.advance(src));
    h.i16(keep.has(src) ? font.lsb(src) : 0);
  }
  const hmtx = h.b;

  const headSrc = font.table('head');
  const head = new Uint8Array(font.buf.subarray(headSrc.offset, headSrc.offset + headSrc.length));
  head[8] = head[9] = head[10] = head[11] = 0;
  head[50] = 0; head[51] = 1;

  const hheaSrc = font.table('hhea');
  const hhea = new Uint8Array(font.buf.subarray(hheaSrc.offset, hheaSrc.offset + hheaSrc.length));
  hhea[34] = (numGlyphs >> 8) & 0xff; hhea[35] = numGlyphs & 0xff;

  const maxpSrc = font.table('maxp');
  const maxp = new Uint8Array(font.buf.subarray(maxpSrc.offset, maxpSrc.offset + maxpSrc.length));
  maxp[4] = (numGlyphs >> 8) & 0xff; maxp[5] = numGlyphs & 0xff;

  const post = new Uint8Array(32);
  post[1] = 3;

  const tables = new Map();
  tables.set('head', head);
  tables.set('hhea', hhea);
  tables.set('maxp', maxp);
  tables.set('hmtx', hmtx);
  tables.set('loca', loca);
  tables.set('glyf', glyf);
  tables.set('post', post);
  const pairs = [];
  for (const [code, gid] of codePairs) { const ng = newGidOf.get(gid); if (ng !== undefined) pairs.push([code, ng]); }
  const cm = buildCmap(pairs);
  if (cm) tables.set('cmap', cm);
  for (const tag of ['name', 'OS/2', 'cvt ', 'fpgm', 'prep', 'gasp']) {
    const t = font.table(tag);
    if (t && KEEP_TABLES.has(tag)) tables.set(tag, new Uint8Array(font.buf.subarray(t.offset, t.offset + t.length)));
  }

  const tags = [...tables.keys()].sort();
  const numTables = tags.length;
  let pow = 1, sel = 0;
  while (pow * 2 <= numTables) { pow *= 2; sel++; }
  const headerSize = 12 + numTables * 16;
  let total = headerSize;
  const offsets = new Map();
  for (const tag of tags) {
    offsets.set(tag, total);
    total += pad4(tables.get(tag).length);
  }
  const out = new Uint8Array(total);
  const hdr = new Buf(12);
  hdr.u32(0x00010000).u16(numTables).u16(pow * 16).u16(sel).u16(numTables * 16 - pow * 16);
  out.set(hdr.b, 0);
  tags.forEach((tag, i) => {
    const rec = 12 + i * 16;
    const data = tables.get(tag);
    for (let k = 0; k < 4; k++) out[rec + k] = tag.charCodeAt(k) || 0x20;
    const dv = new DataView(out.buffer);
    dv.setUint32(rec + 4, checksum(data, 0, data.length), false);
    dv.setUint32(rec + 8, offsets.get(tag), false);
    dv.setUint32(rec + 12, data.length, false);
    out.set(data, offsets.get(tag));
  });
  const headAt = offsets.get('head');
  const dv = new DataView(out.buffer);
  dv.setUint32(headAt + 8, 0, false);
  const adj = (0xb1b0afba - checksum(out, 0, out.length)) >>> 0;
  dv.setUint32(headAt + 8, adj, false);

  return { data: out, font: TrueTypeFont.load(out), numGlyphs, glyphOrder: retainGids ? null : order, gidMap: newGidOf };
}