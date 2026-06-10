@echo off
chcp 65001 >nul
title Xem IP may server
color 0A

echo.
echo ============================================================
echo   IP CUA MAY NAY (de gui cho AE QC)
echo ============================================================
echo.

ipconfig | findstr /c:"IPv4"

echo.
echo ============================================================
echo  Lay IP dang 192.168.x.x hoac 10.x.x.x
echo  BO QUA cac IP:
echo    - 127.0.0.1     (localhost)
echo    - 169.254.x.x   (loi mang)
echo.
echo  Vi du IP dung: 192.168.1.50
echo  --> Gui cho AE QC: http://192.168.1.50:8501
echo ============================================================
echo.

pause
