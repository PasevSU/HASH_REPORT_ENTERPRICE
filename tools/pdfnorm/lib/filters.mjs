// Stream filters needed to read and verify real-world PDFs.
import zlib from 'node:zlib';
import { Name } from './objects.mjs';

export function inflate(data) { return new Uint8Array(zlib.inflateSync(Buffer.from(data))); }
export function deflate(data, level = 9) { return new Uint8Array(zlib.deflateSync(Buffer.from(data), { level })); }

export function asciiHexDecode(data) {
  const s = Buffer.from(data).toString('latin1').replace(/[^0-9A-Fa-f>]/g, '');
  const truncated = s.includes('>') ? s.slice(0, s.indexOf('>')) : s;
  const padded = truncated.length % 2 ? truncated + '0' : truncated;
  return new Uint8Array(Buffer.from(padded, 'hex'));
}
export function ascii85Decode(data) {
  const s = Buffer.from(data).toString('latin1').replace(/\s+/g, '');
  const body = s.replace(/^<~/, '');
  const end = body.indexOf('~>');
  const src = end >= 0 ? body.slice(0, end) : body;
  const out = [];
  let group = [];
  for (const ch of src) {
    if (ch === 'z' && group.length === 0) { out.push(0, 0, 0, 0); continue; }
    group.push(ch.charCodeAt(0) - 33);
    if (group.length === 5) { out.push(...b85group(group)); group = []; }
  }
  if (group.length) { const n = group.length; while (group.length < 5) group.push(84); out.push(...b85group(group).slice(0, n - 1)); }
  return new Uint8Array(out);
}
function b85group(g) {
  let v = 0;
  for (const d of g) v = v * 85 + d;
  return [(v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255];
}
export function lzwDecode(data, earlyChange = 1) {
  const out = [];
  let dict = [], codeLen = 9, next = 258, prev = null;
  for (let i = 0; i < 256; i++) dict[i] = [i];
  dict[256] = null; dict[257] = null;
  let bitBuf = 0, bitCnt = 0, pos = 0;
  const read = () => {
    while (bitCnt < codeLen) { if (pos >= data.length) return -1; bitBuf = (bitBuf << 8) | data[pos++]; bitCnt += 8; }
    const code = (bitBuf >> (bitCnt - codeLen)) & ((1 << codeLen) - 1);
    bitCnt -= codeLen; return code;
  };
  for (;;) {
    const code = read();
    if (code < 0) break;
    if (code === 256) { dict = []; for (let i = 0; i < 256; i++) dict[i] = [i]; dict[256] = null; dict[257] = null; codeLen = 9; next = 258; prev = null; continue; }
    if (code === 257) break;
    let entry;
    if (code < next && dict[code]) entry = dict[code];
    else if (prev) entry = [...prev, prev[0]];
    else break;
    out.push(...entry);
    if (prev && next < 4096) { dict[next++] = [...prev, entry[0]]; }
    prev = entry;
    if (next + earlyChange >= (1 << codeLen) && codeLen < 12) codeLen++;
  }
  return new Uint8Array(out);
}
export function runLengthDecode(data) {
  const out = [];
  for (let i = 0; i < data.length;) {
    const n = data[i++];
    if (n === 128) break;
    if (n < 128) { for (let j = 0; j <= n; j++) out.push(data[i++]); }
    else { const b = data[i++]; for (let j = 0; j < 257 - n; j++) out.push(b); }
  }
  return new Uint8Array(out);
}

const pget = (o, k) => (o && typeof o.get === 'function' ? o.get(k) : o?.[k]);

export function unpredict(data, parms) {
  const predictor = Number(pget(parms, 'Predictor') ?? 1);
  if (predictor <= 1) return data;
  const colors = Number(pget(parms, 'Colors') ?? 1);
  const bpc = Number(pget(parms, 'BitsPerComponent') ?? 8);
  const columns = Number(pget(parms, 'Columns') ?? 1);
  const bpp = Math.max(1, Math.ceil((colors * bpc) / 8));
  const rowBytes = Math.ceil((colors * bpc * columns) / 8);
  if (predictor === 2) {
    const out = Uint8Array.from(data);
    for (let r = 0; r + rowBytes <= out.length; r += rowBytes)
      for (let i = bpp; i < rowBytes; i++) out[r + i] = (out[r + i] + out[r + i - bpp]) & 255;
    return out;
  }
  const rows = Math.floor(data.length / (rowBytes + 1));
  const out = new Uint8Array(rows * rowBytes);
  let prev = new Uint8Array(rowBytes);
  for (let r = 0; r < rows; r++) {
    const type = data[r * (rowBytes + 1)];
    const row = data.subarray(r * (rowBytes + 1) + 1, (r + 1) * (rowBytes + 1));
    const cur = new Uint8Array(rowBytes);
    for (let i = 0; i < rowBytes; i++) {
      const left = i >= bpp ? cur[i - bpp] : 0, up = prev[i], ul = i >= bpp ? prev[i - bpp] : 0;
      let v = row[i];
      if (type === 1) v += left;
      else if (type === 2) v += up;
      else if (type === 3) v += (left + up) >> 1;
      else if (type === 4) {
        const p = left + up - ul, pa = Math.abs(p - left), pb = Math.abs(p - up), pc = Math.abs(p - ul);
        v += pa <= pb && pa <= pc ? left : pb <= pc ? up : ul;
      }
      cur[i] = v & 255;
    }
    out.set(cur, r * rowBytes);
    prev = cur;
  }
  return out;
}

/** Applies the /Filter chain. `getParms(i)` resolves a possibly-indirect /DecodeParms entry. */
export function decodeStream(stream, getParms = i => null) {
  const raw = stream.data instanceof Uint8Array ? stream.data : new Uint8Array(stream.data);
  const fl = stream.dict.get('Filter');
  if (!fl) return raw;
  const filters = Array.isArray(fl) ? fl : [fl];
  let data = raw;
  filters.forEach((f, i) => {
    const name = f instanceof Name ? f.text : String(f).replace(/^\//, '');
    let parms = getParms(i) || {};
    if (Array.isArray(parms)) parms = parms[i] || {};
    if (name === 'FlateDecode' || name === 'Fl') { data = unpredict(inflate(data), parms); return; }
    if (name === 'ASCIIHexDecode' || name === 'AHx') { data = asciiHexDecode(data); return; }
    if (name === 'ASCII85Decode' || name === 'A85') { data = ascii85Decode(data); return; }
    if (name === 'LZWDecode' || name === 'LZW') { data = lzwDecode(data, Number(pget(parms, 'EarlyChange') ?? 1)); return; }
    if (name === 'RunLengthDecode' || name === 'RL') { data = runLengthDecode(data); return; }
    throw new Error('unsupported filter: ' + name);
  });
  return data;
}