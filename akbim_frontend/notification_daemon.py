#!/usr/bin/env python3
"""
LimeOBS Arka Plan Bildirim Servisi (Notification Daemon)
Uygulama kapalıyken bile belirli aralıklarla OBS sistemini kontrol eder:
- Yeni gelen mesajlar (Inbox mails)
- Yeni verilen ödevler (Homeworks)
- Yeni duyurular (Announcements)
- Yeni sınavlar ve etkinlikler
Tespit edildiğinde Linux masaüstüne (notify-send / libnotify) yerel bildirim gönderir.
"""

import sys
import time
import json
import subprocess
from pathlib import Path

# Proje dizinini sys.path'e ekle
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import akbim_api

CONFIG_FILE = PROJECT_DIR / "lime_daemon_state.json"
CHECK_INTERVAL_SECONDS = 180  # 3 dakikada bir kontrol et
ICON_PATH = PROJECT_DIR / "akbim_frontend" / "app_icon.png"


def load_previous_state():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "seen_mail_ids": [],
        "seen_homework_ids": [],
        "seen_announcement_ids": [],
        "seen_exam_ids": [],
        "last_check_timestamp": 0
    }


def save_state(state):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Daemon] Durum kaydetme hatası: {e}")


def send_system_notification(title, message, urgency="normal"):
    """
    Sistem masaüstü bildirimini tetikler.
    macOS: 'osascript -e display notification'
    Linux: 'notify-send'
    """
    import sys
    try:
        if sys.platform == "darwin":
            # macOS AppleScript ile yerel bildirim
            safe_title = title.replace('"', '\\"')
            safe_msg = message.replace('"', '\\"')
            script = f'display notification "{safe_msg}" with title "{safe_title}" subtitle "LimeOBS"'
            subprocess.run(["osascript", "-e", script], check=False)
            print(f"[Daemon] macOS Bildirim gönderildi: {title} -> {message}")
        elif sys.platform.startswith("win"):
            # Windows PowerShell Toast Bildirimi
            safe_title = title.replace('"', '`"')
            safe_msg = message.replace('"', '`"')
            ps_cmd = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
                f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                f"$textNodes = $template.GetElementsByTagName('text'); "
                f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) > $null; "
                f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) > $null; "
                f"$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LimeOBS'); "
                f"$notification = [Windows.UI.Notifications.ToastNotification]::new($template); "
                f"$notifier.Show($notification)"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False)
            print(f"[Daemon] Windows Bildirim gönderildi: {title} -> {message}")
        else:
            # Linux notify-send
            cmd = [
                "notify-send",
                title,
                message,
                "-a", "LimeOBS",
                "-u", urgency,
            ]
            if ICON_PATH.exists():
                cmd.extend(["-i", str(ICON_PATH)])
            subprocess.run(cmd, check=False)
            print(f"[Daemon] Linux Bildirim gönderildi: {title} -> {message}")
    except Exception as e:
        print(f"[Daemon] Bildirim gönderme hatası: {e}")


def check_updates():
    # 1. Oturum yükle ve kontrol et
    loaded = akbim_api.load_session()
    if not loaded:
        print("[Daemon] Kayıtlı oturum bulunamadı. Bekleniyor...")
        return

    is_valid = akbim_api.check_session()
    if not is_valid:
        print("[Daemon] Oturum süresi dolmuş veya geçersiz.")
        return

    state = load_previous_state()
    seen_mails = set(state.get("seen_mail_ids", []))
    seen_hws = set(state.get("seen_homework_ids", []))
    seen_anns = set(state.get("seen_announcement_ids", []))

    # İlk çalıştırma kontrolü (kullanıcıyı eski tüm bildirimlerle boğmamak için)
    is_initial_run = (state.get("last_check_timestamp", 0) == 0)

    # 2. Gelen Mesajları Kontrol Et
    try:
        res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/mail/getInbox", timeout=15)
        if res.ok:
            data = res.json()
            mails = data.get("data", {}).get("mail", [])
            for m in mails:
                mid = str(m.get("id"))
                if mid and mid not in seen_mails:
                    seen_mails.add(mid)
                    if not is_initial_run:
                        sender = m.get("sender") or "Öğretmen"
                        title = m.get("mailTitle") or "Yeni Mesaj"
                        send_system_notification(
                            f"📩 Yeni Mesaj: {sender}",
                            f"{title}\nOkumak için LimeOBS'u açın."
                        )
    except Exception as e:
        print(f"[Daemon] Mesaj kontrolü hatası: {e}")

    # 3. Ödevleri Kontrol Et
    try:
        res_hw = akbim_api.homeworks()
        if isinstance(res_hw, dict) and res_hw.get("success"):
            hws = res_hw.get("data", [])
            for h in hws:
                hid = str(h.get("id"))
                if hid and hid not in seen_hws:
                    seen_hws.add(hid)
                    if not is_initial_run:
                        lesson = h.get("lesson") or "Ders"
                        end_date = h.get("endDate") or ""
                        send_system_notification(
                            f"📚 Yeni Ödev Verildi: {lesson}",
                            f"Son Teslim: {end_date}\nDetaylar için LimeOBS'u açın."
                        )
    except Exception as e:
        print(f"[Daemon] Ödev kontrolü hatası: {e}")

    # 4. Duyuruları Kontrol Et
    try:
        # adaptive index
        idx_res = akbim_api.session.post(
            f"{akbim_api.BASEURL}/pages/student/require/indexAction.php",
            data={"request": "loadIndex"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=15
        )
        if idx_res.ok:
            idata = idx_res.json().get("data", {})
            announcements = idata.get("announcementList", [])
            for a in announcements:
                aid = str(a.get("id"))
                if aid and aid not in seen_anns:
                    seen_anns.add(aid)
                    if not is_initial_run:
                        atitle = a.get("title") or "Okul Duyurusu"
                        send_system_notification(
                            "📢 Yeni Okul Duyurusu",
                            f"{atitle}"
                        )
    except Exception as e:
        print(f"[Daemon] Duyuru kontrolü hatası: {e}")

    # Durumu güncelle
    state["seen_mail_ids"] = list(seen_mails)
    state["seen_homework_ids"] = list(seen_hws)
    state["seen_announcement_ids"] = list(seen_anns)
    state["last_check_timestamp"] = int(time.time())
    save_state(state)


def main():
    print(f"[Daemon] LimeOBS arka plan servisi başlatıldı (Aralık: {CHECK_INTERVAL_SECONDS} sn)...")
    while True:
        try:
            check_updates()
        except Exception as e:
            print(f"[Daemon] Döngü hatası: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
