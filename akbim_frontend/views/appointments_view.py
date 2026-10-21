import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_appointments_data, fetch_surveys_data


class AppointmentsView(Gtk.ScrolledWindow):
    """
    LimeOBS Randevu & Anket Takip Görünümü
    Veli-öğretmen randevu durumunu, rehberlik türlerini ve okul anketlerini listeler.
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
        title_lbl.set_markup("<span size='large' weight='bold'>📅 Randevu &amp; Anket Sistemi</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        subtitle_lbl = Gtk.Label()
        subtitle_lbl.set_markup("<span size='small' alpha='70%'>Öğretmen randevuları, rehberlik görüşmeleri ve okul değerlendirme anketleri</span>")
        subtitle_lbl.set_halign(Gtk.Align.START)
        title_box.append(subtitle_lbl)

        header_box.append(title_box)

        # Yenile Butonu
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Randevuları Yenile")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # 2. KPI İstatistik Kartları
        self.kpi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.kpi_box.set_homogeneous(True)
        self.main_box.append(self.kpi_box)

        # 3. İçerik Konteyneri
        self.content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.append(self.content_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Önbellek
        self._appointments_data = {}
        self._surveys_data = {}

    def reset_state(self):
        """Hesap veya profil değiştiğinde durumu sıfırlar."""
        self._appointments_data.clear()
        self._surveys_data.clear()

        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

    def load_data(self):
        def worker():
            try:
                app_data = fetch_appointments_data()
                surv_data = fetch_surveys_data()
                GLib.idle_add(self.apply_data, app_data, surv_data)
            except Exception as e:
                print(f"AppointmentsView yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def apply_data(self, app_data, surv_data):
        self._appointments_data = app_data or {}
        self._surveys_data = surv_data or {}
        self.render_content()

    def render_content(self):
        while child := self.kpi_box.get_first_child():
            self.kpi_box.remove(child)
        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

        appointments = self._appointments_data.get("appointments", [])
        types = self._appointments_data.get("types", [])
        surveys = self._surveys_data.get("surveys", [])
        teacher_surveys = self._surveys_data.get("teacherSurveys", [])

        # KPI Sayaçları
        total_apps = len(appointments)
        total_survs = len(surveys) + len(teacher_surveys)
        total_types = len(types)

        self.add_kpi_card("Kayıtlı Randevu", str(total_apps), "appointment-soon-symbolic")
        self.add_kpi_card("Görüşme Türü", str(total_types), "user-available-symbolic")
        self.add_kpi_card("Okul Anketleri", str(total_survs), "emblem-documents-symbolic")

        # 1. 📋 Randevularım Grubu
        app_group = Adw.PreferencesGroup()
        app_group.set_title("Randevularım")

        if appointments:
            for item in appointments:
                teacher = item.get("teacherName") or item.get("hostName") or "Öğretmen / İdareci"
                date_time = f"{item.get('date', '')} {item.get('time', '')}".strip()
                type_desc = item.get("typeDescription") or item.get("type", "Randevu")
                status = item.get("status", "Onaylandı")

                row = Adw.ActionRow()
                row.set_title(teacher)
                row.set_subtitle(f"{date_time} • {type_desc}")
                row.set_icon_name("avatar-default-symbolic")

                badge = Gtk.Label(label=status)
                badge.add_css_class("badge-primary")
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)

                app_group.add(row)
        else:
            empty_app = Adw.ActionRow()
            empty_app.set_title("Planlanmış Aktif Randevunuz Bulunmuyor")
            empty_app.set_subtitle("Öğretmenlerinizle veya okul rehberlik servisiyle randevu oluşturduğunuzda burada listelenecektir.")
            empty_app.set_icon_name("dialog-information-symbolic")
            app_group.add(empty_app)

        self.content_container.append(app_group)

        # 2. 🎯 Görüşme & Rehberlik Türleri
        if types:
            type_group = Adw.PreferencesGroup()
            type_group.set_title("Rehberlik & Randevu Hizmetleri")

            for t in types:
                t_desc = t.get("description", "Rehberlik Hizmeti")
                row = Adw.ActionRow()
                row.set_title(t_desc)
                row.set_subtitle("Okul PDR ve danışmanlık servisi görüşme türü")
                row.set_icon_name("help-about-symbolic")
                type_group.add(row)

            self.content_container.append(type_group)

        # 3. 📝 Okul ve Öğretmen Değerlendirme Anketleri
        survey_group = Adw.PreferencesGroup()
        survey_group.set_title("Okul ve Öğretmen Anketleri")

        all_surveys = surveys + teacher_surveys
        if all_surveys:
            for s in all_surveys:
                s_title = s.get("title") or s.get("name") or "Okul Anketi"
                s_time = s.get("remainingTime") or s.get("expiry") or ""
                s_status = s.get("status", "Aktif")

                row = Adw.ActionRow()
                row.set_title(s_title)
                row.set_subtitle(f"Kalan Süre: {s_time}" if s_time else "Değerlendirme Anketi")
                row.set_icon_name("edit-select-all-symbolic")

                badge = Gtk.Label(label=s_status)
                badge.add_css_class("badge-warning")
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)

                survey_group.add(row)
        else:
            empty_survey = Adw.ActionRow()
            empty_survey.set_title("Şu Anda Aktif Bir Anket Bulunmuyor")
            empty_survey.set_subtitle("Okul idaresi veya rehberlik servisi anket tanımladığında burada görüntülenecektir.")
            empty_survey.set_icon_name("dialog-information-symbolic")
            survey_group.add(empty_survey)

        self.content_container.append(survey_group)

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
