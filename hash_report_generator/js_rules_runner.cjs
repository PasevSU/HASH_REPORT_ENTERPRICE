"use strict";
// Batch loader for declarative *.js rule documents.
//
// One Node process loads every requested rule, so the caller never pays a
// process spawn (nor a network stat storm) per file. All filesystem hardening
// lives here: the caller only does I/O-free lexical checks. See
// docu/V90_JS_CAPABILITY_ANALYSIS_BG.md.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function fail(code, detail) {
  // stdout stays pure payload; errors travel as JSON on stderr.
  process.stderr.write(JSON.stringify({code: code, detail: String(detail)}));
  process.exit(2);
}

let input;
try {
  input = JSON.parse(fs.readFileSync(0, 'utf8'));
} catch (error) {
  fail('BAD_INPUT', error && error.message);
}

let base;
try {
  base = fs.realpathSync(input.root);
} catch (error) {
  fail('MISSING_FOLDER', input.root);
}

const result = [];
for (const requested of input.files) {
  let entry;
  try {
    // lstat first: a symlink must be rejected before resolution hides it.
    entry = fs.lstatSync(requested);
  } catch (error) {
    fail('MISSING_FILE', requested);
  }
  if (entry.isSymbolicLink()) fail('SYMLINK', requested);

  let file;
  try {
    file = fs.realpathSync(requested);
  } catch (error) {
    fail('MISSING_FILE', requested);
  }
  if (file !== base && !file.startsWith(base + path.sep)) fail('OUTSIDE', requested);
  if (!file.endsWith('.js')) fail('SUFFIX', requested);
  if (!entry.isFile()) fail('NOT_FILE', requested);

  let source;
  try {
    source = fs.readFileSync(file, 'utf8');
  } catch (error) {
    fail('UNREADABLE', file);
  }
  if (source.length > 200000) fail('TOO_LARGE', file);

  const context = vm.createContext({module: {exports: null}},
    {codeGeneration: {strings: false, wasm: false}});
  try {
    new vm.Script(source, {filename: file}).runInContext(context, {timeout: 1000});
  } catch (error) {
    fail('EVALUATION', file + ': ' + (error && error.message));
  }
  const data = context.module.exports;
  if (!data || Array.isArray(data) || typeof data !== 'object') fail('NOT_OBJECT', file);
  result.push(data);
}
process.stdout.write(JSON.stringify(result));
