@echo off
chcp 65001 >nul
title QC Component Manager - SERVER LAN
color 0E

echo.
echo ============================================================
echo   QC COMPONENT MANAGER - SERVER LAN
echo   Dai Dung - Phong QC
echo ============================================================
echo.

REM Lay IP LAN
set "MY_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    if not defined MY_IP set "MY_IP=%%a"
)
set "MY_IP=%MY_IP: =%"

echo  Server: %COMPUTERNAME%
echo  IP LAN: %MY_IP%
echo  Port:   8501
echo.
echo  AE QC mo Chrome/Edge va go dia chi:
echo.
echo      http://%MY_IP%:8501
echo.
echo ============================================================
echo  GIU CUA SO NAY MO - dong = server tat
echo  Dong server: nhan Ctrl+C, hoac dong cua so
echo ============================================================
echo.

REM Doi sang thu muc app
cd /d "%~dp0"

REM Kich hoat venv (neu co)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Chay Streamlit
streamlit run streamlit_qc\app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false --server.maxUploadSize=200

echo.
echo Server da tat. Nhan phim bat ky de dong...
pause >nul
