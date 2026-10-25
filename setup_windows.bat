@echo off
chcp 65001 >nul
title LimeOBS - Windows Baslatici
cd /d "%~dp0"

echo ======================================================================
echo  🍋 LimeOBS Windows Baslatici (Download and Go)
echo ======================================================================
echo.

:: 1. Bagimsiz Hazir EXE Kontrolu (Sifir bagimlilik - Dogrudan calisir)
if exist "dist\LimeOBS\LimeOBS.exe" (
    echo [✓] Bagimsiz LimeOBS.exe tespit edildi. Baslatiliyor...
    start "" "dist\LimeOBS\LimeOBS.exe"
    exit /b 0
)

if exist "LimeOBS\LimeOBS.exe" (
    echo [✓] Bagimsiz LimeOBS.exe tespit edildi. Baslatiliyor...
    start "" "LimeOBS\LimeOBS.exe"
    exit /b 0
)

if exist "LimeOBS.exe" (
    echo [✓] Bagimsiz LimeOBS.exe tespit edildi. Baslatiliyor...
    start "" "LimeOBS.exe"
    exit /b 0
)

:: 2. MSYS2 UCRT64 Python Ortami Kontrolu (PyQt6)
if exist "C:\msys64\ucrt64\bin\python.exe" (
    echo [✓] MSYS2 UCRT64 Python ortami tespit edildi.
    set "PATH=C:\msys64\ucrt64\bin;%PATH%"
    start "" "C:\msys64\ucrt64\bin\pythonw.exe" "akbim_qt/main.py"
    if %errorlevel% neq 0 (
        "C:\msys64\ucrt64\bin\python.exe" "akbim_qt/main.py"
    )
    exit /b 0
)

:: 3. Standart Sistem Python Kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Bagimsiz LimeOBS.exe veya Python bulunamadi!
    echo.
    echo Eger 'LimeOBS_Windows_Portable.zip' dosyaniz varsa, zipten cikartip
    echo icindeki 'LimeOBS.exe' dosyasina cift tiklayarak aninda calistirabilirsiniz.
    pause
    exit /b 1
)

echo [1/2] Sistem Python dogrulandi.
python -m pip install PyQt6 requests beautifulsoup4 pillow pypdf >nul 2>&1

echo [2/2] LimeOBS Baslatiliyor...
start "" pythonw akbim_qt/main.py
if %errorlevel% neq 0 (
    python akbim_qt/main.py
)

exit /b 0
