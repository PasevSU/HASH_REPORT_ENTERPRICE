#!/usr/bin/env bash
# GitSU: allowlisted Git execution. Never eval user input.
set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0
export GIT_CONFIG_NOSYSTEM=0
umask 077
usage() { printf 'Usage: %s <operation> <repository> [remote]\n' "$0" >&2; exit 64; }
[[ $# -ge 2 && $# -le 4 ]] || usage
operation=$1; repo=$2; remote=${3:-origin}; value=${4:-}
if [[ "$operation" == clone ]]; then
  [[ $# -eq 4 ]] || usage
  [[ "$remote" =~ ^(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?|git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?)$ ]] || { echo 'ERROR: invalid GitHub URL' >&2; exit 64; }
  [[ ! -e "$repo" ]] || { echo 'ERROR: destination exists' >&2; exit 73; }
  [[ "$value" == CONFIRM ]] || { echo 'ERROR: confirmation required' >&2; exit 77; }
  git -c credential.interactive=never clone --progress -- "$remote" "$repo"
  exit
fi
[[ -d "$repo" ]] || { echo 'ERROR: directory does not exist' >&2; exit 66; }
command -v git >/dev/null || { echo 'ERROR: git missing' >&2; exit 69; }
if [[ "$operation" != commit && "$operation" != restore && "$operation" != restore-staged && "$operation" != config-get && "$operation" != config-set-local && "$operation" != archive && "$operation" != bundle-create ]]; then
  [[ "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$ ]] || { echo 'ERROR: invalid argument' >&2; exit 64; }
fi
# Disallow Git option injection; never pass arbitrary user-provided flags.
if [[ "$operation" != commit && "$operation" != restore && "$operation" != restore-staged && "$operation" != archive && "$operation" != bundle-create ]]; then
  [[ "$remote" != -* && "$remote" != */../* && "$remote" != *'..'* ]] || exit 64
fi
repo=$(cd -- "$repo" && pwd -P)
[[ -n "$repo" && "$repo" != '/' ]] || exit 64
# Never grant trust implicitly. Check Git's ownership protection first.
if [[ "$operation" == trust-check ]]; then
  git -C "$repo" rev-parse --show-toplevel
  exit
fi
if [[ "$operation" == trust-add ]]; then
  [[ ${GITSU_TRUST_CONFIRMED:-} == YES ]] || { echo 'ERROR: explicit trust confirmation required' >&2; exit 77; }
  # Only exact chosen directory, never '*' and never broad trust.
  git config --global --add safe.directory "$repo"
  git -C "$repo" rev-parse --show-toplevel
  exit
fi
# Git refuses dubious ownership here unless separately trusted.
git -C "$repo" rev-parse --is-inside-work-tree >/dev/null
# Reject invocation in a subfolder: operations must target repository root.
top=$(git -C "$repo" rev-parse --show-toplevel)
[[ "${top%/}" == "${repo%/}" ]] || { echo 'ERROR: select repository root' >&2; exit 65; }
case "$operation" in
  status) git -C "$repo" status --short --branch ;;
  verify) git -C "$repo" fsck --no-reflogs ;;
  branches) git -C "$repo" branch -avv ;;
  stash-list) git -C "$repo" stash list ;;
  tag-list) git -C "$repo" tag --list ;;
  diff-cached) git -C "$repo" diff --cached --stat ;;
  add-all) git -C "$repo" add --all ;;
  stash-push) git -C "$repo" stash push -m 'GitSU managed stash' ;;
  stash-pop) [[ "$remote" == CONFIRM ]] || exit 77; git -C "$repo" stash pop ;;
  commit)
    [[ $# -eq 3 && -n "$remote" && ${#remote} -le 500 ]] || usage
    git -C "$repo" diff --cached --quiet && { echo 'ERROR: no staged changes' >&2; exit 73; }
    git -C "$repo" commit -m "$remote" ;;
  create-branch|switch|tag-create)
    [[ "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$ && "$remote" != *..* && "$remote" != */*/* ]] || exit 64
    case "$operation" in
      create-branch) git -C "$repo" switch -c "$remote" ;;
      switch) git -C "$repo" switch "$remote" ;;
      tag-create) git -C "$repo" tag "$remote" ;;
    esac ;;
  remote-add|remote-set|remote-remove)
    [[ "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || exit 64
    if [[ "$operation" != remote-remove ]]; then
      [[ "$value" =~ ^(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?|git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?)$ ]] || exit 64
    fi
    case "$operation" in
      remote-add) git -C "$repo" remote add "$remote" "$value" ;;
      remote-set) [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77; git -C "$repo" remote set-url "$remote" "$value" ;;
      remote-remove) [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77; git -C "$repo" remote remove "$remote" ;;
    esac ;;
  restore|restore-staged)
    [[ $# -eq 3 && "$remote" != -* && "$remote" != /* && "$remote" != *..* ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    if [[ "$operation" == restore ]]; then git -C "$repo" restore -- "$remote"; else git -C "$repo" restore --staged -- "$remote"; fi ;;
  reset-soft)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" reset --soft HEAD~1 ;;
  rebase-ff)
    [[ -z "$(git -C "$repo" status --porcelain)" ]] || exit 73
    git -C "$repo" pull --ff-only --progress "$remote" ;;
  branch) git -C "$repo" branch --show-current ;;
  log) git -C "$repo" log -n 20 --format='%h %aI %s' ;;
  remote) git -C "$repo" remote -v ;;
  diff) git -C "$repo" diff --stat ;;
  fetch) git -C "$repo" -c credential.interactive=never fetch --progress --prune "$remote" ;;
  pull-ff)
    [[ -z "$(git -C "$repo" status --porcelain)" ]] || { echo 'ERROR: working tree not clean' >&2; exit 73; }
    git -C "$repo" -c credential.interactive=never pull --ff-only --progress "$remote" ;;
  push)
    branch=$(git -C "$repo" symbolic-ref --quiet --short HEAD) || { echo 'ERROR: detached HEAD' >&2; exit 65; }
    git -C "$repo" -c credential.interactive=never push --progress "$remote" "refs/heads/$branch:refs/heads/$branch" ;;
  # Read-only inspection and repository diagnostics
  show) git -C "$repo" show --stat --oneline HEAD ;;
  reflog) git -C "$repo" reflog -n 30 ;;
  fsck) git -C "$repo" fsck --full --no-reflogs ;;
  count-objects) git -C "$repo" count-objects -v ;;
  ls-files) git -C "$repo" ls-files ;;
  ls-tree) git -C "$repo" ls-tree -r --name-only HEAD ;;
  show-ref) git -C "$repo" show-ref ;;
  remote-show) git -C "$repo" remote show -n "$remote" ;;
  submodule-status) git -C "$repo" submodule status ;;
  worktree-list) git -C "$repo" worktree list --porcelain ;;
  stash-show) git -C "$repo" stash show --stat ;;
  shortlog) git -C "$repo" shortlog -sn HEAD ;;
  config-list-local) git -C "$repo" config --local --list ;;
  config-get)
    [[ $# -eq 3 && "$remote" =~ ^(user\.(name|email)|core\.(autocrlf|filemode)|pull\.rebase|init\.defaultBranch)$ ]] || exit 64
    git -C "$repo" config --local --get "$remote" ;;
  # Controlled mutation; confirmation is never inferred from GUI text.
  remote-rename)
    [[ $# -eq 4 && "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ && "$value" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" remote rename "$remote" "$value" ;;
  branch-delete)
    [[ $# -eq 3 && "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$ && "$remote" != *..* ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" branch -d "$remote" ;;
  merge-ff)
    [[ $# -eq 3 && "$remote" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$ && "$remote" != *..* ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    [[ -z "$(git -C "$repo" status --porcelain)" ]] || exit 73
    git -C "$repo" merge --ff-only "$remote" ;;
  revert-commit)
    [[ $# -eq 3 && "$remote" =~ ^[a-fA-F0-9]{7,40}$ ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    [[ -z "$(git -C "$repo" status --porcelain)" ]] || exit 73
    git -C "$repo" revert --no-edit "$remote" ;;
  stash-apply)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" stash apply ;;
  submodule-init)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" -c credential.interactive=never submodule update --init --recursive --progress ;;
  submodule-sync)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" submodule sync --recursive ;;
  maintenance-run)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" maintenance run ;;
  gc)
    [[ "$remote" == CONFIRM && ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" gc ;;
  config-set-local)
    [[ $# -eq 4 && "$remote" =~ ^(user\.(name|email)|core\.(autocrlf|filemode)|pull\.rebase)$ && -n "$value" && ${#value} -le 250 ]] || exit 64
    [[ ${GITSU_MUTATION_CONFIRMED:-} == YES ]] || exit 77
    git -C "$repo" config --local "$remote" "$value" ;;
  *) usage ;;
esac
