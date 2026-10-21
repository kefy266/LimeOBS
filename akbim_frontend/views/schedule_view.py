import threading
from datetime import datetime, time, timedelta
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import get_adaptive_index_data, get_effective_school_date, get_effective_school_day_idx


class ScheduleView(Gtk.ScrolledWindow):
    """
    Haftalık Ders Programı Görünümü (Dikey / Gün Gruplu Akış)
    Dikey, ferah, gün gün ayrılmış ve her ekrana/çözünürlüğe mükemmel oturan tasarım.
    """
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)
        clamp.set_tightening_threshold(700)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.main_box.set_margin_top(22)
        self.main_box.set_margin_bottom(30)
        self.main_box.set_margin_start(18)
        self.main_box.set_margin_end(18)

        # Üst Başlık ve Yenile Butonu
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        header_label = Gtk.Label()
        header_label.set_markup("<span size='x-large' weight='bold'>📅 Ders Programı</span>")
        header_label.set_halign(Gtk.Align.START)
        title_box.append(header_label)

        sub_label = Gtk.Label()
        sub_label.set_markup("<span size='small' alpha='65%'>Haftalık ders saatleri ve öğretmen tablosu</span>")
        sub_label.set_halign(Gtk.Align.START)
        title_box.append(sub_label)
        title_box.set_hexpand(True)
        header_box.append(title_box)

        print_btn = Gtk.Button(label="Yazdır / PDF")
        print_btn.set_icon_name("document-print-symbolic")
        print_btn.set_tooltip_text("Haftalık Ders Programını A4 PDF Olarak Yazdır / Kaydet")
        print_btn.connect("clicked", lambda _: self.print_or_export_schedule())
        header_box.append(print_btn)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Ders Programını Yenile")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # Gün Atlama / Filtre Butonları (Tüm Hafta, Pazartesi, Salı, ...)
        filter_scroll = Gtk.ScrolledWindow()
        filter_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        filter_scroll.set_hexpand(True)

        self.day_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.day_buttons_box.add_css_class("segmented-bar")
        filter_scroll.set_child(self.day_buttons_box)
        self.main_box.append(filter_scroll)

        self.selected_day_filter = 0  # 0: Tüm Hafta, 1..7: Belirli Gün

        # Dikey Ders Grupları Kapsayıcısı
        self.days_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.append(self.days_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Önbellek verileri
        self._cached_x_info = []
        self._cached_y_info = []
        self._cached_lessons = []

    def reset_state(self):
        """Hesap değiştiğinde ScheduleView önbelleğini ve arayüzünü sıfırlar."""
        self._cached_x_info = []
        self._cached_y_info = []
        self._cached_lessons = []
        self.selected_day_filter = 0
        while child := self.day_buttons_box.get_first_child():
            self.day_buttons_box.remove(child)
        while child := self.days_container.get_first_child():
            self.days_container.remove(child)

    def load_data(self):
        def worker():
            try:
                data = get_adaptive_index_data()
                schedule = data.get("data", {}).get("lessonSchedule", {}).get("data", {})
                x_info = schedule.get("xInfo", [])
                y_info = schedule.get("yInfo", [])
                lessons = schedule.get("data", [])

                GLib.idle_add(self.set_schedule_data, x_info, y_info, lessons)
            except Exception as e:
                print(f"Ders programı yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def set_schedule_data(self, x_info, y_info, lessons):
        self._cached_x_info = x_info
        self._cached_y_info = y_info
        self._cached_lessons = lessons
        self.build_filter_buttons()
        self.render_vertical_schedule()

    def build_filter_buttons(self):
        while self.day_buttons_box.get_first_child():
            self.day_buttons_box.remove(self.day_buttons_box.get_first_child())

        now = datetime.now()
        effective_day_idx = get_effective_school_day_idx(now)
        effective_date = get_effective_school_date(now)

        all_btn = Gtk.Button(label="Tüm Hafta")
        if self.selected_day_filter == 0:
            all_btn.add_css_class("suggested-action")
        all_btn.connect("clicked", lambda _: self.select_filter(0))
        self.day_buttons_box.append(all_btn)

        for day_index, day_data in enumerate(self._cached_y_info, start=1):
            # Cumartesi (6) ve Pazar (7) ders programında gösterilmez
            if day_index > 5:
                continue

            day_name = day_data[0] if len(day_data) > 0 else f"Gün {day_index}"
            if day_name.strip() in ("Cumartesi", "Pazar"):
                continue

            is_effective = (day_index == effective_day_idx)
            if is_effective:
                if effective_date == now.date():
                    lbl = f"⭐ {day_name} (Bugün)"
                elif effective_date == now.date() + timedelta(days=1):
                    lbl = f"⭐ {day_name} (Yarın)"
                else:
                    lbl = f"⭐ {day_name}"
            else:
                lbl = day_name

            btn = Gtk.Button(label=lbl)
            if self.selected_day_filter == day_index:
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda _, idx=day_index: self.select_filter(idx))
            self.day_buttons_box.append(btn)

    def select_filter(self, day_idx):
        self.selected_day_filter = day_idx
        self.build_filter_buttons()
        self.render_vertical_schedule()

    def render_vertical_schedule(self):
        now = datetime.now()
        effective_day_idx = get_effective_school_day_idx(now)
        effective_date = get_effective_school_date(now)
        weekday_idx = now.isoweekday()
        cur_time = now.time()

        while self.days_container.get_first_child():
            self.days_container.remove(self.days_container.get_first_child())

        if not self._cached_lessons or not self._cached_y_info:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            empty_box.set_valign(Gtk.Align.CENTER)
            empty_box.set_halign(Gtk.Align.CENTER)
            empty_box.set_margin_top(40)
            empty_lbl = Gtk.Label(label="Ders programı bulunamadı.")
            empty_box.append(empty_lbl)
            self.days_container.append(empty_box)
            return

        visible_days_count = 0
        for day_index, day_data in enumerate(self._cached_y_info, start=1):
            # Cumartesi ve Pazar gösterilmez
            if day_index > 5:
                continue

            day_name = day_data[0] if len(day_data) > 0 else f"Gün {day_index}"
            if day_name.strip() in ("Cumartesi", "Pazar"):
                continue

            if self.selected_day_filter != 0 and day_index != self.selected_day_filter:
                continue

            # Aktif haftaya ait gerçek takvim tarihini hesapla
            calc_date = effective_date + timedelta(days=(day_index - effective_day_idx))
            day_date_str = calc_date.strftime("%d.%m.%Y")

            is_effective = (day_index == effective_day_idx)
            is_today = (day_index == weekday_idx)

            # Gün Grubu (PreferencesGroup dikey düzenli liste)
            day_group = Adw.PreferencesGroup()
            title_text = f"📅 {day_name} ({day_date_str})"
            if is_effective:
                if effective_date == now.date():
                    title_text += " — BUGÜN"
                elif effective_date == now.date() + timedelta(days=1):
                    title_text += " — YARIN"
                else:
                    title_text += " — SIRADAKİ OKUL GÜNÜ"
            day_group.set_title(title_text)

            day_lessons = sorted(
                [l for l in self._cached_lessons if l.get("y") == day_index],
                key=lambda item: item.get("x", 0)
            )

            if not day_lessons:
                empty_row = Adw.ActionRow()
                empty_row.set_title("Bu gün için ders programı bulunmuyor.")
                day_group.add(empty_row)
            else:
                for l in day_lessons:
                    x_idx = l.get("x", 1) - 1
                    slot = self._cached_x_info[x_idx][0] if 0 <= x_idx < len(self._cached_x_info) else "??:??"
                    texts = l.get("text", [])
                    teacher = texts[0].strip() if len(texts) > 0 else "-"
                    subject = texts[1].strip() if len(texts) > 1 else "-"
                    header_title = l.get("data", {}).get("headerTitle", "").strip()

                    row = Adw.ActionRow()
                    row.set_title(subject)
                    
                    sub_text = f"👤 {teacher}"
                    if header_title:
                        sub_text += f"  •  {header_title}"
                    row.set_subtitle(sub_text)

                    # Sol taraf: Saat rozeti
                    time_badge = Gtk.Label()
                    time_badge.set_markup(f"<span weight='bold' size='small' foreground='#38bdf8'>⏰ {slot}</span>")
                    time_badge.set_valign(Gtk.Align.CENTER)
                    time_badge.set_margin_start(4)
                    time_badge.set_margin_end(6)
                    row.add_prefix(time_badge)

                    # Şu anki ders mi kontrolü
                    is_current = False
                    if is_today and "-" in slot:
                        try:
                            start_str, end_str = slot.split("-")
                            sh, sm = map(int, start_str.strip().split(":"))
                            eh, em = map(int, end_str.strip().split(":"))
                            st_time = time(sh, sm)
                            end_time = time(eh, em)

                            if st_time <= cur_time <= end_time:
                                is_current = True
                        except Exception:
                            pass

                    if is_current:
                        cur_badge = Gtk.Label(label="Şu Anda")
                        cur_badge.add_css_class("badge-active")
                        cur_badge.set_valign(Gtk.Align.CENTER)
                        row.add_suffix(cur_badge)
                        row.add_css_class("active-lesson-card")

                    # Sağ taraf: Öğretmene mesaj gönder butonu
                    if teacher and teacher != "-":
                        msg_btn = Gtk.Button(icon_name="mail-message-new-symbolic")
                        msg_btn.set_tooltip_text(f"{teacher} öğretmenine mesaj gönder")
                        msg_btn.add_css_class("flat")
                        msg_btn.set_valign(Gtk.Align.CENTER)
                        msg_btn.connect("clicked", lambda _, t=teacher: self.send_teacher_message(t))
                        row.add_suffix(msg_btn)

                    day_group.add(row)

            self.days_container.append(day_group)
            visible_days_count += 1

        if visible_days_count == 0:
            finish_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            finish_box.set_valign(Gtk.Align.CENTER)
            finish_box.set_halign(Gtk.Align.CENTER)
            finish_box.set_margin_top(50)
            f_lbl = Gtk.Label()
            f_lbl.set_markup("<span size='large' weight='bold'>🎉 Bu haftaki tüm dersler tamamlandı!</span>")
            f_sub = Gtk.Label()
            f_sub.set_markup("<span size='small' alpha='65%'>İyi dinlenmeler, yeni hafta dersleri yakında başlayacak.</span>")
            finish_box.append(f_lbl)
            finish_box.append(f_sub)
            self.days_container.append(finish_box)

    def send_teacher_message(self, teacher_name):
        from views.compose_mail_dialog import open_compose_message_dialog
        from api_bridge import search_mail_receivers
        root_window = self.get_root()

        def resolve_and_open():
            found_rec = None
            try:
                results = search_mail_receivers(teacher_name.strip())
                if results:
                    found_rec = results[0]
            except Exception:
                pass

            if not found_rec:
                found_rec = {
                    "nameSurname": teacher_name,
                    "teaNameSurname": teacher_name,
                    "type": "Öğretmen",
                    "userType": 3
                }

            GLib.idle_add(lambda: open_compose_message_dialog(root_window, preselected_receiver=found_rec))

        threading.Thread(target=resolve_and_open, daemon=True).start()

    def print_or_export_schedule(self):
        """Haftalık ders programını A4 yatay formatta profesyonel bir PDF tablosu olarak oluşturur ve PDF görüntüleyicisinde açar."""
        if not self._cached_x_info or not self._cached_lessons:
            return

        import tempfile, cairo
        from views.pdf_viewer_dialog import open_pdf_viewer

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        width, height = 842, 595  # A4 Yatay Boyut (Points)
        surface = cairo.PDFSurface(tmp.name, width, height)
        cr = cairo.Context(surface)

        # 1. Arka Plan
        cr.set_source_rgb(0.97, 0.98, 0.99)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # 2. Başlık ve Çerçeve
        cr.set_source_rgb(0.08, 0.12, 0.22)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(18)
        cr.move_to(36, 42)
        cr.show_text("LimeOBS — Haftalık Ders Programı")

        cr.set_source_rgb(0.45, 0.52, 0.62)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        cr.move_to(36, 58)
        now_str = datetime.now().strftime("%d.%m.%Y")
        cr.show_text(f"Oluşturulma Tarihi: {now_str}  •  Pazartesi – Cuma Ders ve Öğretmen Tablosu")

        # 3. Tablo Parametreleri
        table_x = 36
        table_y = 74
        table_w = width - 72  # 770 pt
        table_h = height - 96  # 425 pt

        # Sütunlar: Saat Dilimi Sütunu (90 pt) + 5 Gün Sütunu (her biri (770-90)/5 = 136 pt)
        time_col_w = 90
        day_col_w = (table_w - time_col_w) / 5.0

        days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
        slots = [s[0] if isinstance(s, list) and len(s) > 0 else f"{i+1}. Ders" for i, s in enumerate(self._cached_x_info[:8])]
        num_slots = max(1, len(slots))
        header_row_h = 32
        row_h = (table_h - header_row_h) / float(num_slots)

        # Başlık Satırı Zemini (Lacivert Cam)
        cr.set_source_rgb(0.12, 0.22, 0.40)
        cr.rectangle(table_x, table_y, table_w, header_row_h)
        cr.fill()

        # Başlık Metinleri
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(11)
        cr.move_to(table_x + 16, table_y + 20)
        cr.show_text("Ders / Saat")

        for d_idx, d_name in enumerate(days):
            col_x = table_x + time_col_w + d_idx * day_col_w
            cr.move_to(col_x + 12, table_y + 20)
            cr.show_text(d_name)

        # Satırlar ve Ders Hücreleri
        lessons_map = {(l.get("x"), l.get("y")): l for l in self._cached_lessons}

        for s_idx, slot in enumerate(slots):
            r_y = table_y + header_row_h + s_idx * row_h

            # Alternatif satır rengi
            if s_idx % 2 == 0:
                cr.set_source_rgb(1.0, 1.0, 1.0)
            else:
                cr.set_source_rgb(0.94, 0.96, 0.98)
            cr.rectangle(table_x, r_y, table_w, row_h)
            cr.fill()

            # Saat Hücresi
            cr.set_source_rgb(0.18, 0.24, 0.36)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(9)
            cr.move_to(table_x + 8, r_y + (row_h / 2.0) + 3)
            cr.show_text(slot.replace(" - ", "–"))

            # Gün Hücreleri
            for d_idx in range(5):
                day_num = d_idx + 1
                slot_num = s_idx + 1
                c_x = table_x + time_col_w + d_idx * day_col_w
                les = lessons_map.get((slot_num, day_num))

                if les:
                    texts = les.get("text", [])
                    tea = texts[0].strip() if len(texts) > 0 else ""
                    sub = texts[1].strip() if len(texts) > 1 else ""

                    # Ders Adı
                    cr.set_source_rgb(0.08, 0.15, 0.30)
                    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                    cr.set_font_size(9.5)
                    cr.move_to(c_x + 8, r_y + 16)
                    cr.show_text(sub[:20])

                    # Öğretmen Adı
                    if tea and tea != "-":
                        cr.set_source_rgb(0.45, 0.50, 0.60)
                        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                        cr.set_font_size(8)
                        cr.move_to(c_x + 8, r_y + 30)
                        cr.show_text(tea[:22])

        # Tablo Çerçeve ve Izgara Çizgileri
        cr.set_source_rgb(0.82, 0.86, 0.90)
        cr.set_line_width(0.75)
        # Dikey çizgiler
        for c in range(6):
            lx = table_x + time_col_w + c * day_col_w if c > 0 else table_x + time_col_w
            cr.move_to(lx, table_y)
            cr.line_to(lx, table_y + table_h)
            cr.stroke()

        # Yatay çizgiler
        for r in range(num_slots + 1):
            ly = table_y + header_row_h + r * row_h
            cr.move_to(table_x, ly)
            cr.line_to(table_x + table_w, ly)
            cr.stroke()

        # Dış sınır
        cr.set_source_rgb(0.20, 0.30, 0.50)
        cr.set_line_width(1.2)
        cr.rectangle(table_x, table_y, table_w, table_h)
        cr.stroke()

        surface.show_page()
        surface.finish()

        # PDF Görüntüleyicide Aç
        open_pdf_viewer(self.get_root(), tmp.name, title="Haftalık Ders Programı Çıktısı (A4)")

