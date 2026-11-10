"""
LimeOBS e-posta bildirimleri. Gizli kefy266/LimeOBS-mailer deposundaki zamanlanmış GitHub Actions
işi bu betiği çalıştırır; şifreler ve iş kayıtları o gizli depoda durur.

Modlar:
  digest  Sabah özeti: günün ders programı, yemek listesi, yaklaşan sınavlar, teslimi yaklaşan ödevler
  check   Yeni ödev / gelen mesaj / duyuru / OBS bildirimi varsa e-posta gönderir
  test    Sabah özetini hemen gönderir (konu satırında [TEST])

Ortam değişkenleri (LimeOBS-mailer > Settings > Secrets and variables > Actions):
  OBS_TC, OBS_PASSWORD         OBS giriş bilgileri
  GMAIL_USER                   Gönderen Gmail adresi
  GMAIL_APP_PASSWORD           Gmail uygulama şifresi (gerçek Gmail şifresi DEĞİL)
  MAIL_TO                      (isteğe bağlı) alıcı; boşsa GMAIL_USER
  OBS_BASE_URL                 (isteğe bağlı) varsayılan https://tedemkolejiobs.com
  STATE_FILE                   (isteğe bağlı) görülen kayıtların tutulduğu dosya

Depo herkese açık olduğundan iş kayıtlarına ad, ders, not gibi kişisel bilgi YAZILMAZ; yalnızca sayılar.
Yerel önizleme: python scripts/obs_mailer.py digest --dry-run onizleme.html
"""
import argparse
import html
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "akbim_frontend")]

import akbim_api  # noqa: E402
import api_bridge  # noqa: E402
from food_menu import parse_food_menu, parse_day_date_obj  # noqa: E402

TR_TZ = timezone(timedelta(hours=3))  # Türkiye yaz saati uygulamıyor, sabit UTC+3
DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
          "Eylül", "Ekim", "Kasım", "Aralık"]


def tr_title(text):
    """Türkçe uyumlu baş harf büyütme: 'PİRİNÇ PİLAVI' -> 'Pirinç Pilavı' (str.title() 'Pi̇ri̇nç Pilavi' yapar)."""
    def word(w):
        low = w.replace("I", "ı").replace("İ", "i").lower()
        head = {"i": "İ", "ı": "I"}.get(low[:1], low[:1].upper())
        return head + low[1:]
    return " ".join(word(w) for w in text.split())


def log(msg):
    print(f"[obs-mailer] {msg}", flush=True)


def now_tr():
    return datetime.now(TR_TZ)


def fmt_date(d):
    return f"{d.day} {MONTHS[d.month - 1]} {DAY_NAMES[d.weekday()]}"


# --------------------------------------------------------------------------- OBS

def login():
    akbim_api.BASEURL = os.environ.get("OBS_BASE_URL", "https://tedemkolejiobs.com").rstrip("/")
    tc, password = os.environ.get("OBS_TC"), os.environ.get("OBS_PASSWORD")
    if not tc or not password:
        if api_bridge.ensure_valid_session():  # yerelde kayıtlı oturum/anahtarlık
            return
        raise SystemExit("OBS_TC / OBS_PASSWORD tanımlı değil.")
    res = akbim_api.login(tc, password)
    if not res.get("success"):
        raise SystemExit("OBS girişi başarısız (TC/şifre yanlış olabilir).")
    api_bridge._last_session_status = True
    api_bridge._last_session_check_time = __import__("time").time()


def todays_lessons(index, today):
    sched = (index.get("lessonSchedule") or {}).get("data") or {}
    x_info = sched.get("xInfo") or []
    y = today.isoweekday()  # 1=Pazartesi, yInfo ile aynı sıra
    out = []
    for cell in sched.get("data") or []:
        if cell.get("y") != y:
            continue
        text = cell.get("text") or []
        x = cell.get("x") or 0
        slot = x_info[x - 1][0] if 0 < x <= len(x_info) and x_info[x - 1] else ""
        out.append({
            "x": x,
            "time": slot,
            "lesson": text[1] if len(text) > 1 else (text[0] if text else ""),
            "teacher": text[0] if len(text) > 1 else "",
        })
    return sorted(out, key=lambda c: c["x"])


def todays_menu(today):
    data = api_bridge.fetch_food_list_data(force_refresh=True)
    if not data.get("pdf_bytes"):
        return None
    for week in parse_food_menu(data["pdf_bytes"]):
        for day in week["days"]:
            if parse_day_date_obj(day["date"], default_year=today.year) == today:
                return day["meals"]
    return None


def upcoming_exams(index, today, days=7):
    out = []
    for e in index.get("examList") or []:
        try:
            d = datetime.strptime(e.get("sinavTarih", ""), "%d.%m.%Y").date()
        except ValueError:
            continue
        if today <= d <= today + timedelta(days=days):
            out.append({"date": d, "name": e.get("sinavAd", "Sınav"), "type": e.get("examType", "")})
    return sorted(out, key=lambda e: e["date"])


def due_homeworks(homeworks, today, days=3):
    out = []
    for h in homeworks or []:
        if h.get("status") == 1:  # Tamamlandı
            continue
        try:
            d = datetime.strptime(h.get("endDate", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= d <= today + timedelta(days=days):
            out.append({"date": d, "title": h.get("title", ""), "lesson": h.get("lesson", "")})
    return sorted(out, key=lambda h: h["date"])


def collect_new_items():
    """Görülme takibi yapılacak kayıtlar: {tür: {id: başlık}}"""
    items = {"homework": {}, "mail": {}, "announcement": {}, "notification": {}}
    for h in api_bridge.fetch_homeworks_list(force_refresh=True) or []:
        items["homework"][str(h.get("id"))] = f"{h.get('lesson', '')}: {h.get('title', '')}"
    inbox = (api_bridge.fetch_messages_data() or [[]])[0] or []
    for m in inbox:
        items["mail"][str(m.get("id"))] = f"{m.get('sender', '')}: {m.get('mailTitle', '')}"
    index = (api_bridge.get_adaptive_index_data(force_refresh=True) or {}).get("data") or {}
    for a in index.get("announcementList") or []:
        aid = a.get("id") or a.get("announcementId") or a.get("title")
        items["announcement"][str(aid)] = a.get("title") or a.get("baslik") or "Duyuru"
    for n in api_bridge.fetch_system_notifications() or []:
        items["notification"][str(n.get("id"))] = n.get("title", "Bildirim")
    return items


# --------------------------------------------------------------------------- HTML

CSS = """
body{margin:0;background:#f4f5f2;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#151513}
.wrap{max-width:560px;margin:0 auto;padding:24px 16px}
.card{background:#fff;border:1px solid #e6e7e3;border-radius:12px;padding:18px 20px;margin-bottom:14px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#6b6b66;font-size:14px;margin:0 0 18px}
h2{font-size:15px;color:#2f8a2b;margin:0 0 10px}
table{width:100%;border-collapse:collapse;font-size:14px}
td{padding:7px 0;border-top:1px solid #f0f0ed;vertical-align:top}
tr:first-child td{border-top:0}
.t{color:#8a8a84;white-space:nowrap;padding-right:14px;width:1%}
.m{color:#8a8a84;font-size:12px}
.empty{color:#8a8a84;font-size:14px;margin:0}
.badge{display:inline-block;background:#eef7ec;color:#2f8a2b;border-radius:6px;padding:1px 7px;font-size:12px;margin-left:6px}
.foot{color:#a3a39e;font-size:12px;text-align:center;margin-top:18px}
"""


def page(title, subtitle, sections):
    body = "".join(
        f'<div class="card"><h2>{html.escape(h)}</h2>{content}</div>' for h, content in sections
    )
    return (
        f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
        f'<div class="wrap"><h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p>'
        f'{body}<p class="foot">LimeOBS otomatik bildirimi</p></div></body></html>'
    )


def rows(items):
    if not items:
        return ""
    return "<table>" + "".join(f'<tr><td class="t">{html.escape(a)}</td><td>{b}</td></tr>' for a, b in items) + "</table>"


def empty(text):
    return f'<p class="empty">{html.escape(text)}</p>'


def build_digest(today):
    index = (api_bridge.get_adaptive_index_data(force_refresh=True) or {}).get("data") or {}
    lessons = todays_lessons(index, today)
    menu = todays_menu(today)
    exams = upcoming_exams(index, today)
    hws = due_homeworks(api_bridge.fetch_homeworks_list(force_refresh=True), today)
    log(f"özet: ders={len(lessons)} yemek={len(menu or [])} sınav={len(exams)} ödev={len(hws)}")

    def rel(d):
        if d == today:
            return '<span class="badge">BUGÜN</span>'
        if d == today + timedelta(days=1):
            return '<span class="badge">YARIN</span>'
        return ""

    sections = [
        ("📅 Günün dersleri", rows([
            (l["time"].replace(" ", ""), f'{html.escape(tr_title(l["lesson"]))}<br><span class="m">{html.escape(tr_title(l["teacher"]))}</span>')
            for l in lessons
        ]) or empty("Bugün ders görünmüyor.")),
        ("🍲 Yemek listesi", ("<table>" + "".join(
            f"<tr><td>{html.escape(tr_title(m) if m.isupper() else m)}</td></tr>" for m in menu
        ) + "</table>") if menu else empty("Bugünün menüsü listede bulunamadı.")),
        ("📝 Yaklaşan sınavlar (7 gün)", rows([
            (f'{e["date"].day} {MONTHS[e["date"].month - 1]}', f'{html.escape(e["name"])}{rel(e["date"])}')
            for e in exams
        ]) or empty("Önümüzdeki 7 günde sınav yok.")),
        ("📚 Teslimi yaklaşan ödevler (3 gün)", rows([
            (f'{h["date"].day} {MONTHS[h["date"].month - 1]}',
             f'{html.escape(h["title"])}{rel(h["date"])}<br><span class="m">{html.escape(tr_title(h["lesson"]))}</span>')
            for h in hws
        ]) or empty("Teslimi yaklaşan ödev yok.")),
    ]
    subject = f"🍋 LimeOBS — {fmt_date(today)}"
    return subject, page("Günaydın 👋", fmt_date(today), sections)


def build_new_items_mail(new):
    labels = {"homework": "📚 Yeni ödev", "mail": "✉️ Yeni mesaj",
              "announcement": "📢 Yeni duyuru", "notification": "🔔 OBS bildirimi"}
    sections = [
        (labels[k], "<table>" + "".join(f"<tr><td>{html.escape(t)}</td></tr>" for t in v.values()) + "</table>")
        for k, v in new.items() if v
    ]
    total = sum(len(v) for v in new.values())
    short = {"homework": "yeni ödev", "mail": "yeni mesaj", "announcement": "yeni duyuru", "notification": "OBS bildirimi"}
    parts = [f"{len(v)} {short[k]}" for k, v in new.items() if v]
    subject = f"🔔 LimeOBS — {', '.join(parts)}"
    return subject, page(f"{total} yeni bildirim", fmt_date(now_tr().date()), sections)


# --------------------------------------------------------------------------- Gönderim

def send(subject, html_body, dry_run=None):
    if dry_run:
        Path(dry_run).write_text(html_body, encoding="utf-8")
        log(f"önizleme yazıldı (gönderilmedi): {subject}")
        return
    user, app_pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not app_pw:
        raise SystemExit("GMAIL_USER / GMAIL_APP_PASSWORD tanımlı değil.")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"LimeOBS <{user}>"
    msg["To"] = os.environ.get("MAIL_TO") or user
    msg.set_content("Bu e-posta HTML içerir; HTML destekleyen bir istemciyle açın.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, app_pw.replace(" ", ""))
        smtp.send_message(msg)
    log("e-posta gönderildi.")


def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["digest", "check", "test"])
    ap.add_argument("--dry-run", metavar="HTML_DOSYASI", help="göndermek yerine HTML'i dosyaya yaz")
    args = ap.parse_args()

    login()
    today = now_tr().date()

    if args.mode in ("digest", "test"):
        subject, body = build_digest(today)
        if args.mode == "test":
            subject = "[TEST] " + subject
        send(subject, body, args.dry_run)
        return

    # check: önceki çalıştırmada görülmeyen kayıtları bildir
    state_path = os.environ.get("STATE_FILE", str(ROOT / ".obs_mailer_state.json"))
    seen = load_state(state_path)
    current = collect_new_items()
    log("takip edilen kayıt: " + ", ".join(f"{k}={len(v)}" for k, v in current.items()))
    if seen is None:
        log("ilk çalıştırma: mevcut kayıtlar görüldü olarak işaretlendi, e-posta gönderilmedi.")
    else:
        new = {k: {i: t for i, t in v.items() if i not in set(seen.get(k, []))} for k, v in current.items()}
        if any(new.values()):
            log("yeni kayıt: " + ", ".join(f"{k}={len(v)}" for k, v in new.items()))
            send(*build_new_items_mail(new), args.dry_run)
        else:
            log("yeni kayıt yok.")
    merged = {k: sorted(set((seen or {}).get(k, [])) | set(v)) for k, v in current.items()}
    Path(state_path).write_text(json.dumps(merged), encoding="utf-8")


if __name__ == "__main__":
    main()
