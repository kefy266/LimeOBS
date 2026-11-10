"""
Okulun aylık yemek listesi PDF'ini gün gün ayrıştırır. GTK'ya bağımlı değildir; hem arayüz hem de
GitHub Actions'taki e-posta bildirimi (scripts/obs_mailer.py) tarafından kullanılır.
"""
import io
import re
from datetime import datetime, date

from pypdf import PdfReader


MONTH_NAMES_TR = {
    'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6,
    'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12
}


def parse_day_date_obj(date_str, default_year=None):
    """
    '12 Ekim 2026 Pazartesi' gibi metinlerden date objesi üretir.
    """
    if not date_str:
        return None
    if default_year is None:
        default_year = datetime.now().year
    parts = date_str.strip().split()
    d = None
    m = None
    y = default_year
    for p in parts:
        if p.isdigit():
            val = int(p)
            if 1 <= val <= 31 and d is None:
                d = val
            elif val > 2000:
                y = val
        else:
            p_clean = p.replace('İ', 'i').replace('I', 'ı').lower()
            if p_clean in MONTH_NAMES_TR:
                m = MONTH_NAMES_TR[p_clean]
    if d and m and y:
        try:
            return date(y, m, d)
        except Exception:
            pass
    return None


def clean_meal_text(txt):
    """
    PDF içindeki kısaltmaları ve bölünmüş metinleri düzeltir:
    T.Y -> Tereyağlı
    Z.Y -> Zeytinyağlı
    TA V A -> TAVA
    """
    if not txt:
        return ""
    t = re.sub(r'\s+', ' ', txt).strip()
    # "Z.YAĞLI", "Z . Y", "T.YAĞLI" gibi kısaltmalar (sonda AĞLI varsa tekrar eklenmesin)
    t = re.sub(r'(?<![^\s])Z\s*\.\s*Y(?:AĞLI)?(?![^\s])', 'ZEYTİNYAĞLI', t)
    t = re.sub(r'(?<![^\s])T\s*\.\s*Y(?:AĞLI)?(?![^\s])', 'TEREYAĞLI', t)
    replacements = {
        "TA V A": "TAVA",
        "TA VA": "TAVA",
        "TA V UK": "TAVUK",
        "TA VUK": "TAVUK",
        "PİLA VI": "PİLAVI",
        "Pİ LA VI": "PİLAVI",
        "PİLA V": "PİLAV",
        "Pİ LA V": "PİLAV",
        "T . Y ": "TEREYAĞLI ",
        "T . Y": "TEREYAĞLI",
        "T.Y ": "TEREYAĞLI ",
        "T.Y": "TEREYAĞLI",
        "T .Y ": "TEREYAĞLI ",
        "T .Y": "TEREYAĞLI",
        "Z . Y ": "ZEYTİNYAĞLI ",
        "Z . Y": "ZEYTİNYAĞLI",
        "Z.Y ": "ZEYTİNYAĞLI ",
        "Z.Y": "ZEYTİNYAĞLI",
        "Z .Y ": "ZEYTİNYAĞLI ",
        "Z .Y": "ZEYTİNYAĞLI",
        "ZY ": "ZEYTİNYAĞLI ",
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t


_PARSED_FOOD_CACHE = {}


def rejoin_split_words(text, known_words):
    """
    PDF bazı kelimeleri harf harf ayrı parçalar olarak saklar ('T AVUK', 'ETLİ KURU F ASULYE').
    pypdf'in düz metni yazı tipi ölçüleriyle doğru birleştirir; komşu parçaların birleşimi o metinde
    tek kelime olarak geçiyorsa boşluksuz birleştir.
    """
    tokens = text.split()
    out = []
    i = 0
    while i < len(tokens):
        merged = False
        for n in (3, 2):  # önce en uzun birleşimi dene
            if i + n <= len(tokens):
                cand = "".join(tokens[i:i + n])
                if cand in known_words and not all(t in known_words for t in tokens[i:i + n]):
                    out.append(cand)
                    i += n
                    merged = True
                    break
        if not merged:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


DAY_NAMES_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _is_date_text(txt):
    """Başlık parçası bir gün adı ya da ay adı içeriyor mu? (Ekim PDF'i gün adlı, Kasım PDF'i yalnızca tarihli)"""
    if any(d in txt for d in DAY_NAMES_TR[:5]):
        return True
    low = txt.replace('İ', 'i').replace('I', 'ı').lower()
    return any(m in low.split() for m in MONTH_NAMES_TR)


def parse_food_menu(pdf_bytes):
    """
    Okulun yemek listesi PDF dosyasını dinamik olarak gün gün ve yemek yemek ayrıştırır.
    Sabit koordinatlara bağımlı kalmadan gün sütunlarını ve yemek bloklarını tespit eder.
    """
    if not pdf_bytes:
        return []

    cache_key = (len(pdf_bytes), hash(pdf_bytes[:4096]))
    if cache_key in _PARSED_FOOD_CACHE:
        return _PARSED_FOOD_CACHE[cache_key]

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        all_weeks = []

        for p_idx, page in enumerate(reader.pages):
            items = []
            def visitor(text, cm, tm, font_dict, font_size):
                if text.strip():
                    items.append((tm[4], tm[5], text.strip()))
            page.extract_text(visitor_text=visitor)

            if not items:
                continue
            page_words = set(page.extract_text().split())

            # 1. Gün başlık satırını bul: gün ya da ay adı içeren parçaların en kalabalık olduğu satır.
            #    ("KASIM AYI YEMEK LİSTESİ" gibi tek parçalı başlık satırı böylece elenir.)
            date_like = [it for it in items if _is_date_text(it[2]) and it[1] >= 300]
            if not date_like:
                continue
            ref_y = max(
                {round(it[1]) for it in date_like},
                key=lambda y: sum(1 for it in date_like if abs(it[1] - y) < 8),
            )
            if sum(1 for it in date_like if abs(it[1] - ref_y) < 8) < 2:
                continue
            header_row = [it for it in items if abs(it[1] - ref_y) < 8]
            header_row.sort(key=lambda it: it[0])

            # Yatay bölünmüş metinleri birleştir (ör. '26 Ekim' + '2026 Pazartesi', '1' + '0' + 'Kasım 2026')
            merged_headers = []
            for it in header_row:
                if not merged_headers:
                    merged_headers.append([it[0], it[1], it[2]])
                else:
                    last = merged_headers[-1]
                    if 0 <= (it[0] - last[0]) < 85:
                        # Yan yana rakamlar ('1','0') tek sayıdır: boşluksuz birleştir
                        sep = "" if last[2][-1:].isdigit() and it[2][:1].isdigit() and len(last[2].split()[-1]) < 3 and it[0] - last[3] < 12 else " "
                        last[2] = f"{last[2]}{sep}{it[2]}"
                    else:
                        merged_headers.append([it[0], it[1], it[2]])
                merged_headers[-1][3:] = [it[0]]

            date_items = [m[:3] for m in merged_headers if _is_date_text(m[2])]
            date_items.sort(key=lambda it: it[0])

            if len(date_items) < 2:
                continue

            # 2. Sütun sınırlarını dinamik oluştur
            cols = []
            for i, d in enumerate(date_items):
                x_curr = d[0]
                x_start = x_curr - 35
                if i + 1 < len(date_items):
                    x_next = date_items[i+1][0]
                    x_end = (x_curr + x_next) / 2
                else:
                    x_end = 9999
                cols.append({
                    "date": d[2],
                    "header_y": d[1],
                    "x_start": x_start,
                    "x_end": x_end,
                    "food_items": []
                })

            # Başlıkların en düşük y değerini al
            min_header_y = min(c["header_y"] for c in cols)

            # 3. Yemek satırlarını ait olduğu sütuna ata
            for it in items:
                x, y, txt = it
                # Başlıkların altındaki ve sayfa altı hariç metinler
                if y < min_header_y - 10 and y >= 60:
                    for col in cols:
                        if col["x_start"] <= x < col["x_end"]:
                            col["food_items"].append((y, txt))
                            break

            days = []
            for col in cols:
                # Yukarıdan aşağıya sırala (y azalan sırada)
                col["food_items"].sort(key=lambda it: -it[0])
                meals = []
                cur_meal = []
                last_y = None

                for y, txt in col["food_items"]:
                    # Yüksek satır farkı yeni bir yemeğe geçildiğini gösterir
                    if last_y is not None and abs(last_y - y) > 20:
                        if cur_meal:
                            m_str = clean_meal_text(rejoin_split_words(" ".join(cur_meal), page_words))
                            if m_str and len(m_str) > 1:
                                meals.append(m_str)
                            cur_meal = []
                    cur_meal.append(txt)
                    last_y = y

                if cur_meal:
                    m_str = clean_meal_text(rejoin_split_words(" ".join(cur_meal), page_words))
                    if m_str and len(m_str) > 1:
                        meals.append(m_str)

                # Tarih metnini güzelleştir; gün adı yoksa tarihten hesaplayıp ekle
                date_clean = re.sub(r'\s+', ' ', col["date"]).strip()
                if not any(d in date_clean for d in DAY_NAMES_TR):
                    d_obj = parse_day_date_obj(date_clean)
                    if d_obj:
                        date_clean = f"{date_clean} {DAY_NAMES_TR[d_obj.weekday()]}"

                days.append({
                    "date": date_clean,
                    "meals": meals
                })

            all_weeks.append({
                "week_num": p_idx + 1,
                "days": days
            })

        if all_weeks:
            _PARSED_FOOD_CACHE[cache_key] = all_weeks
        return all_weeks
    except Exception as e:
        print(f"Yemek listesi ayrıştırma hatası: {e}")
        return []
