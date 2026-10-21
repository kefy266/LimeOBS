import os
import tempfile
import threading
import io
import re
from datetime import datetime, date, timedelta
from pypdf import PdfReader

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_food_list_data, get_effective_school_date
from views.pdf_viewer_dialog import open_pdf_viewer


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


def classify_meal(meal_name, index_in_day=0):
    """
    Yemeğin adını analiz ederek doğru kategoriyi ve GTK ikonunu belirler.
    Tüm menüler için dinamik çalışır.
    """
    m = meal_name.upper().strip()
    
    # 1. Tatil kontrolü
    if "TATİL" in m:
        return ("Resmi / Okul Tatili", "weather-clear-symbolic")

    # 2. Çorba / Başlangıç
    if "ÇORBA" in m:
        return ("Başlangıç / Çorba", "food-symbolic")

    # 3. Tatlı, İçecek, Su, Salata
    dessert_drink_keywords = [
        "TATLI", "MEYVE", "İÇECEK", "SU", "BARDAK SU", "SALATBAR",
        "SALATA", "AYRAN", "KOMPOSTO", "PUDİNG", "KADAYIF", "BAKLAVA",
        "SÜTLAÇ", "REVANİ", "KAZANDİBİ", "MUHALLEBİ", "DONDURMA", "MANDALİNA", "ELMA", "PORTAKAL"
    ]
    if any(k in m for k in dessert_drink_keywords):
        return ("Tatlı / İçecek / Salata", "starred-symbolic")

    # 4. Garnitür / Yardımcı Yemek / Hamur İşi
    side_keywords = [
        "PİLAV", "MAKARNA", "BÖREK", "SPAGETTİ", "ERİŞTE", "BULGUR",
        "MANTI", "KISIR", "PATATES KIZARTMASI", "ELMA DİLİMİ", "HALKASI",
        "PÜRE", "MÜCVER", "SOSLU MAKARNA"
    ]
    if any(k in m for k in side_keywords):
        return ("Garnitür / Yardımcı Yemek", "view-grid-symbolic")

    # 5. Ana Yemekler (Et, Tavuk, Balık, Sebze Yahnileri, Güveç, Bakliyat, vb.)
    main_dish_keywords = [
        "KEBAP", "KÖFTE", "TAVUK", "ET", "PİZZA", "NOHUT", "KARNIYARIK",
        "FASÜLYE", "DÖNER", "HAMBURGER", "TANTUNİ", "GRATEN", "PİRZOLA",
        "TÜRKLÜ", "TÜRLÜ", "GÜVEÇ", "ROTI", "ROTİ", "YAHNİ", "BEZELYE",
        "BAMYA", "KARNABAHAR", "KABAK", "PIRASA", "ISPANAK", "ŞAKŞUKA",
        "KABUSKA", "KAPUSKA", "BORANİ", "TOPALAK", "ŞİNİTZEL", "TAS KEBABI",
        "SARMA", "DOLMA", "MUSAKKA", "FAHITA", "GÖVEÇ", "TAVA", "PANE"
    ]
    if any(k in m for k in main_dish_keywords):
        return ("Ana Yemek", "emblem-favorite-symbolic")

    # 6. Zeytinyağlı / Sebze Yemeği Belirteçleri
    if "Z.Y" in m or "ZY" in m or "T.Y" in m or "SEBZE" in m or "KIZARTMA" in m:
        return ("Ana Yemek / Sebze", "emblem-favorite-symbolic")

    # 7. Konum bazlı fallback:
    # Genelde 1. sırada çorba, 2. sırada ana yemek, 3. sırada garnitür, 4. ve sonrasında tatlı/içecek gelir.
    if index_in_day == 0:
        return ("Başlangıç", "food-symbolic")
    elif index_in_day == 1:
        return ("Ana Yemek", "emblem-favorite-symbolic")
    elif index_in_day == 2:
        return ("Garnitür", "view-grid-symbolic")
    else:
        return ("Tatlı / İçecek / Yan Ürün", "starred-symbolic")


def parse_food_menu(pdf_bytes):
    """
    Okulun yemek listesi PDF dosyasını dinamik olarak gün gün ve yemek yemek ayrıştırır.
    Sabit koordinatlara bağımlı kalmadan gün sütunlarını ve yemek bloklarını tespit eder.
    """
    if not pdf_bytes:
        return []

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        all_weeks = []

        day_names_keywords = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]

        for p_idx, page in enumerate(reader.pages):
            items = []
            def visitor(text, cm, tm, font_dict, font_size):
                if text.strip():
                    items.append((tm[4], tm[5], text.strip()))
            page.extract_text(visitor_text=visitor)

            if not items:
                continue

            # 1. Gün başlıklarını dinamik tespit et ve yatay bölünmüş metinleri (ör. '26 Ekim' ve '2026 Pazartesi') birleştir
            day_keyword_items = [it for it in items if any(d in it[2] for d in day_names_keywords) and it[1] >= 300]
            if not day_keyword_items:
                continue

            ref_y = day_keyword_items[0][1]
            header_row = [it for it in items if abs(it[1] - ref_y) < 8]
            header_row.sort(key=lambda it: it[0])

            merged_headers = []
            for it in header_row:
                if not merged_headers:
                    merged_headers.append([it[0], it[1], it[2]])
                else:
                    last = merged_headers[-1]
                    if 0 <= (it[0] - last[0]) < 85:
                        last[2] = f"{last[2]} {it[2]}"
                    else:
                        merged_headers.append([it[0], it[1], it[2]])

            date_items = [m for m in merged_headers if any(d in m[2] for d in day_names_keywords)]
            date_items.sort(key=lambda it: it[0])

            if not date_items:
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
                            m_str = clean_meal_text(" ".join(cur_meal))
                            if m_str and len(m_str) > 1:
                                meals.append(m_str)
                            cur_meal = []
                    cur_meal.append(txt)
                    last_y = y

                if cur_meal:
                    m_str = clean_meal_text(" ".join(cur_meal))
                    if m_str and len(m_str) > 1:
                        meals.append(m_str)

                # Tarih metnini güzelleştir
                date_clean = re.sub(r'\s+', ' ', col["date"]).strip()

                days.append({
                    "date": date_clean,
                    "meals": meals
                })

            all_weeks.append({
                "week_num": p_idx + 1,
                "days": days
            })

        return all_weeks
    except Exception as e:
        print(f"Yemek listesi ayrıştırma hatası: {e}")
        return []


class FoodListView(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(900)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(30)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        # Üst Başlık & Butonlar
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        header_label = Gtk.Label()
        header_label.set_markup("<span size='large' weight='bold'>🍽️ Okul Yemek Listesi</span>")
        header_label.set_halign(Gtk.Align.START)
        header_label.set_hexpand(True)
        header_box.append(header_label)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Yemek Listesini Yenile")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.open_pdf_btn = Gtk.Button(label="Orijinal PDF & Yazdır")
        self.open_pdf_btn.set_icon_name("document-open-symbolic")
        self.open_pdf_btn.connect("clicked", self.on_open_pdf_clicked)
        self.open_pdf_btn.set_sensitive(False)
        header_box.append(self.open_pdf_btn)

        self.main_box.append(header_box)

        # Hafta Seçim Sekmesi
        self.stack = Adw.ViewStack()
        self.switcher = Adw.ViewSwitcher()
        self.switcher.set_stack(self.stack)
        self.switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        self.switcher.set_halign(Gtk.Align.CENTER)
        self.switcher.set_visible(False)
        self.main_box.append(self.switcher)

        # İçerik Alanı
        self.content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.content_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        self.show_loading()

    def reset_state(self):
        """Hesap değiştiğinde FoodListView önbelleğini ve arayüzünü sıfırlar."""
        self.show_loading()
        self.open_pdf_btn.set_sensitive(False)

    def show_loading(self):
        self.clear_container()
        self.switcher.set_visible(False)
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        loading_box.set_halign(Gtk.Align.CENTER)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_margin_top(60)
        loading_box.set_margin_bottom(60)

        spinner = Gtk.Spinner()
        spinner.set_size_request(36, 36)
        spinner.start()
        loading_box.append(spinner)

        lbl = Gtk.Label()
        lbl.set_markup("<span size='medium' weight='semibold'>Yemek listesi hazırlanıyor...</span>")
        loading_box.append(lbl)

        self.content_container.append(loading_box)

    def clear_container(self):
        child = self.content_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.content_container.remove(child)
            child = next_child

    def load_data(self):
        self.show_loading()

        def worker():
            try:
                res = fetch_food_list_data()
                pdf_bytes = res.get("pdf_bytes") if res.get("success") else None
                weeks = parse_food_menu(pdf_bytes)
                GLib.idle_add(self.on_data_loaded, pdf_bytes, weeks)
            except Exception as e:
                print(f"Yemek listesi yükleme hatası: {e}")
                GLib.idle_add(self.on_data_loaded, None, [])

        threading.Thread(target=worker, daemon=True).start()

    def on_data_loaded(self, pdf_bytes, weeks):
        self.clear_container()
        self.pdf_bytes = pdf_bytes

        if not pdf_bytes or not weeks:
            self.open_pdf_btn.set_sensitive(False)
            self.switcher.set_visible(False)
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty_box.set_halign(Gtk.Align.CENTER)
            empty_box.set_margin_top(60)
            lbl = Gtk.Label()
            lbl.set_markup("<span size='large' weight='bold'>Yemek Listesi Bulunamadı</span>")
            sub = Gtk.Label(label="Okul yönetimi henüz güncel yemek listesini yüklememiş olabilir.")
            sub.add_css_class("dim-label")
            empty_box.append(lbl)
            empty_box.append(sub)
            self.content_container.append(empty_box)
            return

        self.open_pdf_btn.set_sensitive(True)

        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(pdf_bytes)
            tmp.close()
            self.temp_pdf_path = tmp.name
        except Exception:
            self.temp_pdf_path = None

        # Stack'i temizle
        while self.stack.get_pages().get_n_items() > 0:
            item = self.stack.get_pages().get_item(0)
            self.stack.remove(item.get_child())

        now = datetime.now()
        effective_date = get_effective_school_date(now)

        first_active_page_name = None
        active_weeks_count = 0

        # Aktif haftayı tespit et (içinde hedef okul günü veya sonrası bulunan ilk hafta)
        active_target_wn = None
        for w in weeks:
            w_dates = [parse_day_date_obj(d["date"]) for d in w["days"]]
            valid_w_dates = [d for d in w_dates if d]
            if any(d >= effective_date for d in valid_w_dates):
                active_target_wn = w["week_num"]
                break

        for w in weeks:
            wn = w["week_num"]
            w_dates = [parse_day_date_obj(d["date"]) for d in w["days"]]
            valid_w_dates = [d for d in w_dates if d]

            # 6 günden daha eski tamamen bitmiş eski haftaları filtrele
            if valid_w_dates and max(valid_w_dates) < (effective_date - timedelta(days=6)):
                continue

            week_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            days_added = 0

            for day in w["days"]:
                d_obj = parse_day_date_obj(day["date"])
                day_group = Adw.PreferencesGroup()
                is_effective_day = (d_obj == effective_date)
                if is_effective_day:
                    if effective_date == now.date():
                        today_tag = " — BUGÜN"
                    elif effective_date == now.date() + timedelta(days=1):
                        today_tag = " — YARININ MENÜSÜ"
                    else:
                        today_tag = " — SIRADAKİ MENÜ"
                else:
                    today_tag = ""

                day_group.set_title(f"📅 {day['date']}{today_tag}")

                meals = day["meals"]
                if not meals or all("TATİL" in m.upper() for m in meals):
                    row = Adw.ActionRow()
                    row.set_title("🏖️ Resmi / Okul Tatili")
                    row.set_subtitle("Bugün yemek hizmeti bulunmuyor.")
                    row.set_icon_name("weather-clear-symbolic")
                    day_group.add(row)
                else:
                    for idx, meal in enumerate(meals):
                        row = Adw.ActionRow()
                        row.set_title(meal)
                        
                        # Dinamik yemek sınıflandırma ve temiz simgeler
                        cat_title, cat_icon = classify_meal(meal, index_in_day=idx)
                        row.set_subtitle(cat_title)
                        row.set_icon_name(cat_icon)

                        day_group.add(row)

                week_box.append(day_group)
                days_added += 1

            if days_added > 0:
                page_name = f"week_{wn}"
                self.stack.add_titled_with_icon(week_box, page_name, f"{wn}. Hafta", "food-symbolic")
                if first_active_page_name is None or (active_target_wn and wn == active_target_wn):
                    first_active_page_name = page_name
                active_weeks_count += 1

        if active_weeks_count == 0:
            empty_group = Adw.PreferencesGroup()
            empty_group.set_title("Yemek Listesi")
            empty_row = Adw.ActionRow()
            empty_row.set_title("Bu döneme ait tüm yemek günleri tamamlandı.")
            empty_row.set_subtitle("Yakında yeni ayın menüsü yayınlanacaktır.")
            empty_row.set_icon_name("emblem-ok-symbolic")
            empty_group.add(empty_row)
            self.content_container.append(empty_group)
            self.switcher.set_visible(False)
            return

        if first_active_page_name:
            self.stack.set_visible_child_name(first_active_page_name)

        self.switcher.set_visible(active_weeks_count > 1)
        self.content_container.append(self.stack)

    def on_open_pdf_clicked(self, button):
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                open_pdf_viewer(self.get_root(), self.temp_pdf_path, title="Yemek Menüsü PDF")
            except Exception as e:
                print(f"Dahili PDF açma hatası: {e}")
                from api_bridge import open_file_external
                open_file_external(self.temp_pdf_path)
