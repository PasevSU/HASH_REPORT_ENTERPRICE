@echo off
rem Report-name orchestrator of the ChronoSeal CLI edition.
rem Example: Run_Report.bat COMBO_ALL D:\cases\2026-08 --url https://host/static/
setlocal
python "%~dp0chronoseal_report.py" %*
exit /b %errorlevel%
