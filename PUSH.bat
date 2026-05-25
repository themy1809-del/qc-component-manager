@echo off
title Push to GitHub
cd /d "%~dp0"

if exist ".git\index.lock" del /F /Q ".git\index.lock"

echo Adding all changes...
git add -A

echo Committing...
git commit -m "fix: remove pdfplumber from requirements (optional); use plain qrcode + pillow"

echo Pushing...
git push origin main

echo.
echo Done. Wait 60-90s for Cloud rebuild then F5 the app.
echo Reportlab will load correctly once container restarts.
pause
