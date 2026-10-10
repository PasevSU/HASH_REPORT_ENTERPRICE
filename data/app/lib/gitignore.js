'use strict';
// gitignore — structured authoring for .gitignore files.
//
// Pure module (no I/O): the UI collects a structured model, this module serializes it into
// .gitignore content and parses existing content back into the same model. It is deliberately
// deterministic so it can be unit-tested. Unknown/comment lines are preserved in `custom`.

const PRESETS = {
  dependencies: {
    labelEn: 'Dependencies',
    label: { bg: 'Зависимости', de: 'Abhängigkeiten' },
    entries: ['node_modules/', 'vendor/', '__pycache__/', '*.pyc', '.venv/', 'venv/']
  },
  build: {
    labelEn: 'Build artifacts',
    label: { bg: 'Артефакти от компилация', de: 'Build-Artefakte' },
    entries: ['dist/', 'build/', 'out/', 'target/', '*.o', '*.exe']
  },
  secrets: {
    labelEn: 'Secrets & local config',
    label: { bg: 'Тайни и локална конфигурация', de: 'Geheimnisse & lokale Konfiguration' },
    entries: ['.env', '.env.local', '*.key', '*.pem', 'secrets.yml']
  },
  ide: {
    labelEn: 'IDE / editor',
    label: { bg: 'IDE / редактор', de: 'IDE / Editor' },
    entries: ['.vscode/', '.idea/', '*.swp', '*.sublime-project']
  },
  os: {
    labelEn: 'Operating system',
    label: { bg: 'Операционна система', de: 'Betriebssystem' },
    entries: ['.DS_Store', 'Thumbs.db', 'desktop.ini']
  },
  logs: {
    labelEn: 'Logs / cache / temp',
    label: { bg: 'Логове / кеш / временни', de: 'Logs / Cache / Temporär' },
    entries: ['*.log', '.cache/', 'tmp/', '*.bak']
  }
};

// Category metadata: the field name in the model, a stable English section header and
// bilingual UI labels used by the editor.
const CATEGORIES = [
  {
    key: 'files',
    titleEn: 'Specific files',
    label: { bg: 'Конкретни файлове', de: 'Bestimmte Dateien' },
    placeholder: { bg: 'secret.txt, config.local.json', de: 'secret.txt, config.local.json' }
  },
  {
    key: 'patterns',
    titleEn: 'Wildcard patterns',
    label: { bg: 'Шаблони с wildcard', de: 'Wildcard-Muster' },
    placeholder: { bg: '*.log, *.tmp, temp*', de: '*.log, *.tmp, temp*' }
  },
  {
    key: 'dirs',
    titleEn: 'Whole directories',
    label: { bg: 'Цели директории', de: 'Ganze Verzeichnisse' },
    placeholder: { bg: 'node_modules/, dist/, build/', de: 'node_modules/, dist/, build/' }
  },
  {
    key: 'subdirs',
    titleEn: 'In all subdirectories',
    label: { bg: 'Във всички поддиректории', de: 'In allen Unterverzeichnissen' },
    placeholder: { bg: '**/logs, **/*.pdf', de: '**/logs, **/*.pdf' }
  },
  {
    key: 'exceptions',
    titleEn: 'Exceptions (negation)',
    label: { bg: 'Изключения (negation)', de: 'Ausnahmen (Negation)' },
    placeholder: { bg: '!important.log', de: '!important.log' }
  },
  {
    key: 'rootOnly',
    titleEn: 'Only in root',
    label: { bg: 'Само в корена', de: 'Nur im Stammverzeichnis' },
    placeholder: { bg: '/TODO.txt', de: '/TODO.txt' }
  }
];

const GLOBAL_HINT = {
  labelEn: 'Global ignore',
  label: { bg: 'Глобален ignore', de: 'Globaler ignore' },
  command: 'git config --global core.excludesfile ~/.gitignore_global'
};

// A model has exactly these fields.
function emptyModel() {
  return {
    files: [],
    patterns: [],
    dirs: [],
    subdirs: [],
    exceptions: [],
    rootOnly: [],
    presets: [],
    custom: []
  };
}

function normalizeModel(input) {
  const base = emptyModel();
  const src = input && typeof input === 'object' ? input : {};
  for (const key of Object.keys(base)) {
    base[key] = Array.isArray(src[key]) ? src[key].map((x) => String(x)) : [];
  }
  return base;
}

// Split a user-supplied field value into clean, non-empty lines. Accepts commas or newlines.
function splitEntries(value) {
  return String(value || '')
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function presetEntries(name) {
  return (PRESETS[name] && PRESETS[name].entries) || [];
}

function serialize(input) {
  const m = normalizeModel(input);
  const out = [];
  const section = (title, items) => {
    if (!items || !items.length) return;
    out.push('# ' + title);
    out.push(...items);
    out.push('');
  };
  section('Specific files', m.files);
  section('Wildcard patterns', m.patterns);
  section('Whole directories', m.dirs);
  section('In all subdirectories', m.subdirs);
  section('Exceptions (negation)', m.exceptions);
  section('Only in root', m.rootOnly);
  for (const p of m.presets) {
    const preset = PRESETS[p];
    if (!preset) continue;
    section(preset.labelEn, preset.entries);
  }
  if (m.custom && m.custom.length) {
    out.push(...m.custom);
    if (out[out.length - 1] !== '') out.push('');
  }
  const text = out.join('\n');
  return text ? text.replace(/\n*$/, '\n') : '';
}

function classify(line) {
  const v = line.trim();
  if (!v) return { key: null, value: null };
  if (v.startsWith('!')) return { key: 'exceptions', value: v };
  if (v.startsWith('/') && !v.includes('**')) return { key: 'rootOnly', value: v };
  if (v.includes('**/')) return { key: 'subdirs', value: v };
  if (v.endsWith('/')) return { key: 'dirs', value: v };
  if (/[*?[\]]/.test(v)) return { key: 'patterns', value: v };
  return { key: 'files', value: v };
}

function parse(content) {
  const m = emptyModel();
  if (typeof content !== 'string' || !content) return m;
  for (const raw of content.split(/\r?\n/)) {
    const line = raw.replace(/\r$/, '');
    if (!line.trim()) {
      m.custom.push(line);
      continue;
    }
    if (line.trim().startsWith('#')) {
      m.custom.push(line);
      continue;
    }
    const c = classify(line);
    if (c.key) m[c.key].push(c.value);
    else m.custom.push(line);
  }
  return m;
}

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Compile the body of a gitignore pattern (no leading/trailing slash semantics)
// into a RegExp source fragment. Handles '**', '*', '?', '[abc]' classes and
// backslash escapes. '*' and '?' never match '/'.
function globSource(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*') {
      if (glob[i + 1] === '*') {
        let j = i;
        while (glob[j] === '*') j++;
        if (glob[j] === '/') { re += '(?:.*/)?'; i = j; }
        else { re += '.*'; i = j - 1; }
      } else {
        re += '[^/]*';
      }
    } else if (c === '?') {
      re += '[^/]';
    } else if (c === '[') {
      let j = i + 1, cls = '';
      if (glob[j] === '!' || glob[j] === '^') { cls += '^'; j++; }
      if (glob[j] === ']') { cls += '\\]'; j++; }
      while (j < glob.length && glob[j] !== ']') { cls += glob[j]; j++; }
      const closed = glob[j] === ']';
      re += '[' + cls + ']';
      i = closed ? j : glob.length;
    } else if (c === '\\' && i + 1 < glob.length) {
      re += escapeRegExp(glob[i + 1]);
      i++;
    } else {
      re += escapeRegExp(c);
    }
  }
  return re;
}

// Build a RegExp for a single gitignore pattern (which may carry '!', a leading
// '/' anchor or a trailing '/' directory marker). Matches a full slash-separated
// path relative to the .gitignore location.
function compilePattern(pattern) {
  let p = pattern;
  let dirOnly = false;
  if (p.endsWith('/')) { dirOnly = true; p = p.slice(0, -1); }
  let anchored = false;
  if (p.startsWith('/')) { anchored = true; p = p.slice(1); }
  else if (p.includes('/')) { anchored = true; }
  const body = globSource(p);
  if (!body) return null;
  const src = dirOnly
    ? (anchored ? '^' + body + '(?:/.*)?$' : '(?:^|.*/)' + body + '(?:/.*)?$')
    : (anchored ? '^' + body + '$' : '(?:^|.*/)' + body + '$');
  return new RegExp(src);
}

// Determine whether a repository-relative path is ignored by a .gitignore
// content string. Rules are evaluated top-to-bottom; '!' negates the last match.
function isIgnoredPath(relPath, content) {
  if (typeof relPath !== 'string' || typeof content !== 'string') return false;
  const rel = relPath.replace(/\\/g, '/').replace(/^\.\//, '');
  if (!rel) return false;
  let ignored = false;
  for (let raw of content.split(/\r?\n/)) {
    let line = raw.replace(/\r$/, '');
    if (!line || line.startsWith('#')) continue;
    let negate = false;
    if (line.startsWith('!')) { negate = true; line = line.slice(1); }
    if (!line) continue;
    const re = compilePattern(line);
    if (re && re.test(rel)) ignored = !negate;
  }
  return ignored;
}

module.exports = {
  PRESETS,
  CATEGORIES,
  GLOBAL_HINT,
  emptyModel,
  normalizeModel,
  splitEntries,
  presetEntries,
  serialize,
  parse,
  classify,
  isIgnoredPath
};
