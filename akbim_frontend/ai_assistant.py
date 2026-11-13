"""
LimeOBS yapay zekâ asistanı (GTK'dan bağımsız).

Küçük modeller ham veriden hesap yaparken uyduruyor; bu yüzden puan farkları, en yüksek puan, teslim
tarihleri gibi her şeyi önce kod hesaplar ("doğrulanmış bilgiler") ve model yalnızca bunları yorumlar.

Model Groq üzerinden çalışır ama uygulama Groq'a doğrudan bağlanmaz: istekler LimeOBS'un aracı sunucusuna
(proxy/ klasöründeki Cloudflare Worker) gider. Groq anahtarı yalnızca o sunucuda gizli değişken olarak durur;
uygulamada ve kullanıcıda hiçbir anahtar yoktur. Sunucu kişi başı kullanım sınırı uygular.
"""
import json
import os
import time
from datetime import date, datetime, timedelta

import requests

import api_bridge
from food_menu import parse_day_date_obj, parse_food_menu

# Cloudflare Worker yayınlandıktan sonra adresi buraya yazılır (ör. https://limeobs-ai.<hesap>.workers.dev).
# Geliştirme için LIMEOBS_AI_PROXY ortam değişkeni ya da config'teki ai_assistant.proxy_url da kullanılabilir.
AI_PROXY_URL = "https://limeobs-ai.limeobs.workers.dev"

DEFAULTS = {
    "proxy_url": "",
}

DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

SYSTEM_PROMPT = """Sen LimeOBS'un öğrenci asistanısın; 7. sınıf bir öğrenciyle Türkçe konuşuyorsun.
Sana her soruda okulun OBS sisteminden alınmış "DOĞRULANMIŞ BİLGİLER" veriliyor. Puan farkları, en yüksek \
puan, kalan gün sayısı gibi hesaplar zaten yapılmış durumda; kendin yeniden hesaplama, verilen sayıları kullan.
- Yalnızca bu bilgilere dayan. Bilgilerde olmayan bir ödev, sınav, ders ya da sayı uydurma; \
bilmiyorsan "OBS'de bu bilgi yok" de.
- Kısa ve net yaz: birkaç cümle ya da en fazla 6 maddelik liste. Gerektiğinde **kalın** kullanabilirsin.
- Samimi ve cesaretlendirici ol ama abartma. Çalışma önerilerin somut olsun (hangi ders, ne kadar süre).
- Ödevin çözümünü yazma; nasıl yaklaşacağını ve neye dikkat edeceğini anlat."""

QUICK_ACTIONS = [
    ("Haftamı analiz et", "Bu haftaki ödev ve ders yükümü analiz et, nelere öncelik vermeliyim?"),
    ("Sınav gidişatım", "Deneme sınavlarındaki gidişatımı yorumla: nerede iyiyim, nereye çalışmalıyım?"),
    ("Yarına hazırlık", "Yarın için neye hazırlanmalıyım? Dersler ve teslim edeceğim ödevlere göre kısa bir plan yap."),
]


class AssistantError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşır."""


# --------------------------------------------------------------------------- Ayarlar

def load_settings():
    settings = dict(DEFAULTS)
    try:
        with open(api_bridge.CONFIG_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f).get("ai_assistant") or {})
    except (OSError, ValueError):
        pass
    return settings


def proxy_url():
    return (os.environ.get("LIMEOBS_AI_PROXY") or load_settings().get("proxy_url") or AI_PROXY_URL).rstrip("/")


def service_configured():
    return bool(proxy_url())


# --------------------------------------------------------------------------- Doğrulanmış bilgiler

def _tr_title(text):
    def word(w):
        low = w.replace("I", "ı").replace("İ", "i").lower()
        if low in ("ve", "ile", "veya"):
            return low
        return {"i": "İ", "ı": "I"}.get(low[:1], low[:1].upper()) + low[1:]
    return " ".join(word(w) for w in (text or "").split())


def _fmt(d):
    return f"{d.day}.{d.month}.{d.year} {DAY_NAMES[d.weekday()]}"


def _next_school_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _lessons_for(index, day):
    sched = (index.get("lessonSchedule") or {}).get("data") or {}
    names = []
    for cell in sorted(sched.get("data") or [], key=lambda c: c.get("x") or 0):
        if cell.get("y") == day.isoweekday():
            text = cell.get("text") or []
            name = _tr_title(text[1] if len(text) > 1 else (text[0] if text else ""))
            if name:
                names.append(name)
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    return [f"{n} ({c} saat)" if c > 1 else n for n, c in counts.items()]


def _exam_trends(exams):
    """Sınavları türüne göre gruplar ve gidişatı hesaplar."""
    groups = {}
    for e in exams or []:
        try:
            d = datetime.strptime(e.get("examDate", ""), "%d.%m.%Y").date()
        except ValueError:
            continue
        name = e.get("examName", "")
        kind = "DAS" if "DAS" in name.upper() else ("Deneme" if "DENEME" in name.upper() else "Diğer")
        groups.setdefault(kind, []).append({
            "tarih": d, "ad": name, "puan": float(e.get("point") or 0), "net": float(e.get("net") or 0),
            "dogru": e.get("dogru"), "yanlis": e.get("yanlis"), "bos": e.get("bos"),
        })
    lines = []
    for kind, items in groups.items():
        items.sort(key=lambda x: x["tarih"])
        lines.append(f"{kind} sınavları (eskiden yeniye):")
        for x in items:
            lines.append(f"  - {x['tarih'].day}.{x['tarih'].month} {x['ad']}: puan {x['puan']:.1f}, net {x['net']:.2f} "
                         f"(D {x['dogru']} / Y {x['yanlis']} / B {x['bos']})")
        if len(items) >= 2:
            last, prev, first = items[-1], items[-2], items[0]
            best = max(items, key=lambda x: x["puan"])
            lines.append(f"  * Son sınav bir öncekine göre puan {last['puan'] - prev['puan']:+.1f}, "
                         f"net {last['net'] - prev['net']:+.2f}.")
            lines.append(f"  * İlk sınavdan son sınava puan {last['puan'] - first['puan']:+.1f}, "
                         f"net {last['net'] - first['net']:+.2f}.")
            lines.append(f"  * En yüksek puan: {best['puan']:.1f} ({best['ad']})"
                         + (" — bu son sınav." if best is last else "."))
            streak = 0
            for a, b in zip(items[::-1][1:], items[::-1]):
                if b["puan"] > a["puan"]:
                    streak += 1
                else:
                    break
            if streak >= 2:
                lines.append(f"  * Son {streak + 1} sınavda puan sürekli yükseliyor.")
    return lines


def _menu_for(day):
    try:
        data = api_bridge.fetch_food_list_data()
        for week in parse_food_menu(data.get("pdf_bytes")) if data.get("pdf_bytes") else []:
            for d in week["days"]:
                if parse_day_date_obj(d["date"], default_year=day.year) == day:
                    return [m for m in d["meals"] if m.strip().lower() not in ("bardak su", "su")]
    except Exception:
        pass
    return []


_FACTS_CACHE = {"time": 0.0, "text": None}


def build_facts(force=False):
    """OBS verisinden kodla hesaplanmış, modele verilecek bilgi metnini üretir (5 dk önbellek)."""
    if not force and _FACTS_CACHE["text"] and time.time() - _FACTS_CACHE["time"] < 300:
        return _FACTS_CACHE["text"]
    if not api_bridge.ensure_valid_session():
        raise AssistantError("OBS oturumu açık değil. Lütfen tekrar giriş yapın.")

    today = date.today()
    tomorrow = _next_school_day(today)
    index = (api_bridge.get_adaptive_index_data() or {}).get("data") or {}

    lines = [f"Bugün: {_fmt(today)}. Bir sonraki okul günü: {_fmt(tomorrow)}."]
    if today.weekday() < 5:
        lessons = _lessons_for(index, today)
        lines.append("Bugünün dersleri: " + (", ".join(lessons) if lessons else "yok") + ".")
    lessons = _lessons_for(index, tomorrow)
    lines.append(f"{_fmt(tomorrow)} dersleri: " + (", ".join(lessons) if lessons else "yok") + ".")

    menu = _menu_for(today if today.weekday() < 5 else tomorrow)
    if menu:
        lines.append("Öğle yemeği: " + ", ".join(_tr_title(m) for m in menu) + ".")

    pending = []
    for h in api_bridge.fetch_homeworks_list() or []:
        if h.get("status") == 1:  # Tamamlandı
            continue
        try:
            due = datetime.strptime(h.get("endDate", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if due >= today:
            pending.append((due, h))
    pending.sort(key=lambda x: x[0])
    lines.append(f"Teslim edilmemiş ve süresi geçmemiş ödevler ({len(pending)} adet):")
    for due, h in pending[:25]:
        left = (due - today).days
        when = "bugün" if left == 0 else ("yarın" if left == 1 else f"{left} gün sonra")
        lines.append(f"  - {h.get('title', '')} — {_tr_title(h.get('lesson', ''))}, teslim {_fmt(due)} ({when}), "
                     f"durum: {h.get('statusName', '')}")

    upcoming = []
    for e in index.get("examList") or []:
        try:
            d = datetime.strptime(e.get("sinavTarih", ""), "%d.%m.%Y").date()
        except ValueError:
            continue
        if today <= d <= today + timedelta(days=21):
            upcoming.append(f"  - {e.get('sinavAd', 'Sınav')} — {_fmt(d)} ({(d - today).days} gün sonra)")
    lines.append("Önümüzdeki 3 haftadaki sınavlar:" if upcoming else "Önümüzdeki 3 haftada planlanmış sınav yok.")
    lines.extend(upcoming)

    lines.extend(_exam_trends(api_bridge.fetch_all_student_exams()))

    text = "\n".join(lines)
    _FACTS_CACHE.update(time=time.time(), text=text)
    return text


# --------------------------------------------------------------------------- Aracı sunucu (Groq)

def _ask_proxy(messages, on_text):
    base = proxy_url()
    if not base:
        raise AssistantError("Asistan servisi henüz kurulmadı.")
    try:
        res = requests.post(f"{base}/v1/chat", json={"messages": messages}, stream=True, timeout=(10, 120),
                            headers={"User-Agent": "LimeOBS"})
    except requests.exceptions.RequestException:
        raise AssistantError("Asistan servisine bağlanılamadı. İnternet bağlantınızı kontrol edin.")
    if res.status_code == 429:
        raise AssistantError("Kısa sürede çok fazla soru sordun. Biraz bekleyip tekrar dene.")
    if res.status_code == 413:
        raise AssistantError("Soru çok uzun. Daha kısa yazmayı dene.")
    if not res.ok:
        raise AssistantError(f"Asistan şu an cevap veremiyor (HTTP {res.status_code}). Biraz sonra tekrar dene.")

    out = []
    res.encoding = "utf-8"
    for line in res.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            delta = json.loads(data)["choices"][0].get("delta") or {}
        except (ValueError, KeyError, IndexError):
            continue
        piece = delta.get("content")
        if piece:
            out.append(piece)
            on_text(piece)
    return "".join(out)


class Conversation:
    """Asistan sohbeti: her soruya güncel doğrulanmış bilgileri ekler, önceki soru-cevapları hatırlar."""

    def __init__(self):
        self.history = []

    def reset(self):
        self.history = []

    def ask(self, question, on_text):
        facts = build_facts()
        # Groq, GPT-OSS gibi düşünen modellerde talimatların sistem mesajı yerine kullanıcı mesajında olmasını öneriyor
        user_content = f"{SYSTEM_PROMPT}\n\nDOĞRULANMIŞ BİLGİLER:\n{facts}\n\nSORU: {question}"
        messages = self.history + [{"role": "user", "content": user_content}]
        answer = _ask_proxy(messages, on_text)
        # Geçmişte bilgileri tekrar taşımamak için yalnızca soruyu sakla
        self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]
        self.history = self.history[-12:]
        return answer
