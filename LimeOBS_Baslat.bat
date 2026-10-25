@echo off
chcp 65001 >nul
title LimeOBS - GTK4 & Libadwaita Edition
cd /d "%~dp0"

echo [*] LimeOBS GTK4 baslatiliyor...

set "PATH=C:\msys64\ucrt64\bin;%PATH%"
set "GSETTINGS_SCHEMA_DIR=C:\msys64\ucrt64\share\glib-2.0\schemas"
set "XDG_DATA_DIRS=%~dp0akbim_frontend\icons;C:\msys64\ucrt64\share"
set "FREETYPE_PROPERTIES=truetype:interpreter-version=40"
set "FONTCONFIG_PATH=C:\msys64\ucrt64\etc\fonts"

start "" "C:\msys64\ucrt64\bin\pythonw.exe" "akbim_frontend\main.py"
exit /b 0
