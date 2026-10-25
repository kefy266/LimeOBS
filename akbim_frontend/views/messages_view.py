import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_mail_content
from views.compose_mail_dialog import open_compose_message_dialog


class MessagesView(Gtk.ScrolledWindow):
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

        # Başlık ve Yeni Mesaj Butonu
        header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_label = Gtk.Label()
        header_label.set_markup("<span size='large' weight='bold'>📬 Posta Kutusu &amp; Mesajlar</span>")
        header_label.set_halign(Gtk.Align.START)
        header_label.set_hexpand(True)
        header_hbox.append(header_label)

        compose_btn = Gtk.Button(label="✏️ Yeni Mesaj Yaz")
        compose_btn.add_css_class("pill")
        compose_btn.add_css_class("suggested-action")
        compose_btn.connect("clicked", lambda _: open_compose_message_dialog(self.get_root()))
        header_hbox.append(compose_btn)

        self.main_box.append(header_hbox)

        # Mesaj Grupları Kapsayıcısı
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde MessagesView arayüzünü sıfırlar."""
        while child := self.container.get_first_child():
            self.container.remove(child)

    def load_data(self):
        def worker():
            try:
                from api_bridge import fetch_messages_data
                inbox_mails, sent_mails, counts = fetch_messages_data()
                GLib.idle_add(self.render_messages, inbox_mails, sent_mails, counts)
            except Exception as e:
                print(f"Mesaj yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def open_mail_detail(self, mail_summary, is_sent=False):
        mail_id = mail_summary.get("id")
        
        # Modal Pencere Aç
        root_window = self.get_root()
        dialog = Adw.Window()
        if root_window:
            dialog.set_transient_for(root_window)
            dialog.set_modal(True)
        
        from api_bridge import apply_theme_to_window
        apply_theme_to_window(dialog)

        dialog.set_title("Mesaj Detayı")
        dialog.set_default_size(540, 520)
        dialog.set_resizable(True)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header_bar = Adw.HeaderBar()
        sender_initial = mail_summary.get("sender") or "Okul"
        recipient_initial = mail_summary.get("recipient") or ("Alıcı Belirtilmedi" if is_sent else "Siz")
        sub_title_text = f"Alıcı: {recipient_initial}" if is_sent else f"Gönderen: {sender_initial}"
        win_title = Adw.WindowTitle(
            title=mail_summary.get("mailTitle", "Mesaj Detayı"),
            subtitle=sub_title_text
        )
        header_bar.set_title_widget(win_title)

        # Yanıtla Butonu (Sadece gelen kutusu için)
        if not is_sent:
            reply_btn = Gtk.Button(label="Yanıtla")
            reply_btn.add_css_class("pill")
            reply_btn.add_css_class("suggested-action")
            def on_reply_clicked(_):
                sender_name = mail_summary.get("sender") or ""
                u_type = mail_summary.get("userType", 3)
                u_id = mail_summary.get("userId")
                pre_rec = {
                    "nameSurname": sender_name,
                    "userType": u_type,
                    "userId": u_id,
                    "type": "Öğretmen" if u_type == 3 else "Yönetici"
                } if sender_name else None
                open_compose_message_dialog(
                    parent_window=dialog,
                    preselected_receiver=pre_rec,
                    reply_to_id=str(mail_id)
                )
            reply_btn.connect("clicked", on_reply_clicked)
            header_bar.pack_end(reply_btn)

        main_vbox.append(header_bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content_box.set_margin_top(18)
        content_box.set_margin_bottom(20)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # Bilgi Grubu
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Mesaj Bilgileri")

        # Gönderen Satırı
        sender_row = Adw.ActionRow()
        sender_row.set_title("Gönderen")
        sender_row.set_subtitle(sender_initial if not is_sent else (mail_summary.get("sender") or "Siz"))
        sender_row.set_icon_name("avatar-default-symbolic")
        info_group.add(sender_row)

        # Alıcı Satırı
        recipient_row = Adw.ActionRow()
        recipient_row.set_title("Alıcı")
        recipient_row.set_subtitle(recipient_initial if is_sent else "Siz")
        recipient_row.set_icon_name("mail-send-symbolic")
        info_group.add(recipient_row)

        # Tarih
        date_val = mail_summary.get("sendDate") or mail_summary.get("date") or "Tarih belirtilmedi"
        date_row = Adw.ActionRow()
        date_row.set_title("Tarih")
        date_row.set_subtitle(date_val)
        date_row.set_icon_name("appointment-soon-symbolic")
        info_group.add(date_row)

        content_box.append(info_group)

        # Mesaj İçeriği Grubu
        body_group = Adw.PreferencesGroup()
        body_group.set_title("İçerik")

        body_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body_card.add_css_class("card")
        body_card.set_margin_top(4)
        body_card.set_margin_bottom(4)

        # Yükleniyor / İçerik alanı
        body_label = Gtk.Label()
        body_label.set_wrap(True)
        body_label.set_selectable(True)
        body_label.set_xalign(0)
        body_label.set_margin_top(16)
        body_label.set_margin_bottom(16)
        body_label.set_margin_start(16)
        body_label.set_margin_end(16)
        
        # Önizleme başlangıç metni
        initial_text = mail_summary.get("mailPreview") or "Mesaj içeriği yükleniyor..."
        body_label.set_text(initial_text)
        body_card.append(body_label)
        body_group.add(body_card)
        content_box.append(body_group)

        # Ek dosya grubu (varsa)
        attachment_group = Adw.PreferencesGroup()
        content_box.append(attachment_group)

        scroll.set_child(content_box)
        main_vbox.append(scroll)
        dialog.set_content(main_vbox)
        dialog.present()

        # Arka planda tam içeriği ve kesin alıcı listesini çek
        def fetch_worker():
            content_data = fetch_mail_content(mail_id)
            if not content_data:
                return
            
            full_body = content_data.get("mailContent") or mail_summary.get("mailPreview", "")
            # HTML etiketlerini (<p>, <br> vb.) gerekirse temizle
            import re
            clean_body = re.sub(r'<br\s*/?>', '\n', full_body)
            clean_body = re.sub(r'<p[^>]*>', '', clean_body)
            clean_body = re.sub(r'</p>', '\n\n', clean_body)
            clean_body = re.sub(r'<[^>]+>', '', clean_body).strip()
            if not clean_body:
                clean_body = full_body

            file_name = content_data.get("fileName")
            read_date = content_data.get("readDate")
            receivers_data = content_data.get("receivers", [])
            rec_names = [r.get("receiver") for r in receivers_data if r.get("receiver")]
            receiver_text = ", ".join(rec_names) if rec_names else None

            def update_dialog():
                if clean_body:
                    body_label.set_text(clean_body)
                if read_date:
                    date_row.set_subtitle(f"{date_val} (Okunma: {read_date})")
                if is_sent and receiver_text:
                    recipient_row.set_subtitle(receiver_text)
                    win_title.set_subtitle(f"Alıcı: {receiver_text}")
                if file_name:
                    attachment_group.set_title("Ek Dosya")
                    att_row = Adw.ActionRow()
                    att_row.set_title("Ek")
                    att_row.set_subtitle(str(file_name))
                    att_row.set_icon_name("mail-attachment-symbolic")
                    attachment_group.add(att_row)

            GLib.idle_add(update_dialog)

        threading.Thread(target=fetch_worker, daemon=True).start()

    def render_messages(self, inbox_mails, sent_mails, counts):
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        # 1. GELEN KUTUSU
        inbox_group = Adw.PreferencesGroup()
        unread_count = counts.get("received", {}).get("notRead", "0")
        inbox_group.set_title(f"📥 Gelen Kutusu ({len(inbox_mails)} Mesaj" + (f", {unread_count} Okunmamış" if unread_count != "0" else "") + ")")

        if not inbox_mails:
            row = Adw.ActionRow()
            row.set_title("Gelen kutunuz boş.")
            row.set_subtitle("Okuldan henüz bir mesaj veya bildirim gönderilmemiş.")
            row.set_icon_name("mail-unread-symbolic")
            inbox_group.add(row)
        else:
            for mail in inbox_mails:
                sender = mail.get("sender", "Okul")
                title = mail.get("mailTitle", "Başlıksız")
                date = mail.get("sendDate") or mail.get("date") or ""
                preview = mail.get("mailPreview", "")
                
                subtitle_parts = [f"Gönderen: {sender}", "Alıcı: Siz"]
                if date:
                    subtitle_parts.append(f"Tarih: {date}")
                if preview:
                    short_preview = preview[:60] + ("..." if len(preview) > 60 else "")
                    subtitle_parts.append(short_preview)

                row = Adw.ActionRow()
                row.set_title(f"{title}")
                row.set_subtitle("  •  ".join(subtitle_parts))
                row.set_icon_name("mail-unread-symbolic")
                row.set_activatable(True)

                if date:
                    date_badge = Gtk.Label(label=date.split(" ")[0] if " " in date else date)
                    date_badge.add_css_class("badge-primary")
                    row.add_suffix(date_badge)

                arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
                row.add_suffix(arrow)

                # Satıra tıklandığında tam içeriği aç
                row.connect("activated", lambda _, m=mail: self.open_mail_detail(m, is_sent=False))

                inbox_group.add(row)

        self.container.append(inbox_group)

        # 2. GÖNDERİLENLER
        sent_group = Adw.PreferencesGroup()
        sent_group.set_title(f"📤 Gönderilen Postalar ({len(sent_mails)})")

        if not sent_mails:
            row = Adw.ActionRow()
            row.set_title("Gönderilen mesaj bulunmuyor.")
            row.set_icon_name("mail-send-symbolic")
            sent_group.add(row)
        else:
            for mail in sent_mails:
                title = mail.get("mailTitle", "Başlıksız")
                date = mail.get("sendDate") or mail.get("date") or ""
                preview = mail.get("mailPreview", "")
                # Başlangıçta mail nesnesinde recipient yoksa gönderen (öğrenci) adını değil Alıcı göster
                rec_val = mail.get("recipient")

                subtitle_parts = []
                if rec_val:
                    subtitle_parts.append(f"Alıcı: {rec_val}")
                subtitle_parts.append("Gönderen: Siz")
                if date:
                    subtitle_parts.append(f"Tarih: {date}")
                if preview:
                    short_preview = preview[:60] + ("..." if len(preview) > 60 else "")
                    subtitle_parts.append(short_preview)

                row = Adw.ActionRow()
                row.set_title(title)
                row.set_subtitle("  •  ".join(subtitle_parts))
                row.set_icon_name("mail-send-symbolic")
                row.set_activatable(True)

                if date:
                    date_badge = Gtk.Label(label=date.split(" ")[0] if " " in date else date)
                    date_badge.add_css_class("badge-primary")
                    row.add_suffix(date_badge)

                arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
                row.add_suffix(arrow)

                # Satıra tıklandığında tam içeriği aç
                row.connect("activated", lambda _, m=mail: self.open_mail_detail(m, is_sent=True))

                sent_group.add(row)

                # Arka planda alıcı adını çekip dinamik güncelle
                def update_sent_row_recipient(cur_row, cur_mail):
                    c_data = fetch_mail_content(cur_mail.get("id"))
                    if c_data:
                        r_list = [r.get("receiver") for r in c_data.get("receivers", []) if r.get("receiver")]
                        if r_list:
                            actual_rec = ", ".join(r_list)
                            cur_mail["recipient"] = actual_rec
                            def apply_rec_label():
                                s_parts = [f"Alıcı: {actual_rec}", "Gönderen: Siz"]
                                if cur_mail.get("sendDate"):
                                    s_parts.append(f"Tarih: {cur_mail['sendDate']}")
                                cur_p = cur_mail.get("mailPreview", "")
                                if cur_p:
                                    s_parts.append(cur_p[:60] + ("..." if len(cur_p) > 60 else ""))
                                cur_row.set_subtitle("  •  ".join(s_parts))
                            GLib.idle_add(apply_rec_label)
                threading.Thread(target=update_sent_row_recipient, args=(row, mail), daemon=True).start()

        self.container.append(sent_group)
