@echo off
setlocal
cd /d "%~dp0"
echo ==== ChronoSeal Windows Diagnostics ====
python --version
if errorlevel 1 goto :fail
node --version
if errorlevel 1 goto :fail
where node
if errorlevel 1 goto :fail
where openssl
python -c "from chronoseal.settings import executable; p=executable('openssl'); print('OpenSSL:',p or 'MISSING'); raise SystemExit(p is None)"
if errorlevel 1 goto :fail
call npm ls --depth=0
if errorlevel 1 goto :fail
python -m chronoseal.selfheal
if errorlevel 1 goto :fail
call npm run doctor
if errorlevel 1 goto :fail
call npm run verify:vendor
if errorlevel 1 goto :fail
python -m unittest discover -s tests
if errorlevel 1 goto :fail
python -m unittest discover -s hash_report_generator\tests
if errorlevel 1 goto :fail
python test_all_report_imports.py
if errorlevel 1 goto :fail
node --check bridge\stamp.mjs
if errorlevel 1 goto :fail
echo ALL CONFIGURED DIAGNOSTIC CHECKS PASSED.
pause
exit /b 0
:fail
echo DIAGNOSTICS FAILED. Review the first failing command above.
pause
exit /b 1
