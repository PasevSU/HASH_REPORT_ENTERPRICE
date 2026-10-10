#!/usr/bin/env bash
# Usage: start-watcher.sh [repo-path]   (configure via watcher.env)
[[ -n ${1:-} ]] && export REPO_PATH=$1
exec bash "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/gitsu-watcher.sh"
