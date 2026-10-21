import os
import subprocess
import tempfile
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from api_bridge import apply_theme_to_window, open_file_external


class PdfViewerDialog(Adw.Window):
    """
    LimeOBS Dahili PDF Görüntüleyici ve Yazdırıcı
    Doğrudan PNG rasterizer ile hatasız render, yakınlaştırma (Zoom),
    sistemde açma ve doğrudan yazdırma (Print) desteği sunar.
    Popup açıldığında aktif tema (Liquid Glass / Light / Dark) otomatik uygulanır.
    """
    def __init__(self, parent_window, pdf_path_or_bytes, title="PDF Görüntüleyici"):
        super().__init__()
        if parent_window:
            self.set_transient_for(parent_window)
            self.set_modal(True)

        # Aktif temayı popup penceresine de uygula
        apply_theme_to_window(self)

        self.set_title(title)
        self.set_default_size(880, 820)

        self.temp_file_path = None
        self.page_image_paths = []
        self.current_page_idx = 0
        self.total_pages = 0
        self.zoom_level = 1.0

        # Dokümanı diske ve sayfa resimlerine hazırla
        self.prepare_pdf(pdf_path_or_bytes)

        # Arayüzü inşa et
        self.build_ui(title)

    def prepare_pdf(self, source):
        try:
            if isinstance(source, (bytes, bytearray)):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.write(source)
                tmp.close()
                self.temp_file_path = tmp.name
            else:
                self.temp_file_path = str(source)

            # Sayfa resimlerini pdftoppm ile dönüştür (150 DPI yüksek kalite)
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                out_prefix = os.path.join(tempfile.gettempdir(), f"limeobs_pdf_{os.getpid()}_{self.current_page_idx}")
                cmd = ["pdftoppm", "-png", "-r", "150", self.temp_file_path, out_prefix]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Üretilen PNG dosyalarını sırayla bul
                dir_path = tempfile.gettempdir()
                base_name = os.path.basename(out_prefix)
                found = []
                for fname in sorted(os.listdir(dir_path)):
                    if fname.startswith(base_name) and fname.endswith(".png"):
                        found.append(os.path.join(dir_path, fname))

                self.page_image_paths = sorted(found)
                self.total_pages = len(self.page_image_paths)
        except Exception as e:
            print(f"PDF hazırlama hatası: {e}")
            self.page_image_paths = []
            self.total_pages = 0

    def build_ui(self, title):
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # 1. HeaderBar
        header = Adw.HeaderBar()
        self.title_widget = Adw.WindowTitle(
            title=title,
            subtitle=f"Sayfa {self.current_page_idx + 1} / {max(1, self.total_pages)}" if self.total_pages > 0 else "Hata"
        )
        header.set_title_widget(self.title_widget)

        # Sayfa Gezinme Butonları (Önceki / Sonraki)
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.prev_btn = Gtk.Button(icon_name="go-previous-symbolic")
        self.prev_btn.set_tooltip_text("Önceki Sayfa")
        self.prev_btn.connect("clicked", lambda _: self.change_page(-1))
        nav_box.append(self.prev_btn)

        self.page_label = Gtk.Label(label=f"{self.current_page_idx + 1} / {max(1, self.total_pages)}")
        self.page_label.add_css_class("numeric")
        self.page_label.set_margin_start(4)
        self.page_label.set_margin_end(4)
        nav_box.append(self.page_label)

        self.next_btn = Gtk.Button(icon_name="go-next-symbolic")
        self.next_btn.set_tooltip_text("Sonraki Sayfa")
        self.next_btn.connect("clicked", lambda _: self.change_page(1))
        nav_box.append(self.next_btn)

        header.pack_start(nav_box)

        # Araçlar: Yazdır, Zoom & Sistemde Aç Butonları
        tools_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # 🖨️ Doğrudan Yazdırma Butonu
        print_btn = Gtk.Button(icon_name="printer-symbolic")
        print_btn.set_tooltip_text("Yazıcıya Gönder (Yazdır)")
        print_btn.connect("clicked", lambda _: self.print_pdf())
        tools_box.append(print_btn)

        zoom_out_btn = Gtk.Button(icon_name="zoom-out-symbolic")
        zoom_out_btn.set_tooltip_text("Uzaklaştır")
        zoom_out_btn.connect("clicked", lambda _: self.change_zoom(-0.2))
        tools_box.append(zoom_out_btn)

        zoom_in_btn = Gtk.Button(icon_name="zoom-in-symbolic")
        zoom_in_btn.set_tooltip_text("Yakınlaştır")
        zoom_in_btn.connect("clicked", lambda _: self.change_zoom(0.2))
        tools_box.append(zoom_in_btn)

        if self.temp_file_path:
            open_ext_btn = Gtk.Button(icon_name="document-open-symbolic")
            open_ext_btn.set_tooltip_text("Sistem PDF Uygulamasında Aç")
            open_ext_btn.connect("clicked", lambda _: open_file_external(self.temp_file_path))
            tools_box.append(open_ext_btn)

        header.pack_end(tools_box)
        main_vbox.append(header)

        # 2. Kaydırılabilir Sayfa Alanı
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_vexpand(True)
        self.scroll.set_hexpand(True)

        self.image_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.image_container.set_halign(Gtk.Align.CENTER)
        self.image_container.set_valign(Gtk.Align.CENTER)
        self.image_container.set_margin_top(16)
        self.image_container.set_margin_bottom(16)
        self.image_container.set_margin_start(16)
        self.image_container.set_margin_end(16)

        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
        self.picture.add_css_class("card")
        self.image_container.append(self.picture)

        self.scroll.set_child(self.image_container)
        main_vbox.append(self.scroll)

        self.set_content(main_vbox)
        self.update_page_ui()

    def change_page(self, delta):
        if self.total_pages == 0:
            return
        new_page = self.current_page_idx + delta
        if 0 <= new_page < self.total_pages:
            self.current_page_idx = new_page
            self.update_page_ui()

    def change_zoom(self, delta):
        self.zoom_level = max(0.6, min(2.5, self.zoom_level + delta))
        self.update_page_ui()

    def update_page_ui(self):
        if self.total_pages == 0 or not self.page_image_paths:
            self.prev_btn.set_sensitive(False)
            self.next_btn.set_sensitive(False)
            self.page_label.set_text("0 / 0")
            return

        self.prev_btn.set_sensitive(self.current_page_idx > 0)
        self.next_btn.set_sensitive(self.current_page_idx < self.total_pages - 1)
        self.page_label.set_text(f"{self.current_page_idx + 1} / {self.total_pages}")
        self.title_widget.set_subtitle(f"Sayfa {self.current_page_idx + 1} / {self.total_pages} (%{int(self.zoom_level * 100)})")

        img_path = self.page_image_paths[self.current_page_idx]
        if os.path.exists(img_path):
            try:
                texture = Gdk.Texture.new_from_filename(img_path)
                self.picture.set_paintable(texture)
                orig_w = texture.get_width()
                orig_h = texture.get_height()
                self.picture.set_size_request(int(orig_w * self.zoom_level * 0.65), int(orig_h * self.zoom_level * 0.65))
            except Exception as e:
                print(f"Texture yükleme hatası: {e}")

    def print_pdf(self):
        """PDF dosyasını sistem yazıcısına gönderir."""
        if not self.temp_file_path or not os.path.exists(self.temp_file_path):
            return

        try:
            # 1. lp komutu varsa doğrudan yazıcıya gönder
            subprocess.run(["lp", self.temp_file_path], check=True)
            print("Yazıcıya gönderildi:", self.temp_file_path)
        except Exception:
            try:
                # 2. Alternatif: Sistem yazdırma aracıyla aç
                subprocess.Popen(["xdg-open", self.temp_file_path])
            except Exception as err:
                print(f"Yazdırma hatası: {err}")


def open_pdf_viewer(parent_window, pdf_path_or_bytes, title="PDF Görüntüleyici"):
    """Dahili PDF Görüntüleyicisini modal olarak açar."""
    viewer = PdfViewerDialog(parent_window, pdf_path_or_bytes, title)
    viewer.present()
    return viewer
