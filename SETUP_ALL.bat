@echo off
REM ============================================================
REM QC Component Manager Web v2.0 - One-click installer wrapper
REM
REM Anh oke chi can:
REM   1. Right-click file nay -^> "Run as administrator"
REM   2. Bam "Yes" khi Windows hoi
REM   3. Doi 5-10 phut
REM
REM Script PowerShell se tu lam tat ca:
REM   - Tai Python 3.11 ve %TEMP%
REM   - Cai Python im lang
REM   - Tao venv
REM   - Cai 6 thu vien
REM   - Tao run_app.bat
REM ============================================================
title QC Component Manager - Setup
chcp 65001 >nul

cd /d "%~dp0"

REM Check if running as admin
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo *** CAN QUYEN ADMINISTRATOR ***
    echo.
    echo Vui long: right-click file SETUP_ALL.bat -^> "Run as administrator"
    echo.
    echo Tu dong xin quyen admin trong 3 giay...
    timeout /t 3 >nul
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

REM Run PowerShell script with bypass execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP_ALL.ps1"

pause
