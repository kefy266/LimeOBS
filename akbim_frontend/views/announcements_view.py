import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import get_adaptive_index_data


class AnnouncementsView(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(900)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(20)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        header_label = Gtk.Label()
        header_label.set_markup("<span size='large' weight='bold'>📢 Okul Duyuruları &amp; Etkinlikler</span>")
        header_label.set_halign(Gtk.Align.START)
        self.main_box.append(header_label)

        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde AnnouncementsView arayüzünü sıfırlar."""
        while child := self.container.get_first_child():
            self.container.remove(child)

    def load_data(self):
        def worker():
            try:
                data = get_adaptive_index_data()
                announcements = data.get("data", {}).get("announcementList", []) or []
                events = data.get("data", {}).get("eventList", []) or []
                GLib.idle_add(self.render_data, announcements, events)
            except Exception as e:
                print(f"Duyurular yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_data(self, announcements, events):
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        # 1. DUYURULAR GRUBU
        announcements_group = Adw.PreferencesGroup()
        announcements_group.set_title("📢 Okul Duyuruları")
        announcements_group.set_description(f"Toplam {len(announcements)} Duyuru")

        if not announcements:
            row = Adw.ActionRow()
            row.set_title("Aktif duyuru bulunmuyor.")
            row.set_subtitle("Okul yönetimi tarafından henüz yeni bir duyuru yayınlanmamış.")
            row.set_icon_name("alarm-symbolic")
            announcements_group.add(row)
        else:
            for a in announcements:
                row = Adw.ActionRow()
                ann_text = str(a)
                row.set_title(ann_text[:80] + ("..." if len(ann_text) > 80 else ""))
                row.set_subtitle("Detayı okumak için tıklayın")
                row.set_icon_name("alarm-symbolic")
                row.set_activatable(True)
                row.connect("activated", lambda _, text=ann_text: self.show_announcement_dialog("Okul Duyurusu", text))
                announcements_group.add(row)

        # 2. ETKİNLİKLER GRUBU
        events_group = Adw.PreferencesGroup()
        events_group.set_title("🎯 Etkinlik Takvimi")
        events_group.set_description(f"Toplam {len(events)} Etkinlik")

        if not events:
            row = Adw.ActionRow()
            row.set_title("Aktif etkinlik bulunmuyor.")
            row.set_subtitle("Okul tarafından planlanan etkinlikler burada listelenecektir.")
            row.set_icon_name("starred-symbolic")
            events_group.add(row)
        else:
            for e in events:
                row = Adw.ActionRow()
                if isinstance(e, dict):
                    title = e.get("title", "Etkinlik")
                    date = e.get("eventDate") or e.get("date") or "-"
                    location = e.get("location", "")
                    sub = f"Tarih: {date}" + (f"  •  Yer: {location}" if location else "")
                    row.set_title(title)
                    row.set_subtitle(sub)
                    if date and date != "-":
                        badge = Gtk.Label(label=date)
                        badge.add_css_class("badge-primary")
                        row.add_suffix(badge)
                    row.set_activatable(True)
                    row.connect("activated", lambda _, t=title, d=sub: self.show_announcement_dialog(t, d))
                else:
                    ev_text = str(e)
                    row.set_title(ev_text)
                    row.set_subtitle("Etkinlik detayı için tıklayın")
                    row.set_activatable(True)
                    row.connect("activated", lambda _, text=ev_text: self.show_announcement_dialog("Etkinlik Detayı", text))
                
                row.set_icon_name("starred-symbolic")
                events_group.add(row)

        self.container.append(announcements_group)
        self.container.append(events_group)

    def show_announcement_dialog(self, title, message):
        root = self.get_root()
        alert = Adw.AlertDialog.new(title, message)
        alert.add_response("ok", "Kapat")
        alert.present(root)
