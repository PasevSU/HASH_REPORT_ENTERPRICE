#!/usr/bin/env node
// Programmatic API for the JavaScript clone: every exported helper returns the
// same summary object the CLI prints, so callers never parse console text.
import fs from 'node:fs';
import path from 'node:path';
import { CLONE_VERSION, EXIT_ERROR, EXIT_OK, run } from './cli.mjs';
import { REPO_ROOT } from './lib/config.mjs';

export { CLONE_VERSION };

/** Translate plain options into the argument vector `run()` understands. */
export function buildArgv({
  source = null,
  files = [],
  filters = [],
  recursive = false,
  output = null,
  profile = null,
  archive = null,
  normalise = true,
  requireLayoutPass = false,
  perFile = false,
  embedPdf = false,
  quiet = false,
} = {}) {
  const argv = [];
  if (source) argv.push('--source', source);
  if (files.length) argv.push('--files', files.join(','));
  if (recursive) argv.push('--recursive');
  for (const pattern of filters) if (pattern) argv.push('--filter', pattern);
  if (output) argv.push('--output', output);
  if (profile) argv.push('--profile', profile);
  if (archive === true) argv.push('--archive');
  if (archive === false) argv.push('--no-archive');
  if (!normalise) argv.push('--no-normalise');
  if (requireLayoutPass) argv.push('--require-layout-pass');
  if (perFile) argv.push('--per-file');
  if (embedPdf) argv.push('--embed-pdf');
  if (quiet) argv.push('--quiet');
  return argv;
}

/** The output folder is a caller convenience: the API creates it, the CLI does not. */
export function prepareOutput(directory) {
  const resolved = path.resolve(directory);
  fs.mkdirSync(resolved, { recursive: true });
  return resolved;
}

function normalise(result) {
  return {
    exitCode: result.exitCode ?? EXIT_OK,
    summary: result.summary ?? null,
    layout: result.layout ?? null,
    published: result.published ?? null,
    evidenceDirectory: result.evidenceDirectory ?? null,
    archive: result.archive ?? null,
  };
}

/** Console output is off unless the caller asks for it with log: true. */
function quietFor(options) {
  return options.log === true ? false : options.quiet !== false;
}

async function execute(argv, options) {
  const result = await run(argv, { repoRoot: options.repoRoot || REPO_ROOT });
  return normalise(result);
}

/**
 * One combined report for a folder.
 *
 * @returns {Promise<{exitCode:number, summary:object, published:string}>}
 */
export async function reportForFolder(folder, options = {}) {
  const source = path.resolve(folder);
  if (!fs.existsSync(source)) throw new Error('Folder does not exist: ' + source);
  if (!fs.statSync(source).isDirectory()) throw new Error('Not a folder: ' + source);
  const output = prepareOutput(options.output || source);
  return execute(buildArgv({ ...options, source, output, quiet: quietFor(options) }), options);
}

/** One SINGLE report for exactly one file. */
export async function reportForFile(file, options = {}) {
  const target = path.resolve(file);
  if (!fs.existsSync(target)) throw new Error('File does not exist: ' + target);
  if (!fs.statSync(target).isFile()) throw new Error('Not a regular file: ' + target);
  const output = prepareOutput(options.output || path.dirname(target));
  return execute(buildArgv({ ...options, files: [target], output, quiet: quietFor(options) }), options);
}

/**
 * One report **per file**: N files produce N independent reports, each with its
 * own report number, evidence case and archive row. A failing file never hides
 * the reports of the files that succeeded unless `continueOnError` is false.
 */
export async function reportForFiles(files, options = {}) {
  if (!Array.isArray(files) || !files.length) throw new Error('reportForFiles needs at least one file');
  const continueOnError = options.continueOnError !== false;
  const output = prepareOutput(options.output || path.dirname(path.resolve(files[0])));
  const reports = [];
  let failed = 0;
  const started = Date.now();
  for (const file of files) {
    try {
      const result = await reportForFile(file, { ...options, output });
      if (result.exitCode !== EXIT_OK) failed += 1;
      reports.push({ file: path.resolve(file), ...result });
    } catch (error) {
      if (!continueOnError) throw error;
      failed += 1;
      reports.push({ file: path.resolve(file), exitCode: EXIT_ERROR, summary: null, error: error.message });
    }
  }
  return {
    exitCode: failed ? EXIT_ERROR : EXIT_OK,
    status: failed ? 'ERROR' : 'PASS',
    files: files.length,
    failed,
    reports,
    elapsed_seconds: Math.round((Date.now() - started) / 10) / 100,
  };
}

export default { CLONE_VERSION, buildArgv, prepareOutput, reportForFolder, reportForFile, reportForFiles };