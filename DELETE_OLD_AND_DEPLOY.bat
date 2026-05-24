@echo off
title Delete Old Pages + Deploy

echo ========================================
echo  CLEANUP + DEPLOY V2 ADVANCED
echo ========================================
echo.

cd /d "%~dp0"

echo Step 1: Remove git lock if any...
if exist ".git\index.lock" del /F /Q ".git\index.lock"

echo Step 2: Delete old A/B/C/D page files (replaced by 10/11/12/13)...
cd streamlit_qc\pages
del /F /Q "A_*.py" 2>nul
del /F /Q "B_*.py" 2>nul
del /F /Q "C_*.py" 2>nul
del /F /Q "D_*.py" 2>nul
echo OK - cleaned
cd ..\..

echo Step 3: List remaining page files...
dir /B streamlit_qc\pages\*.py

echo.
echo Step 4: Stage ALL changes...
git add -A

echo Step 5: Commit...
git commit -m "v2 advanced: RFI + ITP + Batch + Material + Share Portal (renamed A-D to 10-13)"

echo Step 6: Push to GitHub...
git push origin main
if errorlevel 1 (
    echo ERROR: push failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo  SUCCESS! Wait 30-60s for rebuild.
echo  Then F5 the app to see 4 new pages:
echo    10. RFI       11. ITP
echo    12. Ban giao  13. Share Portal
echo ========================================
pause
