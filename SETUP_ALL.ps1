#Requires -Version 5.0
<#
.SYNOPSIS
    QC Component Manager Web v2.0 - One-click setup
    Tu dong tai + cai Python 3.11 + dependencies + tao run script

.DESCRIPTION
    Khong can anh oke lam gi them - chi can run as admin va doi.

.NOTES
    Author: Claude AI assistant
    For:    oke - QC Dai Dung
#>

# Force UTF-8 console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Note: Do NOT use "Stop" because pip warnings xuat ra stderr se bi treat la error.
$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  QC COMPONENT MANAGER WEB v2.0 - AUTO SETUP" -ForegroundColor Cyan
Write-Host "  Phong QC - Cong ty Dai Dung" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ====================================================================
# CHECK ADMIN RIGHTS
# ====================================================================
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "*** CAN QUYEN ADMIN ***" -ForegroundColor Red
    Write-Host "Script can quyen Administrator de cai Python." -ForegroundColor Yellow
    Write-Host "Dang khoi dong lai voi quyen admin..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$($MyInvocation.MyCommand.Path)`""
    exit
}

# ====================================================================
# STEP 1: CHECK / INSTALL PYTHON 3.11
# ====================================================================
Write-Host "[1/5] Kiem tra Python 3.11..." -ForegroundColor Yellow

$pythonInstalled = $false
try {
    $version = & py -3.11 --version 2>&1
    if ($version -match "Python 3\.11\.") {
        Write-Host "    OK - Da co: $version" -ForegroundColor Green
        $pythonInstalled = $true
    }
} catch {
    # py launcher chua co hoac chua co 3.11
}

if (-not $pythonInstalled) {
    Write-Host "    Chua co Python 3.11. Bat dau tai installer..." -ForegroundColor Yellow

    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installerPath = "$env:TEMP\python-3.11.9-amd64.exe"

    if (Test-Path $installerPath) {
        $size = (Get-Item $installerPath).Length / 1MB
        if ($size -lt 20) {
            Remove-Item $installerPath -Force
        }
    }

    if (-not (Test-Path $installerPath)) {
        Write-Host "    Dang tai tu python.org (khoang 25MB, mat 1-2 phut)..." -ForegroundColor Yellow
        try {
            # Use TLS 1.2 for python.org
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $ProgressPreference = 'SilentlyContinue'  # Speed up download

            Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing

            $ProgressPreference = 'Continue'
            $sizeKB = [math]::Round((Get-Item $installerPath).Length / 1KB, 0)
            Write-Host "    Tai xong ($sizeKB KB)" -ForegroundColor Green
        } catch {
            Write-Host "*** LOI tai Python installer: $_" -ForegroundColor Red
            Write-Host "Anh thu cach thu cong:" -ForegroundColor Yellow
            Write-Host "  1. Vao https://www.python.org/downloads/release/python-3119/" -ForegroundColor Yellow
            Write-Host "  2. Tai 'Windows installer (64-bit)'" -ForegroundColor Yellow
            Write-Host "  3. Cai dat: tick 'py launcher' + 'for all users'" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
    } else {
        Write-Host "    Da co installer trong %TEMP%, dung lai." -ForegroundColor Green
    }

    Write-Host "    Dang cai Python 3.11 (im lang, mat 1-2 phut)..." -ForegroundColor Yellow
    $installArgs = @(
        "/quiet",
        "InstallAllUsers=1",
        "PrependPath=0",           # KHONG them vao PATH, dung qua py launcher
        "Include_launcher=1",      # Bat buoc co py launcher
        "Include_test=0",
        "Include_doc=0",
        "Include_pip=1",
        "Include_tcltk=1"
    )

    $proc = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "*** Python installer ket thuc voi exit code $($proc.ExitCode)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    # Verify
    Start-Sleep -Seconds 2
    try {
        $version = & py -3.11 --version 2>&1
        if ($version -match "Python 3\.11\.") {
            Write-Host "    OK - Da cai: $version" -ForegroundColor Green
        } else {
            Write-Host "*** Cai xong nhung khong tim duoc py -3.11" -ForegroundColor Red
            Read-Host "Press Enter to exit"
            exit 1
        }
    } catch {
        Write-Host "*** Loi verify Python: $_" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host ""

# ====================================================================
# STEP 2: CREATE VIRTUAL ENV
# ====================================================================
Write-Host "[2/5] Tao virtual environment (.venv)..." -ForegroundColor Yellow

$venvPath = Join-Path $ScriptDir ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (Test-Path $venvPython) {
    Write-Host "    .venv da co san, bo qua." -ForegroundColor Green
} else {
    & py -3.11 -m venv $venvPath
    if (-not (Test-Path $venvPython)) {
        Write-Host "*** Loi tao venv" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "    OK" -ForegroundColor Green
}

Write-Host ""

# ====================================================================
# STEP 3: CLEAR PIP CACHE + UPGRADE PIP
# ====================================================================
Write-Host "[3/5] Don pip cache + cap nhat pip..." -ForegroundColor Yellow

# Don cache cu (tranh warning "Cache entry deserialization failed")
cmd /c "`"$venvPython`" -m pip cache purge >nul 2>&1"

# Upgrade pip - dung cmd /c de stderr/stdout duoc merge va khong gay loi PowerShell
$upgradeOutput = cmd /c "`"$venvPython`" -m pip install --upgrade pip --disable-pip-version-check 2>&1"
$upgradeExitCode = $LASTEXITCODE

if ($upgradeExitCode -ne 0) {
    Write-Host "*** Pip upgrade failed (exit code $upgradeExitCode):" -ForegroundColor Red
    Write-Host $upgradeOutput -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "    OK" -ForegroundColor Green
Write-Host ""

# ====================================================================
# STEP 4: INSTALL DEPENDENCIES
# ====================================================================
Write-Host "[4/5] Cai thu vien (streamlit, pandas, plotly, openpyxl, pyxlsb)..." -ForegroundColor Yellow
Write-Host "    Co the mat 2-5 phut tuy mang. Anh oke ngoi cho..." -ForegroundColor Gray

$reqFile = Join-Path $ScriptDir "streamlit_qc\requirements.txt"
if (-not (Test-Path $reqFile)) {
    Write-Host "*** Khong tim thay $reqFile" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Dung cmd /c de tranh PowerShell treat stderr warnings la exception
$installOutput = cmd /c "`"$venvPython`" -m pip install -r `"$reqFile`" --disable-pip-version-check 2>&1"
$installExitCode = $LASTEXITCODE

# Hien thi vai dong cuoi cua output de anh thay tien do
$lines = $installOutput -split "`n" | Where-Object { $_ -match "Successfully installed|ERROR|Collecting (streamlit|pandas|plotly|pyxlsb|openpyxl|python-dateutil)" }
foreach ($line in ($lines | Select-Object -Last 15)) {
    Write-Host "    $line" -ForegroundColor Gray
}

if ($installExitCode -ne 0) {
    Write-Host "*** Loi cai thu vien (exit code $installExitCode):" -ForegroundColor Red
    Write-Host ($installOutput -split "`n" | Select-Object -Last 30) -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "    OK - Tat ca thu vien da cai xong" -ForegroundColor Green
Write-Host ""

# ====================================================================
# STEP 5: CREATE run_app.bat
# ====================================================================
Write-Host "[5/5] Tao file run_app.bat..." -ForegroundColor Yellow

$runAppContent = @"
@echo off
chcp 65001 >nul
title QC Component Manager - Running
cd /d "%~dp0"
call .venv\Scripts\activate.bat
cd streamlit_qc
echo.
echo ======================================================
echo  QC Component Manager Web v2.0 dang khoi dong...
echo  Truy cap: http://localhost:8501
echo  An Ctrl+C trong cua so nay de tat
echo ======================================================
echo.
streamlit run app.py
pause
"@

$runAppPath = Join-Path $ScriptDir "run_app.bat"
Set-Content -Path $runAppPath -Value $runAppContent -Encoding ASCII
Write-Host "    OK - Da tao: $runAppPath" -ForegroundColor Green
Write-Host ""

# ====================================================================
# DONE
# ====================================================================
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  CAI DAT HOAN TAT!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Lan sau muon chay app:" -ForegroundColor White
Write-Host "  -> Double-click file: run_app.bat" -ForegroundColor Cyan
Write-Host ""

$ans = Read-Host "Chay app NGAY bay gio? (Y/N)"
if ($ans -match "^[Yy]") {
    Write-Host ""
    Write-Host "Dang khoi dong app..." -ForegroundColor Cyan
    Start-Process -FilePath $runAppPath -WorkingDirectory $ScriptDir
    Start-Sleep -Seconds 5
    Write-Host ""
    Write-Host "App da chay. Mo trinh duyet va vao:" -ForegroundColor Green
    Write-Host "  http://localhost:8501" -ForegroundColor Cyan
    Write-Host ""
}

Read-Host "Press Enter to close this window"
