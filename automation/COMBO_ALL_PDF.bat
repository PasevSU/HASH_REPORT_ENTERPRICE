@echo off
setlocal
if "%~1"=="" (echo Usage: %~nx0 INPUT_PATH OUTPUT_DIR EMBED_PDF [before^|after] 1>&2 & exit /b 2)
if "%~2"=="" (echo Missing OUTPUT_DIR 1>&2 & exit /b 2)
if "%~3"=="" (echo Missing EMBED_PDF 1>&2 & exit /b 2)
set "POS=%~4"
if "%POS%"=="" set "POS=after"
if /I not "%POS%"=="before" if /I not "%POS%"=="after" (
 echo BLOCKED: position must be before or after. 1>&2
 exit /b 2
)
if not exist "%~3" (echo BLOCKED: embedded PDF not found: %~3 1>&2 & exit /b 2)
echo This wrapper creates SEALED evidence (RFC 3161) and includes %~3 as COMBO_ALL_PDF.
python "%~dp0..\chronoseal_cli.py" "%~1" --output-dir "%~2" --embed-pdf "%~3" --embed-position "%POS%" --recursive
exit /b %errorlevel%
