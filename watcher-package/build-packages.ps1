#Requires -Version 7
# Builds dist\gitsu-watcher-windows-<ver>.zip, dist\gitsu-watcher-ha-<ver>.tar.gz and SHA256SUMS.txt
param([string]$Version = '0.40.0')
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'src'; $dist = Join-Path $PSScriptRoot 'dist'
Remove-Item $dist -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory $dist | Out-Null
$sets = @{
  'windows' = @('gitsu-watcher.ps1','start-watcher.cmd','install-task.ps1','watcher.env.example','README-windows.md')
  'ha'      = @('gitsu-watcher.sh','start-watcher.sh','watcher.env.example','README-ha.md')
}
foreach ($k in $sets.Keys) {
  $stage = Join-Path $dist "stage-$k\gitsu-watcher"; New-Item -ItemType Directory $stage -Force | Out-Null
  foreach ($f in $sets[$k]) {
    $t = Join-Path $stage $f
    if ($f -like '*.sh') { [IO.File]::WriteAllText($t, ((Get-Content $src\$f -Raw) -replace "`r`n","`n")) } else { Copy-Item $src\$f $t }
  }
  "$Version" | Set-Content (Join-Path $stage 'VERSION')
  $out = Join-Path $dist "gitsu-watcher-$k-$Version"
  Push-Location (Split-Path $stage)
  if ($k -eq 'windows') { Compress-Archive -Path gitsu-watcher -DestinationPath "$out.zip" } else { tar -czf "$out.tar.gz" gitsu-watcher }
  Pop-Location
  Remove-Item (Split-Path $stage) -Recurse -Force
}
Get-ChildItem $dist -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content (Join-Path $dist 'SHA256SUMS.txt')
Get-ChildItem $dist | Select-Object Name, Length
