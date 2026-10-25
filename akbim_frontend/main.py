import os
import sys
from pathlib import Path

# Log all outputs to gtk_debug.log so we can see any unhandled crash or exception
LOG_FILE = Path(__file__).resolve().parent.parent / "gtk_debug.log"
try:
    log_f = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_f
    sys.stderr = log_f
    print("[LimeOBS GTK4] Logging started", flush=True)
except Exception:
    pass

import threading

# ==============================================================================
# WINDOWS ENVIRONMENT & GRAPHICS FIXES
# ==============================================================================
if sys.platform.startswith("win"):
    # 0. Add MSYS2 UCRT64 binary path to DLL directory and PATH
    if hasattr(os, "add_dll_directory"):
        for p in ["C:/msys64/ucrt64/bin", "C:/msys64/mingw64/bin"]:
            if os.path.isdir(p):
                try:
                    os.add_dll_directory(p)
                except Exception:
                    pass
    if "C:\\msys64\\ucrt64\\bin" not in os.environ.get("PATH", ""):
        os.environ["PATH"] = "C:\\msys64\\ucrt64\\bin;" + os.environ.get("PATH", "")

    # Windows AppUserModelID for taskbar icon grouping
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.kagan.limeobs")
    except Exception:
        pass

    if os.path.isdir("C:/msys64/ucrt64/share/glib-2.0/schemas"):
        os.environ["GSETTINGS_SCHEMA_DIR"] = "C:/msys64/ucrt64/share/glib-2.0/schemas"
    
    # Custom project icons + MSYS2 XDG data dirs
    custom_icons = str(Path(__file__).resolve().parent / "icons")
    cur_xdg = os.environ.get("XDG_DATA_DIRS", "")
    os.environ["XDG_DATA_DIRS"] = custom_icons + os.pathsep + "C:/msys64/ucrt64/share" + (os.pathsep + cur_xdg if cur_xdg else "")

    # FreeType & Fontconfig settings for crystal-clear Windows subpixel font rendering (ClearType)
    os.environ["FREETYPE_PROPERTIES"] = "truetype:interpreter-version=40"
    if os.path.isdir("C:/msys64/ucrt64/etc/fonts"):
        os.environ["FONTCONFIG_PATH"] = "C:/msys64/ucrt64/etc/fonts"

    # 2. Fix GdkPixbuf loaders.cache with absolute paths to ensure PNG, SVG, JPEG
    # load properly in PyInstaller frozen bundles
    try:
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
            internal_dir = Path(getattr(sys, '_MEIPASS', base_dir / '_internal'))
        else:
            base_dir = Path(__file__).resolve().parent.parent
            internal_dir = base_dir

        loader_candidates = [
            internal_dir / "lib" / "gdk-pixbuf" / "loaders",
            internal_dir / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders",
            Path("C:/msys64/ucrt64/lib/gdk-pixbuf-2.0/2.10.0/loaders"),
        ]
        loader_dir = next((d for d in loader_candidates if d.is_dir()), None)

        cache_candidates = [
            internal_dir / "lib" / "gdk-pixbuf" / "loaders.cache",
            internal_dir / "lib" / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache",
            Path("C:/msys64/ucrt64/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"),
        ]
        cache_file = next((f for f in cache_candidates if f.is_file()), None)

        if loader_dir and cache_file:
            import tempfile
            with open(cache_file, "r", encoding="utf-8") as f:
                content = f.read()

            new_lines = []
            for line in content.splitlines():
                line_s = line.strip()
                if line_s.startswith('"') and ('.dll"' in line_s or '.so"' in line_s):
                    dll_name = Path(line_s.strip('"').replace('\\', '/')).name
                    abs_dll = str(loader_dir / dll_name).replace("\\", "\\\\")
                    new_lines.append(f'"{abs_dll}"')
                else:
                    new_lines.append(line)

            tmp_cache = Path(tempfile.gettempdir()) / f"gdk_pixbuf_loaders_{os.getpid()}.cache"
            with open(tmp_cache, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")

            os.environ["GDK_PIXBUF_MODULE_FILE"] = str(tmp_cache)

        # 3. Fix XDG_DATA_DIRS for Adwaita icon themes
        share_candidates = [
            internal_dir / "share",
            Path("C:/msys64/ucrt64/share"),
        ]
        share_dir = next((d for d in share_candidates if d.is_dir()), None)
        if share_dir:
            cur_xdg = os.environ.get("XDG_DATA_DIRS", "")
            os.environ["XDG_DATA_DIRS"] = str(share_dir) + (os.pathsep + cur_xdg if cur_xdg else "")
    except Exception as env_err:
        print(f"Windows environment bootstrap warning: {env_err}")

# Add project root to sys.path so we can import backend in read-only mode
if getattr(sys, 'frozen', False):
    # AppImage / PyInstaller içinde çalışırken
    APP_DIR = Path(sys._MEIPASS)
    if sys.platform.startswith("win"):
        ROOT_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "LimeOBS"
    else:
        ROOT_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "limeobs"
    ROOT_DIR.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(APP_DIR))
    sys.path.insert(0, str(APP_DIR / "akbim_frontend"))
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT_DIR))

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
if sys.platform.startswith("win"):
    try:
        gi.require_version("GdkWin32", "4.0")
        from gi.repository import GdkWin32
    except Exception:
        pass
from gi.repository import Gtk, Adw, GLib, Gio, Gdk

GLib.set_prgname("com.kagan.limeobs")
GLib.set_application_name("LimeOBS")

import akbim_api
# COOKIE_FILE'ın yazılabilir bir dizinde saklanmasını garantiye alalım
akbim_api.COOKIE_FILE = str(ROOT_DIR / "akbim_session.pkl")
from views.login_view import LoginView
from views.home_view import HomeView
from views.schedule_view import ScheduleView
from views.exams_view import ExamsView
from views.announcements_view import AnnouncementsView
from views.profile_view import ProfileView
from views.messages_view import MessagesView
from views.food_list_view import FoodListView
from views.teachers_view import TeachersView
from views.homework_view import HomeworkView
from views.attendance_view import AttendanceView
from views.library_view import LibraryView
from views.etut_view import EtutView
from views.classical_exams_view import ClassicalExamsView
from views.notifications_dialog import show_notifications_popover
from views.command_palette_dialog import CommandPaletteDialog
from api_bridge import (
    get_adaptive_profile_data,
    clear_active_session,
    get_school_metadata,
    get_saved_theme,
    save_theme,
    add_session_expired_callback,
    get_saved_credentials,
    ensure_valid_session,
)


class AkbimApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=None,
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.window = None
        # Apply Native Windows 11 Fluent font settings and fractional subpixel metrics
        try:
            settings = Gtk.Settings.get_default()
            if settings:
                settings.set_property("gtk-icon-theme-name", "Adwaita")
                settings.set_property("gtk-font-name", "Segoe UI Variable Text 10.5")
                settings.set_property("gtk-hint-font-metrics", False)
                settings.set_property("gtk-font-rendering", 0)
                settings.set_property("gtk-xft-antialias", 1)
                settings.set_property("gtk-xft-hinting", 1)
                settings.set_property("gtk-xft-hintstyle", "hintslight")
                settings.set_property("gtk-xft-rgba", "rgb")
            gi.require_version("PangoCairo", "1.0")
            from gi.repository import PangoCairo
            fm = PangoCairo.font_map_get_default()
            if hasattr(fm, "set_resolution"):
                fm.set_resolution(96.0)
        except Exception:
            pass

    def do_activate(self):
        print("[LimeOBS GTK4] do_activate started", flush=True)
        self.load_icons()
        if not self.window:
            print("[LimeOBS GTK4] Creating AkbimMainWindow...", flush=True)
            self.load_css()
            self.window = AkbimMainWindow(self)
        
        saved_theme = get_saved_theme()
        self.apply_theme(saved_theme)
        print("[LimeOBS GTK4] Presenting window...", flush=True)
        self.window.present()
        print("[LimeOBS GTK4] Window presented successfully!", flush=True)

    def apply_theme(self, theme_name):
        style_mgr = Adw.StyleManager.get_default()
        if theme_name == "light":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            if self.window:
                self.window.remove_css_class("theme-liquid")
                self.window.remove_css_class("theme-dark")
                self.window.add_css_class("theme-light")
        elif theme_name == "dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            if self.window:
                self.window.remove_css_class("theme-liquid")
                self.window.remove_css_class("theme-light")
                self.window.add_css_class("theme-dark")
        else: # "liquid"
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            if self.window:
                self.window.remove_css_class("theme-dark")
                self.window.remove_css_class("theme-light")
                self.window.add_css_class("theme-liquid")
        save_theme(theme_name)

    def load_icons(self):
        frontend_dir = Path(__file__).parent
        display = Gdk.Display.get_default()
        if display:
            settings = Gtk.Settings.get_default()
            if settings:
                try:
                    settings.set_property("gtk-icon-theme-name", "Adwaita")
                    settings.set_property("gtk-font-name", "Segoe UI Variable Text 10.5")
                    settings.set_property("gtk-hint-font-metrics", False)
                    settings.set_property("gtk-font-rendering", 0)
                    settings.set_property("gtk-xft-antialias", 1)
                    settings.set_property("gtk-xft-hinting", 1)
                    settings.set_property("gtk-xft-hintstyle", "hintslight")
                    settings.set_property("gtk-xft-rgba", "rgb")
                except Exception:
                    pass

            icon_theme = Gtk.IconTheme.get_for_display(display)
            icons_dir = frontend_dir / "icons"
            if icons_dir.is_dir():
                icon_theme.add_search_path(str(icons_dir))
            icon_theme.add_search_path(str(frontend_dir))
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
                meipass = Path(getattr(sys, '_MEIPASS', base_dir / '_internal'))
                icon_theme.add_search_path(str(meipass / "share" / "icons"))
                icon_theme.add_search_path(str(meipass / "akbim_frontend"))
                icon_theme.add_search_path(str(base_dir / "_internal" / "share" / "icons"))
            icon_theme.add_search_path(str(Path(sys.prefix) / "share" / "icons"))
            icon_theme.add_search_path(str(frontend_dir.parent / "share" / "icons"))
            icon_theme.add_search_path("C:/msys64/ucrt64/share/icons")
            if not sys.platform.startswith("win"):
                icon_theme.add_search_path("/usr/share/icons")

    def load_css(self):
        candidate_paths = [
            Path(__file__).parent / "style.css",
            Path(__file__).resolve().parent.parent / "style.css",
        ]
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            candidate_paths.insert(0, meipass / "akbim_frontend" / "style.css")
            candidate_paths.insert(0, meipass / "style.css")

        css_path = next((p for p in candidate_paths if p.exists()), None)
        if css_path:
            provider = Gtk.CssProvider()
            provider.load_from_path(str(css_path))
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )


class AkbimMainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("LimeOBS — Öğrenci & Veli Paneli")
        self.set_icon_name("limeobs")
        self.set_default_size(1180, 780)

        # Apply native Windows icon to HWND on realize
        if sys.platform.startswith("win"):
            def on_realize_win(win):
                try:
                    surface = win.get_surface()
                    if surface and hasattr(surface, "get_handle"):
                        hwnd = surface.get_handle()
                        if hwnd:
                            ico_path = str(Path(__file__).parent / "app_icon.ico")
                            if os.path.exists(ico_path):
                                import ctypes
                                h_big = ctypes.windll.user32.LoadImageW(None, ico_path, 1, 32, 32, 0x10)
                                h_sm = ctypes.windll.user32.LoadImageW(None, ico_path, 1, 16, 16, 0x10)
                                if h_big:
                                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, h_big)
                                if h_sm:
                                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, h_sm)
                except Exception:
                    pass
            self.connect("realize", on_realize_win)

        # Ana Ekran Yöneticisi (Stack: Giriş Sayfası vs Ana Panel)
        self.main_stack = Gtk.Stack()
        self.main_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Giriş Sayfası (LoginView)
        self.login_view = LoginView(on_login_success=self.on_login_successful)
        self.main_stack.add_named(self.login_view, "login")

        # 2. Ana Dashboard Sayfası
        self.dashboard_widget = self.build_dashboard()
        self.main_stack.add_named(self.dashboard_widget, "dashboard")

        self.set_content(self.main_stack)
        self.main_stack.set_visible_child_name("login")

        # ⌨️ Genel Klavye Kısayolları (Ctrl + K -> Quick Launcher)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_window_key_pressed)
        self.add_controller(key_controller)

        # 🔔 Oturum Düşme / Sona Erme Dinleyicisi
        add_session_expired_callback(self.on_session_expired)

        # Oturum Kontrolü ve Başlangıç Ekranı
        self.check_initial_session()

    def on_session_expired(self, reason="Oturumunuz sona erdi. Lütfen tekrar giriş yapın."):
        GLib.idle_add(self._handle_session_expired_ui, reason)

    def _handle_session_expired_ui(self, reason="Oturumunuz sona erdi. Lütfen tekrar giriş yapın."):
        self._timer_started = False
        self.reset_all_views()
        self.login_view.show_session_expired(reason)
        if self.main_stack.get_visible_child_name() != "login":
            self.main_stack.set_visible_child_name("login")
            try:
                alert = Adw.AlertDialog.new("Oturum Sona Erdi", reason)
                alert.add_response("ok", "Tekrar Giriş Yap")
                alert.set_default_response("ok")
                alert.present(self)
            except Exception as e:
                print(f"AlertDialog gösterim hatası: {e}")

    def on_window_key_pressed(self, controller, keyval, keycode, state):
        # macOS için Command (Meta/Super) veya Linux/Windows için Ctrl kontrolü
        is_ctrl_or_cmd = bool(
            (state & Gdk.ModifierType.CONTROL_MASK) or
            (state & Gdk.ModifierType.META_MASK) or
            (state & Gdk.ModifierType.SUPER_MASK)
        )
        if is_ctrl_or_cmd and keyval in [Gdk.KEY_k, Gdk.KEY_K]:
            self.open_command_palette()
            return True
        return False

    def open_command_palette(self):
        dialog = CommandPaletteDialog(
            parent_window=self,
            on_navigate=self.navigate_to_tab
        )
        dialog.present()

    def check_initial_session(self):
        def worker():
            try:
                had_saved_session = akbim_api.load_session()
                is_valid = False
                if had_saved_session:
                    from api_bridge import check_session_status
                    status = check_session_status()
                    if status is True:
                        is_valid = True
                    elif status is None:
                        # Ağ hatası / sunucu geçici olarak ulaşılamadı. Kayıtlı oturumla dashboard'a girmeyi dene
                        print("[LimeOBS] Başlangıçta sunucuya ulaşılamadı, kayıtlı oturum çereziyle devam ediliyor.")
                        is_valid = True
                    else:
                        # status is False -> Sunucu yanıt verdi, oturum süresi dolmuş
                        is_valid = ensure_valid_session()

                if not is_valid:
                    # Sadece kayıtlı kimlik bilgisi varsa oturum açmayı dene
                    if get_saved_credentials():
                        is_valid = ensure_valid_session()

                if is_valid:
                    GLib.idle_add(self.on_login_successful)
                else:
                    def show_login():
                        self.main_stack.set_visible_child_name("login")
                        if had_saved_session:
                            self.login_view.show_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                    GLib.idle_add(show_login)
            except Exception as e:
                print(f"[LimeOBS] Oturum veya bağlantı kontrol hatası: {e}")
                def show_login_err():
                    self.main_stack.set_visible_child_name("login")
                    self.login_view.show_session_expired("Oturumunuz sona erdi veya bağlantı kurulamadı. Lütfen tekrar giriş yapın.")
                GLib.idle_add(show_login_err)

        threading.Thread(target=worker, daemon=True).start()

    def build_dashboard(self):
        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(230)
        self.split_view.set_max_sidebar_width(280)
        # Ekran daraldığında veya küçük çözünürlüklerde menü otomatik katlanır (Drawer/Overlay olur)
        self.split_view.set_collapsed(False)
        self.split_view.set_sidebar_width_fraction(0.24)

        # Sidebar (Sol Menü)
        self.sidebar_page = Adw.NavigationPage.new(self.build_sidebar(), "Menü")
        self.split_view.set_sidebar(self.sidebar_page)

        # İçerik Alanı (ViewStack)
        self.stack = Adw.ViewStack()
        
        self.home_view = HomeView(
            on_navigate_tab=self.navigate_to_tab
        )
        self.schedule_view = ScheduleView()
        self.exams_view = ExamsView()
        self.classical_exams_view = ClassicalExamsView()
        self.food_view = FoodListView()
        self.homework_view = HomeworkView()
        self.attendance_view = AttendanceView()
        self.announcements_view = AnnouncementsView()
        self.teachers_view = TeachersView()
        self.messages_view = MessagesView()
        self.library_view = LibraryView()
        self.etut_view = EtutView()
        self.profile_view = ProfileView(on_logout=self.on_logout_clicked)

        self.stack.add_titled_with_icon(self.home_view, "home", "Anasayfa", "user-home-symbolic")
        self.stack.add_titled_with_icon(self.schedule_view, "schedule", "Dersler", "appointment-soon-symbolic")
        self.stack.add_titled_with_icon(self.etut_view, "etut", "Etüt ve Birebir", "accessories-calculator-symbolic")
        self.stack.add_titled_with_icon(self.attendance_view, "attendance", "Devamsızlık", "user-available-symbolic")
        self.stack.add_titled_with_icon(self.homework_view, "homework", "Ödevler", "x-office-document-symbolic")
        self.stack.add_titled_with_icon(self.classical_exams_view, "classical_exams", "Yazılı Sınavlar", "accessories-dictionary-symbolic")
        self.stack.add_titled_with_icon(self.exams_view, "exams", "Sınavlar", "view-continuous-symbolic")
        self.stack.add_titled_with_icon(self.food_view, "food", "Yemek Listesi", "emoji-food-symbolic")
        self.stack.add_titled_with_icon(self.library_view, "library", "Kütüphane", "starred-symbolic")
        self.stack.add_titled_with_icon(self.announcements_view, "announcements", "Duyuru ve Etkinlik", "alarm-symbolic")
        self.stack.add_titled_with_icon(self.teachers_view, "teachers", "Öğretmenler", "avatar-default-symbolic")
        self.stack.add_titled_with_icon(self.messages_view, "messages", "Gelen Kutusu", "mail-unread-symbolic")
        self.stack.add_titled_with_icon(self.profile_view, "profile", "Profil", "contact-new-symbolic")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        header_bar = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title="LimeOBS", subtitle="Öğrenci Bilgi Sistemi")
        header_bar.set_title_widget(self.window_title)

        # macOS ve Linux pencere butonları (Kapatma, Büyütme, Simge Durumu)
        header_bar.set_show_end_title_buttons(True)
        header_bar.set_show_start_title_buttons(True)

        # 📱 Küçük ekranlarda / dar pencerelerde kenar çubuğunu açıp kapatma butonu
        self.toggle_sidebar_btn = Gtk.Button(icon_name="sidebar-show-symbolic")
        self.toggle_sidebar_btn.set_tooltip_text("Menüyü Göster/Gizle")
        def on_toggle_sidebar(_):
            if self.split_view.get_collapsed():
                # Katlanmış modda: içerik görünüyorsa menüyü göster (show_content=False), aksi halde içeriği göster
                self.split_view.set_show_content(not self.split_view.get_show_content())
            else:
                # Geniş ekranda geçici olarak katla / aç
                self.split_view.set_collapsed(True)
                self.split_view.set_show_content(False)
        self.toggle_sidebar_btn.connect("clicked", on_toggle_sidebar)
        header_bar.pack_start(self.toggle_sidebar_btn)

        # ⚡ Hızlı Komut Paleti Butonu (Ctrl + K)
        palette_btn = Gtk.Button(icon_name="system-search-symbolic")
        palette_btn.set_tooltip_text("Hızlı Komut Paleti (Ctrl + K / ⌘ + K)")
        palette_btn.connect("clicked", lambda _: self.open_command_palette())
        header_bar.pack_start(palette_btn)

        # 🎨 Tema Değiştirme Butonu (Liquid Glass / Beyaz / Koyu)
        theme_btn = Gtk.Button(icon_name="preferences-desktop-appearance-symbolic")
        theme_btn.set_tooltip_text("Tema Değiştir (Liquid Glass / Beyaz / Koyu)")
        
        def on_theme_toggle(_):
            cur_theme = get_saved_theme()
            if cur_theme == "liquid":
                next_theme = "light"
            elif cur_theme == "light":
                next_theme = "dark"
            else:
                next_theme = "liquid"
            self.get_application().apply_theme(next_theme)
        
        theme_btn.connect("clicked", on_theme_toggle)
        header_bar.pack_end(theme_btn)

        # 🔔 Canlı Bildirim Merkezi Butonu (Açılır Bildirim Paneli)
        self.notify_btn = Gtk.Button(icon_name="alarm-symbolic")
        self.notify_btn.set_tooltip_text("Canlı Okul Bildirimleri")
        self.notify_btn.connect("clicked", lambda btn: show_notifications_popover(btn, on_navigate_tab=self.navigate_to_tab))
        header_bar.pack_end(self.notify_btn)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Tüm Verileri Yenile")
        refresh_btn.connect("clicked", lambda _: self.on_refresh_all(None))
        header_bar.pack_end(refresh_btn)

        content_box.append(header_bar)
        content_box.append(self.stack)

        self.content_page = Adw.NavigationPage.new(content_box, "İçerik")
        self.split_view.set_content(self.content_page)

        return self.split_view

    def navigate_to_tab(self, tab_tag):
        if tab_tag == "change_password":
            self.stack.set_visible_child_name("profile")
            for row, tag in self.rows_map.items():
                if tag == "profile":
                    self.nav_list.select_row(row)
                    break
            if hasattr(self, "profile_view") and hasattr(self.profile_view, "show_change_password_dialog"):
                GLib.idle_add(self.profile_view.show_change_password_dialog)
            return

        if tab_tag == "compose_message":
            from views.compose_mail_dialog import open_compose_message_dialog
            open_compose_message_dialog(self)
            return

        self.stack.set_visible_child_name(tab_tag)
        for row, tag in self.rows_map.items():
            if tag == tab_tag:
                self.nav_list.select_row(row)
                break

    def goto_messages(self):
        self.navigate_to_tab("messages")

    def build_sidebar(self):
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # 0. Sidebar Üst Çubuğu (macOS için sol üst kapatma/simge durumuna alma butonları ve Logo)
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_start_title_buttons(True)
        sidebar_header.set_show_end_title_buttons(False)

        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brand_logo_paths = [
            Path(__file__).parent / "app_icon.png",
        ]
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            brand_logo_paths.insert(0, meipass / "akbim_frontend" / "app_icon.png")
            brand_logo_paths.insert(0, meipass / "app_icon.png")

        brand_logo_file = next((p for p in brand_logo_paths if p.exists()), None)
        if brand_logo_file:
            try:
                texture = Gdk.Texture.new_from_filename(str(brand_logo_file))
                brand_img = Gtk.Image.new_from_paintable(texture)
                brand_img.set_pixel_size(24)
            except Exception:
                brand_img = Gtk.Image.new_from_icon_name("limeobs")
                brand_img.set_pixel_size(24)
        else:
            brand_img = Gtk.Image.new_from_icon_name("limeobs")
            brand_img.set_pixel_size(24)
        brand_box.append(brand_img)

        brand_label = Gtk.Label()
        brand_label.set_markup("<span size='medium' weight='bold'>LimeOBS</span>")
        brand_box.append(brand_label)
        sidebar_header.set_title_widget(brand_box)
        sidebar_box.append(sidebar_header)

        sidebar_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar_content.set_margin_bottom(14)
        sidebar_content.set_margin_start(12)
        sidebar_content.set_margin_end(12)

        # 1. Profil Kartı (Tıklanabilir -> ProfileView'e gider)
        profile_card = Adw.PreferencesGroup()
        self.user_row = Adw.ActionRow()
        self.user_row.set_title("Giriş Yapıldı")
        self.user_row.set_subtitle("Profili Görüntüle")
        
        self.sidebar_avatar = Adw.Avatar()
        self.sidebar_avatar.set_size(36)
        self.sidebar_avatar.set_show_initials(True)
        self.sidebar_avatar.set_text("K")
        self.user_row.add_prefix(self.sidebar_avatar)

        self.user_row.set_activatable(True)
        self.user_row.connect("activated", lambda _: self.stack.set_visible_child_name("profile"))
        profile_card.add(self.user_row)
        sidebar_content.append(profile_card)

        # 2. Gezinme Menüsü
        nav_group = Adw.PreferencesGroup()
        nav_group.set_title("Gezinme")

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")

        menu_items = [
            ("Anasayfa", "user-home-symbolic", "home"),
            ("Ders Programı", "appointment-soon-symbolic", "schedule"),
            ("Etüt ve Birebir", "accessories-calculator-symbolic", "etut"),
            ("Devamsızlık Takip", "user-available-symbolic", "attendance"),
            ("Ödevlerim", "x-office-document-symbolic", "homework"),
            ("Yazılı Sınavlarım", "accessories-dictionary-symbolic", "classical_exams"),
            ("Deneme Sınavlarım", "view-continuous-symbolic", "exams"),
            ("Yemek Listesi", "emoji-food-symbolic", "food"),
            ("Okul Kütüphanesi", "starred-symbolic", "library"),
            ("Duyuru ve Etkinlik", "alarm-symbolic", "announcements"),
            ("Öğretmenlerim", "avatar-default-symbolic", "teachers"),
            ("Gelen Kutusu", "mail-unread-symbolic", "messages"),
            ("Kullanıcı Profili", "contact-new-symbolic", "profile"),
        ]

        self.rows_map = {}
        for title, icon, tag in menu_items:
            row = Adw.ActionRow()
            row.set_title(title)
            img = Gtk.Image.new_from_icon_name(icon)
            row.add_prefix(img)
            row.set_activatable(True)
            self.nav_list.append(row)
            self.rows_map[row] = tag

        self.nav_list.connect("row-activated", self.on_menu_activated)
        nav_group.add(self.nav_list)
        sidebar_content.append(nav_group)

        first_row = self.nav_list.get_row_at_index(0)
        if first_row:
            self.nav_list.select_row(first_row)

        # Boşluk genişletici
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar_content.append(spacer)

        # 3. Sol Alt Bilgi Kartı: Bağlı Okul & Eğitim Dönemi
        school_info_group = Adw.PreferencesGroup()
        self.school_info_row = Adw.ActionRow()
        self.school_info_row.set_title("Bağlı Okul: Yükleniyor...")
        self.school_info_row.set_subtitle("Eğitim Dönemi: -")
        school_icon = Gtk.Image.new_from_icon_name("help-about-symbolic")
        self.school_info_row.add_prefix(school_icon)
        school_info_group.add(self.school_info_row)
        sidebar_content.append(school_info_group)

        # Çıkış Yap Butonu
        logout_btn = Gtk.Button(label="Çıkış Yap")
        logout_btn.add_css_class("destructive-action")
        logout_btn.set_icon_name("system-log-out-symbolic")
        logout_btn.connect("clicked", lambda _: self.on_logout_clicked())
        sidebar_content.append(logout_btn)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_vexpand(True)
        sidebar_scroll.set_hexpand(True)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_child(sidebar_content)
        sidebar_box.append(sidebar_scroll)

        return sidebar_box

    def on_menu_activated(self, listbox, row):
        tag = self.rows_map.get(row)
        if tag:
            self.stack.set_visible_child_name(tag)
            if self.split_view.get_collapsed():
                self.split_view.set_show_content(True)
            # İlgili sekmeye geçildiğinde verilerini tazele
            view_map = {
                "home": self.home_view,
                "schedule": self.schedule_view,
                "etut": self.etut_view,
                "attendance": self.attendance_view,
                "homework": self.homework_view,
                "classical_exams": self.classical_exams_view,
                "exams": self.exams_view,
                "food": self.food_view,
                "library": self.library_view,
                "announcements": self.announcements_view,
                "teachers": self.teachers_view,
                "messages": self.messages_view,
                "profile": self.profile_view,
            }
            target_view = view_map.get(tag)
            if target_view and hasattr(target_view, "load_data"):
                target_view.load_data()

    def reset_all_views(self):
        """Hesap değiştirildiğinde veya çıkış yapıldığında tüm arayüz bileşenlerini temizler."""
        self.update_user_header("Giriş Yapıldı", "Profili Görüntüle", None, "Akbim OBS", "-")
        self.sidebar_avatar.set_text("K")
        self.sidebar_avatar.set_custom_image(None)

        all_views = [
            getattr(self, "home_view", None),
            getattr(self, "schedule_view", None),
            getattr(self, "homework_view", None),
            getattr(self, "classical_exams_view", None),
            getattr(self, "exams_view", None),
            getattr(self, "food_view", None),
            getattr(self, "messages_view", None),
            getattr(self, "attendance_view", None),
            getattr(self, "announcements_view", None),
            getattr(self, "teachers_view", None),
            getattr(self, "library_view", None),
            getattr(self, "etut_view", None),
            getattr(self, "profile_view", None),
        ]
        for v in all_views:
            if v and hasattr(v, "reset_state"):
                try:
                    v.reset_state()
                except Exception as e:
                    print(f"View reset error: {e}")

        if hasattr(self, "nav_list"):
            first_row = self.nav_list.get_row_at_index(0)
            if first_row:
                self.nav_list.select_row(first_row)
        if hasattr(self, "stack"):
            self.stack.set_visible_child_name("home")


    def on_login_successful(self):
        self.login_view.clear_alerts()
        self.reset_all_views()
        self.main_stack.set_visible_child_name("dashboard")
        self.on_refresh_all(None)

    def on_logout_clicked(self):
        clear_active_session(clear_saved_login=True)
        self._timer_started = False
        self.reset_all_views()
        if hasattr(self, "login_view") and hasattr(self.login_view, "reset_fields"):
            self.login_view.reset_fields()
        self.main_stack.set_visible_child_name("login")

    def on_refresh_all(self, button):
        def worker():
            try:
                profile = get_adaptive_profile_data()
                school_meta = get_school_metadata()
                role = profile.get("role", "Öğrenci")
                is_parent = (role == "Veli")
                
                name = profile.get("parent_name") if is_parent else profile.get("student_name")
                name = name or "Kullanıcı"
                sinif = profile.get("student_class", "")
                student_no = profile.get("student_no", "")

                # Sol üst profil alt yazısı (Öğrenci Numarası ekli)
                if is_parent:
                    subtitle_parts = ["Veli Hesabı"]
                    if student_no:
                        subtitle_parts.append(f"Öğr No: {student_no}")
                    subtitle = " • ".join(subtitle_parts)
                else:
                    subtitle_parts = []
                    if sinif:
                        subtitle_parts.append(f"Sınıf: {sinif}")
                    if student_no:
                        subtitle_parts.append(f"No: {student_no}")
                    subtitle = " • ".join(subtitle_parts) if subtitle_parts else "Öğrenci Hesabı"

                photo_bytes = profile.get("photo_bytes")
                school_name = school_meta.get("school_name", "Akbim OBS")
                academic_term = school_meta.get("academic_term", "2026-2027")

                GLib.idle_add(self.update_user_header, name, subtitle, photo_bytes, school_name, academic_term)
                GLib.idle_add(self.home_view.load_data)
                GLib.idle_add(self.schedule_view.load_data)

                # Sadece anasayfa ve ders programını yükle; diğer sekmeler tıklandıkça tembel (lazy) yüklenecektir.
                cur_tab = self.stack.get_visible_child_name()
                if cur_tab and cur_tab not in ("home", "schedule"):
                    view_map = {
                        "classical_exams": self.classical_exams_view,
                        "exams": self.exams_view,
                        "homework": self.homework_view,
                        "food": self.food_view,
                        "messages": self.messages_view,
                        "attendance": self.attendance_view,
                        "announcements": self.announcements_view,
                        "teachers": self.teachers_view,
                        "library": self.library_view,
                        "etut": self.etut_view,
                        "profile": self.profile_view,
                    }
                    target = view_map.get(cur_tab)
                    if target and hasattr(target, "load_data"):
                        GLib.idle_add(target.load_data)

                # ⏱️ 60 Saniyelik Canlı Güncelleme ve Bildirim Kontrolü Başlat
                if not hasattr(self, "_timer_started") or not self._timer_started:
                    self._timer_started = True
                    GLib.timeout_add_seconds(60, self.on_periodic_status_tick)
            except Exception as e:
                print(f"Yenileme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def on_periodic_status_tick(self):
        """Her 60 saniyede bir canlı ders sayacını günceller ve yeni okul bildirimlerini kontrol eder."""
        if self.main_stack.get_visible_child_name() != "dashboard":
            self._timer_started = False
            return False  # Login ekranındaysak veya çıkış yapıldıysa arka plan sorgusunu sonlandır

        try:
            # 1. HomeView canlı sayacını tazele
            if hasattr(self, "home_view") and hasattr(self.home_view, "load_data"):
                self.home_view.load_data()

            # 2. 🔔 Arka planda yeni bildirim kontrolü (Masaüstü Bildirimi Gönder)
            def check_notifs():
                try:
                    from api_bridge import fetch_system_notifications
                    notifs = fetch_system_notifications()
                    if notifs:
                        latest = notifs[0]
                        latest_id = str(latest.get("id") or latest.get("title"))
                        last_seen_id = getattr(self, "_last_notif_id", None)
                        if last_seen_id is not None and latest_id != last_seen_id:
                            # Yeni bir bildirim geldi! Masaüstü bildirimi tetikle
                            from notification_daemon import send_system_notification
                            send_system_notification("LimeOBS — Yeni Bildirim", title)
                        self._last_notif_id = latest_id
                except Exception:
                    pass
            threading.Thread(target=check_notifs, daemon=True).start()
        except Exception:
            pass
        return True  # Zamanlayıcının çalışmaya devam etmesi için

    def update_user_header(self, name, subtitle, photo_bytes=None, school_name="Akbim OBS", academic_term="2026-2027"):
        self.user_row.set_title(name)
        self.user_row.set_subtitle(subtitle)
        self.sidebar_avatar.set_text(name if name else "K")
        if photo_bytes:
            try:
                glib_bytes = GLib.Bytes.new(photo_bytes)
                texture = Gdk.Texture.new_from_bytes(glib_bytes)
                self.sidebar_avatar.set_custom_image(texture)
            except Exception as e:
                print(f"Sidebar avatar hatası: {e}")
                self.sidebar_avatar.set_custom_image(None)
        else:
            self.sidebar_avatar.set_custom_image(None)

        # Sol alttaki okul ve eğitim dönemi bilgisi
        self.school_info_row.set_title(f"Bağlı Okul: {school_name}")
        self.school_info_row.set_subtitle(f"Eğitim Dönemi: {academic_term}")


if __name__ == "__main__":
    app = AkbimApplication()
    app.run(None)
