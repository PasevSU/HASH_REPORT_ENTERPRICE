# GitSU Watcher (Windows, PowerShell 7+). Same behaviour as gitsu-watcher.sh.
# Config via environment or watcher.env next to this script.
# Modes: (none) run watcher | -Mode lease-status | -Mode lease-break
param([ValidateSet('run','lease-status','lease-break')][string]$Mode = 'run')
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $here 'watcher.env'
if (Test-Path -LiteralPath $envFile) {
  foreach ($l in Get-Content -LiteralPath $envFile) {
    if ($l -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$' -and -not [Environment]::GetEnvironmentVariable($Matches[1])) {
      [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'))
    }
  }
}
function EnvInt($n, $d) { $v = [Environment]::GetEnvironmentVariable($n); if ($v) { [int]$v } else { $d } }
$repo = if ($env:REPO_PATH) { $env:REPO_PATH } else { (Get-Location).Path }
$debounce = EnvInt 'DEBOUNCE' 30
$poll = EnvInt 'POLL_INTERVAL' 5
$maxBackoff = EnvInt 'MAX_BACKOFF' 900
$ttl = EnvInt 'LEASE_TTL' 180
$grace = EnvInt 'LEASE_GRACE' 30
$followInterval = EnvInt 'FOLLOW_INTERVAL' 30
$apply = $env:APPLY -eq '1'
$scan = $env:SECRET_SCAN -ne '0'
$stageUntracked = $env:STAGE_UNTRACKED -eq '1'
$follow = $env:FOLLOW -ne '0'
$leaseOn = $env:LEASE -ne '0'
$nodeName = if ($env:NODE_ID) { $env:NODE_ID } else { [Environment]::MachineName }
if ($poll -lt 1 -or $debounce -lt 0 -or $ttl -lt 15 -or $grace -lt 0) { throw 'Invalid intervals (LEASE_TTL >= 15)' }

Set-Location -LiteralPath $repo
$root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0) { throw 'Not a Git repository' }
if (([IO.Path]::GetFullPath($root).TrimEnd('\','/')) -ne ([IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\','/'))) { throw 'Not repository root' }
$branch = if ($env:BRANCH) { $env:BRANCH } else { (& git branch --show-current) }
if (-not $branch -or (& git branch --show-current) -ne $branch) { throw 'Wrong branch / detached HEAD' }
& git remote get-url origin *> $null
if ($LASTEXITCODE -ne 0) { throw 'Missing origin' }

$gitdir = (& git rev-parse --absolute-git-dir)
$logFile = if ($env:LOG_FILE) { $env:LOG_FILE } else { Join-Path $gitdir 'gitsu-watcher.log' }
$script:state = 'INIT'
function Log($m) {
  $line = "$((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')) [$script:state] $m"
  Write-Host $line
  try {
    Add-Content -LiteralPath $logFile -Value $line
    if ((Get-Item -LiteralPath $logFile).Length -gt 1MB) { Move-Item -LiteralPath $logFile "$logFile.1" -Force }
  } catch {}
}
function Now { [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

# ---- Distributed lease: a CAS-updated ref on origin (refs/gitsu/lease/<branch>) ----
# Only the holder may commit/push. Others fast-forward (FOLLOWING). Clocks must be NTP-synced.
$me = "${nodeName}:${PID}:$(Get-Random -Maximum 32768)"
$lref = "refs/gitsu/lease/$branch"
$script:heldSha = ''; $script:lastRenew = 0; $script:lastAttempt = 0
$script:rSha = ''; $script:rOwner = ''; $script:rNode = ''; $script:rExp = 0
$emptyTree = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

function MkLease {
  $msg = "gitsu-lease $me`nowner=$me`nnode=$nodeName`nexpires=$((Now) + $ttl)"
  $sha = (& git -c user.name=gitsu -c user.email=gitsu@localhost commit-tree $emptyTree -m $msg)
  if ($LASTEXITCODE -ne 0) { return $null }
  $sha
}
function LeaseRemote { # 0 ok, 2 error
  $script:rSha = ''; $script:rOwner = ''; $script:rNode = ''; $script:rExp = 0
  $out = & git ls-remote origin $lref 2>$null
  if ($LASTEXITCODE -ne 0) { return 2 }
  if (-not $out) { return 0 }
  $script:rSha = ($out -split "\s+")[0]
  & git fetch -q --no-tags origin $lref 2>$null
  if ($LASTEXITCODE -ne 0) { return 2 }
  $body = (& git cat-file commit $script:rSha 2>$null) -join "`n"
  if ($LASTEXITCODE -ne 0) { return 2 }
  if ($body -match '(?m)^owner=(.*)$') { $script:rOwner = $Matches[1].Trim() }
  if ($body -match '(?m)^node=(.*)$') { $script:rNode = $Matches[1].Trim() }
  if ($body -match '(?m)^expires=(\d+)') { $script:rExp = [int64]$Matches[1] }
  0
}
function LeaseTry { # 0 mine, 1 other, 2 error
  if ((LeaseRemote) -ne 0) { return 2 }
  if ($script:rSha -and $script:rOwner -ne $me) {
    if ((Now) -le $script:rExp + $grace) { return 1 }
    Log "Taking over expired lease from $($script:rNode)"
  }
  $new = MkLease
  if (-not $new) { return 2 }
  & git push -q origin "--force-with-lease=${lref}:$($script:rSha)" "${new}:${lref}" 2>$null
  if ($LASTEXITCODE -eq 0) { $script:heldSha = $new; $script:lastRenew = Now; return 0 }
  1
}
function LeaseRelease {
  if (-not $script:heldSha) { return }
  & git push -q origin "--force-with-lease=${lref}:$($script:heldSha)" ":$lref" 2>$null
  if ($LASTEXITCODE -eq 0) { Log 'Lease released' }
  $script:heldSha = ''
}

if ($Mode -eq 'lease-status') {
  if ((LeaseRemote) -ne 0) { Write-Error 'Cannot read lease (network?)'; exit 2 }
  if (-not $script:rSha) { "No lease holder for $branch" } else { "Holder: $($script:rNode) ($($script:rOwner)) expires in $($script:rExp - (Now))s" }
  exit 0
}
if ($Mode -eq 'lease-break') {
  if ((LeaseRemote) -ne 0) { Write-Error 'Cannot read lease'; exit 2 }
  if (-not $script:rSha) { 'No lease to break'; exit 0 }
  & git push -q origin "--force-with-lease=${lref}:$($script:rSha)" ":$lref"
  if ($LASTEXITCODE -eq 0) { "Lease of $($script:rNode) broken"; exit 0 } else { Write-Error 'Break failed'; exit 1 }
}

# ---- Local locks ----
function PidAlive($p) { if (-not $p) { return $false }; [bool](Get-Process -Id ([int]$p) -ErrorAction SilentlyContinue) }
function TakeLock($dir) {
  try { New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null }
  catch {
    $old = Get-Content -LiteralPath (Join-Path $dir 'pid') -ErrorAction SilentlyContinue
    if (PidAlive $old) { return $false }
    Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    try { New-Item -ItemType Directory -Path $dir -ErrorAction Stop | Out-Null } catch { return $false }
  }
  Set-Content -LiteralPath (Join-Path $dir 'pid') -Value $PID
  $true
}
function ReleaseLock($dir) { Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue }

$lock = Join-Path $gitdir 'gitsu-watcher.lock'
$oplock = Join-Path $gitdir 'gitsu-op.lock'
if (-not (TakeLock $lock)) { throw 'Watcher already running or lock unavailable' }

function Snapshot { ((& git status --porcelain=v1 --untracked-files=no) -join "`n") }
function SecretScan {
  if (-not $scan) { return $true }
  $names = & git diff --cached --name-only --diff-filter=ACMR
  $bad = $names | Where-Object { $_ -match '(^|/)(\.env(\..*)?|id_(rsa|ed25519|ecdsa|dsa)|secrets\.ya?ml|.*\.(pem|key|pfx|p12|kdbx))$' }
  if ($bad) { Log "SECRET BLOCK: sensitive file names staged: $($bad -join ' ')"; return $false }
  $added = (& git diff --cached -U0 --no-color) | Where-Object { $_ -match '^\+' }
  if ($added -match '-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}') {
    Log 'SECRET BLOCK: staged diff contains a key/token pattern'; return $false
  }
  $true
}
$script:fails = 0; $script:hold = 0
function Backoff {
  $script:fails++
  $w = [Math]::Min($maxBackoff, [Math]::Max(5, $debounce * [Math]::Pow(2, [Math]::Min(6, $script:fails - 1))))
  $script:hold = (Now) + $w; Log "Retry delayed ${w}s (failure #$($script:fails))"
}

$useLease = $apply -and $leaseOn
$script:leader = -not $useLease
$script:lastFollow = 0
$renewEvery = [Math]::Max(5, [int]($ttl / 3))

function LeaseTick {
  if (-not $useLease) { return }
  $t = Now
  if ($t - $script:lastAttempt -lt $renewEvery) { return }
  $script:lastAttempt = $t
  $rc = LeaseTry
  if ($rc -eq 0) {
    if (-not $script:leader) { $script:leader = $true; $script:state = 'IDLE'; Log "LEASE ACQUIRED ($nodeName)" }
  } elseif ($rc -eq 1) {
    if ($script:leader) { $script:leader = $false; $script:heldSha = ''; $script:state = 'FOLLOWING'; Log "LEASE LOST: held by $($script:rNode)" }
  } elseif ($script:leader -and ($t - $script:lastRenew -ge $ttl - $grace)) {
    $script:leader = $false; $script:heldSha = ''; $script:state = 'FOLLOWING'; Log 'LEASE LOST: cannot renew (network)'
  }
}
function FollowTick {
  if ($script:leader -or -not $follow) { return }
  $t = Now
  if ($t - $script:lastFollow -lt $followInterval) { return }
  $script:lastFollow = $t
  & git fetch -q --no-tags origin $branch 2>$null
  if ($LASTEXITCODE -ne 0) { return }
  & git merge-base --is-ancestor HEAD "refs/remotes/origin/$branch"
  if ($LASTEXITCODE -ne 0) { return }
  if ((& git rev-parse HEAD) -eq (& git rev-parse "refs/remotes/origin/$branch")) { return }
  & git merge --ff-only -q "refs/remotes/origin/$branch" 2>$null
  if ($LASTEXITCODE -eq 0) { $script:state = 'FOLLOWING'; Log "FOLLOWED origin/$branch -> $(& git rev-parse --short HEAD)"; $script:previous = Snapshot }
  else { Log 'FOLLOW blocked by local changes' }
}

$script:state = 'IDLE'
Log "Watcher started repo=$repo branch=$branch apply=$apply lease=$useLease node=$nodeName secret_scan=$scan pid=$PID"
$script:previous = Snapshot
$last = Now
try {
  while ($true) {
    Start-Sleep -Seconds $poll
    LeaseTick
    FollowTick
    $script:state = if ($useLease -and -not $script:leader) { 'FOLLOWING' } else { 'IDLE' }
    $current = Snapshot
    if ($current -cne $script:previous) { $script:previous = $current; $last = Now; $script:state = 'CHANGED'; continue }
    if (-not $current) { $script:fails = 0; continue }
    $t = Now
    if (($t - $last) -lt $debounce -or $t -lt $script:hold) { $script:state = 'STABILIZING'; continue }
    if (-not $apply) { $script:state = 'CHANGED'; Log 'DRY RUN: tracked changes detected; no commit/push'; $last = $t; continue }
    if (-not $script:leader) { Log "Not the writer: lease held by $(if ($script:rNode) { $script:rNode } else { 'another node' }); local changes stay unpublished"; $last = $t; continue }
    if ((& git branch --show-current) -ne $branch) { $script:state = 'FAILED'; Log 'Branch changed; stopping'; exit 4 }
    if (-not (TakeLock $oplock)) { $script:state = 'STABILIZING'; Log 'Another Git operation holds the repo lock'; continue }
    try {
      if ($useLease) {
        $script:lastAttempt = Now
        if ((LeaseTry) -ne 0) { $script:leader = $false; $script:heldSha = ''; $script:state = 'FOLLOWING'; Log 'LEASE LOST before write; aborting cycle'; continue }
      }
      $script:state = 'FETCHING'
      & git fetch --no-tags origin $branch
      if ($LASTEXITCODE -ne 0) { $script:state = 'FAILED'; Log 'Fetch failed; no commit'; Backoff; continue }
      $remoteHead = (& git rev-parse "refs/remotes/origin/$branch")
      & git merge-base --is-ancestor $remoteHead HEAD
      if ($LASTEXITCODE -ne 0) {
        & git merge-base --is-ancestor HEAD $remoteHead
        $canFf = $LASTEXITCODE -eq 0
        if ($canFf) { & git merge --ff-only -q $remoteHead 2>$null; $canFf = $LASTEXITCODE -eq 0 }
        if ($canFf) { Log "Fast-forwarded to origin/$branch before commit" }
        else { $script:state = 'CONFLICT'; Log 'Remote ahead or diverged: manual reconciliation required'; Backoff; continue }
      }

      $script:state = 'COMMITTING'
      $indexBefore = (& git write-tree)
      if ($stageUntracked) { & git add -A -- . } else { & git add -u -- . }
      if ($LASTEXITCODE -ne 0) { $script:state = 'FAILED'; Log 'Staging failed'; Backoff; continue }
      & git diff --cached --quiet
      if ($LASTEXITCODE -eq 0) { $script:previous = Snapshot; continue }
      if (-not (SecretScan)) {
        $script:state = 'FAILED'
        if ($indexBefore) { & git read-tree -q $indexBefore 2>$null } else { & git reset -q }
        Backoff; continue
      }
      & git -c core.quotepath=false commit -q -m "auto-sync($nodeName): $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))"
      if ($LASTEXITCODE -ne 0) { $script:state = 'FAILED'; Log 'Commit failed'; Backoff; continue }

      $script:state = 'PUSHING'
      & git push -q origin "HEAD:refs/heads/$branch"
      if ($LASTEXITCODE -eq 0) {
        $localSha = (& git rev-parse HEAD)
        $remoteSha = ((& git ls-remote origin "refs/heads/$branch") -split "\s+")[0]
        if ($remoteSha -eq $localSha) { $script:state = 'VERIFIED'; Log "PUSH VERIFIED $localSha"; $script:fails = 0 }
        else { $script:state = 'FAILED'; Log "PUSH UNVERIFIED local=$localSha remote=$remoteSha"; Backoff }
      } else { $script:state = 'FAILED'; Log 'PUSH FAILED: local commit retained'; Backoff }
      $script:previous = Snapshot; $last = Now
    } finally { ReleaseLock $oplock }
  }
} finally { LeaseRelease; ReleaseLock $lock }
