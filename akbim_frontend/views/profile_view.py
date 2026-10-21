import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from api_bridge import get_adaptive_profile_data, change_user_password


class ProfileView(Gtk.ScrolledWindow):
    def __init__(self, on_logout):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.on_logout = on_logout

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)
        clamp.set_tightening_threshold(500)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(25)
        self.main_box.set_margin_bottom(25)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)

        # 1. Profil Başlık Kartı (Resmi Fotoğraf / Avatar + İsim + Rol Rozeti)
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.header_box.set_halign(Gtk.Align.CENTER)

        # Resim / Avatar kapsayıcısı
        self.photo_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.photo_container.set_halign(Gtk.Align.CENTER)
        
        self.fallback_avatar = Adw.Avatar()
        self.fallback_avatar.set_size(100)
        self.fallback_avatar.set_show_initials(True)
        self.photo_container.append(self.fallback_avatar)

        self.header_box.append(self.photo_container)

        self.name_label = Gtk.Label()
        self.name_label.set_markup("<span size='x-large' weight='bold'>Kullanıcı Profili</span>")
        self.header_box.append(self.name_label)

        self.role_badge = Gtk.Label(label="LimeOBS")
        self.role_badge.add_css_class("badge-primary")
        self.header_box.append(self.role_badge)

        self.main_box.append(self.header_box)

        # 2. Dinamik Bilgi Grupları Kapsayıcısı
        self.info_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.append(self.info_container)

        # 3. Oturum ve Hesap İşlemleri Grubu
        account_group = Adw.PreferencesGroup()
        account_group.set_title("⚙️ Hesap ve Güvenlik")

        # Şifre Değiştirme Butonu (changePassword.php)
        pwd_row = Adw.ActionRow()
        pwd_row.set_title("Şifre Değiştir")
        pwd_row.set_subtitle("OBS hesap şifrenizi güncelleyin")
        pwd_row.set_icon_name("dialog-password-symbolic")
        pwd_row.set_activatable(True)
        pwd_row.connect("activated", lambda _: self.show_change_password_dialog())

        pwd_btn = Gtk.Button(label="Değiştir")
        pwd_btn.add_css_class("suggested-action")
        pwd_btn.connect("clicked", lambda _: self.show_change_password_dialog())
        pwd_row.add_suffix(pwd_btn)
        account_group.add(pwd_row)

        # Tema Seçimi (Liquid Glass / Beyaz / Koyu)
        from api_bridge import get_saved_theme
        theme_row = Adw.ActionRow()
        theme_row.set_title("Görünüm Teması")
        theme_row.set_subtitle("Aktif tema stilini seçin")
        theme_row.set_icon_name("preferences-desktop-appearance-symbolic")

        theme_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        btn_liquid = Gtk.Button(label="Liquid Glass")
        btn_light = Gtk.Button(label="Beyaz")
        btn_dark = Gtk.Button(label="Koyu")

        def update_active_theme_ui():
            cur = get_saved_theme()
            for b, t in [(btn_liquid, "liquid"), (btn_light, "light"), (btn_dark, "dark")]:
                if cur == t:
                    b.add_css_class("suggested-action")
                    b.remove_css_class("flat")
                else:
                    b.remove_css_class("suggested-action")
                    b.add_css_class("flat")

        def set_app_theme(t_name):
            app = self.get_root().get_application() if self.get_root() else None
            if app and hasattr(app, "apply_theme"):
                app.apply_theme(t_name)
            update_active_theme_ui()

        btn_liquid.connect("clicked", lambda _: set_app_theme("liquid"))
        btn_light.connect("clicked", lambda _: set_app_theme("light"))
        btn_dark.connect("clicked", lambda _: set_app_theme("dark"))

        update_active_theme_ui()

        theme_btn_box.append(btn_liquid)
        theme_btn_box.append(btn_light)
        theme_btn_box.append(btn_dark)

        theme_row.add_suffix(theme_btn_box)
        account_group.add(theme_row)

        session_row = Adw.ActionRow()
        session_row.set_title("Oturum Durumu")
        session_row.set_subtitle("Aktif (Güvenli Bağlantı)")
        session_row.set_icon_name("security-high-symbolic")
        account_group.add(session_row)

        logout_row = Adw.ActionRow()
        logout_row.set_title("Oturumu Kapat")
        logout_row.set_subtitle("Mevcut hesaptan çıkış yap")
        logout_row.set_icon_name("system-log-out-symbolic")
        
        logout_btn = Gtk.Button(label="Çıkış")
        logout_btn.add_css_class("destructive-action")
        logout_btn.connect("clicked", lambda _: self.on_logout())
        logout_row.add_suffix(logout_btn)
        account_group.add(logout_row)

        self.main_box.append(account_group)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def show_change_password_dialog(self):
        root_window = self.get_root()
        dialog = Adw.Window(transient_for=root_window)
        dialog.set_modal(True)

        from api_bridge import apply_theme_to_window
        apply_theme_to_window(dialog)

        dialog.set_title("Şifre Değiştir")
        dialog.set_default_size(380, 420)
        dialog.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(16)
        box.set_margin_bottom(24)
        box.set_margin_start(20)
        box.set_margin_end(20)

        header_bar = Adw.HeaderBar()
        header_bar.set_show_title(True)
        dialog_title = Adw.WindowTitle(title="Şifre Değiştir", subtitle="Akbim OBS")
        header_bar.set_title_widget(dialog_title)

        box.append(header_bar)

        pref_group = Adw.PreferencesGroup()
        pref_group.set_title("Yeni Şifre Bilgileri")
        pref_group.set_description("En az 6, en fazla 30 karakter olmalıdır.")

        old_row = Adw.PasswordEntryRow()
        old_row.set_title("Mevcut Şifre")
        pref_group.add(old_row)

        new_row = Adw.PasswordEntryRow()
        new_row.set_title("Yeni Şifre")
        pref_group.add(new_row)

        renew_row = Adw.PasswordEntryRow()
        renew_row.set_title("Yeni Şifre (Tekrar)")
        pref_group.add(renew_row)

        box.append(pref_group)

        status_label = Gtk.Label()
        status_label.set_wrap(True)
        status_label.set_halign(Gtk.Align.CENTER)
        box.append(status_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="İptal")
        cancel_btn.connect("clicked", lambda _: dialog.close())
        btn_box.append(cancel_btn)

        submit_btn = Gtk.Button(label="Güncelle")
        submit_btn.add_css_class("suggested-action")

        def on_submit(_):
            old_p = old_row.get_text().strip()
            new_p = new_row.get_text().strip()
            renew_p = renew_row.get_text().strip()

            if not old_p or not new_p or not renew_p:
                status_label.set_markup("<span color='#e01b24'>Boş alan bıraktınız.</span>")
                return

            if len(new_p) < 6:
                status_label.set_markup("<span color='#e01b24'>Yeni şifreniz en az 6 haneli olmalıdır.</span>")
                return

            if new_p != renew_p:
                status_label.set_markup("<span color='#e01b24'>Şifreleriniz eşleşmiyor.</span>")
                return

            submit_btn.set_sensitive(False)
            status_label.set_markup("<span>Güncelleniyor...</span>")

            def worker():
                res = change_user_password(old_p, new_p, renew_p)
                def update_done():
                    submit_btn.set_sensitive(True)
                    if res.get("success"):
                        dialog.close()
                        # Başarılı bildirim
                        alert = Adw.AlertDialog.new("Başarılı", res.get("message", "Şifreniz başarıyla değiştirildi."))
                        alert.add_response("ok", "Tamam")
                        alert.present(root_window)
                    else:
                        status_label.set_markup(f"<span color='#e01b24'>{res.get('message')}</span>")
                GLib.idle_add(update_done)

            threading.Thread(target=worker, daemon=True).start()

        submit_btn.connect("clicked", on_submit)
        btn_box.append(submit_btn)

        box.append(btn_box)

        dialog.set_content(box)
        dialog.present()

    def reset_state(self):
        """Hesap değiştiğinde ProfileView arayüzünü sıfırlar."""
        self.fallback_avatar.set_text("K")
        self.name_label.set_markup("<span size='x-large' weight='bold'>Kullanıcı Profili</span>")
        self.role_badge.set_text("LimeOBS")
        while child := self.photo_container.get_first_child():
            self.photo_container.remove(child)
        self.photo_container.append(self.fallback_avatar)
        while child := self.info_container.get_first_child():
            self.info_container.remove(child)

    def load_data(self):
        def worker():
            try:
                profile = get_adaptive_profile_data()
                GLib.idle_add(self.render_profile, profile)
            except Exception as e:
                print(f"Profil yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_profile(self, profile):
        role = profile.get("role", "Öğrenci")
        is_parent = (role == "Veli")

        student_name = profile.get("student_name") or "Öğrenci"
        student_class = profile.get("student_class") or ""
        student_no = profile.get("student_no") or "-"
        parent_name = profile.get("parent_name") or "Kayıtlı Veli"
        photo_bytes = profile.get("photo_bytes")

        primary_name = parent_name if is_parent else student_name
        self.fallback_avatar.set_text(primary_name)
        self.name_label.set_markup(f"<span size='x-large' weight='bold'>{primary_name}</span>")
        self.role_badge.set_text(f"{role} Hesabı" + (f" • Sınıf: {student_class}" if not is_parent and student_class else ""))

        # 📸 Gerçek Vesikalık Fotoğrafı Ekrana Yerleştir
        # Önce kapsayıcıyı temizle
        p_child = self.photo_container.get_first_child()
        while p_child:
            next_p = p_child.get_next_sibling()
            self.photo_container.remove(p_child)
            p_child = next_p

        if photo_bytes:
            try:
                glib_bytes = GLib.Bytes.new(photo_bytes)
                texture = Gdk.Texture.new_from_bytes(glib_bytes)

                # Web sitesindeki gibi şık çerçeveli gerçek vesikalık resim
                picture = Gtk.Picture.new_for_paintable(texture)
                picture.set_size_request(160, 200)
                picture.set_can_shrink(True)
                picture.add_css_class("profile-picture")
                self.photo_container.append(picture)
            except Exception as e:
                print(f"Resim oluşturma hatası: {e}")
                self.photo_container.append(self.fallback_avatar)
        else:
            self.photo_container.append(self.fallback_avatar)

        # Eski dinamik grupları temizle
        child = self.info_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.info_container.remove(child)
            child = next_child

        # 1. Veli Bilgileri Grubu
        parent_group = Adw.PreferencesGroup()
        parent_group.set_title("👨‍👩‍👦 Veli Bilgileri")
        
        row_parent = Adw.ActionRow()
        row_parent.set_title("Veli Adı Soyadı")
        row_parent.set_subtitle(str(parent_name))
        row_parent.set_icon_name("contact-new-symbolic")
        parent_group.add(row_parent)

        if is_parent:
            self.info_container.append(parent_group)

        # 2. Öğrenci Bilgileri Grubu
        student_group = Adw.PreferencesGroup()
        student_group.set_title("👤 Öğrenci Bilgileri")

        if is_parent:
            row_st_name = Adw.ActionRow()
            row_st_name.set_title("Öğrenci Adı Soyadı")
            row_st_name.set_subtitle(str(student_name))
            row_st_name.set_icon_name("avatar-default-symbolic")
            student_group.add(row_st_name)

        row_no = Adw.ActionRow()
        row_no.set_title("Öğrenci Numarası")
        row_no.set_subtitle(str(student_no))
        row_no.set_icon_name("starred-symbolic")
        student_group.add(row_no)

        if student_class:
            row_class = Adw.ActionRow()
            row_class.set_title("Sınıf Kodu")
            row_class.set_subtitle(str(student_class))
            row_class.set_icon_name("appointment-soon-symbolic")
            student_group.add(row_class)

        self.info_container.append(student_group)

        if not is_parent:
            self.info_container.append(parent_group)
