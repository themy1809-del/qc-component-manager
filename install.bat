@echo off
REM ===========================================================
REM QC Component Manager Web v2.0 - Auto installer
REM Dung sau khi da cai Python 3.11 tu python.org
REM Double-click file nay de chay
REM ===========================================================
chcp 65001 >nul
title QC Component Manager - Cai dat moi truong

echo.
echo ======================================================
echo  QC COMPONENT MANAGER WEB v2.0 - INSTALLER
echo  Cong ty Dai Dung - Phong QC
echo ======================================================
echo.

REM Chuyen ve thu muc cua file BAT
cd /d "%~dp0"

echo [1/5] Kiem tra Python 3.11...
py -3.11 --version 2>nul
if errorlevel 1 (
    echo.
    echo *** LOI: Khong tim thay Python 3.11
    echo Anh oke can cai Python 3.11 truoc:
    echo   1. Vao https://www.python.org/downloads/release/python-3119/
    echo   2. Tai "Windows installer (64-bit)"
    echo   3. Cai dat ^(KHONG tick "Add to PATH"^)
    echo   4. Tick "py launcher"
    echo.
    pause
    exit /b 1
)
echo OK!
echo.

echo [2/5] Tao moi truong ao .venv...
if exist ".venv\Scripts\python.exe" (
    echo .venv da co san, bo qua buoc nay.
) else (
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo *** LOI: Khong tao duoc venv
        pause
        exit /b 1
    )
    echo OK!
)
echo.

echo [3/5] Kich hoat moi truong ao + nang cap pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
echo OK!
echo.

echo [4/5] Cai thu vien ^(co the mat 2-5 phut, anh oke ngoi cho^)...
echo Dang tai streamlit, pandas, plotly, openpyxl, pyxlsb...
pip install -r streamlit_qc\requirements.txt
if errorlevel 1 (
    echo.
    echo *** LOI: Cai thu vien that bai
    echo Vui long copy paste loi do tren vao chat de em xem
    pause
    exit /b 1
)
echo.
echo OK!
echo.

echo [5/5] Tao file run_app.bat de chay app sau nay...
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title QC Component Manager - Running
    echo cd /d "%%~dp0"
    echo call .venv\Scripts\activate.bat
    echo cd streamlit_qc
    echo echo.
    echo echo ======================================
    echo echo  App dang khoi dong...
    echo echo  Truy cap: http://localhost:8501
    echo echo  An Ctrl+C trong cua so nay de tat
    echo echo ======================================
    echo echo.
    echo streamlit run app.py
    echo pause
) > run_app.bat
echo OK!
echo.

echo ======================================================
echo  CAI DAT HOAN TAT!
echo ======================================================
echo.
echo Bay gio anh oke chay app bang cach:
echo   - Double-click file "run_app.bat"
echo   - Hoac chay file "run_app.bat" ngay bay gio?
echo.

choice /c YN /m "Chay app ngay bay gio (Y/N)"
if errorlevel 2 (
    echo Da xong. Lan sau chi can chay run_app.bat
    pause
    exit /b 0
)

call run_app.bat
