@echo off
setlocal EnableDelayedExpansion
title ChronoSeal HASH REPORT - JavaScript clone

pushd "%~dp0.." 2>nul
if errorlevel 1 (
  echo Cannot enter the repository root from "%~dp0".
  pause
  exit /b 2
)

where node >nul 2>nul
if errorlevel 1 (
  echo BLOCKED: Node.js was not found on PATH.
  pause
  exit /b 2
)

set "SOURCE="
set "OUTPUT="
set "FILES="
set "FILTERS="
set "RECURSIVE=0"
set "PERFILE=0"
set "ARCHIVE=config"
set "STRICT=0"
set "EMBED=0"
set "EMBEDPDF="
set "EMBEDPOS=after"
set "PROFILE=auto"

:MENU
cls
echo ================================================================
echo   ChronoSeal HASH REPORT - JavaScript clone
echo   repository: %CD%
echo ================================================================
echo   1. Source folder or single file ........ [%SOURCE%]
echo   2. Recursive, include subfolders ....... %RECURSIVE%
echo   3. Add filter pattern .................. [%FILTERS%]
echo   4. Clear filters
echo   5. Output folder ....................... [%OUTPUT%]
echo   6. One report per file (per-file) ...... %PERFILE%
echo   7. Archive ............................. %ARCHIVE%
echo   8. Strict layout gate .................. %STRICT%
echo   9. Explicit file list .................. [%FILES%]
echo  10. Embedded source PDF (one PDF) ....... %EMBED%
echo  11. Report type ........................ [%PROFILE%]
echo  12. PDF to include ..................... [%EMBEDPDF%]
echo  13. Where it goes ...................... %EMBEDPOS%
echo ----------------------------------------------------------------
echo   R. Run        H. Help        Q. Quit
echo ================================================================
set "CHOICE="
set /p "CHOICE=Choice> "
if /i "%CHOICE%"=="1" goto :SETSOURCE
if /i "%CHOICE%"=="2" goto :TOGRECURSIVE
if /i "%CHOICE%"=="3" goto :ADDFILTER
if /i "%CHOICE%"=="4" (
  set "FILTERS="
  goto :MENU
)
if /i "%CHOICE%"=="5" goto :SETOUTPUT
if /i "%CHOICE%"=="6" goto :TOGPERFILE
if /i "%CHOICE%"=="7" goto :CYCLEARCHIVE
if /i "%CHOICE%"=="8" goto :TOGSTRICT
if /i "%CHOICE%"=="9" goto :SETFILES
if /i "%CHOICE%"=="10" goto :TOGEMBED
if /i "%CHOICE%"=="11" goto :CYCLEPROFILE
if /i "%CHOICE%"=="12" goto :SETEMBEDPDF
if /i "%CHOICE%"=="13" goto :TOGEMBEDPOS
if /i "%CHOICE%"=="R" goto :RUN
if /i "%CHOICE%"=="H" goto :HELP
if /i "%CHOICE%"=="Q" goto :END
goto :MENU

:SETSOURCE
echo.
set "ANSWER="
set /p "ANSWER=Folder or file (drag and drop works, empty keeps current)> "
if not "%ANSWER%"=="" (
  set "ANSWER=%ANSWER:"=%"
  set "SOURCE=%ANSWER%"
)
goto :MENU

:SETOUTPUT
echo.
set "ANSWER="
set /p "ANSWER=Output folder (empty = same as source)> "
if not "%ANSWER%"=="" (
  set "ANSWER=%ANSWER:"=%"
  set "OUTPUT=%ANSWER%"
)
goto :MENU

:SETFILES
echo.
echo One path per line. Leave the line empty to finish.
set "FILES="
:SETFILESLOOP
set "ONE="
set /p "ONE=File> "
if "%ONE%"=="" goto :MENU
set "ONE=%ONE:"=%"
if "%FILES%"=="" (
  set "FILES=%ONE%"
) else (
  set "FILES=%FILES%,%ONE%"
)
goto :SETFILESLOOP

:ADDFILTER
echo.
echo Filter grammar is the same as the Python panel: *eml.pdf, *.pdf, RPT-*.json
echo Leave the line empty to stop. The next field appears immediately.
:ADDFILTERLOOP
set "PATTERN="
set /p "PATTERN=Filter> "
if "%PATTERN%"=="" goto :MENU
set "PATTERN=%PATTERN:"=%"
set "FILTERS=%FILTERS% --filter "%PATTERN%""
echo   added: %PATTERN%
goto :ADDFILTERLOOP

:TOGRECURSIVE
if "%RECURSIVE%"=="1" (set "RECURSIVE=0") else (set "RECURSIVE=1")
goto :MENU

:TOGPERFILE
if "%PERFILE%"=="1" (set "PERFILE=0") else (set "PERFILE=1")
goto :MENU

:TOGSTRICT
if "%STRICT%"=="1" (set "STRICT=0") else (set "STRICT=1")
goto :MENU

:TOGEMBED
if "%EMBED%"=="1" (set "EMBED=0") else (set "EMBED=1")
goto :MENU

:TOGEMBEDPOS
if /i "%EMBEDPOS%"=="after" (set "EMBEDPOS=before") else (set "EMBEDPOS=after")
goto :MENU

:SETEMBEDPDF
echo.
set "ANSWER="
set /p "ANSWER=PDF to include in a folder report (empty clears)> "
if not "%ANSWER%"=="" (
  set "ANSWER=%ANSWER:"=%"
  if not exist "%ANSWER%" (
    echo BLOCKED: no such file: %ANSWER%
    pause
    goto :MENU
  )
)
set "EMBEDPDF=%ANSWER%"
goto :MENU

:CYCLEPROFILE
if /i "%PROFILE%"=="auto" (
  set "PROFILE=single"
) else if /i "%PROFILE%"=="single" (
  set "PROFILE=combo"
) else if /i "%PROFILE%"=="combo" (
  set "PROFILE=combo_all"
) else if /i "%PROFILE%"=="combo_all" (
  set "PROFILE=combo_pdf"
) else if /i "%PROFILE%"=="combo_pdf" (
  set "PROFILE=combo_all_pdf"
) else if /i "%PROFILE%"=="combo_all_pdf" (
  set "PROFILE=volume"
) else if /i "%PROFILE%"=="volume" (
  set "PROFILE=file_information_report"
) else if /i "%PROFILE%"=="file_information_report" (
  set "PROFILE=single_pdf"
) else (
  set "PROFILE=auto"
)
goto :MENU

;READYEMBED is a subroutine on purpose: an unescaped parenthesis inside
;an if(...) block would terminate the block early.
:READYEMBED
if "%EMBEDPDF%"=="" goto :READYEMBEDSELF
echo %EMBEDPDF%| findstr /i /e /c:".pdf" >nul
if errorlevel 1 (
  echo BLOCKED: the included file must be a .pdf: %EMBEDPDF%
  pause
  exit /b 1
)
exit /b 0
:READYEMBEDSELF
if not "%FILES%"=="" goto :READYEMBEDFILES
if exist "%SOURCE%\" (
  echo BLOCKED: the embedded mode needs one PDF file, not a folder.
  pause
  exit /b 1
)
exit /b 0
:READYEMBEDFILES
echo %FILES%| findstr /c:"," >nul
if not errorlevel 1 (
  echo BLOCKED: the embedded mode accepts exactly one file.
  pause
  exit /b 1
)
exit /b 0

:CYCLEARCHIVE
if /i "%ARCHIVE%"=="config" (
  set "ARCHIVE=on"
) else if /i "%ARCHIVE%"=="on" (
  set "ARCHIVE=off"
) else (
  set "ARCHIVE=config"
)
goto :MENU

:RUN
echo.
set "EMBEDNEEDED=0"
if "%EMBED%"=="1" set "EMBEDNEEDED=1"
if not "%EMBEDPDF%"=="" set "EMBEDNEEDED=1"
if "%EMBEDNEEDED%"=="1" (
  call :READYEMBED
  if errorlevel 1 goto :MENU
)
if "%SOURCE%"=="" if "%FILES%"=="" (
  echo BLOCKED: set a source folder or an explicit file list first.
  pause
  goto :MENU
)
if not "%FILES%"=="" if not "%FILTERS%"=="" (
  echo NOTE: filters do not apply to an explicit file list; clearing them.
  set "FILTERS="
)
if not "%FILES%"=="" if "%RECURSIVE%"=="1" (
  echo NOTE: recursive scanning does not apply to an explicit file list.
  set "RECURSIVE=0"
)
if "%OUTPUT%"=="" (
  if not "%FILES%"=="" (
    for %%F in ("%FILES%") do (
      for %%D in ("%%~dpF.") do set "OUTPUT=%%~fD"
    )
  ) else (
    set "OUTPUT=%SOURCE%"
  )
)
if not exist "%OUTPUT%" mkdir "%OUTPUT%" >nul 2>nul

set "ARGS=--output "%OUTPUT%""
if not "%SOURCE%"=="" set "ARGS=%ARGS% --source "%SOURCE%""
if not "%FILES%"=="" set "ARGS=%ARGS% --files "%FILES%""
if "%RECURSIVE%"=="1" set "ARGS=%ARGS% --recursive"
if "%PERFILE%"=="1" set "ARGS=%ARGS% --per-file"
if /i not "%PROFILE%"=="auto" if "%PERFILE%"=="0" set "ARGS=%ARGS% --profile %PROFILE%"
if /i "%ARCHIVE%"=="on" set "ARGS=%ARGS% --archive"
if /i "%ARCHIVE%"=="off" set "ARGS=%ARGS% --no-archive"
if "%STRICT%"=="1" set "ARGS=%ARGS% --require-layout-pass"
if "%EMBED%"=="1" if "%EMBEDPDF%"=="" set "ARGS=%ARGS% --embed-pdf"
if not "%EMBEDPDF%"=="" set "ARGS=%ARGS% --embed-pdf "%EMBEDPDF%""
if not "%EMBEDPOS%"=="after" if "%EMBEDNEEDED%"=="1" set "ARGS=%ARGS% --embed-position %EMBEDPOS%"
if not "%FILTERS%"=="" set "ARGS=%ARGS% %FILTERS%"

echo node js\cli.mjs %ARGS%
echo.
call node "js\cli.mjs" %ARGS%
set "RC=!errorlevel!"
call :RESULT !RC!
echo.
pause
goto :MENU

:HELP
cls
echo ChronoSeal HASH REPORT - JavaScript clone, launcher
echo.
echo This launcher only collects options; every report is produced by
echo   node js/cli.mjs
echo so the launcher and the command line always behave identically.
echo.
echo Menu options
echo   1  Source folder, or one file for a SINGLE report.
echo   2  Recursive scan of subfolders.
echo   3  Filter patterns, added one after another until an empty line.
echo      The format matches the Python panel: *eml.pdf, *.pdf, RPT-*.
echo   4  Drop every filter.
echo   5  Output folder, created when missing.
echo   6  Per-file mode: one SINGLE report per selected file, each with its
echo      own report number, evidence case and archive row.
echo   7  Archive: config (respect the repository configuration), on, off.
echo   8  Strict layout gate: block publication instead of reporting REVIEW.
echo   9  Explicit file list, one path per line.
echo  10  Embedded source PDF: the report is about one .pdf, keeps its own
echo      pages, appends the pages of that PDF and attaches the original
echo      byte for byte, exactly like the Python single_pdf profile.
echo      This mode always uses the single_pdf report type.
echo  11  Report type, cycled:
echo        auto                     derive it from the selection (default):
echo                                 one file -^> SINGLE, folder -^> COMBO,
echo                                 recursive -^> COMBO_ALL
echo        single                   one file, evidence package
echo        combo                    current folder, evidence package
echo        combo_all                recursive, with the folder breakdown
echo        combo_pdf                folder plus one included PDF
echo        combo_all_pdf            recursive plus one included PDF
echo        volume                   where the bytes live, per folder
echo        file_information_report  SHA-256 file sheet, no legal reprint
echo        single_pdf               one embedded source PDF
echo  12  PDF to include in a folder report: the report keeps its own
echo      pages, inserts the pages of that PDF and attaches the original
echo      byte for byte - the Python combo_pdf / combo_all_pdf types.
echo      A folder report takes one chosen PDF here; option 10 takes
echo      the file the one-file report is about. Set one, not both.
echo  13  Position of the included pages: after the report (default)
echo      or before it, exactly like --embed-position in Python.
echo      An explicit type is ignored by per-file mode, which always writes
echo      one SINGLE report per file.
echo      A type that documents an included PDF (single_pdf, combo_pdf,
echo      combo_all_pdf) needs option 10 or 12; without it the CLI refuses,
echo      because the name would describe content the document lacks.
echo.
echo Exit codes: 0 = report published, 2 = layout review, 1 = error.
echo.
pause
goto :MENU

:END
popd
endlocal
exit /b 0

:RESULT
echo.
if "%~1"=="0" echo RESULT: PASS - published report, exit code 0
if "%~1"=="2" echo RESULT: LAYOUT REVIEW - nothing published, exit code 2
if not "%~1"=="0" if not "%~1"=="2" echo RESULT: ERROR - see the messages above, exit code %~1
goto :eof