@echo off
title Migrate Supabase Sydney -> US
cd /d "%~dp0"
echo ============================================================
echo   MIGRATE SUPABASE: Sydney  -^>  US (giam lag)
echo ============================================================
echo.
if not exist "supabase_old.txt" (
    echo Tao file supabase_old.txt - dan chuoi Supabase CU (Sydney) vao:
    echo postgresql://postgres.lehmenrkcwvywprijqnd:Minhkhoi%%400309@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres>supabase_old.txt
    echo (da dien san chuoi Sydney cua ban)
)
if not exist "supabase_new.txt" (
    echo postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres>supabase_new.txt
    echo.
    echo Chua co supabase_new.txt - dang mo Notepad. Dan chuoi Supabase MOI (US) vao, LUU, roi chay lai.
    notepad supabase_new.txt
    pause
    exit /b 0
)
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install psycopg2-binary --quiet --disable-pip-version-check
"%PY%" migrate_pg_to_pg.py
pause
