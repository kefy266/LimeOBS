import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_system_notifications


def show_notifications_popover(parent_button, on_navigate_tab=None):
    """
    Canlı sistem bildirimlerini şık bir Adw.Popover/Dialog içinde açar.
    """
    popover = Gtk.Popover()
    popover.set_parent(parent_button)
    popover.set_autohide(True)

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    main_box.set_size_request(380, 460)
    main_box.set_margin_top(12)
    main_box.set_margin_bottom(12)
    main_box.set_margin_start(12)
    main_box.set_margin_end(12)

    # Başlık
    header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    title_lbl = Gtk.Label()
    title_lbl.set_markup("<span weight='bold' size='medium'>🔔 Canlı Okul Bildirimleri</span>")
    title_lbl.set_hexpand(True)
    title_lbl.set_halign(Gtk.Align.START)
    header_box.append(title_lbl)
    main_box.append(header_box)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)

    list_box = Gtk.ListBox()
    list_box.add_css_class("boxed-list")
    list_box.set_selection_mode(Gtk.SelectionMode.NONE)

    # Yükleniyor durumu
    loading_row = Adw.ActionRow()
    loading_row.set_title("Bildirimler yükleniyor...")
    list_box.append(loading_row)

    scroll.set_child(list_box)
    main_box.append(scroll)
    popover.set_child(main_box)
    popover.popup()

    def worker():
        notifs = fetch_system_notifications()
        def update_ui():
            # Temizle
            while list_box.get_first_child():
                list_box.remove(list_box.get_first_child())

            if not notifs:
                empty_row = Adw.ActionRow()
                empty_row.set_title("Yeni bir bildiriminiz bulunmuyor")
                empty_row.set_subtitle("Tüm ödev ve okul duyuruları güncel.")
                empty_row.set_icon_name("alarm-symbolic")
                list_box.append(empty_row)
                return

            for n in notifs[:25]:
                row = Adw.ActionRow()
                t = n.get("title", "Okul Bildirimi")
                c_date = n.get("createDate", "")
                c_time = n.get("createTime", "")
                m_type = n.get("moduleType", 0)

                type_desc = "Ödev Bildirimi" if m_type == 2 else "Okul Bildirimi"

                row.set_title(t)
                row.set_subtitle(f"{type_desc}  •  {c_date} {c_time}")
                row.set_icon_name("alarm-symbolic" if m_type == 2 else "alarm-symbolic")
                row.set_activatable(True)

                if on_navigate_tab:
                    def make_click_cb(module):
                        return lambda *_: (popover.popdown(), on_navigate_tab("homework" if module == 2 else "announcements"))
                    row.connect("activated", make_click_cb(m_type))

                list_box.append(row)

        GLib.idle_add(update_ui)

    import threading
    threading.Thread(target=worker, daemon=True).start()
