@echo off
setlocal
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if errorlevel 1 (echo Python is required.& pause & exit /b 1)
start "ChronoSeal" pythonw.exe "ChronoSeal_GUI.pyw"
