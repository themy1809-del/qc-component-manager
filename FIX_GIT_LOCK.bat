@echo off
title Fix Git Lock + Deploy

echo ========================================
echo  FIX GIT LOCK + DEPLOY ALL
echo ========================================
echo.

cd /d "%~dp0"

echo Step 1: Removing git index.lock if any...
if exist ".git\index.lock" (
    del /F /Q ".git\index.lock"
    echo OK - lock removed
) else (
    echo OK - no lock
)
echo.

echo Step 2: git add -A (stage ALL files, including new ones)...
git add -A
if errorlevel 1 goto :error_add
echo OK
echo.

echo Step 3: git commit...
git commit -m "v2 advanced: RFI + ITP + Batch + Material + Share Portal"
echo.

echo Step 4: git push origin main...
git push origin main
if errorlevel 1 goto :error_push
echo.

echo ========================================
echo  SUCCESS! Streamlit Cloud will rebuild
echo  in 30-60 seconds. Refresh browser.
echo ========================================
echo.
pause
goto :eof

:error_add
echo.
echo ERROR: git add failed
pause
exit /b 1

:error_push
echo.
echo ERROR: git push failed - check network and credentials
pause
exit /b 1
