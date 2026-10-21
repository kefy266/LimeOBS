import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import (
    fetch_etut_records,
    fetch_course_dashboard,
    fetch_birebir_form_metadata,
    fetch_birebir_teachers,
    fetch_birebir_schedule
)


class EtutView(Gtk.ScrolledWindow):
    """
    Etüt & Birebir Ders Yönetimi ve Takvimi Görünümü
    """
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(900)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        # Üst Başlık
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='x-large' weight='bold'>🎯 Etüt &amp; Birebir Takvimi</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        sub_lbl = Gtk.Label()
        sub_lbl.set_markup("<span size='small' alpha='65%'>Öğretmen etütleri, birebir çalışma programı ve istatistikleri</span>")
        sub_lbl.set_halign(Gtk.Align.START)
        title_box.append(sub_lbl)
        title_box.set_hexpand(True)
        header_box.append(title_box)

        # Yenile Butonu
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Yenile")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # 1. ÖZET İSTATİSTİK KARTLARI (Tüm Dönem / Bu Ay Etüt & Birebir Sayıları)
        self.stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.stats_box.set_homogeneous(True)
        self.main_box.append(self.stats_box)

        # 2. AKTİF ETÜTLERİM VE BİREBİRLERİM
        self.my_records_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.append(self.my_records_container)

        # 3. YENİ ETÜT / BİREBİR TAKVİMİ İNCELEME
        lookup_title = Gtk.Label()
        lookup_title.set_markup("<span size='medium' weight='bold'>🔍 Ders &amp; Öğretmen Etüt Programı Arama</span>")
        lookup_title.set_halign(Gtk.Align.START)
        lookup_title.set_margin_top(8)
        self.main_box.append(lookup_title)

        # Seçim Kutuları (Ders, Öğretmen, Tür)
        filter_card = Adw.PreferencesGroup()
        filter_card.set_title("Program Filtresi")
        filter_card.set_description("Öğretmenlerin uygun olduğu saatleri görmek için ders ve öğretmen seçiniz")

        # Tür (Etüt / Birebir)
        self.type_combo = Adw.ComboRow()
        self.type_combo.set_title("Ders Türü")
        type_model = Gtk.StringList.new(["Etüt", "Birebir"])
        self.type_combo.set_model(type_model)
        self.type_combo.connect("notify::selected", self.on_filter_changed)
        filter_card.add(self.type_combo)

        # Ders Seçimi
        self.lesson_combo = Adw.ComboRow()
        self.lesson_combo.set_title("Ders")
        self.lesson_model = Gtk.StringList.new(["Ders Seçiniz..."])
        self.lesson_combo.set_model(self.lesson_model)
        self.lesson_combo.connect("notify::selected", self.on_lesson_changed)
        filter_card.add(self.lesson_combo)

        # Öğretmen Seçimi
        self.teacher_combo = Adw.ComboRow()
        self.teacher_combo.set_title("Öğretmen")
        self.teacher_model = Gtk.StringList.new(["Önce Ders Seçiniz..."])
        self.teacher_combo.set_model(self.teacher_model)
        self.teacher_combo.connect("notify::selected", self.on_filter_changed)
        filter_card.add(self.teacher_combo)

        self.main_box.append(filter_card)

        # Takvim Sonuçları Konteyneri
        self.schedule_results_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_box.append(self.schedule_results_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Dahili hafıza
        self.lessons_data = []
        self.teachers_data = []
        self.program_id = "3"
        self._initial_loaded = False

    def reset_state(self):
        """Hesap değiştiğinde EtutView önbelleğini ve arayüzünü sıfırlar."""
        self.lessons_data = []
        self.teachers_data = []
        self._initial_loaded = False
        while child := self.stats_box.get_first_child():
            self.stats_box.remove(child)
        while child := self.my_records_container.get_first_child():
            self.my_records_container.remove(child)
        while child := self.schedule_results_container.get_first_child():
            self.schedule_results_container.remove(child)

    def load_data(self):
        def worker():
            records = fetch_etut_records()
            dashboard = fetch_course_dashboard()
            form_meta = fetch_birebir_form_metadata()

            GLib.idle_add(self._render_dashboard_and_records, records, dashboard, form_meta)

        threading.Thread(target=worker, daemon=True).start()

    def _render_dashboard_and_records(self, records, dashboard, form_meta):
        # 1. İstatistikleri Çiz
        while self.stats_box.get_first_child():
            self.stats_box.remove(self.stats_box.get_first_child())

        course_counts = dashboard.get("courseCounts", {})
        e_counts = course_counts.get("E", {})
        b_counts = course_counts.get("B", {})

        yearly_etut = e_counts.get("yearly", 0)
        monthly_etut = e_counts.get("monthly", 0)
        yearly_bir = b_counts.get("yearly", 0)

        self.stats_box.append(self._create_stat_badge("Tüm Dönem Etüt", str(yearly_etut), "accessories-calculator-symbolic", "#10b981"))
        self.stats_box.append(self._create_stat_badge("Bu Ayki Etüt", str(monthly_etut), "appointment-soon-symbolic", "#3b82f6"))
        self.stats_box.append(self._create_stat_badge("Birebir Sayısı", str(yearly_bir), "avatar-default-symbolic", "#8b5cf6"))

        # 2. Kayıtları Çiz
        while self.my_records_container.get_first_child():
            self.my_records_container.remove(self.my_records_container.get_first_child())

        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Kayıtlı Etüt &amp; Birebirlerim")

        etut_list = records.get("etut", [])
        bir_list = records.get("birebir", [])
        all_mine = []
        for e in etut_list:
            e["type_label"] = "Etüt"
            all_mine.append(e)
        for b in bir_list:
            b["type_label"] = "Birebir"
            all_mine.append(b)

        if not all_mine:
            empty_row = Adw.ActionRow()
            empty_row.set_title("Kayıtlı etüt veya birebir dersiniz bulunmuyor")
            empty_row.set_subtitle("Aşağıdaki arama bölümünden öğretmenlerin müsait saatlerini inceleyebilirsiniz.")
            empty_row.add_prefix(Gtk.Image.new_from_icon_name("info-symbolic"))
            pref_group.add(empty_row)
        else:
            for item in all_mine:
                row = Adw.ActionRow()
                row.set_title(f"{item.get('lesson', '')} - {item.get('teaNameSurname', '')}")
                sub_txt = f"📅 {item.get('date', '')}  ⏰ {item.get('unitLabel', '')}"
                if item.get("hallName"):
                    sub_txt += f"  📍 {item.get('hallName')}"
                row.set_subtitle(sub_txt)
                badge = Gtk.Label(label=item.get("type_label", "Etüt"))
                badge.add_css_class("badge-label")
                row.add_suffix(badge)
                pref_group.add(row)

        self.my_records_container.append(pref_group)

        # 3. Form derslerini yükle (ilk açılışta)
        if not self._initial_loaded:
            self._initial_loaded = True
            self.lessons_data = form_meta.get("lessons", [])
            programs = form_meta.get("programs", [])
            if programs:
                self.program_id = programs[0].get("id", "3")

            lesson_titles = ["Ders Seçiniz..."] + [l["title"] for l in self.lessons_data]
            self.lesson_model = Gtk.StringList.new(lesson_titles)
            self.lesson_combo.set_model(self.lesson_model)

    def _create_stat_badge(self, title, count_str, icon_name, color_hex):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("card")
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        icon.set_halign(Gtk.Align.CENTER)
        box.append(icon)

        num_lbl = Gtk.Label()
        num_lbl.set_markup(f"<span size='xx-large' weight='heavy' foreground='{color_hex}'>{count_str}</span>")
        num_lbl.set_halign(Gtk.Align.CENTER)
        box.append(num_lbl)

        txt_lbl = Gtk.Label()
        txt_lbl.set_markup(f"<span size='small' alpha='75%'>{title}</span>")
        txt_lbl.set_halign(Gtk.Align.CENTER)
        box.append(txt_lbl)

        return box

    def on_lesson_changed(self, combo, _param):
        sel_idx = combo.get_selected()
        if sel_idx <= 0 or sel_idx > len(self.lessons_data):
            self.teachers_data = []
            self.teacher_model = Gtk.StringList.new(["Önce Ders Seçiniz..."])
            self.teacher_combo.set_model(self.teacher_model)
            return

        lesson = self.lessons_data[sel_idx - 1]
        lesson_id = lesson["id"]

        def worker():
            teachers = fetch_birebir_teachers(lesson_id)
            GLib.idle_add(self._update_teacher_list, teachers)

        threading.Thread(target=worker, daemon=True).start()

    def _update_teacher_list(self, teachers):
        self.teachers_data = teachers
        if not teachers:
            self.teacher_model = Gtk.StringList.new(["Bu derse ait öğretmen bulunamadı"])
        else:
            titles = ["Öğretmen Seçiniz..."] + [t["name"] for t in teachers]
            self.teacher_model = Gtk.StringList.new(titles)
        self.teacher_combo.set_model(self.teacher_model)

    def on_filter_changed(self, _obj, _param):
        lesson_idx = self.lesson_combo.get_selected()
        teacher_idx = self.teacher_combo.get_selected()
        type_idx = self.type_combo.get_selected()  # 0: Etüt, 1: Birebir

        if lesson_idx <= 0 or teacher_idx <= 0 or not self.teachers_data:
            return

        lesson_id = self.lessons_data[lesson_idx - 1]["id"]
        teacher_id = self.teachers_data[teacher_idx - 1]["id"]
        course_type = "0" if type_idx == 0 else "1"

        def worker():
            sched = fetch_birebir_schedule(
                lesson_id=lesson_id,
                teacher_id=teacher_id,
                program_id=self.program_id,
                course_type=course_type
            )
            GLib.idle_add(self._render_schedule_table, sched)

        threading.Thread(target=worker, daemon=True).start()

    def _render_schedule_table(self, sched_data):
        while self.schedule_results_container.get_first_child():
            self.schedule_results_container.remove(self.schedule_results_container.get_first_child())

        if not sched_data or not sched_data.get("success"):
            row = Adw.ActionRow()
            row.set_title("Bu öğretmen için takvim verisi bulunamadı veya program tanımlanmamış.")
            row.add_prefix(Gtk.Image.new_from_icon_name("dialog-information-symbolic"))
            self.schedule_results_container.append(row)
            return

        headers = sched_data.get("header", [])
        times = sched_data.get("time", [])

        group = Adw.PreferencesGroup()
        group.set_title("Haftalık Uygunluk ve Ders Saatleri")
        group.set_description(f"Toplam {len(headers)} gün ve {len(times)} saat dilimi listeleniyor.")

        for day in headers:
            exp_row = Adw.ExpanderRow()
            exp_row.set_title(f"{day.get('title', '')} ({day.get('date', '')})")
            exp_row.set_subtitle(f"{len(times)} Etüt/Birebir Saati")
            exp_row.add_prefix(Gtk.Image.new_from_icon_name("x-office-calendar-symbolic"))

            for t in times:
                time_row = Adw.ActionRow()
                time_row.set_title(t.get("title", ""))
                status_lbl = Gtk.Label(label="Müsait / Talep Edilebilir")
                status_lbl.add_css_class("accent")
                time_row.add_suffix(status_lbl)
                exp_row.add_row(time_row)

            group.add(exp_row)

        self.schedule_results_container.append(group)
