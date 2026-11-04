#!/usr/bin/env bash
# LimeOBS'u bu kullanıcı için masaüstüne kurar: uygulama menüsü, KRunner araması ve ikonlar.
# Root gerektirmez; her şey ~/.local altına yazılır. Kaldırmak için: ./install_desktop.sh --uninstall
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPIMAGE="$PROJECT_DIR/dist_appimage/LimeOBS-x86_64.AppImage"
ICON_SRC="$PROJECT_DIR/akbim_frontend/app_icon.png"
APP_ID="com.kagan.limeobs"

BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
ICON_ROOT="$HOME/.local/share/icons/hicolor"
SIZES="16 22 24 32 48 64 128 256 512"

refresh_caches() {
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
    kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true
}

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN_DIR/limeobs" "$APPS_DIR/$APP_ID.desktop"
    for size in $SIZES; do
        rm -f "$ICON_ROOT/${size}x${size}/apps/$APP_ID.png"
    done
    refresh_caches
    echo "LimeOBS masaüstü entegrasyonu kaldırıldı."
    exit 0
fi

if command -v magick >/dev/null; then
    RESIZE=(magick)
elif command -v convert >/dev/null; then
    RESIZE=(convert)
else
    echo "HATA: İkonları boyutlandırmak için ImageMagick (magick/convert) gerekli." >&2
    exit 1
fi

echo "=== Başlatıcı ==="
mkdir -p "$BIN_DIR" "$APPS_DIR"
cat << EOF > "$BIN_DIR/limeobs"
#!/usr/bin/env bash
if [ -x "$PROJECT_DIR/venv/bin/python" ] && [ -f "$PROJECT_DIR/akbim_frontend/main.py" ]; then
    exec "$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/akbim_frontend/main.py" "\$@"
elif [ -x "$APPIMAGE" ]; then
    exec "$APPIMAGE" "\$@"
fi
echo "LimeOBS bulunamadı: $PROJECT_DIR" >&2
exit 1
EOF
chmod +x "$BIN_DIR/limeobs"

echo "=== İkonlar (hicolor) ==="
for size in $SIZES; do
    dir="$ICON_ROOT/${size}x${size}/apps"
    mkdir -p "$dir"
    "${RESIZE[@]}" "$ICON_SRC" -background none -resize "${size}x${size}" "$dir/$APP_ID.png"
done

echo "=== Masaüstü dosyası (uygulama menüsü + KRunner) ==="
cat << EOF > "$APPS_DIR/$APP_ID.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=LimeOBS
GenericName=Öğrenci Bilgi Sistemi
Comment=Modern ve Akıcı Okul Yönetim Paneli
Exec=$BIN_DIR/limeobs
TryExec=$BIN_DIR/limeobs
Icon=$APP_ID
Terminal=false
Categories=Education;
Keywords=limeobs;obs;akbim;tedem;okul;öğrenci;ders;sınav;
StartupWMClass=$APP_ID
StartupNotify=true
EOF

refresh_caches
echo "=== BAŞARILI: LimeOBS uygulama menüsüne ve KRunner'a eklendi ==="
