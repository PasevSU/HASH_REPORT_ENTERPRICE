@echo off
rem Usage: start-watcher.cmd [repo-path]   (configure via watcher.env)
if not "%~1"=="" set "REPO_PATH=%~1"
where pwsh >nul 2>nul || (echo PowerShell 7 ^(pwsh^) is required: winget install Microsoft.PowerShell & exit /b 1)
pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0gitsu-watcher.ps1"
