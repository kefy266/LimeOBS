#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPDIR="/tmp/LimeOBS.AppDir"
OUT_DIR="$PROJECT_DIR/dist_appimage"
ICON_SRC="$PROJECT_DIR/akbim_frontend/app_icon.png"

echo "=== 1. Temizlik ve Dizin Yapısı Hazırlığı ==="
rm -rf "$APPDIR" build dist
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$OUT_DIR"

# Standart hicolor ikon boyutlarını oluşturalım
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps"
    convert "$ICON_SRC" -resize "${size}x${size}" "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/limeobs.png"
    cp "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/limeobs.png" "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/com.kagan.limeobs.png"
done

# Root seviyesi ikonlar (AppImage standardı)
convert "$ICON_SRC" -resize 256x256 "$APPDIR/limeobs.png"
convert "$ICON_SRC" -resize 256x256 "$APPDIR/com.kagan.limeobs.png"
convert "$ICON_SRC" -resize 256x256 "$APPDIR/.DirIcon"

echo "=== 2. PyInstaller ile Binary ve Bağımlılıkların Derlenmesi ==="
"$PROJECT_DIR/venv/bin/pyinstaller" \
    --noconfirm \
    --clean \
    --name "limeobs-bin" \
    --onedir \
    --windowed \
    --paths "$PROJECT_DIR" \
    --paths "$PROJECT_DIR/akbim_frontend" \
    --add-data "$PROJECT_DIR/akbim_frontend:akbim_frontend" \
    --add-data "$PROJECT_DIR/akbim_api.py:." \
    --collect-all gi \
    --collect-all requests \
    --collect-all bs4 \
    --collect-all PIL \
    "$PROJECT_DIR/akbim_frontend/main.py"

echo "=== 3. AppDir İçine Kopyalama ==="
cp -r dist/limeobs-bin/* "$APPDIR/usr/bin/"

# Masaüstü dosyası (AppImage root ve usr/share)
cat << 'DESKTOP' > "$APPDIR/limeobs.desktop"
[Desktop Entry]
Type=Application
Name=LimeOBS
GenericName=Öğrenci Bilgi Sistemi
Comment=Modern ve Akıcı Okul Yönetim Paneli
Exec=limeobs-bin
Icon=limeobs
Categories=Education;
Terminal=false
StartupWMClass=com.kagan.limeobs
DESKTOP
cp "$APPDIR/limeobs.desktop" "$APPDIR/usr/share/applications/limeobs.desktop"
cp "$APPDIR/limeobs.desktop" "$APPDIR/usr/share/applications/com.kagan.limeobs.desktop"

# AppRun
cat << 'APPRUN' > "$APPDIR/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/bin:${LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="${HERE}/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export GSETTINGS_SCHEMA_DIR="${HERE}/usr/share/glib-2.0/schemas:${GSETTINGS_SCHEMA_DIR}"

exec "${HERE}/usr/bin/limeobs-bin" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# Sistem şemalarını AppDir içerisine ekleyelim
mkdir -p "$APPDIR/usr/share/glib-2.0/schemas"
if [ -d /usr/share/glib-2.0/schemas ]; then
    cp -r /usr/share/glib-2.0/schemas/* "$APPDIR/usr/share/glib-2.0/schemas/" || true
    glib-compile-schemas "$APPDIR/usr/share/glib-2.0/schemas" || true
fi

echo "=== 4. AppImage Oluşturma ==="
ARCH=x86_64 "$PROJECT_DIR/tools/squashfs-root/AppRun" "$APPDIR" "$OUT_DIR/LimeOBS-x86_64.AppImage"

chmod +x "$OUT_DIR/LimeOBS-x86_64.AppImage"
echo "=== BAŞARILI: $OUT_DIR/LimeOBS-x86_64.AppImage oluşturuldu ==="
