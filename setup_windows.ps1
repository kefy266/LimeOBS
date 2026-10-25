<#
.SYNOPSIS
    LimeOBS - Windows PowerShell Başlatıcı (Download and Go)
.DESCRIPTION
    Bağımsız LimeOBS.exe varsa doğrudan başlatır (hiçbir Python veya kütüphane gerektirmez).
    Kaynak koddan çalıştırma durumunda ortamı kontrol eder.
#>

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 🍋 LimeOBS Windows PowerShell Başlatıcı" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Bağımsız Hazır EXE Kontrolü
$exePaths = @(
    Join-Path $PSScriptRoot "dist\LimeOBS\LimeOBS.exe",
    Join-Path $PSScriptRoot "LimeOBS\LimeOBS.exe",
    Join-Path $PSScriptRoot "LimeOBS.exe"
)

foreach ($exe in $exePaths) {
    if (Test-Path $exe) {
        Write-Host "[✓] Bağımsız LimeOBS.exe bulundu: $exe" -ForegroundColor Green
        Write-Host "[✓] Başlatılıyor (Sıfır bağımlılık / Portable)..." -ForegroundColor Cyan
        Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe)
        exit 0
    }
}

# 2. MSYS2 UCRT64 Python Kontrolü
$msysPython = "C:\msys64\ucrt64\bin\python.exe"
if (Test-Path $msysPython) {
    Write-Host "[✓] MSYS2 UCRT64 Python tespit edildi. Başlatılıyor..." -ForegroundColor Green
    $env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
    Start-Process -FilePath $msysPython -ArgumentList "akbim_qt/main.py" -WorkingDirectory $PSScriptRoot
    exit 0
}

# 3. Sistem Python Kontrolü
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "[✓] Sistem Python bulundu: $pythonVersion" -ForegroundColor Green
    & python -m pip install PyQt6 requests beautifulsoup4 pillow pypdf --quiet
    Start-Process -FilePath "python" -ArgumentList "akbim_qt/main.py" -WorkingDirectory $PSScriptRoot
    exit 0
} catch {
    Write-Host "[HATA] Ne bağımsız LimeOBS.exe ne de Python bulunabildi!" -ForegroundColor Red
    Write-Host "Lütfen 'LimeOBS_Windows_Portable.zip' arşivini bir klasöre çıkartıp içindeki 'LimeOBS.exe'ye çift tıklayın." -ForegroundColor Yellow
    pause
    exit 1
}
