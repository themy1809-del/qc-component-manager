@echo off
chcp 65001 >nul
title Deploy code len Streamlit Cloud
color 0A

cd /d "%~dp0"

echo.
echo ============================================================
echo   DEPLOY CODE LEN STREAMLIT CLOUD
echo   (push len GitHub - Cloud tu rebuild)
echo ============================================================
echo.

REM Check git
git --version >nul 2>&1
if errorlevel 1 (
    echo LOI: chua cai Git. Tai: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/4] Kiem tra file thay doi...
git status --short
echo.

REM Lay timestamp lam commit message
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value ^| find "="') do set datetime=%%a
set "ts=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2% %datetime:~8,2%:%datetime:~10,2%"

echo [2/4] Stage tat ca file thay doi...
git add -A

echo [3/4] Commit voi message tu dong...
git commit -m "update: %ts%" 2>nul
if errorlevel 1 (
    echo Khong co thay doi gi de commit ^(hoac da commit roi^).
)
echo.

echo [4/4] Push len GitHub...
echo.
git push
if errorlevel 1 (
    echo.
    echo LOI khi push. Co the:
    echo   - Mat ket noi internet
    echo   - Chua login GitHub ^(chay 1 lan: git config --global user.name "ten"^)
    echo   - Conflict ^(co nguoi push truoc^) - thu: git pull roi chay lai
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  THANH CONG! Cho 30-60s Streamlit Cloud rebuild.
echo  Sau do F5 trinh duyet app online de thay code moi.
echo ============================================================
echo.

REM Tu mo Streamlit Cloud dashboard de xem progress
echo Mo Streamlit Cloud dashboard de xem rebuild...
start https://share.streamlit.io

pause
