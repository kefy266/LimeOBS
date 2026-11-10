"""
LimeOBS Telegram botu: komutlara OBS verisiyle cevap verir.

Komutlar:
  /bugun  Bugünün dersleri, yemeği ve yarın teslim edilecek ödevler
  /yarin  Bir sonraki okul gününün dersleri, yemeği ve o gün teslim edilecek ödevler
  /odev   Teslim edilmemiş, tarihi geçmemiş ödevler
  /yemek  Bugünün (okul günü değilse bir sonraki okul gününün) yemeği
  /sinav  Önümüzdeki 14 gündeki sınavlar

Yalnızca anahtarlıktaki (telegram_setup.py ile kaydedilen) sohbetten gelen mesajlara cevap verir;
başka kimse botu kullanarak OBS bilgisi alamaz. systemd kullanıcı servisi olarak sürekli çalışır:
install_notifier.sh kurar.
"""
import html
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_mailer as m  # noqa: E402

COMMANDS = [
    ("bugun", "Bugünün dersleri, yemeği ve yarınki ödevler"),
    ("yarin", "Yarının dersleri, yemeği ve ödevleri"),
    ("odev", "Teslim edilmemiş ödevler"),
    ("yemek", "Günün yemeği"),
    ("sinav", "Yaklaşan sınavlar"),
]


def api(token, method, **params):
    res = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=70)
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", f"HTTP {res.status_code}"))
    return data["result"]


def ensure_login():
    m.login()  # oturum geçerliyse önbellekten döner (120 sn), düşmüşse anahtarlıktaki bilgilerle yeniden girer


def school_day(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def lessons_sentence(index, day):
    counts = {}
    for lesson in m.todays_lessons(index, day):
        name = m.tr_title(lesson["lesson"])
        counts[name] = counts.get(name, 0) + 1
    names = [f"{n} ({c} saat)" if c > 1 else n for n, c in counts.items()]
    return f"{m.join_tr(names)}." if names else "Ders görünmüyor."


def menu_sentence(day):
    menu = [x for x in (m.todays_menu(day) or []) if x.strip().lower() not in m.SKIP_MEALS]
    if not menu:
        return "Menü listede bulunamadı."
    text = m.join_tr([m.tr_lower(x) for x in menu])
    return m.tr_title(text.split()[0]) + text[len(text.split()[0]):] + "."


def homework_lines(homeworks, due_day=None, today=None):
    items = []
    for h in m.due_homeworks(homeworks, today, days=60):
        if due_day is None or h["date"] == due_day:
            when = "" if due_day else f'{h["date"].day} {m.MONTHS[h["date"].month - 1]} — '
            items.append(f'• {when}{html.escape(h["title"])} ({html.escape(m.tr_title(h["lesson"]))})')
    return items


def day_report(day, today, title, due_day):
    index = (m.api_bridge.get_adaptive_index_data(force_refresh=True) or {}).get("data") or {}
    homeworks = m.api_bridge.fetch_homeworks_list(force_refresh=True)
    hw = homework_lines(homeworks, due_day=due_day, today=today)
    if due_day == today + timedelta(days=1):
        due_label = "Yarın teslim"
    elif due_day == day:
        due_label = "O gün teslim"
    else:
        due_label = f"{m.DAY_NAMES[due_day.weekday()]} teslim"
    parts = [
        f"<b>{title} — {html.escape(m.fmt_date(day))}</b>",
        f"<b>📅 Dersler</b>\n{html.escape(lessons_sentence(index, day))}",
        f"<b>🍲 Yemek</b>\n{html.escape(menu_sentence(day))}",
        f"<b>📚 {due_label}</b>\n" + ("\n".join(hw) if hw else "Teslim edilecek ödev yok."),
    ]
    return "\n\n".join(parts)


def handle(command):
    today = m.now_tr().date()
    ensure_login()
    if command in ("start", "help", "yardim"):
        return "<b>LimeOBS komutları</b>\n" + "\n".join(f"/{c} — {d}" for c, d in COMMANDS)
    if command == "bugun":
        return day_report(today, today, "📌 Bugün", m.next_school_day(today))
    if command == "yarin":
        day = school_day(today + timedelta(days=1))
        return day_report(day, today, "➡️ Yarın", day)
    if command == "odev":
        hw = homework_lines(m.api_bridge.fetch_homeworks_list(force_refresh=True), today=today)
        return "<b>📚 Teslim edilmemiş ödevler</b>\n" + ("\n".join(hw) if hw else "Bekleyen ödev yok 🎉")
    if command == "yemek":
        day = school_day(today)
        return f"<b>🍲 Yemek — {html.escape(m.fmt_date(day))}</b>\n{html.escape(menu_sentence(day))}"
    if command == "sinav":
        index = (m.api_bridge.get_adaptive_index_data(force_refresh=True) or {}).get("data") or {}
        exams = m.upcoming_exams(index, today, days=14)
        lines = [f'• {e["date"].day} {m.MONTHS[e["date"].month - 1]} — {html.escape(e["name"])}' for e in exams]
        return "<b>📝 Yaklaşan sınavlar (14 gün)</b>\n" + ("\n".join(lines) if lines else "Sınav yok.")
    return "Bu komutu bilmiyorum. /help yazarak komutları görebilirsin."


def main():
    token, chat_id = m.get_secret("telegram_bot_token"), m.get_secret("telegram_chat_id")
    if not token or not chat_id:
        raise SystemExit("Telegram ayarı yok: önce scripts/telegram_setup.py çalıştırın.")
    api(token, "setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
    m.log("bot başladı.")
    offset = None
    while True:
        try:
            updates = api(token, "getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
        except Exception as e:
            m.log(f"getUpdates hatası: {type(e).__name__}")
            time.sleep(10)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message") or {}
            if str(msg.get("chat", {}).get("id")) != str(chat_id):
                continue  # yalnızca kayıtlı sohbet
            text = (msg.get("text") or "").strip()
            if not text.startswith("/"):
                continue
            command = text[1:].split()[0].split("@")[0].lower()
            command = command.translate(str.maketrans("ıüğşöç", "iugsoc"))
            m.log(f"komut: /{command}")
            try:
                reply = handle(command)
            except Exception as e:
                m.log(f"komut hatası: {type(e).__name__}")
                reply = "Şu an OBS'ye ulaşılamadı, biraz sonra tekrar dene."
            try:
                api(token, "sendMessage", chat_id=chat_id, text=reply[:4000], parse_mode="HTML",
                    disable_web_page_preview=True)
            except Exception as e:
                m.log(f"cevap gönderilemedi: {type(e).__name__}")


if __name__ == "__main__":
    os.chdir(m.ROOT)
    main()
