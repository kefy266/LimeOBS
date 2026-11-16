"""
LimeOBS telefon bildirimleri (Telegram) — herkes kendi botunu kullanır.

Kullanıcı Telegram'da @BotFather ile kendi botunu oluşturur ve verdiği anahtarı uygulamaya yapıştırır.
Uygulama anahtarı doğrular, botun sohbetini açar; kullanıcı Başlat'a basınca sohbet kimliğini getUpdates ile
bulur. Anahtar ve sohbet kimliği yalnızca bu bilgisayarın sistem anahtarlığında saklanır; istekler doğrudan
api.telegram.org'a gider, hiçbir LimeOBS sunucusundan geçmez.

Yeni kayıt takibi: ödevler, gelen mesajlar, duyurular, OBS bildirimleri ve sınav sonuçları. Bağlanınca
mevcut kayıtlar "görüldü" sayılır (eski her şey bildirilmez); sonraki kontrollerde yalnızca yeniler gönderilir.
"""
import html
import json
import re
import time
from pathlib import Path

import keyring
import requests
from keyring.errors import KeyringError, PasswordDeleteError

import ai_assistant
import api_bridge

SERVICE = "LimeOBS"
TOKEN_KEY = "telegram_app_bot_token"
CHAT_KEY = "telegram_app_chat_id"
CHECK_INTERVAL_MIN = 15
TOKEN_RE = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,60}$")

LABELS = {
    "homework": "📚 Yeni ödev",
    "mail": "✉️ Yeni mesaj",
    "announcement": "📢 Yeni duyuru",
    "notification": "🔔 OBS bildirimi",
    "exam": "📊 Sınav sonucu",
}


class TelegramError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşır."""


def _call(token, method, **params):
    try:
        res = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=25)
    except requests.RequestException:
        raise TelegramError("Telegram'a bağlanılamadı. İnternet bağlantını kontrol et.")
    try:
        data = res.json()
    except ValueError:
        data = {}
    if data.get("ok"):
        return data["result"]
    code = data.get("error_code") or res.status_code
    if code == 401 or code == 404:
        raise TelegramError("Bot anahtarı geçersiz. BotFather'ın verdiği anahtarı eksiksiz yapıştırdığından emin ol.")
    if code == 403:
        raise TelegramError("Bot engellenmiş ya da sohbet silinmiş. Botun sohbetini açıp Başlat'a bas, sonra tekrar bağlan.")
    if code == 409:
        raise TelegramError("Bu bot başka bir yerde kullanılıyor (webhook ya da başka bir program). LimeOBS için yeni bir bot oluştur.")
    if code == 429:
        raise TelegramError("Telegram çok sık istek aldı, biraz bekleyip tekrar dene.")
    raise TelegramError(f"Telegram hatası: {data.get('description') or code}")


# ------------------------------------------------------------------ anahtarlık

def _get(key):
    try:
        return keyring.get_password(SERVICE, key)
    except KeyringError:
        return None


def credentials():
    """(bot anahtarı, sohbet kimliği); bağlı değilse (None, None)."""
    token, chat = _get(TOKEN_KEY), _get(CHAT_KEY)
    return (token, chat) if token and chat else (None, None)


def is_linked():
    return credentials()[0] is not None


def clear():
    for key in (TOKEN_KEY, CHAT_KEY):
        try:
            keyring.delete_password(SERVICE, key)
        except (PasswordDeleteError, KeyringError):
            pass


# ------------------------------------------------------------------ bağlanma

def verify_token(token):
    """Anahtarı doğrular; botun kullanıcı adını döner."""
    token = (token or "").strip()
    if not TOKEN_RE.match(token):
        raise TelegramError("Bu bir bot anahtarına benzemiyor. Anahtar \"123456789:AAE…\" biçiminde olmalı.")
    return _call(token, "getMe")["username"]


def wait_for_chat(token, timeout=180, cancelled=lambda: False):
    """Kullanıcı botun sohbetinde Başlat'a basana (ya da bir mesaj yazana) kadar bekler; (sohbet kimliği, ad) döner."""
    offset = None
    # Daha önce gelmiş eski mesajları atla: yalnızca bağlanma başladıktan sonraki mesajlar sayılır
    old = _call(token, "getUpdates", timeout=0)
    if old:
        offset = old[-1]["update_id"] + 1
    end = time.time() + timeout
    while time.time() < end and not cancelled():
        params = {"timeout": 5, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        for u in _call(token, "getUpdates", **params):
            offset = u["update_id"] + 1
            chat = (u.get("message") or {}).get("chat") or {}
            if chat.get("type") == "private":
                return str(chat["id"]), chat.get("first_name") or ""
    return None, None


def save(token, chat_id):
    keyring.set_password(SERVICE, TOKEN_KEY, token.strip())
    keyring.set_password(SERVICE, CHAT_KEY, chat_id)


def send(text):
    token, chat = credentials()
    if not token:
        raise TelegramError("Telegram bağlı değil.")
    _call(token, "sendMessage", chat_id=chat, text=text[:4000], parse_mode="HTML",
          link_preview_options={"is_disabled": True})


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
    if not is_linked():
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
