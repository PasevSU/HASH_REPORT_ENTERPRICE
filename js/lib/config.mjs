/**
 * Configuration loader for the JS clone (port of chronoseal/settings.py).
 *
 * The clone reads exactly the same config/config.json as the Python program, so
 * one operator decision (archive folder, evidence retention, generator defaults)
 * governs both implementations. Nothing is defaulted silently: a policy that
 * cannot be honoured is rejected instead of ignored.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const DEFAULT_CONFIG_PATH = path.join(REPO_ROOT, 'config', 'config.json');

export const EVIDENCE_RETENTION_KEYS = Object.freeze([
  'keep_tsr',
  'keep_certificates',
  'keep_validation_json',
]);

const GENERATOR_DEFAULTS = Object.freeze({
  package_dir: 'hash_report_generator',
  combined_script: 'hash_report_combined.py',
  single_script: 'hash_report_single.py',
  python: 'python',
  output_glob: '*.pdf',
  search_roots: [],
  timeout_seconds: 0,
  idle_timeout_seconds: 900,
  allow_unreadable_files: false,
  follow_links: false,
  heartbeat_seconds: 30,
  filter_case_sensitive: false,
});

export function loadConfig(configPath = DEFAULT_CONFIG_PATH) {
  const file = path.resolve(String(configPath));
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch (error) {
    throw new Error(`Configuration file is not readable: ${file}: ${error.message}`);
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Configuration file is not valid JSON: ${file}: ${error.message}`);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Configuration root must be a JSON object');
  }
  Object.defineProperty(data, '__path', { value: file, enumerable: false });
  return data;
}

/** Retention switches are mandatory, exactly as in settings.evidence_policy(). */
export function evidencePolicy(config) {
  const policy = (config || {}).evidence || {};
  if (typeof policy !== 'object' || Array.isArray(policy)) {
    throw new Error('config.evidence must be a JSON object');
  }
  const disabled = EVIDENCE_RETENTION_KEYS.filter((key) => policy[key] === false);
  if (disabled.length) {
    throw new Error('config.evidence.' + disabled.join(', config.evidence.')
      + ' cannot be disabled: an archived report must keep its timestamp response, '
      + 'TSA certificates and validation JSON to remain verifiable offline.');
  }
  return Object.fromEntries(EVIDENCE_RETENTION_KEYS.map((key) => [key, true]));
}

export function generatorSettings(config, root = REPO_ROOT) {
  const section = (config || {}).generator || {};
  const merged = { ...GENERATOR_DEFAULTS, ...section };
  const packageDir = path.isAbsolute(String(merged.package_dir))
    ? String(merged.package_dir)
    : path.join(root, String(merged.package_dir));
  return { ...merged, package_dir: packageDir };
}

/**
 * Resolve the archive location. A relative path is anchored at the repository
 * root, mirroring Pipeline.run(); an enabled archive with an empty path is a
 * hard error, never a silent skip.
 */
export function archiveSettings(config, root = REPO_ROOT) {
  const section = (config || {}).archive || {};
  const enabled = section.enabled === true;
  if (!enabled) return { enabled: false, directory: null, database: null };
  const directory = String(section.directory || '').trim();
  const database = String(section.database || '').trim();
  if (!directory || !database) {
    throw new Error('Report archive is enabled but its archive directory or SQLite database path is empty.');
  }
  const absolute = (value) => (path.isAbsolute(value) ? path.resolve(value) : path.join(root, value));
  return { enabled: true, directory: absolute(directory), database: absolute(database) };
}

export function toolPath(config, name) {
  const configured = ((config || {}).tools || {})[name];
  if (configured && fs.statSync(String(configured), { throwIfNoEntry: false })?.isFile()) {
    return String(configured);
  }
  return null;
}
