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
