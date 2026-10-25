import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_borrowed_books, search_library_books


class LibraryView(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)
        clamp.set_tightening_threshold(650)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(24)
        self.main_box.set_margin_bottom(28)
        self.main_box.set_margin_start(20)
        self.main_box.set_margin_end(20)

        # Başlık ve Yenile Butonu
        header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)

        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='x-large' weight='bold'>📖 Okul Kütüphanesi</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)

        sub_lbl = Gtk.Label()
        sub_lbl.set_markup("<span size='small' foreground='#b8b8b8'>Ödünç aldığınız kitaplar ve okul kitap kataloğu</span>")
        sub_lbl.set_halign(Gtk.Align.START)
        title_box.append(sub_lbl)

        header_hbox.append(title_box)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Kütüphaneyi Yenile")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_hbox.append(refresh_btn)

        self.main_box.append(header_hbox)

        # 1. Ödünç Kitaplar Grubu Kapsayıcısı
        self.borrowed_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.borrowed_container)

        # 2. Kitap Kataloğunda Arama Grubu
        self.search_group = Adw.PreferencesGroup()
        self.search_group.set_title("🔍 Kütüphane Kataloğu Arama")
        self.search_group.set_description("Okul kütüphanesindeki kitapları arayın")

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Kitap adı veya yazar adı ile arayın...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_group.add(self.search_entry)

        self.main_box.append(self.search_group)

        # Arama Sonuçları Kapsayıcısı
        self.results_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.results_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde LibraryView arayüzünü sıfırlar."""
        while child := self.borrowed_container.get_first_child():
            self.borrowed_container.remove(child)
        while child := self.results_container.get_first_child():
            self.results_container.remove(child)
        self.search_entry.set_text("")

    def load_data(self):
        def worker():
            try:
                books = fetch_borrowed_books()
                GLib.idle_add(self.render_borrowed_books, books)
            except Exception as e:
                print(f"LibraryView load error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_borrowed_books(self, books):
        while self.borrowed_container.get_first_child():
            self.borrowed_container.remove(self.borrowed_container.get_first_child())

        borrowed_group = Adw.PreferencesGroup()
        borrowed_group.set_title("📚 Ödünç Aldığım Kitaplar")
        borrowed_group.set_description("Şu anda sizde bulunan veya teslim geçmişinizdeki kitaplar")

        if not books:
            empty_row = Adw.ActionRow()
            empty_row.set_title("Şu anda ödünç aldığınız bir kitap bulunmuyor")
            empty_row.set_subtitle("Okul kütüphanesinden kitap aldığınızda burada listelenecektir.")
            empty_row.set_icon_name("starred-symbolic")
            borrowed_group.add(empty_row)
        else:
            for b in books:
                row = Adw.ActionRow()
                b_name = b.get("bookName") or b.get("name", "Kitap")
                author = b.get("author", "Bilinmeyen Yazar")
                b_date = b.get("borrowDate", "-")
                r_date = b.get("returnDate", "Teslim Edilmedi")

                row.set_title(b_name)
                row.set_subtitle(f"Yazar: {author}  •  Alış: {b_date}  •  Teslim: {r_date}")
                row.set_icon_name("x-office-document-symbolic")

                is_returned = b.get("isReturned", False)
                badge = Gtk.Label(label="Teslim Edildi" if is_returned else "Ödünçte")
                badge.add_css_class("badge-primary" if is_returned else "badge-active")
                row.add_suffix(badge)
                borrowed_group.add(row)

        self.borrowed_container.append(borrowed_group)

    def on_search_changed(self, entry):
        query = entry.get_text().strip()
        if len(query) < 2:
            while self.results_container.get_first_child():
                self.results_container.remove(self.results_container.get_first_child())
            return

        def search_worker():
            results = search_library_books(query)
            def update_ui():
                while self.results_container.get_first_child():
                    self.results_container.remove(self.results_container.get_first_child())

                res_group = Adw.PreferencesGroup()
                res_group.set_title("Arama Sonuçları")

                if not results:
                    r_empty = Adw.ActionRow()
                    r_empty.set_title("Aramanıza uygun kitap bulunamadı.")
                    r_empty.set_icon_name("system-search-symbolic")
                    res_group.add(r_empty)
                else:
                    for it in results[:15]:
                        row = Adw.ActionRow()
                        row.set_title(it.get("bookName") or it.get("name", "Kitap"))
                        row.set_subtitle(f"Yazar: {it.get('author', '-')}  •  Raf: {it.get('shelf', '-')}")
                        row.set_icon_name("x-office-document-symbolic")
                        res_group.add(row)

                self.results_container.append(res_group)

            GLib.idle_add(update_ui)

        threading.Thread(target=search_worker, daemon=True).start()
