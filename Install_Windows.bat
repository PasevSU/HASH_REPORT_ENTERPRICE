@echo off
setlocal
cd /d "%~dp0"
where python.exe >nul 2>nul
if errorlevel 1 (
 echo ERROR: python.exe missing from PATH.
 pause
 exit /b 2
)
python.exe -c "import sys; print('Python:',sys.version.split()[0]); raise SystemExit(sys.version_info < (3,12))"
if errorlevel 1 (
 echo ERROR: Python 3.12 or newer is required. Install it and restart this installer.
 pause
 exit /b 11
)
where node.exe >nul 2>nul
if errorlevel 1 (
 echo ERROR: Node.js ^>=22.12 is required. Install Node.js and restart this installer.
 pause
 exit /b 5
)
node.exe -e "const [a,b,c]=process.versions.node.split('.').map(Number); if(a<22||(a===22&&(b<12||(b===12&&c<0)))) process.exit(1)"
if errorlevel 1 (
 echo ERROR: Node.js 22.12 or newer is required.
 pause
 exit /b 6
)
echo Installing PDF dependencies into the Python interpreter on PATH...
python.exe -m pip install -r "%~dp0requirements-integration.txt"
if errorlevel 1 (
 echo ERROR: Python dependency installation failed.
 pause
 exit /b 3
)
python.exe -c "import fitz,pypdf,reportlab,cryptography,signxml,lxml,requests,certifi; print('PDF, X.509, XML signature, and revocation dependencies OK')"
if errorlevel 1 (
 echo ERROR: PDF dependencies still unavailable.
 pause
 exit /b 4
)
python.exe -c "from chronoseal.settings import executable; p=executable('openssl'); print('OpenSSL:',p or 'MISSING'); raise SystemExit(p is None)"
if errorlevel 1 (
 echo ERROR: OpenSSL is required for independent RFC 3161 verification. Install it or configure it in Settings.
 pause
 exit /b 10
)
echo Installing the locked RFC 3161 runtime dependency...
call npm install --ignore-scripts --no-audit --no-fund
if errorlevel 1 (
 echo ERROR: Node dependency installation failed.
 pause
 exit /b 7
)
echo Verifying and repairing every dependency (vendored pin)...
python.exe -m chronoseal.selfheal
if errorlevel 1 (
 echo ERROR: Dependency self-check failed. See the blockers above.
 pause
 exit /b 12
)
call npm run doctor
if errorlevel 1 (
 echo ERROR: RFC 3161 Node dependency failed its import check.
 pause
 exit /b 8
)
call npm run verify:vendor
if errorlevel 1 (
 echo ERROR: Bundled RFC 3161 vendor integrity check failed.
 pause
 exit /b 9
)
echo Dependencies ready. Launching ChronoSeal...
call Start_ChronoSeal.bat
