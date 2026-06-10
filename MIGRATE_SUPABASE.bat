@echo off
title Migrate QC data to Supabase Postgres
cd /d "%~dp0"

echo ============================================================
echo   MIGRATE DU LIEU QC  -^>  SUPABASE POSTGRES
echo ============================================================
echo.

if not exist "supabase_url.txt" (
    echo Chua co file supabase_url.txt - dang tao file mau + mo Notepad.
    echo Dan chuoi ket noi Supabase vao, thay [YOUR-PASSWORD] bang mat khau DB,
    echo LUU lai, roi chay lai file .bat nay.
    echo postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres>supabase_url.txt
    notepad supabase_url.txt
    echo.
    echo Sau khi LUU file, chay lai MIGRATE_SUPABASE.bat
    pause
    exit /b 0
)

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo [1/2] Cai psycopg2-binary neu thieu...
"%PY%" -m pip install psycopg2-binary --quiet --disable-pip-version-check
echo.

echo [2/2] Chay migration (16k cau kien)...
echo.
"%PY%" migrate_sqlite_to_postgres.py

echo.
echo ============================================================
echo Neu thay "HOAN TAT MIGRATION!" o tren = thanh cong.
echo Buoc cuoi (tren Streamlit Cloud): Settings - Secrets, them:
echo   DATABASE_URL = "dan y het noi dung trong supabase_url.txt"
echo Roi xoa supabase_url.txt de khong luu mat khau tren may.
echo ============================================================
pause
