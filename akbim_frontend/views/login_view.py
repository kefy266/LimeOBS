import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

import akbim_api


class LoginView(Gtk.Box):
    def __init__(self, on_login_success):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.on_login_success = on_login_success

        clamp = Adw.Clamp()
        clamp.set_maximum_size(450)
        clamp.set_tightening_threshold(350)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(40)
        main_box.set_margin_bottom(40)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # 1. Başlık & Logo
        import sys
        from pathlib import Path
        
        possible_paths = [
            Path(__file__).resolve().parent.parent / "app_icon.png",
            Path(__file__).resolve().parent / "app_icon.png",
        ]
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            possible_paths.insert(0, meipass / "akbim_frontend" / "app_icon.png")
            possible_paths.insert(0, meipass / "app_icon.png")

        logo_path = None
        for p in possible_paths:
            if p.exists():
                logo_path = p
                break

        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        logo_box.set_halign(Gtk.Align.CENTER)

        if logo_path:
            try:
                from gi.repository import Gdk
                texture = Gdk.Texture.new_from_filename(str(logo_path))
                logo_img = Gtk.Image.new_from_paintable(texture)
                logo_img.set_pixel_size(72)
            except Exception:
                logo_img = Gtk.Image.new_from_icon_name("limeobs")
                logo_img.set_pixel_size(72)
            logo_box.append(logo_img)
        else:
            # Fallback olarak kayıtlı ikon temasından çek
            logo_img = Gtk.Image.new_from_icon_name("limeobs")
            logo_img.set_pixel_size(72)
            logo_box.append(logo_img)

        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='xx-large' weight='bold'>LimeOBS</span>")
        logo_box.append(title_lbl)

        sub_lbl = Gtk.Label()
        sub_lbl.set_markup("<span size='medium' foreground='#b8b8b8'>Öğrenci &amp; Veli Masasüstü İstemcisi</span>")
        logo_box.append(sub_lbl)

        main_box.append(logo_box)

        # 1.5 Oturum Sona Erdi / Uyarı Kartı
        self.session_alert = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.session_alert.add_css_class("session-alert-box")
        self.session_alert.set_visible(False)
        self.session_alert.set_margin_top(4)
        self.session_alert.set_margin_bottom(4)

        alert_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        alert_icon.set_pixel_size(24)
        self.session_alert.append(alert_icon)

        self.session_alert_label = Gtk.Label()
        self.session_alert_label.set_markup("<span size='medium' weight='bold'>⚠️ Oturum Sona Erdi</span>\n<span size='small'>Oturumunuz sona erdi. Lütfen tekrar giriş yapın.</span>")
        self.session_alert_label.set_wrap(True)
        self.session_alert_label.set_halign(Gtk.Align.START)
        self.session_alert_label.set_hexpand(True)
        self.session_alert.append(self.session_alert_label)

        main_box.append(self.session_alert)

        # 2. Giriş Formu (Grup)
        form_group = Adw.PreferencesGroup()
        form_group.set_title("Giriş Bilgileri")

        from api_bridge import get_saved_base_url

        self.school_url_row = Adw.EntryRow()
        self.school_url_row.set_title("Okul OBS Sunucu Adresi")
        self.school_url_row.set_text(get_saved_base_url())
        self.school_url_row.connect("entry-activated", lambda _: self.tc_row.grab_focus())
        form_group.add(self.school_url_row)

        self.tc_row = Adw.EntryRow()
        self.tc_row.set_title("T.C. Kimlik No")
        self.tc_row.connect("entry-activated", lambda _: self.password_row.grab_focus())
        form_group.add(self.tc_row)

        self.password_row = Adw.PasswordEntryRow()
        self.password_row.set_title("Şifre")
        self.password_row.connect("entry-activated", lambda _: self.on_login_clicked(None))
        form_group.add(self.password_row)

        # 3. Beni Hatırla SwitchRow
        self.remember_me_row = Adw.SwitchRow()
        self.remember_me_row.set_title("Beni Hatırla")
        self.remember_me_row.set_subtitle("Oturumu bilgisayara kaydet")
        self.remember_me_row.set_active(True)
        form_group.add(self.remember_me_row)

        main_box.append(form_group)

        # 4. Hata Mesajı Alanı
        self.error_label = Gtk.Label()
        self.error_label.add_css_class("error-text")
        self.error_label.set_wrap(True)
        self.error_label.set_visible(False)
        main_box.append(self.error_label)

        # 5. Giriş Butonu & Yükleme Spinner'ı
        action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(24, 24)
        self.spinner.set_visible(False)
        action_box.append(self.spinner)

        self.login_btn = Gtk.Button(label="Giriş Yap")
        self.login_btn.add_css_class("suggested-action")
        self.login_btn.add_css_class("pill")
        self.login_btn.set_size_request(-1, 45)
        self.login_btn.connect("clicked", self.on_login_clicked)
        action_box.append(self.login_btn)

        main_box.append(action_box)

        clamp.set_child(main_box)
        self.append(clamp)

    def reset_fields(self):
        self.tc_row.set_text("")
        self.password_row.set_text("")
        self.clear_alerts()
        self.set_loading(False)

    def on_login_clicked(self, widget):
        from api_bridge import clear_active_session, set_base_url, save_credentials, clear_saved_credentials
        from pathlib import Path

        tc = self.tc_row.get_text().strip()
        password = self.password_row.get_text().strip()

        if not tc or not password:
            self.show_error("Lütfen T.C. Kimlik No ve şifrenizi girin.")
            return

        school_url = self.school_url_row.get_text().strip()
        if school_url:
            set_base_url(school_url)

        # 🧹 Önceki oturum, çerez ve önbellek kalıntılarını tamamen sıfırla
        clear_active_session(clear_saved_login=False)
        self.clear_alerts()
        self.set_loading(True)

        def worker():
            try:
                result = akbim_api.login(tc, password)
                if result.get("success"):
                    if self.remember_me_row.get_active():
                        akbim_api.save_session()
                        save_credentials(tc, password)
                    else:
                        clear_saved_credentials()
                        if hasattr(akbim_api, "COOKIE_FILE"):
                            Path(akbim_api.COOKIE_FILE).unlink(missing_ok=True)
                    GLib.idle_add(self.handle_success)
                else:
                    msg = result.get("msg", "Kullanıcı adı veya şifre yanlış.")
                    GLib.idle_add(self.handle_failure, msg)
            except Exception as e:
                GLib.idle_add(self.handle_failure, f"Bağlantı hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def set_loading(self, is_loading):
        self.login_btn.set_sensitive(not is_loading)
        self.tc_row.set_sensitive(not is_loading)
        self.password_row.set_sensitive(not is_loading)
        self.remember_me_row.set_sensitive(not is_loading)
        self.spinner.set_visible(is_loading)
        if is_loading:
            self.spinner.start()
            self.error_label.set_visible(False)
        else:
            self.spinner.stop()

    def show_session_expired(self, message="Oturumunuz sona erdi. Lütfen tekrar giriş yapın."):
        self.set_loading(False)
        self.session_alert_label.set_markup(
            f"<span size='medium' weight='bold'>⚠️ Oturum Sona Erdi</span>\n<span size='small'>{message}</span>"
        )
        self.session_alert.set_visible(True)
        self.error_label.set_visible(False)

    def show_error(self, message):
        self.error_label.set_text(message)
        self.error_label.set_visible(True)
        self.session_alert.set_visible(False)

    def clear_alerts(self):
        self.session_alert.set_visible(False)
        self.error_label.set_visible(False)

    def handle_failure(self, error_message):
        self.set_loading(False)
        self.show_error(error_message)

    def handle_success(self):
        from api_bridge import reset_session_expired_flag
        reset_session_expired_flag()
        self.set_loading(False)
        self.clear_alerts()
        self.on_login_success()
