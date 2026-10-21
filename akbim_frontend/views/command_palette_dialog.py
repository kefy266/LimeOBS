import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk


class CommandPaletteDialog(Adw.Window):
    """
    LimeOBS Quick Launcher / Hızlı Komut Paleti (Ctrl + K / Meta + K)
    Sayfalar, eylemler, dersler ve öğretmenler arasında tek tıkla arama ve geçiş.
    ESC veya Kapat butonuna basıldığında kesin ve pürüzsüzce kapanır.
    """
    def __init__(self, parent_window, on_navigate, on_search_teacher=None):
        super().__init__(transient_for=parent_window)
        self.on_navigate = on_navigate
        self.on_search_teacher = on_search_teacher

        from api_bridge import apply_theme_to_window
        apply_theme_to_window(self)

        self.set_modal(True)
        self.set_title("Hızlı Komut Paleti")
        self.set_default_size(560, 440)
        self.set_resizable(False)

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Üst Başlık Çubuğu (Görünür Kapat Butonlu HeaderBar)
        header_bar = Adw.HeaderBar()
        header_bar.set_show_end_title_buttons(False)
        header_bar.set_show_start_title_buttons(False)

        title_widget = Adw.WindowTitle(title="Hızlı Komut Paleti", subtitle="Ctrl+K / ⌘+K")
        header_bar.set_title_widget(title_widget)

        # Açık Kapat Butonu
        close_btn = Gtk.Button(label="Kapat")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda _: self.dismiss_dialog())
        header_bar.pack_end(close_btn)

        outer_box.append(header_bar)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)

        # Arama kutusu
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic")
        search_icon.set_pixel_size(18)
        search_box.append(search_icon)

        self.entry = Gtk.SearchEntry()
        self.entry.set_hexpand(True)
        self.entry.set_placeholder_text("Sayfa, ders veya eylem arayın... (Örn: ödev, ders, yemek, etüt)")
        self.entry.connect("search-changed", self.on_search_changed)
        self.entry.connect("activate", self.on_entry_activated)
        search_box.append(self.entry)

        esc_hint = Gtk.Label(label="ESC")
        esc_hint.add_css_class("badge-primary")
        search_box.append(esc_hint)

        main_box.append(search_box)

        # Sonuçlar listesi (Scrolled)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.add_css_class("boxed-list")
        self.list_box.connect("row-activated", self.on_row_activated)
        scrolled.set_child(self.list_box)

        main_box.append(scrolled)
        outer_box.append(main_box)

        self.set_content(outer_box)

        # Tüm komutlar veritabanı
        self.commands = [
            {"title": "Anasayfa & Canlı Ders", "subtitle": "Günün akışı, canlı ders durumu ve özet", "icon": "user-home-symbolic", "tag": "home"},
            {"title": "Haftalık Ders Programı", "subtitle": "Yatay takvim tablosu ve ders saatleri", "icon": "appointment-soon-symbolic", "tag": "schedule"},
            {"title": "Etüt ve Birebir", "subtitle": "Öğretmen etüt saatleri ve birebir programı", "icon": "accessories-calculator-symbolic", "tag": "etut"},
            {"title": "Ödevlerim & Projeler", "subtitle": "Aktif ödevler, teslim tarihleri ve ek dosyalar", "icon": "x-office-document-symbolic", "tag": "homework"},
            {"title": "Yazılı Sınavlarım (MEB)", "subtitle": "Dönemlik klasik yazılı sınav notları ve sınıf ortalamaları", "icon": "accessories-dictionary-symbolic", "tag": "classical_exams"},
            {"title": "Deneme Sınavları & Karneler", "subtitle": "Planlanan sınavlar, deneme sonuçları ve DAS taramaları", "icon": "emblem-documents-symbolic", "tag": "exams"},
            {"title": "Devamsızlık Takibi", "subtitle": "Yoklama ve ders katılım istatistikleri", "icon": "user-available-symbolic", "tag": "attendance"},
            {"title": "Aylık Yemek Menüsü", "subtitle": "Okul yemekhanesi güncel menüsü ve PDF listesi", "icon": "food-symbolic", "tag": "food"},
            {"title": "Okul Kütüphanesi & Ödünç Kitaplar", "subtitle": "Ödünç aldığınız kitaplar ve katalog arama", "icon": "starred-symbolic", "tag": "library"},
            {"title": "Öğretmenlerim", "subtitle": "Ders öğretmenleri listesi ve iletişim", "icon": "avatar-default-symbolic", "tag": "teachers"},
            {"title": "Gelen Kutusu & Mesajlar", "subtitle": "Okul mesajları ve bildirimler", "icon": "mail-inbox-symbolic", "tag": "messages"},
            {"title": "Yeni Mesaj Yaz", "subtitle": "Öğretmene veya idareye yeni mesaj gönder", "icon": "mail-message-new-symbolic", "tag": "compose_message"},
            {"title": "Duyuru ve Etkinlikler", "subtitle": "Okul bildirimleri ve etkinlik takvimi", "icon": "notifications-symbolic", "tag": "announcements"},
            {"title": "Kullanıcı Profili", "subtitle": "Öğrenci bilgileri, profil fotoğrafı", "icon": "contact-new-symbolic", "tag": "profile"},
            {"title": "Şifre Değiştir", "subtitle": "OBS hesap şifresini güvenle güncelle", "icon": "dialog-password-symbolic", "tag": "change_password"},
        ]

        # Klavye kontrolleri (ESC tuşunu hem window hem entry seviyesinde yakala)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)

        entry_key_controller = Gtk.EventControllerKey()
        entry_key_controller.connect("key-pressed", self.on_key_pressed)
        self.entry.add_controller(entry_key_controller)

        self.populate_list(self.commands)
        GLib.idle_add(self.entry.grab_focus)

    def dismiss_dialog(self):
        self.close()
        self.destroy()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.dismiss_dialog()
            return True
        elif keyval == Gdk.KEY_Down:
            row = self.list_box.get_selected_row()
            if not row:
                first = self.list_box.get_row_at_index(0)
                if first:
                    self.list_box.select_row(first)
            return False
        return False

    def populate_list(self, items):
        # Listeyi temizle
        while self.list_box.get_first_child():
            self.list_box.remove(self.list_box.get_first_child())

        for cmd in items:
            row = Adw.ActionRow()
            row.set_title(cmd["title"])
            row.set_subtitle(cmd["subtitle"])
            row.set_icon_name(cmd.get("icon", "system-run-symbolic"))
            row.set_activatable(True)
            row.cmd_data = cmd
            
            nav_arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
            nav_arrow.add_css_class("dim-label")
            row.add_suffix(nav_arrow)
            
            self.list_box.append(row)

        first = self.list_box.get_row_at_index(0)
        if first:
            self.list_box.select_row(first)

    def on_search_changed(self, entry):
        q = entry.get_text().strip().lower()
        if not q:
            self.populate_list(self.commands)
            return

        filtered = []
        for cmd in self.commands:
            t = cmd["title"].lower()
            s = cmd["subtitle"].lower()
            tag = cmd.get("tag", "").lower()
            if q in t or q in s or q in tag:
                filtered.append(cmd)

        self.populate_list(filtered)

    def on_entry_activated(self, entry):
        row = self.list_box.get_selected_row()
        if row and hasattr(row, "cmd_data"):
            self.execute_command(row.cmd_data)

    def on_row_activated(self, list_box, row):
        if hasattr(row, "cmd_data"):
            self.execute_command(row.cmd_data)

    def execute_command(self, cmd):
        self.dismiss_dialog()
        tag = cmd.get("tag")
        if tag and self.on_navigate:
            self.on_navigate(tag)
