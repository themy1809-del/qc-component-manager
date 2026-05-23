@echo off
REM ============================================================
REM Tiep tuc setup tu buoc 3 (Python 3.11 + venv da co san)
REM Dung file nay neu SETUP_ALL.bat bi loi PowerShell warning
REM
REM File nay KHONG can quyen admin.
REM ============================================================
chcp 65001 >nul
title QC Setup - Tiep tuc cai thu vien

cd /d "%~dp0"

echo.
echo ======================================================
echo  TIEP TUC SETUP - Cai thu vien Python
echo ======================================================
echo.

REM Verify venv da co
if not exist ".venv\Scripts\python.exe" (
    echo *** LOI: Khong thay .venv\
    echo Anh chay SETUP_ALL.bat truoc de tao venv.
    pause
    exit /b 1
)

echo [1/3] Don pip cache cu...
.venv\Scripts\python.exe -m pip cache purge >nul 2>&1
echo OK
echo.

echo [2/3] Cap nhat pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 (
    echo *** LOI cap nhat pip
    pause
    exit /b 1
)
echo.

echo [3/3] Cai thu vien (streamlit, pandas, plotly, openpyxl, pyxlsb, python-dateutil)...
echo Co the mat 2-5 phut. Anh oke ngoi cho...
echo.
.venv\Scripts\python.exe -m pip install -r streamlit_qc\requirements.txt --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo *** LOI cai thu vien
    echo Anh oke paste 10-20 dong cuoi cua loi tren vao chat cho em.
    pause
    exit /b 1
)
echo.

echo ======================================================
echo  CAI THU VIEN HOAN TAT!
echo ======================================================
echo.

REM Tao run_app.bat
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title QC Component Manager - Running
    echo cd /d "%%~dp0"
    echo call .venv\Scripts\activate.bat
    echo cd streamlit_qc
    echo echo.
    echo echo ======================================================
    echo echo  QC Component Manager Web v2.0 dang khoi dong...
    echo echo  Truy cap: http://localhost:8501
    echo echo  An Ctrl+C trong cua so nay de tat
    echo echo ======================================================
    echo echo.
    echo streamlit run app.py
    echo pause
) > run_app.bat

echo Da tao file: run_app.bat
echo.
echo Lan sau muon chay app, double-click file run_app.bat
echo.

choice /c YN /m "Chay app NGAY bay gio (Y/N)"
if errorlevel 2 (
    echo Da xong. Chuc anh oke lam viec hieu qua!
    pause
    exit /b 0
)

echo.
echo Dang khoi dong app...
call run_app.bat
