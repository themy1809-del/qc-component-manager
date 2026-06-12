@echo off
chcp 65001 >nul
title QC Tunnel - Auto URL Capture
color 0B

cd /d "%~dp0"

echo.
echo ============================================================
echo   CLOUDFLARE TUNNEL - QC COMPONENT MANAGER
echo   Tu dong bat URL + copy vao clipboard
echo ============================================================
echo.

REM Buoc 1: Download cloudflared.exe neu chua co
if not exist cloudflared.exe (
    echo [1/3] Dang tai cloudflared.exe ^(khoang 18MB^)...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe' -UseBasicParsing"
    if not exist cloudflared.exe (
        echo LOI: Khong tai duoc cloudflared.exe
        echo Kiem tra ket noi internet roi mo lai.
        pause
        exit /b 1
    )
    echo Tai xong!
    echo.
) else (
    echo [1/3] cloudflared.exe da co - bo qua tai
    echo.
)

REM Buoc 2: Check Streamlit dang chay
echo [2/3] Kiem tra Streamlit dang chay tren port 8501...
netstat -an | findstr ":8501" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo.
    echo CANH BAO: Server Streamlit chua chay!
    echo Vui long:
    echo   1. Mo START_SERVER.bat truoc
    echo   2. Cho thay dong "You can now view your Streamlit app"
    echo   3. Sau do mo lai file nay
    echo.
    pause
    exit /b 1
)
echo Server OK!
echo.

REM Buoc 3: Chay PowerShell helper de parse URL tu output
echo [3/3] Khoi tao tunnel ^(cho 10-15 giay^)...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0_tunnel_helper.ps1"

echo.
echo Tunnel da dong. Nhan phim bat ky de dong cua so...
pause >nul
