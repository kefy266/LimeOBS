@echo off
chcp 65001 >nul
title LimeOBS Windows Derleyici
echo ======================================================================
echo  🍋 LimeOBS Windows Standalone EXE Derleyici (PyQt6 + PyInstaller)
echo ======================================================================
echo.
cd /d "%~dp0"
set "PATH=C:\msys64\ucrt64\bin;%PATH%"

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] PyInstaller ucrt64 icinde bulunamadi!
    echo MSYS2 UCRT64 terminalinde su komutu calistirin:
    echo pacman -S mingw-w64-ucrt-x86_64-pyinstaller mingw-w64-ucrt-x86_64-pyinstaller-hooks-contrib
    pause
    exit /b 1
)

echo [*] Eski calisan surecler kontrol ediliyor...
taskkill /F /IM LimeOBS.exe >nul 2>&1

echo [*] LimeOBS Windows bagimsiz (.exe) paketi olusturuluyor...
pyinstaller --noconfirm limeobs_qt.spec

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo  [BASARILI] Derleme tamamlandi!
    echo  Uygulama: dist\LimeOBS\LimeOBS.exe
    echo ======================================================================
) else (
    echo.
    echo [HATA] Derleme sirasinda hata meydana geldi.
)

pause
