import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import search_mail_receivers, send_mail_message


def open_compose_message_dialog(parent_window, preselected_receiver=None, reply_to_id=""):
    """
    Yeni mesaj gönderme modal penceresini açar.
    preselected_receiver: dict (örn: {'nameSurname': 'ALEV KORKMAZ', 'userType': 3, 'userId': 785}) veya None
    reply_to_id: string (cevaplanan mail id'si)
    """
    dialog = Adw.Window()
    if parent_window:
        dialog.set_transient_for(parent_window)
        dialog.set_modal(True)

    from api_bridge import apply_theme_to_window
    apply_theme_to_window(dialog)

    dialog.set_title("Yeni Mesaj Gönder" if not reply_to_id else "Mesajı Yanıtla")
    dialog.set_default_size(560, 520)
    dialog.set_resizable(True)

    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    # HeaderBar
    header_bar = Adw.HeaderBar()
    win_title = Adw.WindowTitle(
        title="Yeni Mesaj Gönder" if not reply_to_id else "Mesajı Yanıtla",
        subtitle="Öğretmen veya Okul İdaresine İlet"
    )
    header_bar.set_title_widget(win_title)
    main_box.append(header_bar)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    content_box.set_margin_top(16)
    content_box.set_margin_bottom(16)
    content_box.set_margin_start(18)
    content_box.set_margin_end(18)

    # 1. Alıcı Grubu
    receiver_group = Adw.PreferencesGroup()
    receiver_group.set_title("Alıcı Bilgisi")
    receiver_group.set_description("Mesaj göndermek istediğiniz öğretmeni veya yöneticiyi seçin.")

    # Alıcı Durum / Seçim Kartı
    active_receiver = {"data": preselected_receiver}

    selected_row = Adw.ActionRow()
    if preselected_receiver:
        r_name = preselected_receiver.get("nameSurname") or preselected_receiver.get("teaNameSurname", "Öğretmen")
        r_type = preselected_receiver.get("type", "Öğretmen")
        selected_row.set_title(r_name)
        selected_row.set_subtitle(f"Alıcı: {r_type}")
    else:
        selected_row.set_title("Henüz alıcı seçilmedi")
        selected_row.set_subtitle("Aşağıdaki arama çubuğunu kullanarak öğretmen bulunuz.")
    selected_row.set_icon_name("avatar-default-symbolic")
    receiver_group.add(selected_row)

    # Alıcı Arama Çubuğu ve Sonuç Listesi (Eğer alıcı önceden seçilmemişse)
    search_entry = Gtk.SearchEntry()
    search_entry.set_placeholder_text("Öğretmen veya idareci adı yazın (en az 2 harf)...")
    search_entry.set_margin_top(6)
    search_entry.set_margin_bottom(4)

    search_results_group = Adw.PreferencesGroup()
    search_results_group.set_title("Arama Sonuçları")
    search_results_group.set_visible(False)

    def on_search_changed(entry):
        query = entry.get_text().strip()
        if len(query) < 2:
            search_results_group.set_visible(False)
            return

        def do_search():
            results = search_mail_receivers(query)
            def update_ui():
                # Önceki sonuçları temizle
                # Adw.PreferencesGroup içinde doğrudan remove olmayabilir, grup yeniden oluşturulur
                search_results_group.set_visible(True)
                if not results:
                    empty_row = Adw.ActionRow()
                    empty_row.set_title("Sonuç bulunamadı.")
                    empty_row.set_icon_name("system-search-symbolic")
                    # Clear items logic
                else:
                    pass
            GLib.idle_add(update_ui)

    receiver_group.add(search_entry)
    content_box.append(receiver_group)

    # Otomatik Tamamlama / Seçim İçin Dropdown veya Arama Listesi
    results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    content_box.append(results_box)

    def select_person(person):
        active_receiver["data"] = person
        p_name = person.get("nameSurname") or person.get("teaNameSurname", "")
        p_type = person.get("type", "Öğretmen")
        selected_row.set_title(p_name)
        selected_row.set_subtitle(f"Seçilen Alıcı: {p_type}")
        # Sonuç kutusunu temizle
        while results_box.get_first_child():
            results_box.remove(results_box.get_first_child())

    def perform_search(text):
        q = text.strip()
        if len(q) < 2:
            while results_box.get_first_child():
                results_box.remove(results_box.get_first_child())
            return
        
        def worker():
            res = search_mail_receivers(q)
            def render_res():
                while results_box.get_first_child():
                    results_box.remove(results_box.get_first_child())
                if not res:
                    no_lbl = Gtk.Label(label="Eşleşen öğretmen veya yönetici bulunamadı.")
                    no_lbl.add_css_class("dim-label")
                    no_lbl.set_halign(Gtk.Align.START)
                    results_box.append(no_lbl)
                    return
                for item in res:
                    item_btn = Gtk.Button()
                    item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    item_box.set_margin_start(10)
                    item_box.set_margin_end(10)
                    item_box.set_margin_top(6)
                    item_box.set_margin_bottom(6)
                    
                    icon = Gtk.Image.new_from_icon_name("avatar-default-symbolic")
                    lbl = Gtk.Label(label=f"{item.get('nameSurname', '')} ({item.get('type', '')})")
                    lbl.set_halign(Gtk.Align.START)
                    lbl.set_hexpand(True)
                    
                    item_box.append(icon)
                    item_box.append(lbl)
                    item_btn.set_child(item_box)
                    item_btn.add_css_class("flat")
                    item_btn.connect("clicked", lambda _, p=item: select_person(p))
                    results_box.append(item_btn)
            GLib.idle_add(render_res)
        threading.Thread(target=worker, daemon=True).start()

    search_entry.connect("search-changed", lambda e: perform_search(e.get_text()))

    # Eğer alıcı önceden tanımlıysa arama kutusunu gizle/küçült
    if preselected_receiver:
        search_entry.set_visible(False)
        change_btn = Gtk.Button(label="Değiştir")
        change_btn.add_css_class("pill")
        change_btn.connect("clicked", lambda _: search_entry.set_visible(True))
        selected_row.add_suffix(change_btn)

    # 2. Mesaj Formu
    form_group = Adw.PreferencesGroup()
    form_group.set_title("Mesaj Detayları")

    # Başlık Satırı
    title_entry = Adw.EntryRow()
    title_entry.set_title("Mesaj Başlığı")
    title_entry.set_text("Ödev ve Ders Hakkında" if not reply_to_id else "Re: Mesaj Yanıtı")
    form_group.add(title_entry)

    # Mesaj Metni Satırı (Girişteki T.C. Kimlik / Şifre inputları gibi Adw.EntryRow)
    content_entry = Adw.EntryRow()
    content_entry.set_title("Mesaj Metni")
    content_entry.set_show_apply_button(False)
    form_group.add(content_entry)

    content_box.append(form_group)

    # Durum / Uyarı Etiketi
    status_label = Gtk.Label()
    status_label.set_wrap(True)
    status_label.set_halign(Gtk.Align.CENTER)
    content_box.append(status_label)

    # 3. Alt Butonlar (Gönder / İptal)
    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    button_box.set_halign(Gtk.Align.END)
    button_box.set_margin_top(10)

    cancel_btn = Gtk.Button(label="Vazgeç")
    cancel_btn.add_css_class("pill")
    cancel_btn.connect("clicked", lambda _: dialog.close())

    send_btn = Gtk.Button(label="✉️ Gönder")
    send_btn.add_css_class("pill")
    send_btn.add_css_class("suggested-action")

    def on_send_clicked(_):
        rec = active_receiver.get("data")
        if not rec:
            status_label.set_markup("<span color='#e01b24'>Lütfen önce bir öğretmen veya alıcı seçin!</span>")
            return

        m_title = title_entry.get_text().strip()
        m_content = content_entry.get_text().strip()

        if len(m_title) < 5:
            status_label.set_markup("<span color='#e01b24'>Başlık en az 5 karakter olmalıdır.</span>")
            return
        if len(m_content) < 10:
            status_label.set_markup("<span color='#e01b24'>Mesaj içeriği en az 10 karakter olmalıdır.</span>")
            return

        # userType ve userId çöz ve doğrula
        u_type = rec.get("userType")
        u_id = rec.get("userId")

        if (not u_id or not u_type) and "id" in rec:
            raw_id = str(rec["id"])
            if len(raw_id) > 1:
                u_type = int(raw_id[0])
                u_id = int(raw_id[1:])
            else:
                u_id = int(raw_id)

        if not u_type:
            r_type_str = str(rec.get("type", "")).lower()
            u_type = 4 if "yönetici" in r_type_str or "idare" in r_type_str else 3

        if not u_id:
            status_label.set_markup("<span color='#e01b24'>Seçilen alıcının kimlik numarası (ID) eksik. Lütfen listeden tekrar seçin.</span>")
            return

        # reply_to_id sayısal değilse veya boşsa boş string yap
        safe_reply_id = str(reply_to_id).strip() if reply_to_id and str(reply_to_id).isdigit() else ""

        send_btn.set_sensitive(False)
        cancel_btn.set_sensitive(False)
        status_label.set_markup("<span color='#3584e4'>Mesaj gönderiliyor...</span>")

        def send_worker():
            res = send_mail_message(
                title=m_title,
                content=m_content,
                receiver_user_type=u_type,
                receiver_user_id=u_id,
                reply_id=safe_reply_id
            )

            def finish_ui():
                send_btn.set_sensitive(True)
                cancel_btn.set_sensitive(True)
                if res.get("success"):
                    msg_text = res.get("data", {}).get("msg", "Mesajınız başarıyla iletildi.")
                    alert = Adw.AlertDialog.new("Başarılı", msg_text)
                    alert.add_response("ok", "Tamam")
                    alert.connect("response", lambda *_: dialog.close())
                    alert.present(dialog)
                else:
                    err_text = res.get("data", {}).get("msg") or res.get("msg") or "Mesaj gönderilemedi."
                    status_label.set_markup(f"<span color='#e01b24'>{err_text}</span>")

            GLib.idle_add(finish_ui)

        threading.Thread(target=send_worker, daemon=True).start()

    send_btn.connect("clicked", on_send_clicked)

    button_box.append(cancel_btn)
    button_box.append(send_btn)
    content_box.append(button_box)

    scroll.set_child(content_box)
    main_box.append(scroll)
    dialog.set_content(main_box)
    dialog.present()
