@echo off
setlocal
rem pushd maps UNC paths (NAS) to a temporary drive letter; "cd /d" does not support UNC.
rem The mapping is released automatically when this script exits.
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (echo Cannot open folder "%~dp0" & pause & exit /b 1)
where py >nul 2>&1
if not errorlevel 1 (py -3 "%~dp0gui.py" & exit /b)
where python >nul 2>&1
if not errorlevel 1 (python "%~dp0gui.py" & exit /b)
echo Python 3 is required to run the source-based portable launcher.
pause
exit /b 1
