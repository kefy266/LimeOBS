#!/usr/bin/env bash
# ==============================================================================
# LimeOBS — macOS Kurulum ve Çalıştırma Scripti (macOS Sequoia / Sonoma / Ventura)
# ==============================================================================

set -e

echo "🍏 LimeOBS macOS Kurulumu Başlatılıyor..."

# 1. Homebrew Kontrolü
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew bulunamadı. Lütfen önce Homebrew kurun: https://brew.sh"
    echo "Komut: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "📦 Gerekli macOS kütüphaneleri (GTK4, Libadwaita, Poppler) kontrol ediliyor..."
brew install python@3.11 gtk4 libadwaita pygobject3 poppler adwaita-icon-theme || true

# 2. Python Sanal Ortamı (venv) Kurulumu
if [ ! -d "venv_mac" ]; then
    echo "🐍 macOS için Python sanal ortamı oluşturuluyor..."
    python3 -m venv --system-site-packages venv_mac
fi

source venv_mac/bin/activate
pip install --upgrade pip
pip install requests beautifulsoup4 pillow pycairo PyGObject

echo "✅ Kurulum tamamlandı!"
echo "🚀 LimeOBS başlatılıyor..."
python3 akbim_frontend/main.py
