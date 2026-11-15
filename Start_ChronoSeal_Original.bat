@echo off
setlocal
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python / pythonw.exe was not found.
  echo Install Python 3.12+ and enable "Add Python to PATH", then run this file again.
  pause
  exit /b 2
)
start "ChronoSeal" pythonw.exe ChronoSeal_GUI.pyw
