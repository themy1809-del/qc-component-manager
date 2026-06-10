@echo off
title Push to GitHub
cd /d "%~dp0"

if exist ".git\index.lock" del /F /Q ".git\index.lock"
if exist ".git\HEAD.lock" del /F /Q ".git\HEAD.lock"

set MSG=%*
if "%MSG%"=="" set MSG=update: map nghiem thu PVF/VIN/GT1 + loc gia tri rac + chuan hoa ngay ISO

echo Adding all changes...
git add -A

echo Committing: %MSG%
git commit -m "%MSG%"

echo Pushing...
git push origin main

echo.
echo Done. Doi 60-90s de Streamlit Cloud rebuild roi F5 app.
pause
