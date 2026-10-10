'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const gitops = require('./gitops');

function run(command, args, cwd, options = {}) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    windowsHide: true,
    ...options
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim();
    throw new Error(`${command} ${args.join(' ')} failed${result.status === null ? '' : ` (exit ${result.status})`}${detail ? `: ${detail}` : ''}`);
  }
  return (result.stdout || '').trim();
}

function git(args, cwd) {
  return run('git', args, cwd);
}

function repositoryRoot(directory) {
  const target = path.resolve(directory);
  if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) {
    throw new Error(`Directory not found: ${target}`);
  }
  return git(['rev-parse', '--show-toplevel'], target);
}

async function updateFromRemote(directory, apply = false) {
  return gitops.pull(directory, { apply: Boolean(apply) });
}

async function pushChanges(directory, options = {}) {
  return gitops.push(directory, { apply: Boolean(options.apply), message: options.message });
}

function validateRepositoryName(name) {
  if (typeof name !== 'string' || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(name)) {
    throw new Error('Repository name must use OWNER/REPOSITORY format.');
  }
  return name;
}

async function publishRepository(directory, options = {}) {
  return gitops.publish(directory, {
    repo: options.repo,
    visibility: options.visibility,
    description: options.description,
    message: options.message,
    apply: Boolean(options.apply)
  });
}

function createScaffold(directory, projectName) {
  const root = path.resolve(directory);
  const name = projectName || path.basename(root);
  if (!/^[a-z0-9][a-z0-9._-]*$/.test(name)) {
    throw new Error('Project name must be a lowercase npm-compatible name.');
  }
  if (fs.existsSync(root)) throw new Error(`Target already exists: ${root}`);
  fs.mkdirSync(path.join(root, 'src'), { recursive: true });
  fs.mkdirSync(path.join(root, 'test'), { recursive: true });
  fs.mkdirSync(path.join(root, 'docs'), { recursive: true });
  fs.writeFileSync(path.join(root, 'README.md'), `# ${name}\n\nA JavaScript project.\n`, { flag: 'wx' });
  fs.writeFileSync(path.join(root, 'package.json'), `${JSON.stringify({
    name,
    version: '1.0.0',
    private: true,
    description: '',
    main: 'src/index.js',
    scripts: { test: 'node --test' }
  }, null, 2)}\n`, { flag: 'wx' });
  fs.writeFileSync(path.join(root, '.gitignore'), 'node_modules/\n.env\n.DS_Store\n', { flag: 'wx' });
  fs.writeFileSync(path.join(root, 'src', 'index.js'), "'use strict';\n\nmodule.exports = {};\n", { flag: 'wx' });
  fs.writeFileSync(path.join(root, 'test', '.gitkeep'), '', { flag: 'wx' });
  fs.writeFileSync(path.join(root, 'docs', '.gitkeep'), '', { flag: 'wx' });
  return { root, name, created: true };
}

async function syncRepositories(configPath, options = {}) {
  const absoluteConfig = path.resolve(configPath);
  const configuration = JSON.parse(fs.readFileSync(absoluteConfig, 'utf8'));
  if (!configuration || !Array.isArray(configuration.repositories) || configuration.repositories.some(item => typeof item !== 'string')) {
    throw new Error('Sync configuration must contain a repositories array of directory paths.');
  }
  const base = path.dirname(absoluteConfig);
  const direction = options.direction || 'pull';
  if (!['pull', 'push'].includes(direction)) throw new Error('Direction must be pull or push.');
  const results = [];
  for (const item of configuration.repositories) {
    const directory = path.resolve(base, item);
    results.push(direction === 'pull'
      ? await updateFromRemote(directory, Boolean(options.apply))
      : await pushChanges(directory, { apply: Boolean(options.apply), message: options.message }));
  }
  return results;
}

module.exports = {
  createScaffold,
  publishRepository,
  pushChanges,
  repositoryRoot,
  syncRepositories,
  updateFromRemote,
  validateRepositoryName
};
