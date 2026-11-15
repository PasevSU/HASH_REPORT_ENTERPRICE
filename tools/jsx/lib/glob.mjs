// fnmatch-compatible glob matcher (Python fnmatch.fnmatchcase semantics).
const RE_SPECIAL = /[\\^$.*+?()[\]{}|]/;

export function translate(pattern) {
  const pat = String(pattern);
  let out = '';
  let i = 0;
  const n = pat.length;
  while (i < n) {
    const c = pat[i];
    i += 1;
    if (c === '*') {
      out += '[\\s\\S]*';
    } else if (c === '?') {
      out += '[\\s\\S]';
    } else if (c === '[') {
      let j = i;
      if (j < n && pat[j] === '!') j += 1;
      if (j < n && pat[j] === ']') j += 1;
      while (j < n && pat[j] !== ']') j += 1;
      if (j >= n) {
        out += '\\[';
      } else {
        let stuff = pat.slice(i, j);
        if (stuff.startsWith('!')) stuff = '^' + stuff.slice(1);
        else if (stuff.startsWith('^')) stuff = '\\' + stuff;
        out += '[' + stuff.replace(/\\/g, '\\\\') + ']';
        i = j + 1;
      }
    } else {
      out += RE_SPECIAL.test(c) ? '\\' + c : c;
    }
  }
  return new RegExp('^(?:' + out + ')$', 'su');
}

const cache = new Map();

export function fnmatchcase(name, pattern) {
  const pat = String(pattern);
  const key = pat;
  let re = cache.get(key);
  if (!re) {
    re = translate(pat);
    if (cache.size > 4096) cache.clear();
    cache.set(key, re);
  }
  return re.test(String(name));
}

export const fnmatch = fnmatchcase;