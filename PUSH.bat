@echo off
title Push to GitHub
cd /d "%~dp0"

if exist ".git\index.lock" del /F /Q ".git\index.lock"

echo Adding all changes...
git add -A

echo Committing...
git commit -m "fix: project_info_strip optional proj arg + ui.py recover"

echo Pushing...
git push origin main

echo.
echo Done. Wait 30-60s then F5 the app.
pause
