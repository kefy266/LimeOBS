@echo off
chcp 65001 >nul
title LimeOBS - GTK4 & Libadwaita Edition
cd /d "%~dp0"

echo [*] LimeOBS GTK4 ve Libadwaita baslatiliyor...

set "PATH=C:\msys64\ucrt64\bin;%PATH%"
set "GSETTINGS_SCHEMA_DIR=C:\msys64\ucrt64\share\glib-2.0\schemas"
set "XDG_DATA_DIRS=C:\msys64\ucrt64\share"

:: Once arka planda takili kalmis eski ornek varsa temizle
taskkill /F /IM python.exe /FI "WINDOWTITLE eq com.kagan.limeobs*" >nul 2>&1

start "" "C:\msys64\ucrt64\bin\pythonw.exe" "akbim_frontend\main.py"
exit /b 0
