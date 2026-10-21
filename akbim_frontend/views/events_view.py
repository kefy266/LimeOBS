import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_events_data


class EventsView(Gtk.ScrolledWindow):
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

        # Üst Başlık
        header_label = Gtk.Label()
        header_label.set_markup("<span size='large' weight='bold'>🎯 Okul Etkinlikleri</span>")
        header_label.set_halign(Gtk.Align.START)
        self.main_box.append(header_label)

        # Etkinlikler Listesi
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def load_data(self):
        def worker():
            try:
                events = fetch_events_data()
                GLib.idle_add(self.render_events, events)
            except Exception as e:
                print(f"Etkinlikler yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_events(self, events):
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        group = Adw.PreferencesGroup()
        group.set_title("Planlanan ve Gerçekleşen Etkinlikler")
        group.set_description(f"Toplam {len(events)} Etkinlik")

        if not events:
            row = Adw.ActionRow()
            row.set_title("Kayıtlı okul etkinliği bulunmuyor.")
            row.set_subtitle("Okul tarafından planlanan etkinlikler burada listelenecektir.")
            row.set_icon_name("weather-clear-symbolic")
            group.add(row)
        else:
            for ev in events:
                title = ev.get("title", "Etkinlik")
                date = ev.get("eventDate") or ev.get("date") or "-"
                location = ev.get("location", "")

                row = Adw.ActionRow()
                row.set_title(title)
                sub = f"Tarih: {date}" + (f"  •  Yer: {location}" if location else "")
                row.set_subtitle(sub)
                row.set_icon_name("starred-symbolic")

                if date and date != "-":
                    date_badge = Gtk.Label(label=date)
                    date_badge.add_css_class("badge-primary")
                    row.add_suffix(date_badge)

                group.add(row)

        self.container.append(group)
