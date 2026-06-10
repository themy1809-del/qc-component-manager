@echo off
title Auto Import Master - QC Component Manager
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
%PY% -u auto_import_master.py %*
echo.
pause
