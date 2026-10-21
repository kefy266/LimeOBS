<#
.SYNOPSIS
    LimeOBS - Windows Otomatik Kurulum ve Başlatma Scripti
.DESCRIPTION
    Windows 10 ve Windows 11 üzerinde LimeOBS için gerekli Python paketlerini,
    bildirim desteğini ve bağımlılıklarını hazırlar ve uygulamayı başlatır.
#>

$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 🍋 LimeOBS Windows PowerShell Kurulum ve Başlatıcı" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Python Kontrolü
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "[✓] Python bulundu: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[HATA] Python bulunamadı! Lütfen Microsoft Store'dan veya python.org'dan Python kurun." -ForegroundColor Red
    pause
    exit 1
}

# 2. Pip Paketlerinin Kurulumu
Write-Host "[*] Gerekli Python paketleri güncelleniyor (requests, beautifulsoup4, pillow)..." -ForegroundColor Yellow
& python -m pip install --upgrade pip requests beautifulsoup4 pillow pycairo PyGObject --quiet

# 3. İsteğe Bağlı Bildirim Desteği (BurntToast)
try {
    if (-not (Get-Module -ListAvailable -Name BurntToast)) {
        Write-Host "[*] Windows yerel Toast bildirim modülü (BurntToast) kuruluyor..." -ForegroundColor Yellow
        Install-Module -Name BurntToast -Force -SkipPublisherCheck -Scope CurrentUser -ErrorAction SilentlyContinue
    }
} catch {
    # Hata olursa PowerShell yerel Windows.UI.Notifications kullanılacaktır
}

# 4. Uygulamayı Başlat
Write-Host "[✓] Kurulum hazır. LimeOBS başlatılıyor..." -ForegroundColor Green
Start-Process -FilePath "python" -ArgumentList "akbim_frontend/main.py" -WorkingDirectory $PSScriptRoot
