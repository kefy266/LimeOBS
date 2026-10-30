import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_classical_exams


class ClassicalExamsView(Gtk.ScrolledWindow):
    """
    LimeOBS Klasik Yazılı Sınavlar Görünümü
    MEB 1. ve 2. Dönem klasik yazılı notları, sözlü/kanaat notları ve sınıf ortalamalarını sunar.
    """
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(960)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        # 1. Başlık Çubuğu
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='large' weight='bold'>📝 MEB Klasik Yazılı Sınavlarım</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        subtitle_lbl = Gtk.Label()
        subtitle_lbl.set_markup("<span size='small' foreground='#b8b8b8'>Dönemlik yazılı sınav notları, sınıf ortalamaları ve karne dereceleri</span>")
        subtitle_lbl.set_halign(Gtk.Align.START)
        title_box.append(subtitle_lbl)

        header_box.append(title_box)

        # Resmi Sınav Takvimi Butonu
        btn_schedule_doc = Gtk.Button(label="Sınav Takvimi (PDF)")
        btn_schedule_doc.set_icon_name("x-office-document-symbolic")
        btn_schedule_doc.add_css_class("flat")
        btn_schedule_doc.set_tooltip_text("Okul Resmi Sınav Günleri Takvimi PDF Belgesi")
        btn_schedule_doc.connect("clicked", lambda _: self.open_exam_schedule_pdf())
        header_box.append(btn_schedule_doc)

        # Yenile Butonu
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Yazılı Sınavları Yenile")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # 2. Dönem Seçim Düğmeleri (1. Dönem / 2. Dönem)
        self.period_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.period_box.set_halign(Gtk.Align.CENTER)
        self.period_box.add_css_class("segmented-bar")

        self.btn_period1 = Gtk.Button(label="1. Dönem Yazılıları")
        self.btn_period1.add_css_class("suggested-action")
        self.btn_period1.connect("clicked", lambda _: self.set_active_period(1))
        self.period_box.append(self.btn_period1)

        self.btn_period2 = Gtk.Button(label="2. Dönem Yazılıları")
        self.btn_period2.connect("clicked", lambda _: self.set_active_period(2))
        self.period_box.append(self.btn_period2)

        self.main_box.append(self.period_box)

        # 3. İstatistik KPI Kartları
        self.kpi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.kpi_box.set_homogeneous(True)
        self.main_box.append(self.kpi_box)

        # 4. Yazılı Sınav Notları Listesi / Tablosu
        self.content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.append(self.content_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Dahili Durum
        self.current_period = 1
        self._raw_data = {}
        self._period1_exams = []
        self._period2_exams = []

    def open_exam_schedule_pdf(self):
        def worker():
            from api_bridge import fetch_exam_days_calendar, open_file_external
            cal = fetch_exam_days_calendar()
            view_url = cal.get("view_url") or cal.get("download_url")
            if view_url:
                try:
                    open_file_external(view_url)
                except Exception as e:
                    print(f"Takvim açma hatası: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def reset_state(self):
        """Kullanıcı veya hesap değiştiğinde durumu sıfırlar."""
        self.current_period = 1
        self._raw_data.clear()
        self._period1_exams.clear()
        self._period2_exams.clear()
        self.btn_period1.add_css_class("suggested-action")
        self.btn_period2.remove_css_class("suggested-action")

        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

    def set_active_period(self, period):
        self.current_period = period
        if period == 1:
            self.btn_period1.add_css_class("suggested-action")
            self.btn_period2.remove_css_class("suggested-action")
        else:
            self.btn_period2.add_css_class("suggested-action")
            self.btn_period1.remove_css_class("suggested-action")
        self.render_exams()

    def load_data(self):
        def worker():
            try:
                classical_data = fetch_classical_exams()
                GLib.idle_add(self.apply_data, classical_data)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def apply_data(self, classical_data):
        self._raw_data = classical_data or {}
        tables = self._raw_data.get("tables", {})
        t3 = tables.get("classicalExamTable3", {})
        
        self._period1_exams = t3.get("period1", {}).get("data", []) or []
        self._period2_exams = t3.get("period2", {}).get("data", []) or []

        self.render_exams()

    def render_exams(self):
        # KPI ve İçerik kutularını temizle
        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

        active_list = self._period1_exams if self.current_period == 1 else self._period2_exams

        # Eğer aktif dönemde sınav yoksa bilgilendirme ekranı bas
        if not active_list:
            card = Adw.PreferencesGroup()
            card.set_title(f"{self.current_period}. Dönem Yazılı Sınav Bilgisi")
            
            status_row = Adw.ActionRow()
            status_row.set_title("Bu döneme ait kayıtlı yazılı sınav notu bulunmuyor")
            status_row.set_subtitle("Milli Eğitim Bakanlığı ortak sınavları veya okul yazılıları sisteme girildiğinde burada listelenecektir.")
            status_row.set_icon_name("dialog-information-symbolic")
            card.add(status_row)
            self.content_container.append(card)

            # Deneme sınavlarına yönlendirme kartı
            guide_group = Adw.PreferencesGroup()
            guide_group.set_title("Diğer Sınavlar")
            guide_row = Adw.ActionRow()
            guide_row.set_title("Deneme Sınavları &amp; DBS Taramalar")
            guide_row.set_subtitle("Girdiğiniz tüm deneme ve konu tarama sınav sonuçlarını 'Sınavlar' sekmesinden inceleyebilirsiniz.")
            guide_row.set_icon_name("emblem-documents-symbolic")
            guide_group.add(guide_row)
            self.content_container.append(guide_group)
            return

        # İstatistikleri hesapla
        total_lessons = len(active_list)
        scores = []
        for row in active_list:
            for k in ["exam1", "exam2", "exam3", "ort", "Puan", "point"]:
                v = row.get(k)
                if v is not None:
                    try:
                        scores.append(float(v))
                    except Exception:
                        pass

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        min_score = min(scores) if scores else 0.0

        # KPI Kutuları
        self.add_kpi_card("Ders Sayısı", str(total_lessons), "accessories-dictionary-symbolic")
        self.add_kpi_card("Yazılı Ortalaması", f"{avg_score:.1f}" if avg_score else "-", "accessories-calculator-symbolic")
        self.add_kpi_card("En Yüksek Not", f"{max_score:.1f}" if max_score else "-", "starred-symbolic")
        self.add_kpi_card("En Düşük Not", f"{min_score:.1f}" if min_score else "-", "view-list-bullet-symbolic")

        # Ders Listesi Kartları
        group = Adw.PreferencesGroup()
        group.set_title(f"{self.current_period}. Dönem Ders ve Not Listesi")

        for item in active_list:
            lesson_name = item.get("lesson") or item.get("ders") or item.get("sinavAd") or "Ders"
            e1 = item.get("exam1") or item.get("yazili1") or "-"
            e2 = item.get("exam2") or item.get("yazili2") or "-"
            e3 = item.get("exam3") or item.get("yazili3") or "-"
            sozlu = item.get("sozlu") or item.get("kanaat") or "-"
            ort = item.get("ort") or item.get("average") or item.get("Puan") or "-"

            row = Adw.ActionRow()
            row.set_title(lesson_name)
            
            sub_parts = []
            if str(e1) != "-":
                sub_parts.append(f"1. Yazılı: {e1}")
            if str(e2) != "-":
                sub_parts.append(f"2. Yazılı: {e2}")
            if str(e3) != "-":
                sub_parts.append(f"3. Yazılı: {e3}")
            if str(sozlu) != "-":
                sub_parts.append(f"Sözlü: {sozlu}")
            
            row.set_subtitle(" • ".join(sub_parts) if sub_parts else "Not girişi bekleniyor")
            row.set_icon_name("accessories-dictionary-symbolic")

            # Ortalama Rozeti
            badge = Gtk.Label(label=f"Ort: {ort}")
            badge.add_css_class("badge-primary")
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)

            group.add(row)

        self.content_container.append(group)

    def add_kpi_card(self, title, value, icon_name):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("card-bubble")
        card.set_margin_top(4)
        card.set_margin_bottom(4)

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        top_box.append(icon)

        t_lbl = Gtk.Label()
        t_lbl.set_markup(f"<span size='small' foreground='#b8b8b8'>{title}</span>")
        top_box.append(t_lbl)
        card.append(top_box)

        v_lbl = Gtk.Label()
        v_lbl.set_markup(f"<span size='x-large' weight='bold'>{value}</span>")
        v_lbl.set_halign(Gtk.Align.START)
        card.append(v_lbl)

        self.kpi_box.append(card)
