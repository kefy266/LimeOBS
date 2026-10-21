import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_teacher_notes


class TeacherNotesView(Gtk.ScrolledWindow):
    """
    LimeOBS Öğretmen Görüşleri ve Rehberlik Notları Görünümü
    Öğretmenlerin öğrenciye özel gelişim ve karne görüşlerini listeler.
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
        title_lbl.set_markup("<span size='large' weight='bold'>💬 Öğretmen Görüşleri &amp; Bülten</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        subtitle_lbl = Gtk.Label()
        subtitle_lbl.set_markup("<span size='small' alpha='70%'>Ders öğretmenleri ve rehberlik servisinin öğrenci gelişim değerlendirmeleri</span>")
        subtitle_lbl.set_halign(Gtk.Align.START)
        title_box.append(subtitle_lbl)

        header_box.append(title_box)

        # Yenile Butonu
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Görüşleri Yenile")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # 2. İstatistik KPI Alanı
        self.kpi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.kpi_box.set_homogeneous(True)
        self.main_box.append(self.kpi_box)

        # 3. Filtreleme Çubuğu (Tümü / Olumlu / Bilgi / Uyarı)
        self.filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.filter_box.add_css_class("segmented-bar")

        self.active_filter = "all"
        self.filter_buttons = {}

        filters = [
            ("all", "Tüm Görüşler"),
            ("positive", "Olumlu Değerlendirmeler"),
            ("info", "Bilgilendirme Notları"),
            ("warning", "Gelişim &amp; Uyarı"),
        ]

        for key, label in filters:
            btn = Gtk.Button()
            lbl = Gtk.Label()
            lbl.set_markup(label)
            btn.set_child(lbl)
            if key == "all":
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda _, k=key: self.set_filter(k))
            self.filter_box.append(btn)
            self.filter_buttons[key] = btn

        self.main_box.append(self.filter_box)

        # 4. Görüşler Listesi
        self.notes_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.append(self.notes_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Dahili Durum
        self._all_comments = []
        self._counts = {}

    def reset_state(self):
        """Hesap veya profil değiştiğinde durumu sıfırlar."""
        self.active_filter = "all"
        self._all_comments.clear()
        self._counts.clear()

        for k, btn in self.filter_buttons.items():
            if k == "all":
                btn.add_css_class("suggested-action")
            else:
                btn.remove_css_class("suggested-action")

        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.notes_container.get_first_child():
            self.notes_container.remove(child)

    def set_filter(self, key):
        self.active_filter = key
        for k, btn in self.filter_buttons.items():
            if k == key:
                btn.add_css_class("suggested-action")
            else:
                btn.remove_css_class("suggested-action")
        self.render_notes()

    def load_data(self):
        def worker():
            try:
                res = fetch_teacher_notes()
                GLib.idle_add(self.apply_data, res)
            except Exception as e:
                print(f"TeacherNotesView yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def apply_data(self, data):
        self._all_comments = data.get("comments", []) or []
        self._counts = data.get("counts", {}) or {}
        self.render_notes()

    def render_notes(self):
        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.notes_container.get_first_child():
            self.notes_container.remove(child)

        # Filtreleme
        filtered = []
        for n in self._all_comments:
            status = int(n.get("status") or 1)
            if self.active_filter == "all":
                filtered.append(n)
            elif self.active_filter == "positive" and status == 5:
                filtered.append(n)
            elif self.active_filter == "info" and status in [1, 2]:
                filtered.append(n)
            elif self.active_filter == "warning" and status in [3, 4]:
                filtered.append(n)

        # KPI Sayaçları
        total_count = len(self._all_comments)
        pos_count = sum(1 for n in self._all_comments if int(n.get("status") or 1) == 5)
        info_count = sum(1 for n in self._all_comments if int(n.get("status") or 1) in [1, 2])
        warn_count = sum(1 for n in self._all_comments if int(n.get("status") or 1) in [3, 4])

        self.add_kpi_card("Toplam Görüş", str(total_count), "chat-symbolic")
        self.add_kpi_card("Olumlu Notlar", str(pos_count), "starred-symbolic")
        self.add_kpi_card("Bilgilendirme", str(info_count), "dialog-information-symbolic")
        self.add_kpi_card("Gelişim Önerisi", str(warn_count), "dialog-warning-symbolic")

        if not filtered:
            group = Adw.PreferencesGroup()
            group.set_title("Öğretmen Görüşleri")
            row = Adw.ActionRow()
            row.set_title("Bu kategoride henüz kayıtlı görüş bulunmuyor")
            row.set_subtitle("Ders öğretmenleriniz veya okul rehberliği görüş paylaştığında burada anlık görüntülenecektir.")
            row.set_icon_name("dialog-information-symbolic")
            group.add(row)
            self.notes_container.append(group)
            return

        group = Adw.PreferencesGroup()
        group.set_title("Öğrenci Değerlendirmeleri")

        for item in filtered:
            teacher_name = item.get("teaNameSurname") or item.get("teacherName") or "Öğretmen"
            comment = item.get("comment") or item.get("description") or "-"
            date_str = item.get("createDate") or ""
            if len(date_str) >= 10:
                parts = date_str[:10].split("-")
                if len(parts) == 3:
                    date_str = f"{parts[2]}.{parts[1]}.{parts[0]}"
            status = int(item.get("status") or 1)

            # Durum başlığı
            status_map = {
                1: ("Normal Not", "badge-primary"),
                2: ("Bilgi Notu", "badge-primary"),
                3: ("Uyarı Notu", "badge-warning"),
                4: ("Gelişim Notu", "badge-warning"),
                5: ("Olumlu Not", "badge-success"),
            }
            status_text, css_class = status_map.get(status, ("Görüş", "badge-primary"))

            exp_row = Adw.ExpanderRow()
            exp_row.set_title(teacher_name)
            exp_row.set_subtitle(f"{date_str} • {comment[:75]}..." if len(comment) > 75 else f"{date_str} • {comment}")
            exp_row.set_icon_name("avatar-default-symbolic")

            # Rozet
            badge = Gtk.Label(label=status_text)
            badge.add_css_class(css_class)
            badge.set_valign(Gtk.Align.CENTER)
            exp_row.add_suffix(badge)

            # Genişletilmiş tam metin
            content_row = Adw.ActionRow()
            content_row.set_title(comment)
            content_row.set_subtitle(f"Görüş Tarihi: {item.get('createDate', '-')}")
            exp_row.add_row(content_row)

            group.add(exp_row)

        self.notes_container.append(group)

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
        t_lbl.set_markup(f"<span size='small' alpha='75%'>{title}</span>")
        top_box.append(t_lbl)
        card.append(top_box)

        v_lbl = Gtk.Label()
        v_lbl.set_markup(f"<span size='x-large' weight='bold'>{value}</span>")
        v_lbl.set_halign(Gtk.Align.START)
        card.append(v_lbl)

        self.kpi_box.append(card)
