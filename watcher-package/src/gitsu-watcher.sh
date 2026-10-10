#!/usr/bin/env bash
# GitSU Watcher (Linux / Home Assistant). Same behaviour as gitsu-watcher.ps1.
# Config via environment or watcher.env next to this script.
# Modes:  (none) run watcher | --lease-status | --lease-break
set -uo pipefail
export GIT_TERMINAL_PROMPT=0
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ -f "$here/watcher.env" ]] && { set -a; . "$here/watcher.env"; set +a; }

repo=${REPO_PATH:-$PWD}
debounce=${DEBOUNCE:-30}
poll=${POLL_INTERVAL:-5}
apply=${APPLY:-0}
scan=${SECRET_SCAN:-1}
stage_untracked=${STAGE_UNTRACKED:-0}
max_backoff=${MAX_BACKOFF:-900}
lease_on=${LEASE:-1}
ttl=${LEASE_TTL:-180}
grace=${LEASE_GRACE:-30}
follow=${FOLLOW:-1}
follow_interval=${FOLLOW_INTERVAL:-30}
node_name=${NODE_ID:-$(hostname 2>/dev/null || echo node)}
mode=${1:-run}
for v in "$debounce" "$max_backoff" "$grace" "$follow_interval" "$ttl"; do [[ $v =~ ^[0-9]+$ ]] || { echo 'Invalid numeric setting' >&2; exit 2; }; done
[[ $poll =~ ^[1-9][0-9]*$ ]] && (( ttl >= 15 )) || { echo 'Invalid intervals (LEASE_TTL >= 15)' >&2; exit 2; }

cd -- "$repo" || { echo "Cannot enter $repo" >&2; exit 2; }
[[ -z $(git rev-parse --show-cdup 2>/dev/null) && $(git rev-parse --is-inside-work-tree 2>/dev/null) == true ]] || { echo 'Not repository root' >&2; exit 2; }
branch=${BRANCH:-$(git branch --show-current)}
[[ -n $branch && $(git branch --show-current) == "$branch" ]] || { echo 'Wrong branch / detached HEAD' >&2; exit 2; }
git remote get-url origin >/dev/null 2>&1 || { echo 'Missing origin' >&2; exit 2; }

gitdir=$(git rev-parse --absolute-git-dir)
logfile=${LOG_FILE:-$gitdir/gitsu-watcher.log}
state=INIT
log() {
  local line; line="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [$state] $*"
  echo "$line"; echo "$line" >> "$logfile" 2>/dev/null || true
  if [[ -f $logfile ]] && (( $(wc -c < "$logfile") > 1048576 )); then mv -f "$logfile" "$logfile.1"; fi
}
now() { date +%s; }

# ---- Distributed lease: a CAS-updated ref on origin (refs/gitsu/lease/<branch>) ----
# Only the holder may commit/push. Others fast-forward (FOLLOWING). Clocks must be NTP-synced.
me="$node_name:$$:$RANDOM"
lref="refs/gitsu/lease/$branch"
held_sha=""; last_renew=0; last_attempt=0
r_sha=""; r_owner=""; r_node=""; r_exp=0

mk_lease() {
  git -c user.name=gitsu -c user.email=gitsu@localhost commit-tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904 \
    -m "gitsu-lease $me
owner=$me
node=$node_name
expires=$(( $(now) + ttl ))"
}
lease_remote() { # 0 ok, 2 network/read error
  local out; r_sha=""; r_owner=""; r_node=""; r_exp=0
  out=$(git ls-remote origin "$lref" 2>/dev/null) || return 2
  r_sha=$(cut -f1 <<<"$out"); [[ -n $r_sha ]] || return 0
  git fetch -q --no-tags origin "$lref" 2>/dev/null || return 2
  local body; body=$(git cat-file commit "$r_sha" 2>/dev/null) || return 2
  r_owner=$(sed -n 's/^owner=//p' <<<"$body" | head -1)
  r_node=$(sed -n 's/^node=//p' <<<"$body" | head -1)
  r_exp=$(sed -n 's/^expires=//p' <<<"$body" | head -1); r_exp=${r_exp:-0}
}
lease_try() { # 0 held by me, 1 held by other, 2 network error
  lease_remote || return 2
  if [[ -n $r_sha && $r_owner != "$me" ]]; then
    (( $(now) <= r_exp + grace )) && return 1
    log "Taking over expired lease from $r_node"
  fi
  local new; new=$(mk_lease) || return 2
  if git push -q origin --force-with-lease="$lref:$r_sha" "$new:$lref" 2>/dev/null; then held_sha=$new; last_renew=$(now); return 0; fi
  return 1
}
lease_release() {
  [[ -n $held_sha ]] || return 0
  git push -q origin --force-with-lease="$lref:$held_sha" ":$lref" 2>/dev/null && log "Lease released"
  held_sha=""
}

case $mode in
  --lease-status)
    lease_remote || { echo 'Cannot read lease (network?)' >&2; exit 2; }
    if [[ -z $r_sha ]]; then echo "No lease holder for $branch"; else echo "Holder: $r_node ($r_owner) expires in $(( r_exp - $(now) ))s"; fi; exit 0 ;;
  --lease-break)
    lease_remote || { echo 'Cannot read lease' >&2; exit 2; }
    [[ -n $r_sha ]] || { echo 'No lease to break'; exit 0; }
    git push -q origin --force-with-lease="$lref:$r_sha" ":$lref" && echo "Lease of $r_node broken" || { echo 'Break failed' >&2; exit 1; }; exit 0 ;;
  run) ;;
  *) echo "Unknown mode $mode" >&2; exit 2 ;;
esac

# ---- Local locks ----
lock="$gitdir/gitsu-watcher.lock"
if ! mkdir "$lock" 2>/dev/null; then
  old=$(cat "$lock/pid" 2>/dev/null || true)
  if [[ -n $old ]] && kill -0 "$old" 2>/dev/null; then echo "Watcher already running (pid $old)" >&2; exit 3; fi
  rm -rf "$lock"; mkdir "$lock" 2>/dev/null || { echo 'Lock unavailable' >&2; exit 3; }
  echo 'Recovered stale lock' >&2
fi
echo $$ > "$lock/pid"
cleanup() { lease_release; rm -rf "$lock" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT TERM

oplock="$gitdir/gitsu-op.lock"
take_oplock() {
  if mkdir "$oplock" 2>/dev/null; then echo $$ > "$oplock/pid"; return 0; fi
  local p; p=$(cat "$oplock/pid" 2>/dev/null || true)
  if [[ -n $p ]] && kill -0 "$p" 2>/dev/null; then return 1; fi
  rm -rf "$oplock"; mkdir "$oplock" 2>/dev/null && echo $$ > "$oplock/pid"
}
release_oplock() { rm -rf "$oplock" 2>/dev/null || true; }

fingerprint() { git status --porcelain=v1 --untracked-files=no | git hash-object --stdin; }
is_dirty() { [[ -n $(git status --porcelain=v1 --untracked-files=no) ]]; }

secret_scan() {
  [[ $scan == 1 ]] || return 0
  local bad
  bad=$(git diff --cached --name-only --diff-filter=ACMR | grep -Ei '(^|/)(\.env(\..*)?|id_(rsa|ed25519|ecdsa|dsa)|secrets\.ya?ml|.*\.(pem|key|pfx|p12|kdbx))$' || true)
  if [[ -n $bad ]]; then log "SECRET BLOCK: sensitive file names staged: $(echo "$bad" | tr '\n' ' ')"; return 1; fi
  if git diff --cached -U0 --no-color | grep -E '^\+' | grep -Eq -- '-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}'; then
    log 'SECRET BLOCK: staged diff contains a key/token pattern'; return 1
  fi
  return 0
}

fails=0; hold=0
backoff() {
  fails=$((fails+1)); local w=$((debounce * (1 << (fails>6?6:fails-1)) ))
  (( w > max_backoff )) && w=$max_backoff; (( w < 5 )) && w=5
  hold=$(( $(now) + w )); log "Retry delayed ${w}s (failure #$fails)"
}

use_lease=0; [[ $apply == 1 && $lease_on != 0 ]] && use_lease=1
leader=1; (( use_lease )) && leader=0
last_follow=0; renew_every=$(( ttl / 3 )); (( renew_every < 5 )) && renew_every=5

lease_tick() {
  (( use_lease )) || return 0
  local t rc; t=$(now)
  (( t - last_attempt >= renew_every )) || return 0
  last_attempt=$t
  lease_try; rc=$?
  if (( rc == 0 )); then
    if (( ! leader )); then leader=1; state=IDLE; log "LEASE ACQUIRED ($node_name)"; fi
  elif (( rc == 1 )); then
    if (( leader )); then leader=0; held_sha=""; state=FOLLOWING; log "LEASE LOST: held by $r_node"; fi
  else
    if (( leader )) && (( t - last_renew >= ttl - grace )); then leader=0; held_sha=""; state=FOLLOWING; log 'LEASE LOST: cannot renew (network)'; fi
  fi
}
follow_tick() {
  (( ! leader )) && [[ $follow == 1 ]] || return 0
  local t; t=$(now); (( t - last_follow >= follow_interval )) || return 0; last_follow=$t
  git fetch -q --no-tags origin "$branch" 2>/dev/null || return 0
  git merge-base --is-ancestor HEAD "refs/remotes/origin/$branch" || return 0
  [[ $(git rev-parse HEAD) == "$(git rev-parse "refs/remotes/origin/$branch")" ]] && return 0
  if git merge --ff-only -q "refs/remotes/origin/$branch" 2>/dev/null; then state=FOLLOWING; log "FOLLOWED origin/$branch -> $(git rev-parse --short HEAD)"; previous=$(fingerprint)
  else log 'FOLLOW blocked by local changes'; fi
}

state=IDLE
log "Watcher started repo=$repo branch=$branch apply=$apply lease=$use_lease node=$node_name secret_scan=$scan pid=$$"
previous=$(fingerprint); changed=$(now)
while :; do
  sleep "$poll"
  lease_tick
  follow_tick
  state=IDLE; (( use_lease && ! leader )) && state=FOLLOWING
  current=$(fingerprint)
  if [[ $current != "$previous" ]]; then previous=$current; changed=$(now); state=CHANGED; continue; fi
  if ! is_dirty; then fails=0; continue; fi
  t=$(now)
  (( t - changed >= debounce && t >= hold )) || { state=STABILIZING; continue; }
  if [[ $apply != 1 ]]; then state=CHANGED; log 'DRY RUN: tracked changes detected; no commit/push'; changed=$t; continue; fi
  if (( ! leader )); then log "Not the writer: lease held by ${r_node:-another node}; local changes stay unpublished"; changed=$t; continue; fi
  if [[ $(git branch --show-current) != "$branch" ]]; then state=FAILED; log 'Branch changed; stopping'; exit 4; fi
  take_oplock || { state=STABILIZING; log 'Another Git operation holds the repo lock'; continue; }
  if (( use_lease )); then
    last_attempt=$(now)
    if ! lease_try; then leader=0; held_sha=""; state=FOLLOWING; log 'LEASE LOST before write; aborting cycle'; release_oplock; continue; fi
  fi

  state=FETCHING
  if ! git fetch --no-tags origin "$branch"; then state=FAILED; log 'Fetch failed; no commit'; release_oplock; backoff; continue; fi
  remote_head=$(git rev-parse "refs/remotes/origin/$branch")
  if ! git merge-base --is-ancestor "$remote_head" HEAD; then
    if git merge-base --is-ancestor HEAD "$remote_head" && git merge --ff-only -q "$remote_head" 2>/dev/null; then log "Fast-forwarded to origin/$branch before commit"
    else state=CONFLICT; log 'Remote ahead or diverged: manual reconciliation required'; release_oplock; backoff; continue; fi
  fi

  state=COMMITTING
  index_before=$(git write-tree 2>/dev/null || true)
  if [[ $stage_untracked == 1 ]]; then git add -A -- .; else git add -u -- .; fi
  if git diff --cached --quiet; then release_oplock; previous=$(fingerprint); continue; fi
  if ! secret_scan; then
    state=FAILED
    if [[ -n $index_before ]]; then git read-tree -q "$index_before" 2>/dev/null || git reset -q; else git reset -q; fi
    release_oplock; backoff; continue
  fi
  if ! git -c core.quotepath=false commit -q -m "auto-sync($node_name): $(date -u '+%Y-%m-%dT%H:%M:%SZ')"; then state=FAILED; log 'Commit failed'; release_oplock; backoff; continue; fi

  state=PUSHING
  if git push -q origin "HEAD:refs/heads/$branch"; then
    local_sha=$(git rev-parse HEAD)
    remote_sha=$(git ls-remote origin "refs/heads/$branch" 2>/dev/null | cut -f1)
    if [[ $remote_sha == "$local_sha" ]]; then state=VERIFIED; log "PUSH VERIFIED $local_sha"; fails=0
    else state=FAILED; log "PUSH UNVERIFIED local=$local_sha remote=${remote_sha:-unknown}"; backoff; fi
  else
    state=FAILED; log 'PUSH FAILED: local commit retained'; backoff
  fi
  release_oplock
  previous=$(fingerprint); changed=$(now)
done
