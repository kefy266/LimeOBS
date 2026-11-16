"""
Okul takvimi: MEB eğitim-öğretim yılı tarihleri (ara tatiller, yarıyıl) ve resmî tatiller.

- MEB tarihleri resmi genelgeden alınmıştır:
  https://www.meb.gov.tr/2026-2027-egitim-ogretim-yili-calisma-takvimi/haber/41057/tr
  Yeni eğitim yılı açıklandığında SCHOOL_YEARS'a eklenir.
- Resmî tatiller Nager.Date açık API'sinden (date.nager.at) çekilir ve 30 gün önbelleğe alınır;
  internet yoksa aşağıdaki yedek liste kullanılır. Dinî bayram tarihleri API'de "geçici" olarak işaretlidir.
"""
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

SCHOOL_YEARS = {
    "2026-2027": {
        "terms": [(date(2026, 9, 14), date(2027, 1, 22)), (date(2027, 2, 8), date(2027, 6, 25))],
        "breaks": [
            ("1. dönem ara tatili", date(2026, 11, 16), date(2026, 11, 20)),
            ("Yarıyıl tatili", date(2027, 1, 25), date(2027, 2, 5)),
            ("2. dönem ara tatili", date(2027, 3, 8), date(2027, 3, 12)),
        ],
    },
}

_FALLBACK_HOLIDAYS = {
    2026: [
        ("2026-01-01", "Yılbaşı"), ("2026-03-20", "Ramazan Bayramı 1. Gün"), ("2026-03-21", "Ramazan Bayramı 2. Gün"),
        ("2026-03-22", "Ramazan Bayramı 3. Gün"), ("2026-04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
        ("2026-05-01", "İşçi Bayramı"), ("2026-05-19", "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
        ("2026-05-27", "Kurban Bayramı 1. Gün"), ("2026-05-28", "Kurban Bayramı 2. Gün"),
        ("2026-05-29", "Kurban Bayramı 3. Gün"), ("2026-05-30", "Kurban Bayramı 4. Gün"),
        ("2026-07-15", "Demokrasi ve Millî Birlik Günü"), ("2026-08-30", "Zafer Bayramı"),
        ("2026-10-29", "Cumhuriyet Bayramı"),
    ],
    2027: [
        ("2027-01-01", "Yılbaşı"), ("2027-03-10", "Ramazan Bayramı 1. Gün"), ("2027-03-11", "Ramazan Bayramı 2. Gün"),
        ("2027-03-12", "Ramazan Bayramı 3. Gün"), ("2027-04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
        ("2027-05-01", "İşçi Bayramı"), ("2027-05-16", "Kurban Bayramı 1. Gün"), ("2027-05-17", "Kurban Bayramı 2. Gün"),
        ("2027-05-18", "Kurban Bayramı 3. Gün"), ("2027-05-19", "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
        ("2027-05-19", "Kurban Bayramı 4. Gün"), ("2027-07-15", "Demokrasi ve Millî Birlik Günü"),
        ("2027-08-30", "Zafer Bayramı"), ("2027-10-29", "Cumhuriyet Bayramı"),
    ],
}

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "limeobs"
_memory = {}


def public_holidays(year):
    """{date: ad} — Nager.Date'ten (30 gün önbellekli), olmazsa yedek listeden."""
    if year in _memory:
        return _memory[year]
    cache = _CACHE_DIR / f"tatiller-{year}.json"
    items = None
    try:
        if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
            items = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        items = None
    if items is None:
        try:
            res = requests.get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/TR", timeout=8)
            res.raise_for_status()
            items = [(h["date"], h["localName"].replace(" (Tentative Date)", "")) for h in res.json()]
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        except Exception:
            items = _FALLBACK_HOLIDAYS.get(year, [])
    out = {}
    for d, name in items:
        day = datetime.strptime(d, "%Y-%m-%d").date()
        out[day] = f"{out[day]} / {name}" if day in out else name
    _memory[year] = out
    return out


def school_break(d):
    """d bir okul tatiline (ara tatil, yarıyıl) denk geliyorsa (ad, başlangıç, bitiş), yoksa None."""
    for year in SCHOOL_YEARS.values():
        for name, start, end in year["breaks"]:
            if start <= d <= end:
                return name, start, end
    return None


def day_off_reason(d):
    """Okulun olmadığı günler için nedeni (hafta sonu hariç), okul günü ise None."""
    brk = school_break(d)
    if brk:
        return brk[0]
    return public_holidays(d.year).get(d)


def is_school_day(d):
    return d.weekday() < 5 and day_off_reason(d) is None


def next_school_day(d):
    """d'den sonraki ilk okul günü (hafta sonu, ara tatil ve resmî tatilleri atlar)."""
    d += timedelta(days=1)
    for _ in range(120):
        if is_school_day(d):
            return d
        d += timedelta(days=1)
    return d


def upcoming(today=None, days=90):
    """Önümüzdeki günlerdeki tatiller: [{name, start, end, kind}] (bugün süren tatil dahil)."""
    today = today or date.today()
    limit = today + timedelta(days=days)
    out = []
    for year in SCHOOL_YEARS.values():
        for name, start, end in year["breaks"]:
            if end >= today and start <= limit:
                out.append({"name": name, "start": start, "end": end, "kind": "okul"})
    for y in {today.year, limit.year}:
        for day, name in public_holidays(y).items():
            if today <= day <= limit and not school_break(day):
                out.append({"name": name, "start": day, "end": day, "kind": "resmi"})
    out.sort(key=lambda e: e["start"])
    return out
