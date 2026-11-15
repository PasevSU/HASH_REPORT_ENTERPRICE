@echo off
setlocal
if "%~1"=="" (echo Usage: %~nx0 INPUT_PATH OUTPUT_DIR --diagnostics-unsealed 1>&2 & exit /b 2)
if "%~2"=="" (echo Missing OUTPUT_DIR 1>&2 & exit /b 2)
if /I not "%~3"=="--diagnostics-unsealed" (
 echo BLOCKED: this runtime only creates unsealed diagnostic evidence. Pass --diagnostics-unsealed explicitly. 1>&2
 exit /b 2
)
if not "%~4"=="" (echo Unexpected extra argument. 1>&2 & exit /b 2)
echo WARNING: output is unsealed diagnostic evidence; RFC 3161 is not verified.
python "%~dp0..\chronoseal_process_cli.py" --profile single_pdf --source "%~1" --output "%~2" --allow-unsealed-diagnostics
exit /b %errorlevel%
