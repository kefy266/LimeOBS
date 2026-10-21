@echo off
chcp 65001 >nul
title LimeOBS - Windows Kurulum ve Baslatici

echo ======================================================================
echo  🍋 LimeOBS Windows Kurulum ve Calistirma Sihirbazi
echo ======================================================================
echo.

:: 1. Python Kontrolu
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python sisteminizde bulunamadi!
    echo Lutfen https://www.python.org/ adresinden Python 3.10 veya daha yenisini kurun.
    echo Kurarken "Add python.exe to PATH" secenegini isaretlemeyi unutmayin.
    pause
    exit /b 1
)

echo [1/3] Python dogrulandi.
echo.

:: 2. GTK4 / PyGObject Kontrolu ve Rehberi
:: Windows uzerinde GTK4 ve Libadwaita en saglikli sekilde MSYS2 veya pip pycairo/PyGObject tekerleri ile calisir.
echo [2/3] Gerekli Python kutuphaneleri yukleniyor...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install requests beautifulsoup4 pillow >nul 2>&1

:: PyGObject kurulumu deneniyor
python -c "import gi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] PyGObject kuruluyor...
    python -m pip install pycairo PyGObject >nul 2>&1
)

python -c "import gi" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [BILGI] Windows'ta GTK4 ve Libadwaita kutuphaneleri icin onerilen kurulum:
    echo 1. MSYS2 kurun: https://www.msys2.org/
    echo 2. MSYS2 ucucbiriminde: pacman -S mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-python-gobject
    echo.
)

:: 3. LimeOBS Calistirma
echo [3/3] LimeOBS Baslatiliyor...
start "" pythonw akbim_frontend/main.py
if %errorlevel% neq 0 (
    python akbim_frontend/main.py
)

exit /b 0
