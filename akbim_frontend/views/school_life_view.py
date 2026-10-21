import subprocess
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import (
    fetch_club_info,
    fetch_service_list_info,
    fetch_exam_days_calendar,
    fetch_newsletters_data,
)


class SchoolLifeView(Gtk.ScrolledWindow):
    """
    LimeOBS Okul Yaşamı & Takvim Görünümü
    Öğrenci kulüpleri, okul servis güzergah listesi, resmi sınav günleri takvimi ve bültenleri içerir.
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
        title_lbl.set_markup("<span size='large' weight='bold'>🚩 Okul Yaşamı &amp; Servis / Kulüp</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        subtitle_lbl = Gtk.Label()
        subtitle_lbl.set_markup("<span size='small' alpha='70%'>Servis güzergahları, öğrenci kulüpleri, sınav takvimi ve okul bültenleri</span>")
        subtitle_lbl.set_halign(Gtk.Align.START)
        title_box.append(subtitle_lbl)

        header_box.append(title_box)

        # Yenile Butonu
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Bilgileri Yenile")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # 2. Bölümler Konteyneri
        self.content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.append(self.content_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Önbellek
        self._club_data = {}
        self._service_data = {}
        self._exam_days_data = {}
        self._newsletters = []

    def reset_state(self):
        """Hesap veya oturum değiştiğinde önbelleği ve arayüzü sıfırlar."""
        self._club_data.clear()
        self._service_data.clear()
        self._exam_days_data.clear()
        self._newsletters.clear()

        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

    def load_data(self):
        def worker():
            try:
                clubs = fetch_club_info()
                service = fetch_service_list_info()
                exam_days = fetch_exam_days_calendar()
                newsletters = fetch_newsletters_data()
                GLib.idle_add(self.apply_data, clubs, service, exam_days, newsletters)
            except Exception as e:
                print(f"SchoolLifeView yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def apply_data(self, clubs, service, exam_days, newsletters):
        self._club_data = clubs or {}
        self._service_data = service or {}
        self._exam_days_data = exam_days or {}
        self._newsletters = newsletters or []
        self.render_content()

    def render_content(self):
        while child := self.content_container.get_first_child():
            self.content_container.remove(child)

        # 1. 📅 Resmi Sınav Günleri Takvimi Kartı
        exam_days_group = Adw.PreferencesGroup()
        exam_days_group.set_title("Resmi Sınav Günleri Takvimi")
        
        exam_row = Adw.ActionRow()
        has_exam_doc = self._exam_days_data.get("has_file")
        if has_exam_doc:
            exam_row.set_title("2026-2027 Okul Sınav Günleri Çizelgesi")
            exam_row.set_subtitle("Okul yönetimi tarafından yayınlanan resmi sınav takvimi PDF belgesi")
            exam_row.set_icon_name("x-office-document-symbolic")

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            btn_box.set_valign(Gtk.Align.CENTER)

            view_url = self._exam_days_data.get("view_url")
            if view_url:
                view_btn = Gtk.Button(label="Takvimi Aç")
                view_btn.add_css_class("suggested-action")
                view_btn.set_icon_name("document-open-symbolic")
                view_btn.connect("clicked", lambda _: self.open_url(view_url))
                btn_box.append(view_btn)

            download_url = self._exam_days_data.get("download_url")
            if download_url:
                dl_btn = Gtk.Button(label="İndir")
                dl_btn.set_icon_name("folder-download-symbolic")
                dl_btn.connect("clicked", lambda _: self.open_url(download_url))
                btn_box.append(dl_btn)

            exam_row.add_suffix(btn_box)
        else:
            exam_row.set_title("Sınav Günleri Listesi Henüz Yüklenmemiş")
            exam_row.set_subtitle(self._exam_days_data.get("msg") or "Okul idaresi resmi sınav günleri çizelgesini yüklediğinde burada görüntülenecektir.")
            exam_row.set_icon_name("dialog-information-symbolic")

        exam_days_group.add(exam_row)
        self.content_container.append(exam_days_group)

        # 2. 🚌 Okul Servis Listesi Kartı
        service_group = Adw.PreferencesGroup()
        service_group.set_title("Okul Servisi & Güzergah Listesi")

        serv_row = Adw.ActionRow()
        has_serv_file = self._service_data.get("has_file")
        if has_serv_file and self._service_data.get("url"):
            serv_row.set_title("Okul Servis Güzergah ve İletişim Listesi")
            serv_row.set_subtitle("Servis şoförü, rehber personel ve güzergah bilgilerini içeren resmi belge")
            serv_row.set_icon_name("emblem-shared-symbolic")

            s_url = self._service_data.get("url")
            open_serv_btn = Gtk.Button(label="Belgeyi Görüntüle")
            open_serv_btn.add_css_class("suggested-action")
            open_serv_btn.set_icon_name("document-open-symbolic")
            open_serv_btn.connect("clicked", lambda _: self.open_url(s_url))
            serv_row.add_suffix(open_serv_btn)
        else:
            serv_row.set_title("Servis Listesi Henüz Yüklenmemiş")
            serv_row.set_subtitle(self._service_data.get("msg") or "Okul yönetimi servis güzergah listesini sisteme eklediğinde buradan erişebilirsiniz.")
            serv_row.set_icon_name("dialog-information-symbolic")

        service_group.add(serv_row)
        self.content_container.append(service_group)

        # 3. 👥 Öğrenci Kulüpleri
        club_group = Adw.PreferencesGroup()
        club_group.set_title("Öğrenci Kulüpleri & Etkinlikler")

        clubs = self._club_data.get("clubs", [])
        if clubs:
            for c in clubs:
                c_title = c.get("title") or c.get("name") or "Kulüp"
                c_teacher = c.get("teacher") or c.get("advisor") or ""
                c_desc = c.get("description") or c.get("purpose") or ""

                c_row = Adw.ExpanderRow()
                c_row.set_title(c_title)
                c_row.set_subtitle(f"Danışman: {c_teacher}" if c_teacher else "Kayıtlı Öğrenci Kulübü")
                c_row.set_icon_name("system-users-symbolic")

                if c_desc:
                    desc_row = Adw.ActionRow()
                    desc_row.set_title("Kulüp Amacı ve Çalışmaları")
                    desc_row.set_subtitle(c_desc)
                    c_row.add_row(desc_row)

                club_group.add(c_row)
        else:
            empty_club_row = Adw.ActionRow()
            empty_club_row.set_title("Üye Olduğunuz Kulüp Bulunmuyor")
            empty_club_row.set_subtitle(self._club_data.get("message") or "Kulüp seçim döneminde danışman öğretmeniniz aracılığıyla kulüplere katılabilirsiniz.")
            empty_club_row.set_icon_name("dialog-information-symbolic")
            club_group.add(empty_club_row)

        self.content_container.append(club_group)

        # 4. 📰 Okul Bülten ve Günceleri
        news_group = Adw.PreferencesGroup()
        news_group.set_title("Okul Bültenleri & Yayınlar")

        if self._newsletters:
            for item in self._newsletters:
                n_title = item.get("title") or item.get("name") or "Bülten"
                n_date = item.get("date") or item.get("created_at") or ""
                n_url = item.get("url") or item.get("file_url")

                n_row = Adw.ActionRow()
                n_row.set_title(n_title)
                n_row.set_subtitle(f"Tarih: {n_date}" if n_date else "Okul Bülteni")
                n_row.set_icon_name("mail-mark-unread-symbolic")

                if n_url:
                    open_n_btn = Gtk.Button(label="Oku / İndir")
                    open_n_btn.set_icon_name("document-open-symbolic")
                    open_n_btn.connect("clicked", lambda _, u=n_url: self.open_url(u))
                    n_row.add_suffix(open_n_btn)

                news_group.add(n_row)
        else:
            empty_news = Adw.ActionRow()
            empty_news.set_title("Henüz Yayınlanmış Bülten Bulunmuyor")
            empty_news.set_subtitle("Dönemlik okul bültenleri ve günceler yayınlandığında burada listelenecektir.")
            empty_news.set_icon_name("dialog-information-symbolic")
            news_group.add(empty_news)

        self.content_container.append(news_group)

    def open_url(self, url):
        if not url:
            return
        try:
            subprocess.Popen(["xdg-open", url])
        except Exception as e:
            print(f"URL açma hatası: {e}")
