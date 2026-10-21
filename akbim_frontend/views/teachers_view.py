import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_teachers_data
from views.compose_mail_dialog import open_compose_message_dialog


class TeachersView(Gtk.ScrolledWindow):
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
        header_label.set_markup("<span size='large' weight='bold'>👨‍🏫 Öğretmenlerim</span>")
        header_label.set_halign(Gtk.Align.START)
        self.main_box.append(header_label)

        # Öğretmenler Listesi
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde TeachersView arayüzünü sıfırlar."""
        while child := self.container.get_first_child():
            self.container.remove(child)

    def load_data(self):
        def worker():
            try:
                teachers = fetch_teachers_data()
                GLib.idle_add(self.render_teachers, teachers)
            except Exception as e:
                print(f"Öğretmenler yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_teachers(self, teachers):
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        group = Adw.PreferencesGroup()
        group.set_title("Ders Öğretmenleri")
        group.set_description(f"Toplam {len(teachers)} Öğretmen")

        if not teachers:
            row = Adw.ActionRow()
            row.set_title("Öğretmen bilgisi bulunamadı.")
            row.set_icon_name("avatar-default-symbolic")
            group.add(row)
        else:
            for t in teachers:
                name = t.get("teaNameSurname", "-")
                lesson = t.get("lesson", "Ders")

                row = Adw.ActionRow()
                row.set_title(name)
                row.set_subtitle(f"Branş: {lesson}")
                row.set_icon_name("avatar-default-symbolic")

                # Rozet (Branş)
                badge = Gtk.Label(label=lesson)
                badge.add_css_class("badge-primary")
                row.add_suffix(badge)

                # Mesaj Gönder Butonu
                msg_btn = Gtk.Button(label="✉️ Mesaj")
                msg_btn.add_css_class("pill")
                msg_btn.add_css_class("suggested-action")
                msg_btn.set_tooltip_text(f"{name} öğretmenine mesaj gönder")
                def on_msg_clicked(_, teacher_data=t):
                    open_compose_message_dialog(
                        parent_window=self.get_root(),
                        preselected_receiver={
                            "nameSurname": teacher_data.get("teaNameSurname", ""),
                            "type": "Öğretmen",
                            "userType": 3
                        }
                    )
                msg_btn.connect("clicked", on_msg_clicked)
                row.add_suffix(msg_btn)

                group.add(row)

        self.container.append(group)

