#!/usr/bin/env bash
set -euo pipefail
script=$(cd "$(dirname "$0")/../scripts" && pwd)/git-safe.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git init -q "$tmp/repo"
git -C "$tmp/repo" config user.name Test
git -C "$tmp/repo" config user.email test@example.invalid
printf 'hello\n' > "$tmp/repo/file"
git -C "$tmp/repo" add file
git -C "$tmp/repo" commit -qm initial
"$script" status "$tmp/repo" >/dev/null
"$script" log "$tmp/repo" | grep -q initial
"$script" branch "$tmp/repo" >/dev/null
if "$script" arbitrary "$tmp/repo" >/dev/null 2>&1; then exit 1; fi
if "$script" push "$tmp/repo" '--upload-pack=evil' >/dev/null 2>&1; then exit 1; fi
if "$script" trust-add "$tmp/repo" >/dev/null 2>&1; then exit 1; fi
if "$script" status "$tmp/repo/file" >/dev/null 2>&1; then exit 1; fi
printf 'PASS: 7 smoke assertions\n'
