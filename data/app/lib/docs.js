'use strict';
// docs — standard project documentation generator (README / CONTRIBUTING / SECURITY).
//
// Pure module (no I/O): the UI collects project metadata, this module renders the three
// mandatory Markdown files so every repository managed by GitSU ships with a complete,
// discoverable documentation set. Templates are adapted to the PasevSU-DEV identity by
// default but fully parameterized so any project can be described. Deterministic output
// makes it unit-testable.

const DEFAULT_META = {
  name: 'project',
  repo: '',                 // 'owner/name'
  description: 'A GitSU-managed project.',
  homepage: 'https://pasevsu.github.io/',
  org: 'PasevSU-DEV',
  author: 'Denislav Pasev',
  year: String(new Date().getFullYear()),
  license: 'Apache-2.0',
  node: '22.12.0+',
  packageManager: 'npm',
  stack: ['Node.js']
};

function normalizeMeta(input) {
  const src = input && typeof input === 'object' ? input : {};
  const out = { ...DEFAULT_META, ...src };
  for (const k of Object.keys(out)) if (out[k] === undefined || out[k] === null) out[k] = DEFAULT_META[k];
  if (out.stack && !Array.isArray(out.stack)) out.stack = [String(out.stack)];
  out.name = String(out.name || 'project').trim() || 'project';
  out.repo = String(out.repo || '').trim();
  out.year = String(out.year || '').trim() || String(new Date().getFullYear());
  return out;
}

const repoUrl = (m) => (m.repo ? `https://github.com/${m.repo}` : m.homepage);

function readme(input) {
  const m = normalizeMeta(input);
  const url = repoUrl(m);
  const stackLine = m.stack && m.stack.length ? m.stack.join(' · ') : 'Node.js';
  const lines = [];
  lines.push(`# ${m.name}`);
  lines.push('');
  lines.push(`> ${m.description}`);
  lines.push('');
  lines.push(`[![License: ${m.license}](https://img.shields.io/badge/License-${m.license.replace(/[-]/g, '_')}-blue.svg)](LICENSE)`);
  lines.push(`[![Stack](https://img.shields.io/badge/Stack-${encodeURIComponent(stackLine)}-green.svg)](${url})`);
  lines.push('');
  lines.push('## About');
  lines.push('');
  lines.push(m.description);
  lines.push('');
  lines.push(`- **Homepage:** ${m.homepage}`);
  if (m.repo) lines.push(`- **Repository:** ${url}`);
  lines.push(`- **Author:** ${m.author} · ${m.org}`);
  lines.push(`- **License:** ${m.license}`);
  lines.push('');
  lines.push('## Requirements');
  lines.push('');
  lines.push(`- Node.js ${m.node}`);
  lines.push(`- Package manager: ${m.packageManager}`);
  lines.push('');
  lines.push('## Install');
  lines.push('');
  lines.push('```bash');
  lines.push('git clone ' + (m.repo ? `${url}.git` : '<repository-url>'));
  lines.push(`cd ${m.name}`);
  lines.push(`${m.packageManager} install`);
  lines.push('```');
  lines.push('');
  lines.push('## Usage');
  lines.push('');
  lines.push('```bash');
  lines.push(`${m.packageManager} start`);
  lines.push('```');
  lines.push('');
  lines.push('## Documentation');
  lines.push('');
  lines.push('- [Contributing](CONTRIBUTING.md)');
  lines.push('- [Security policy](SECURITY.md)');
  lines.push('');
  lines.push('## License');
  lines.push('');
  lines.push(`Licensed under the ${m.license}. See [LICENSE](LICENSE) for details.`);
  lines.push('');
  lines.push(`— ${m.org} · ${m.author}`);
  return lines.join('\n') + '\n';
}

function contributing(input) {
  const m = normalizeMeta(input);
  const url = repoUrl(m);
  const lines = [];
  lines.push(`# Contributing to ${m.name}`);
  lines.push('');
  lines.push(`Thanks for your interest! This project targets Node ${m.node} and uses ${m.packageManager}.`);
  lines.push('');
  lines.push('## Setup');
  lines.push('');
  lines.push('```bash');
  lines.push('git clone ' + (m.repo ? `${url}.git` : '<repository-url>'));
  lines.push(`cd ${m.name}`);
  lines.push(`${m.packageManager} install`);
  lines.push('```');
  lines.push('');
  lines.push('## Commands');
  lines.push('');
  lines.push('| Command | What it does |');
  lines.push('| --- | --- |');
  lines.push(`| \`${m.packageManager} test\` | Run the full test suite |`);
  lines.push(`| \`${m.packageManager} run check\` | Syntax-check every module |`);
  lines.push(`| \`${m.packageManager} run build\` | Build the distributable output |`);
  lines.push(`| \`${m.packageManager} start\` | Run the app from source |`);
  lines.push('');
  lines.push('## Before opening a pull request');
  lines.push('');
  lines.push('1. Run the full check: `' + `${m.packageManager} test && ${m.packageManager} run check` + '`.');
  lines.push('2. Keep changes focused and describe them in the PR description.');
  lines.push('3. Security-relevant changes: confirm the threat model in `SECURITY.md` was considered.');
  lines.push('');
  lines.push('## Reporting bugs');
  lines.push('');
  lines.push('Open an issue at ' + (m.repo ? `${url}/issues/new/choose` : 'the project issue tracker') + ' and include the version, runtime and a minimal reproduction.');
  lines.push('');
  lines.push('## Security issues');
  lines.push('');
  lines.push('Do **not** file public issues for security problems. Follow the disclosure procedure in [SECURITY.md](SECURITY.md).');
  lines.push('');
  lines.push('## License');
  lines.push('');
  lines.push(`By contributing you agree your work is ${m.license}-licensed (see [LICENSE](LICENSE)).`);
  return lines.join('\n') + '\n';
}

function security(input) {
  const m = normalizeMeta(input);
  const url = repoUrl(m);
  const lines = [];
  lines.push('# Security Policy');
  lines.push('');
  lines.push(`We take security reports seriously. This policy describes supported versions and how to disclose a vulnerability in ${m.name}.`);
  lines.push('');
  lines.push('## Supported versions');
  lines.push('');
  lines.push('We support the latest released minor version. Security fixes ship as patch releases against the latest minor.');
  lines.push('');
  lines.push('| Version | Supported |');
  lines.push('| --- | --- |');
  lines.push('| latest | ✓ (current) |');
  lines.push('| older  | — please upgrade |');
  lines.push('');
  lines.push('## Reporting a vulnerability');
  lines.push('');
  lines.push('**Please do not file public issues for security vulnerabilities.**');
  lines.push('');
  lines.push('Preferred channel: **GitHub Security Advisories** at ' + (m.repo ? `${url}/security/advisories/new` : 'the GitHub Security tab') + '.');
  lines.push('');
  lines.push('When reporting, please include:');
  lines.push('');
  lines.push('- A description of the issue and its impact.');
  lines.push('- Steps to reproduce.');
  lines.push('- The affected version and runtime.');
  lines.push('- Whether disclosure is time-sensitive.');
  lines.push('');
  lines.push('You can expect:');
  lines.push('');
  lines.push('- An initial acknowledgement within **5 business days**.');
  lines.push('- A triage assessment within 10 business days.');
  lines.push('- A coordinated-disclosure timeline.');
  lines.push('- Credit in the resulting advisory (unless you ask to remain anonymous).');
  lines.push('');
  lines.push('## Threat model');
  lines.push('');
  lines.push('In scope:');
  lines.push('');
  lines.push('- Remote code execution, path traversal, credential leakage, or privilege escalation reachable from project inputs.');
  lines.push('- Resource-exhaustion vectors (unbounded loops, decompression bombs, large responses).');
  lines.push('');
  lines.push('Out of scope:');
  lines.push('');
  lines.push('- Issues in upstream dependencies — report those upstream; we track and bump as fixes ship.');
  lines.push('- General service outages or rate-limiting.');
  lines.push('');
  lines.push('## Hardening');
  lines.push('');
  lines.push('Run with least privilege, keep dependencies updated, and review the README for any production checklist.');
  return lines.join('\n') + '\n';
}

// Filenames a repository should ship with, in canonical order.
const DOCS = [
  { file: 'README.md', labelEn: 'README (project overview)' },
  { file: 'CONTRIBUTING.md', labelEn: 'Contributing guide' },
  { file: 'SECURITY.md', labelEn: 'Security policy' }
];

const RENDERERS = { 'README.md': readme, 'CONTRIBUTING.md': contributing, 'SECURITY.md': security };

// Render a single file by name, or null for an unknown name.
function render(file, meta) {
  const fn = RENDERERS[file];
  return fn ? fn(meta) : null;
}

// Render every mandatory document into a { file: content } map.
function generateAll(input) {
  const m = normalizeMeta(input);
  const out = {};
  for (const d of DOCS) out[d.file] = RENDERERS[d.file](m);
  return out;
}

module.exports = { DEFAULT_META, DOCS, RENDERERS, normalizeMeta, readme, contributing, security, render, generateAll };
