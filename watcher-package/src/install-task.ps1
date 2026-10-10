#Requires -Version 7
# Registers a per-user Scheduled Task that starts the watcher at logon and verifies it runs.
# Usage: pwsh install-task.ps1 [-Remove] [-Status] [-Name 'GitSU Watcher']
[CmdletBinding()]
param([switch]$Remove, [switch]$Status, [string]$Name = 'GitSU Watcher')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function ConvertTo-NativePath([string]$p) {
    $prefix = 'Microsoft.PowerShell.Core\FileSystem::'
    if ($p.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { return $p.Substring($prefix.Length) }
    $p
}

try {
    $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($Status) {
        if (-not $existing) { Write-Host "[INFO] Task '$Name' is not installed."; exit 0 }
        $i = Get-ScheduledTaskInfo -TaskName $Name
        Write-Host "Task: $Name | State: $($existing.State) | Last run: $($i.LastRunTime) | Result: $($i.LastTaskResult)"
        exit 0
    }
    if ($Remove) {
        if ($existing) {
            Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $Name -Confirm:$false
            Write-Host "[PASS] Removed task '$Name'."
        } else { Write-Host "[INFO] Task '$Name' is not installed." }
        exit 0
    }

    $script = ConvertTo-NativePath ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'gitsu-watcher.ps1')))
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw "WATCHER_NOT_FOUND: $script" }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'watcher.env'))) {
        Write-Warning 'watcher.env not found - copy watcher.env.example to watcher.env and configure it.'
    }
    $pwsh = (Get-Command pwsh -ErrorAction Stop).Source
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name

    $action = New-ScheduledTaskAction -Execute $pwsh -WorkingDirectory (Split-Path $script) `
        -Argument "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

    if ($existing) { Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue; Unregister-ScheduledTask -TaskName $Name -Confirm:$false }
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description 'GitSU Git watcher (poll/commit/push with write-lease).' -Force | Out-Null
    Start-ScheduledTask -TaskName $Name
    Start-Sleep -Seconds 3
    $t = Get-ScheduledTask -TaskName $Name
    if ($t.State -ne 'Running') { throw "TASK_NOT_RUNNING: state=$($t.State)" }
    Write-Host "[PASS] Task '$Name' registered and running as $user."
    exit 0
} catch {
    Write-Error "[FAIL] $($_.Exception.Message)"
    exit 1
}
