import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_attendance_data


class AttendanceView(Gtk.ScrolledWindow):
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
        header_label.set_markup("<span size='large' weight='bold'>📋 Devamsızlık Takip</span>")
        header_label.set_halign(Gtk.Align.START)
        self.main_box.append(header_label)

        # Kapsayıcı
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde AttendanceView arayüzünü sıfırlar."""
        while child := self.container.get_first_child():
            self.container.remove(child)

    def load_data(self):
        def worker():
            try:
                data = fetch_attendance_data()
                GLib.idle_add(self.render_attendance, data)
            except Exception as e:
                print(f"Devamsızlık yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def render_attendance(self, att_data):
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        periods = att_data.get("periods", [])
        period_title = periods[0].get("description", "").strip() if periods else "Aktif Dönem"
        absence_list = att_data.get("absence_list", [])

        # 1. GENEL DURUM ÖZETİ GRUBU
        summary_group = Adw.PreferencesGroup()
        summary_group.set_title(f"Genel Durum  •  {period_title}")

        status_row = Adw.ActionRow()
        if not absence_list:
            status_row.set_title("Devamsızlık Kaydı Bulunmuyor")
            status_row.set_subtitle("Tebrikler! Bu dönem için sisteme işlenmiş devamsızlığınız bulunmamaktadır.")
            status_row.set_icon_name("emblem-ok-symbolic")
            badge = Gtk.Label(label="Mükemmel")
            badge.add_css_class("badge-active")
            status_row.add_suffix(badge)
        else:
            status_row.set_title(f"Toplam {len(absence_list)} Ders Saati Devamsızlık")
            status_row.set_subtitle("Ders yoklaması detaylarını aşağıda görebilirsiniz.")
            status_row.set_icon_name("dialog-warning-symbolic")
            badge = Gtk.Label(label=f"{len(absence_list)} Ders")
            badge.add_css_class("badge-primary")
            status_row.add_suffix(badge)

        summary_group.add(status_row)
        self.container.append(summary_group)

        # 2. AYRINTILI DEVAMSIZLIK LİSTESİ
        list_group = Adw.PreferencesGroup()
        list_group.set_title("📅 Yoklama Kayıtları")

        if not absence_list:
            empty_row = Adw.ActionRow()
            empty_row.set_title("Kayıtlı devamsızlık yok")
            empty_row.set_subtitle("Derslerinize eksiksiz katılım sağladınız.")
            empty_row.set_icon_name("starred-symbolic")
            list_group.add(empty_row)
        else:
            for item in absence_list:
                tarih = item.get("absenceDate", "-")
                ders = item.get("lesson", "Ders")
                ders_no = item.get("lessonNo", "-")
                ogretmen = item.get("teaNameSurname", "-")
                tur = item.get("description", "Devamsız")
                not_txt = item.get("note", "")

                row = Adw.ActionRow()
                row.set_title(f"{ders}  •  {ders_no}. Ders Saati")
                sub = f"Tarih: {tarih}  •  Öğretmen: {ogretmen}" + (f"  •  Not: {not_txt}" if not_txt else "")
                row.set_subtitle(sub)
                row.set_icon_name("appointment-soon-symbolic")

                badge = Gtk.Label(label=tur)
                badge.add_css_class("badge-primary")
                row.add_suffix(badge)

                list_group.add(row)

        self.container.append(list_group)
