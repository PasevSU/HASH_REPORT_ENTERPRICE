#!/usr/bin/env node
'use strict';

const path = require('node:path');
const {
  createScaffold,
  publishRepository,
  pushChanges,
  syncRepositories,
  updateFromRemote
} = require('./lib/repository');

const usage = `18-repo-manager
  node cli.js create <directory> [--name <npm-name>]
  node cli.js update <repository-directory> [--apply]
  node cli.js push <repository-directory> [--message <text>] [--apply]
  node cli.js publish <directory> --repo <owner/name> [--public|--private] [--message <text>] --apply
  node cli.js sync --config <file.json> [--direction pull|push] [--message <text>] [--apply]

GitHub operations use the authenticated GitHub CLI (gh). Remote changes are never
forced. update/push/sync default to dry-run; add --apply to make changes.`;

function option(args, name, required = false) {
  const index = args.indexOf(name);
  if (index === -1) {
    if (required) throw new Error(`Missing required option ${name}.`);
    return undefined;
  }
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(`Missing value after ${name}.`);
  const value = args[index + 1];
  args.splice(index, 2);
  return value;
}

async function main(input) {
  const args = [...input];
  const [command] = args.splice(0, 1);
  if (!command || ['help', '--help', '-h'].includes(command)) {
    console.log(usage);
    return;
  }
  if (command === 'create') {
    const directory = args.shift();
    if (!directory) throw new Error('create requires a target directory.');
    const name = option(args, '--name');
    if (args.length) throw new Error(`Unknown option: ${args[0]}`);
    console.log(JSON.stringify(createScaffold(directory, name), null, 2));
    return;
  }
  if (command === 'update' || command === 'push') {
    const directory = args.shift();
    if (!directory) throw new Error(`${command} requires a repository directory.`);
    const apply = args.includes('--apply');
    const message = option(args, '--message');
    if (apply) args.splice(args.indexOf('--apply'), 1);
    if (args.length) throw new Error(`Unknown option: ${args[0]}`);
    const result = command === 'update'
      ? await updateFromRemote(directory, apply)
      : await pushChanges(directory, { apply, message });
    console.log(JSON.stringify(result, null, 2));
    return;
  }
  if (command === 'publish') {
    const directory = args.shift();
    if (!directory) throw new Error('publish requires a directory.');
    const repo = option(args, '--repo', true);
    const message = option(args, '--message');
    let visibility = 'private';
    if (args.includes('--public')) {
      visibility = 'public';
      args.splice(args.indexOf('--public'), 1);
    } else if (args.includes('--private')) {
      args.splice(args.indexOf('--private'), 1);
    }
    const apply = args.includes('--apply');
    if (apply) args.splice(args.indexOf('--apply'), 1);
    if (args.length) throw new Error(`Unknown option: ${args[0]}`);
    console.log(JSON.stringify(await publishRepository(directory, { repo, message, visibility, apply }), null, 2));
    return;
  }
  if (command === 'sync') {
    const config = option(args, '--config', true);
    const direction = option(args, '--direction') || 'pull';
    const message = option(args, '--message');
    const apply = args.includes('--apply');
    if (apply) args.splice(args.indexOf('--apply'), 1);
    if (args.length) throw new Error(`Unknown option: ${args[0]}`);
    console.log(JSON.stringify(await syncRepositories(path.resolve(config), { direction, message, apply }), null, 2));
    return;
  }
  throw new Error(`Unknown command: ${command}`);
}

(async () => {
  try {
    await main(process.argv.slice(2));
  } catch (error) {
    console.error(`repo-manager: ${error.message}`);
    process.exitCode = 1;
  }
})();
