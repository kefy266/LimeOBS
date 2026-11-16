#!/usr/bin/env bash
# LimeOBS Android için kalıcı imza anahtarı oluşturur ve GitHub Actions'a gizli değişken olarak yükler.
# Otomatik güncellemenin çalışması için tüm APK'ların AYNI anahtarla imzalanması gerekir.
# Bir kez çalıştırılır. Anahtar ve şifresi ~/.local/share/limeobs/android-imza/ klasöründe yedeklenir:
# bu klasörü kaybetme (kaybedersen yeni anahtar gerekir ve herkes uygulamayı bir kez silip yeniden kurmalı).
set -euo pipefail

DEPO="kefy266/LimeOBS"
KLASOR="$HOME/.local/share/limeobs/android-imza"
ANAHTAR="$KLASOR/limeobs.jks"
SIFRE_DOSYASI="$KLASOR/sifre.txt"

mkdir -p "$KLASOR"
chmod 700 "$KLASOR"

if [[ -f "$ANAHTAR" ]]; then
    echo "Anahtar zaten var: $ANAHTAR (yeniden oluşturulmuyor)"
else
    umask 077
    head -c 24 /dev/urandom | base64 | tr -d '/+=' > "$SIFRE_DOSYASI"
    keytool -genkeypair -v -keystore "$ANAHTAR" -storetype PKCS12 -alias limeobs \
        -keyalg RSA -keysize 4096 -validity 10000 \
        -storepass:file "$SIFRE_DOSYASI" -keypass:file "$SIFRE_DOSYASI" \
        -dname "CN=LimeOBS, O=LimeOBS, C=TR" >/dev/null
    echo "Anahtar oluşturuldu: $ANAHTAR"
fi

base64 -w0 "$ANAHTAR" | gh secret set LIMEOBS_KEYSTORE_B64 --repo "$DEPO"
gh secret set LIMEOBS_KEYSTORE_PASS --repo "$DEPO" < "$SIFRE_DOSYASI"
echo "GitHub gizli değişkenleri ayarlandı (LIMEOBS_KEYSTORE_B64, LIMEOBS_KEYSTORE_PASS)."
echo "Şimdi yeni derleme başlatılıyor…"
gh workflow run android.yml --repo "$DEPO" --ref android
echo "Bitti. Derleme birkaç dakika sürer: https://github.com/$DEPO/actions"
