"""
LimeOBS telefon bildirimleri (Telegram).

Uygulama Telegram'a doğrudan bağlanmaz: istekler LimeOBS aracı sunucusuna (proxy/worker.js) gider, bot
anahtarı yalnızca orada durur. Bağlarken uygulama rastgele bir bağlantı kodu üretir ve kullanıcıyı
t.me/<bot>?start=<kod> adresine gönderir; kullanıcı Başlat'a basınca sunucu bu kodu kullanıcının Telegram
sohbetiyle eşler. Kod sistem anahtarlığında saklanır ve o sohbete bildirim göndermenin tek anahtarıdır.

Yeni kayıt takibi: ödevler, gelen mesajlar, duyurular, OBS bildirimleri ve sınav sonuçları. İlk kontrolde
mevcut kayıtlar "görüldü" sayılır (eski her şey bildirilmez); sonraki kontrollerde yalnızca yeniler gönderilir.
"""
import html
import json
import secrets
import time
from pathlib import Path

import keyring
import requests
from keyring.errors import KeyringError, PasswordDeleteError

import ai_assistant
import api_bridge

SERVICE = "LimeOBS"
CODE_KEY = "telegram_app_link_code"
CHECK_INTERVAL_MIN = 15

LABELS = {
    "homework": "📚 Yeni ödev",
    "mail": "✉️ Yeni mesaj",
    "announcement": "📢 Yeni duyuru",
    "notification": "🔔 OBS bildirimi",
    "exam": "📊 Sınav sonucu",
}


class TelegramError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşır."""


def _url(path):
    return ai_assistant.proxy_url().rstrip("/") + path


def _post(path, payload):
    try:
        res = requests.post(_url(path), json=payload, timeout=20)
    except requests.RequestException:
        raise TelegramError("LimeOBS sunucusuna bağlanılamadı. İnternet bağlantını kontrol et.")
    if res.status_code == 429:
        raise TelegramError("Çok sık denendi, biraz bekleyip tekrar dene.")
    if res.status_code == 410:
        clear_code()
        raise TelegramError("Botu Telegram'da engellemişsin; bağlantı kaldırıldı. Tekrar bağlanabilirsin.")
    if res.status_code == 404:
        return {"error": "not_linked"}
    if not res.ok:
        raise TelegramError(f"Telegram bildirimi gönderilemedi (HTTP {res.status_code}).")
    return res.json()


# ------------------------------------------------------------------ bağlantı kodu

def get_code():
    try:
        return keyring.get_password(SERVICE, CODE_KEY)
    except KeyringError:
        return None


def new_code():
    code = secrets.token_urlsafe(32)  # 43 karakter, Telegram start parametresine uygun
    keyring.set_password(SERVICE, CODE_KEY, code)
    return code


def clear_code():
    try:
        keyring.delete_password(SERVICE, CODE_KEY)
    except (PasswordDeleteError, KeyringError):
        pass


# ------------------------------------------------------------------ sunucu işlemleri

def bot_name():
    """Bildirim botunun kullanıcı adı; sunucuda bot kurulmamışsa None."""
    try:
        return requests.get(_url("/tg/info"), timeout=15).json().get("bot")
    except (requests.RequestException, ValueError):
        raise TelegramError("LimeOBS sunucusuna bağlanılamadı. İnternet bağlantını kontrol et.")


def is_linked(code=None):
    code = code or get_code()
    return bool(code) and bool(_post("/tg/status", {"code": code}).get("linked"))


def send(text):
    code = get_code()
    if not code:
        raise TelegramError("Telegram bağlı değil.")
    if _post("/tg/send", {"code": code, "text": text[:3800]}).get("error") == "not_linked":
        raise TelegramError("Telegram bağlantısı bulunamadı (botta /stop yazılmış olabilir). Tekrar bağlan.")


def unlink():
    code = get_code()
    if code:
        try:
            _post("/tg/unlink", {"code": code})
        finally:
            clear_code()


# ------------------------------------------------------------------ ayarlar ve durum dosyaları

def _settings_path(data_dir):
    return Path(data_dir) / "telegram_bildirim.json"


def load_settings(data_dir):
    try:
        return json.loads(_settings_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"kinds": list(LABELS)}


def save_settings(data_dir, settings):
    _settings_path(data_dir).write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")


def _state_path(data_dir):
    return Path(data_dir) / "telegram_gorulen.json"


# ------------------------------------------------------------------ yeni kayıt takibi

def collect_items():
    """Takip edilen kayıtlar: {tür: {kimlik: metin}}"""
    items = {k: {} for k in LABELS}
    for h in api_bridge.fetch_homeworks_list(force_refresh=True) or []:
        due = h.get("endDate", "")
        due = ".".join(reversed(due.split("-")[1:])) if len(due) == 10 else due  # 2026-11-27 → 27.11
        items["homework"][str(h.get("id"))] = f"{ai_assistant._tr_title(h.get('lesson', ''))}: {h.get('title', '')} (teslim {due})"
    inbox = (api_bridge.fetch_messages_data() or [[]])[0] or []
    for m in inbox:
        items["mail"][str(m.get("id"))] = f"{ai_assistant._tr_title(m.get('sender', ''))}: {(m.get('mailTitle') or '').strip()}"
    index = (api_bridge.get_adaptive_index_data(force_refresh=True) or {}).get("data") or {}
    for a in index.get("announcementList") or []:
        aid = a.get("id") or a.get("announcementId") or a.get("title")
        items["announcement"][str(aid)] = a.get("title") or a.get("baslik") or "Duyuru"
    for n in api_bridge.fetch_system_notifications() or []:
        items["notification"][str(n.get("id"))] = n.get("title", "Bildirim")
    for e in api_bridge.fetch_all_student_exams() or []:
        eid = e.get("examId") or e.get("id")
        if eid is None:
            continue
        point = e.get("point") or e.get("puan")
        name = e.get("examName") or e.get("name") or "Sınav"
        items["exam"][str(eid)] = f"{name}" + (f" — puan {point}" if point not in (None, "") else "")
    return items


def format_message(new):
    total = sum(len(v) for v in new.values())
    parts = [f"<b>🍋 LimeOBS — {total} yeni bildirim</b>"]
    for kind, entries in new.items():
        if entries:
            lines = "\n".join(f"• {html.escape(t)}" for t in list(entries.values())[:15])
            more = f"\n… ve {len(entries) - 15} tane daha" if len(entries) > 15 else ""
            parts.append(f"<b>{LABELS[kind]}</b>\n{lines}{more}")
    return "\n\n".join(parts)


def check_and_notify(data_dir):
    """Yeni kayıtları bulur ve Telegram'a gönderir. Döner: gönderilen kayıt sayısı (ilk çalıştırmada 0)."""
    if not get_code():
        return 0
    if not api_bridge.ensure_valid_session():
        raise TelegramError("OBS oturumu açılamadı.")
    kinds = set(load_settings(data_dir).get("kinds") or LABELS)
    path = _state_path(data_dir)
    try:
        seen = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        seen = None
    current = collect_items()
    merged = {k: sorted(set((seen or {}).get(k, [])) | set(v)) for k, v in current.items()}
    sent = 0
    if seen is not None:
        new = {k: {i: t for i, t in v.items() if i not in set(seen.get(k, []))}
               for k, v in current.items() if k in kinds}
        sent = sum(len(v) for v in new.values())
        if sent:
            send(format_message(new))  # hata olursa durum kaydedilmez, bir sonraki kontrolde tekrar denenir
    path.write_text(json.dumps(merged), encoding="utf-8")
    return sent


def mark_all_seen(data_dir):
    """Bağlanınca mevcut kayıtları görüldü say (eski kayıtlar bir anda gönderilmesin)."""
    _state_path(data_dir).write_text(json.dumps({k: sorted(v) for k, v in collect_items().items()}), encoding="utf-8")


def wait_for_link(code, timeout=180, interval=3, cancelled=lambda: False):
    """Kullanıcı Telegram'da Başlat'a basana kadar bekler."""
    end = time.time() + timeout
    while time.time() < end and not cancelled():
        try:
            if is_linked(code):
                return True
        except TelegramError:
            pass
        time.sleep(interval)
    return False
