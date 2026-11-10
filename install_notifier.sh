#!/usr/bin/env bash
# LimeOBS bildirim zamanlayıcılarını (systemd kullanıcı servisi) kurar. Root gerektirmez.
#   - Hafta içi 08:50: sabah özeti
#   - Hafta içi 08:00-20:30 her 30 dk, hafta sonu 12:00 ve 18:00: yeni ödev/mesaj/duyuru kontrolü
#   - Telegram botu (/bugun, /yarin, /odev, /yemek, /sinav) sürekli çalışan servis olarak
# Kanallar: Telegram (anında) + giden kutusu (Claude zamanlanmış görevi Gmail'den gönderir).
# OBS girişi ve Telegram anahtarı sistem anahtarlığından okunur (telegram_setup.py ile kaydedilir).
# Kaldırmak için: ./install_notifier.sh --uninstall
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
CHANNELS="${LIMEOBS_CHANNELS:-telegram,outbox}"

if [ "$1" = "--uninstall" ]; then
    systemctl --user disable --now limeobs-digest.timer limeobs-check.timer limeobs-bot.service 2>/dev/null || true
    rm -f "$UNIT_DIR"/limeobs-digest.{service,timer} "$UNIT_DIR"/limeobs-check.{service,timer} "$UNIT_DIR"/limeobs-bot.service
    systemctl --user daemon-reload
    echo "LimeOBS bildirim zamanlayıcıları kaldırıldı."
    exit 0
fi

mkdir -p "$UNIT_DIR"

for mode in digest check; do
cat > "$UNIT_DIR/limeobs-$mode.service" << EOF
[Unit]
Description=LimeOBS bildirimleri ($mode)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
Environment=LIMEOBS_CHANNELS=$CHANNELS
ExecStart="$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/scripts/obs_mailer.py" $mode
TimeoutStartSec=180
EOF
done

cat > "$UNIT_DIR/limeobs-digest.timer" << 'EOF'
[Unit]
Description=LimeOBS sabah özeti (hafta içi 08:50)

[Timer]
OnCalendar=Mon..Fri *-*-* 08:50:00
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

cat > "$UNIT_DIR/limeobs-check.timer" << 'EOF'
[Unit]
Description=LimeOBS yeni kayıt kontrolü

[Timer]
OnCalendar=Mon..Fri *-*-* 08..20:00,30:00
OnCalendar=Sat,Sun *-*-* 12,18:00:00
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

cat > "$UNIT_DIR/limeobs-bot.service" << EOF
[Unit]
Description=LimeOBS Telegram botu
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$PROJECT_DIR
ExecStart="$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/scripts/telegram_bot.py"
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now limeobs-digest.timer limeobs-check.timer
systemctl --user enable limeobs-bot.service
systemctl --user restart limeobs-bot.service
echo "=== Kuruldu. Sonraki çalışmalar: ==="
systemctl --user list-timers 'limeobs-*' --no-pager
