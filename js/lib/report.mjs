/**
 * Declarative report assembly for the JS clone.
 *
 * A report is not hard-coded here: the profile (report_profiles/*.js) selects an
 * ordered list of modules, and each module rule file decides its title, its
 * fields, and its table columns. The renderer only knows a handful of module
 * types, so adding a section means adding a rule file - exactly like Python.
 *
 * Section wording mirrors the Python generator (hash_report_combined.py) where
 * it describes evidence, so a clone report and a Python report can be read side
 * by side. Statements about RFC 3161 signing are deliberately absent: the clone
 * does not sign, and must never imply that it did.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { REPO_ROOT } from './config.mjs';
import { formatStamp } from './util.mjs';
import { classifyArtifactFile, typeCounts } from './classify.mjs';
import { loadStyles } from '../../tools/jsx/style-loader.mjs';

export const PROFILE_DIR = path.join(REPO_ROOT, 'hash_report_generator', 'report_profiles');
export const MODULE_DIR = path.join(REPO_ROOT, 'hash_report_generator', 'modules');
export const RULE_TIMEOUT_MS = 1000;

export const SUPPORTED_MODULE_TYPES = Object.freeze(['key_values', 'hash_table', 'text', 'file_information']);

/** Report Type line, worded like the Python evidence package. */
export const REPORT_TYPE_LABELS = Object.freeze({
  SINGLE: 'Single File Hash Report (Evidence Package)',
  SINGLE_PDF: 'Single PDF Hash Report (Embedded Source PDF)',
  COMBO: 'Combined File Hash Report (Evidence Package)',
  COMBO_ALL: 'Combined File Hash Report (Evidence Package, recursive)',
  VOLUME: 'Volume Hash Report (Bytes Per Folder)',
  FILE_INFORMATION: 'File Information Report (SHA-256 Sheet)',
});

/** Rule files are declarative: evaluate them with no ambient authority. */
export function evaluateRuleFile(file) {
  const code = fs.readFileSync(file, 'utf8');
  const module = { exports: {} };
  const context = vm.createContext({ module, exports: module.exports });
  vm.runInContext(code, context, { filename: file, timeout: RULE_TIMEOUT_MS });
  return module.exports;
}

export function loadProfile(id) {
  const file = path.join(PROFILE_DIR, `${id}.js`);
  if (!fs.existsSync(file)) throw new Error('Unknown report profile: ' + id);
  const profile = evaluateRuleFile(file);
  if (!Array.isArray(profile.modules) || !profile.modules.length) {
    throw new Error('Report profile declares no modules: ' + id);
  }
  return profile;
}

export function loadModule(id) {
  const file = path.join(MODULE_DIR, `${id}.js`);
  if (!fs.existsSync(file)) throw new Error('Unknown report module: ' + id);
  return evaluateRuleFile(file);
}

export function listProfiles() {
  return fs.readdirSync(PROFILE_DIR)
    .filter((name) => name.endsWith('.js'))
    .sort()
    .map((name) => name.slice(0, -3));
}

/** Report type printed in the manifest and in the published file name. */
export function reportType(profile, { recursive = false } = {}) {
  // The dedicated profiles name their own published type; the generic ones are
  // derived from input_scope the way the Python generator does it.
  if (profile?.id === 'single_pdf') return 'SINGLE_PDF';
  if (profile?.id === 'volume') return 'VOLUME';
  if (profile?.id === 'file_information_report') return 'FILE_INFORMATION';
  const kind = (profile?.input_scope || 'single_file');
  if (kind === 'single_file') return 'SINGLE';
  if (kind === 'recursive_folder') return 'COMBO_ALL';
  if (kind === 'current_folder') return recursive ? 'COMBO_ALL' : 'COMBO';
  return 'COMBO';
}

/** Type label for one evidence file, using the Python classification rules. */
export function classify(name, baseName = '') {
  return classifyArtifactFile(name, baseName);
}

/** `Size (KB)` is in the header, so rows carry the bare number. */
export function sizeKb(bytes) {
  return (Number(bytes) / 1024).toFixed(3);
}

/** Millisecond-precision local timestamp, the format the Python table prints. */
export function timestampText(value) {
  if (!value) return '';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`
    + ` ${two(date.getHours())}:${two(date.getMinutes())}:${two(date.getSeconds())}`
    + `.${String(date.getMilliseconds()).padStart(3, '0')}`;
}

/** Same instant split on two lines: the table prints date above time. */
export function timestampCell(value) {
  const text = timestampText(value);
  if (!/^\d{4}-\d{2}-\d{2} /.test(text)) return text;
  const [date, time] = text.split(' ', 2);
  return `${date}\n${time}`;
}

/** Local zone abbreviation and numeric offset, e.g. `CET +01:00`. */
export function timezoneText(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes < 0 ? '-' : '+';
  const absolute = Math.abs(offsetMinutes);
  const offset = `${sign}${two(Math.floor(absolute / 60))}:${two(absolute % 60)}`;
  let name = '';
  try {
    const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(date);
    name = String((parts.find((part) => part.type === 'timeZoneName') || {}).value || '').trim();
  } catch {
    name = '';
  }
  // A host that only exposes an offset reports GMT+2; the offset alone carries
  // the precise value, so the redundant prefix is dropped.
  if (/^(GMT|UTC)([+-]\d{1,2})?$/.test(name)) name = '';
  return name ? `${name} ${offset}` : offset;
}

function two(number) {
  return String(number).padStart(2, '0');
}

/** Display-only uppercase digest; verification always uses the stored bytes. */
export function displayDigest(value) {
  const text = String(value || '');
  return /^[0-9a-fA-F]{8,}$/.test(text) ? text.toUpperCase() : text;
}

/**
 * Group a digest to the width of its own column, exactly like the Python
 * digest_cell_for_width(): group = column width / (font size * 0.62), clamped
 * to 8..32 and rounded down to a multiple of four. The full digest is always
 * printed - grouping is readability, never truncation.
 */
export function digestGroup(width, size) {
  const font = Math.max(Number(size) || 7, 1);
  let group = Math.max(8, Math.min(32, Math.floor(Number(width) / (font * 0.62))));
  group -= group % 4;
  return Math.max(8, group);
}

export const COMBINED_COLUMNS = Object.freeze([
  { key: 'index', title: '#', weight: 0.045, align: 'CENTER', role: 'regular', size: 7 },
  { key: 'path', title: 'File Name', weight: 0.245, align: 'LEFT', role: 'regular', size: 7 },
  { key: 'type', title: 'Type', weight: 0.095, align: 'LEFT', role: 'regular', size: 7 },
  { key: 'size_kb', title: 'Size (KB)', weight: 0.09, align: 'RIGHT', role: 'regular', size: 7 },
  { key: 'created', title: 'Created', weight: 0.145, align: 'LEFT', role: 'regular', size: 7, multiline: true },
  { key: 'modified', title: 'Modified', weight: 0.145, align: 'LEFT', role: 'regular', size: 7, multiline: true },
  {
    key: 'sha256',
    title: 'SHA-256 Hash',
    weight: 0.235,
    align: 'LEFT',
    role: 'monospace',
    size: 6.5,
    leading: 11,
    chunk: digestGroup,
  },
]);

/** Rule aliases: the module rules speak Python's field names. */
const COLUMN_ALIASES = Object.freeze({
  name: 'path',
  file_name: 'path',
  size_bytes: 'size_kb',
  size: 'size_kb',
});

/** Project hashed rows into the table shape declared by the module rule. */
export function tableRows(files) {
  return files.map((file, position) => ({
    index: String(position + 1),
    path: file.name || file.path,
    type: classify(file.name || file.path),
    size_kb: sizeKb(file.size_bytes),
    created: timestampCell(file.created_at || file.created),
    modified: timestampCell(file.modified_at || file.modified),
    sha256: displayDigest(file.sha256),
  }));
}

function headingMarkup(label) {
  return String(label).trim();
}

function countLabel(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural}`;
}

/**
 * SYSTEM INFORMATION (BEWEISSICHERUNG):
 *
 * The rule file declares generated/type/id; the evidence set itself contributes
 * the totals, the selection filter and the eleven aggregate digests, and the
 * volume block records where the bytes were read from.
 */
function renderSystemInformation(layout, module, context) {
  layout.heading(headingMarkup(module.title), 'section');
  const rows = [];
  const declared = module.fields || ['Generated', 'Report Type', 'Report ID'];
  for (const field of declared) {
    const key = String(field).toLowerCase();
    if (key === 'generated') {
      rows.push(['Generated', `${context.generatedAt} ${context.timezone}`]);
    } else if (key === 'report type') {
      rows.push(['Report Type', REPORT_TYPE_LABELS[context.reportType] || context.reportType]);
    } else if (key === 'report id') {
      rows.push(['Report ID', context.reportId]);
    }
  }
  rows.push(['Total Files', String(context.files.length)]);
  rows.push(['Total Size', `${context.totalSizeKb} KB`]);
  rows.push(['Selection filter', context.filterText]);
  rows.push(['Input', `${context.inputKind}; recursive: ${context.recursive ? 'yes' : 'no'}`]);
  rows.push(['Aggregation method', context.aggregationMethod]);
  layout.keyValues(rows);

  layout.paragraph('Total Checksum (All Files):', {
    size: layout.fonts.body,
    leading: layout.leading.body,
    color: layout.colors.ink,
  });
  for (const [algorithm, digest] of Object.entries(context.courtHashes || {})) {
    layout.paragraph(`${algorithm}  ${String(digest).toUpperCase()}`, {
      size: layout.fonts.small,
      leading: layout.leading.small,
      color: layout.colors.muted,
    });
  }
  layout.gap(4);
  layout.paragraph(
    `Aggregated document proof (SHA-256): ${String(context.documentProof || '').toUpperCase()}`,
    { size: layout.fonts.small, leading: layout.leading.small, color: layout.colors.muted },
  );
  renderVolumeInformation(layout, context);
  renderUserInformation(layout, context);
  return layout;
}

function renderVolumeInformation(layout, context) {
  const volume = context.volume;
  if (!volume) return;
  const rows = [
    ['Working Folder', volume.short_path],
    ['Volume GUID', volume.guid],
    ['Mounted On', volume.mount_point],
    ['Filesystem', volume.filesystem],
    ['Volume Serial', volume.serial],
  ].filter(([, value]) => value);
  if (!rows.length) return;
  layout.gap(6);
  layout.heading('VOLUME:', 'section');
  layout.keyValues(rows);
}

function renderUserInformation(layout, context) {
  const user = context.user;
  if (!user) return;
  const rows = [
    ['Generated by', user.user],
    ['Computer Name', user.host],
    ['Operating System', user.operating_system],
    ['Hardware ID', user.hardware_id],
  ].filter(([, value]) => value);
  if (!rows.length) return;
  layout.gap(6);
  layout.heading('USER INFORMATION:', 'section');
  layout.keyValues(rows);
}

function renderFileInformation(layout, module, context) {
  layout.heading(headingMarkup(module.title), 'section');
  const file = context.files[0] || {};
  const rows = [];
  for (const field of module.fields || []) {
    const key = String(field).toLowerCase();
    if (key === 'name') rows.push(['File name', file.name || file.path || '']);
    else if (key === 'size_kb') rows.push(['Size (KB)', sizeKb(file.size_bytes || 0)]);
    else if (key === 'created') rows.push(['Created', timestampText(file.created_at || file.created)]);
    else if (key === 'modified') rows.push(['Modified', timestampText(file.modified_at || file.modified)]);
    else if (key === 'sha256') rows.push(['SHA-256', displayDigest(file.sha256)]);
    else if (key === 'hardware_id') rows.push(['Hardware ID', context.hardwareId || '']);
    else if (key === 'report_id') rows.push(['Report ID', context.reportId]);
  }
  layout.keyValues(rows);
  return layout;
}

/** Columns in the order the module rule declares them, aliases resolved. */
export function columnsFor(module) {
  const declared = module.columns || ['index', 'path', 'type', 'size_bytes', 'created', 'modified', 'sha256'];
  return declared
    .map((key) => COLUMN_ALIASES[key] || key)
    .map((key) => COMBINED_COLUMNS.find((column) => column.key === key))
    .filter(Boolean);
}

function renderHashTable(layout, module, context) {
  layout.heading(headingMarkup(module.title), 'section');
  layout.table({ columns: columnsFor(module), rows: tableRows(context.files) });
  layout.gap(4);
  layout.paragraph('Evidence Package Summary:', {
    size: layout.fonts.body,
    leading: layout.leading.body,
    color: layout.colors.ink,
  });
  layout.paragraph(`- Total files in package: ${context.files.length}`, {
    size: layout.fonts.small,
    leading: layout.leading.small,
    color: layout.colors.muted,
  });
  layout.paragraph(`- Total package size: ${context.totalSizeKb} KB`, {
    size: layout.fonts.small,
    leading: layout.leading.small,
    color: layout.colors.muted,
  });
  const counts = typeCounts(context.files.map((file) => ({ type: classify(file.name || file.path) })));
  if (counts.length) {
    layout.paragraph('Files by type:', {
      size: layout.fonts.small,
      leading: layout.leading.small,
      color: layout.colors.ink,
    });
    for (const entry of counts) {
      layout.paragraph(`- ${entry.label}: ${entry.count}`, {
        size: layout.fonts.small,
        leading: layout.leading.small,
        color: layout.colors.muted,
      });
    }
  }
  const unreadable = context.unreadable || [];
  if (unreadable.length) {
    layout.paragraph(`Unreadable entries recorded in the evidence package: ${countLabel(unreadable.length, 'file', 'files')}`, {
      size: layout.fonts.small,
      leading: layout.leading.small,
      color: layout.colors.muted,
    });
  }
  return layout;
}

function renderText(layout, module) {
  layout.heading(headingMarkup(module.title), 'section');
  layout.richParagraph(module.content || '');
  return layout;
}

/**
 * Render the profile's modules in declaration order onto the builder.
 *
 * @returns {{pageCount: number, sections: string[]}}
 */
export function renderReport({ builder, layout, profile, modules, context, styles = null }) {
  const resolvedStyles = styles || loadStyles();
  const reportTitle = profile.title || 'ChronoSeal report';
  layout.heading(reportTitle, 'h1', { center: true });
  layout.paragraph(
    `${context.reportId} - ${REPORT_TYPE_LABELS[context.reportType] || context.reportType}`,
    { size: resolvedStyles.FONTS.subheading, leading: resolvedStyles.LEADING.subheading, color: resolvedStyles.COLORS.muted },
  );
  layout.gap(6);
  const rendered = [];
  for (const id of profile.modules) {
    const module = modules.get(id) || loadModule(id);
    const type = module.type || 'text';
    if (!SUPPORTED_MODULE_TYPES.includes(type)) {
      throw new Error(`Unsupported report module type: ${type} (module ${id})`);
    }
    if (type === 'key_values') renderSystemInformation(layout, module, context);
    else if (type === 'file_information') renderFileInformation(layout, module, context);
    else if (type === 'hash_table') renderHashTable(layout, module, context);
    else renderText(layout, module);
    rendered.push(id);
  }
  return { pageCount: layout.pageCount, sections: rendered };
}

export { formatStamp };