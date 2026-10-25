import threading
import tempfile
from pathlib import Path
from datetime import datetime
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import (
    fetch_homeworks_list,
    fetch_homework_detail,
    download_homework_attachment,
    open_file_external,
    apply_theme_to_window,
)
from views.pdf_viewer_dialog import open_pdf_viewer


class HomeworkView(Gtk.ScrolledWindow):
    """
    Ödev & Görev Listesi Görünümü
    Açıklamaları, ek dosyaları (PDF/Word), cevap anahtarlarını ve öğretmen notlarını
    doğrudan kartlar üzerinde ve detay modalında zengin bir şekilde görüntüler.
    """
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(960)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        # Başlık ve Yenileme Butonu
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header_label = Gtk.Label()
        header_label.set_markup("<span size='x-large' weight='bold'>📚 Ödevlerim &amp; Görevler</span>")
        header_label.set_halign(Gtk.Align.START)
        title_box.append(header_label)

        sub_label = Gtk.Label()
        sub_label.set_markup("<span size='small' foreground='#a8a8a8'>Öğretmen açıklamaları, ek belgeler ve teslim takvimi</span>")
        sub_label.set_halign(Gtk.Align.START)
        title_box.append(sub_label)
        title_box.set_hexpand(True)
        header_box.append(title_box)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Ödevleri Yenile")
        refresh_btn.connect("clicked", lambda _: self.load_data())
        header_box.append(refresh_btn)

        self.main_box.append(header_box)

        # Filtre Seçim Butonları (Tümü / Bekleyenler / Tamamlananlar)
        self.filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.filter_box.add_css_class("segmented-bar")
        self.main_box.append(self.filter_box)

        self.current_filter = "all"  # "all", "active", "completed"
        self._cached_homeworks = []
        self._cached_details = {}  # hw_id -> detail_dict
        self._card_dynamic_boxes = {}  # hw_id -> Gtk.Box

        # Ödev Listesi Kapsayıcısı
        self.container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box.append(self.container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde HomeworkView önbelleğini ve arayüzünü sıfırlar."""
        self._cached_homeworks = []
        self._cached_details.clear()
        self._card_dynamic_boxes.clear()
        self.current_filter = "all"
        while child := self.filter_box.get_first_child():
            self.filter_box.remove(child)
        while child := self.container.get_first_child():
            self.container.remove(child)

    def load_data(self):
        def worker():
            try:
                homeworks = fetch_homeworks_list()
                GLib.idle_add(self.set_homeworks_data, homeworks)
            except Exception as e:
                print(f"Ödevler yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def set_homeworks_data(self, homework_list):
        self._cached_homeworks = homework_list or []
        self.build_filter_buttons()
        self.render_filtered_homeworks()
        self._start_details_prefetch()

    def _start_details_prefetch(self):
        """Tüm ödevlerin açıklama ve ek dosyalarını arka planda çeker ve kartlara anında yansıtır."""
        def prefetch_worker():
            # Önce aktif ödevleri, sonra geçmiş ödevleri çek
            active_hws = [h for h in self._cached_homeworks if h.get("isActive", False)]
            other_hws = [h for h in self._cached_homeworks if not h.get("isActive", False)]
            ordered = active_hws + other_hws

            for hw in ordered:
                hw_id = hw.get("id")
                if not hw_id or hw_id in self._cached_details:
                    continue
                try:
                    detail = fetch_homework_detail(hw_id)
                    if detail:
                        self._cached_details[hw_id] = detail
                        GLib.idle_add(self._update_card_with_detail, hw_id, detail)
                except Exception as e:
                    print(f"Ödev detay arka plan çekme hatası ({hw_id}): {e}")

        threading.Thread(target=prefetch_worker, daemon=True).start()

    def build_filter_buttons(self):
        while self.filter_box.get_first_child():
            self.filter_box.remove(self.filter_box.get_first_child())

        total = len(self._cached_homeworks)
        active_count = sum(1 for hw in self._cached_homeworks if hw.get("isActive", False))
        completed_count = total - active_count

        btn_all = Gtk.Button(label=f"Tümü ({total})")
        if self.current_filter == "all":
            btn_all.add_css_class("suggested-action")
        btn_all.connect("clicked", lambda _: self.on_filter_changed("all"))
        self.filter_box.append(btn_all)

        btn_active = Gtk.Button(label=f"⏳ Bekleyen ({active_count})")
        if self.current_filter == "active":
            btn_active.add_css_class("suggested-action")
        btn_active.connect("clicked", lambda _: self.on_filter_changed("active"))
        self.filter_box.append(btn_active)

        btn_comp = Gtk.Button(label=f"✅ Tamamlanan ({completed_count})")
        if self.current_filter == "completed":
            btn_comp.add_css_class("suggested-action")
        btn_comp.connect("clicked", lambda _: self.on_filter_changed("completed"))
        self.filter_box.append(btn_comp)

    def on_filter_changed(self, new_filter):
        self.current_filter = new_filter
        self.build_filter_buttons()
        self.render_filtered_homeworks()

    def render_filtered_homeworks(self):
        while self.container.get_first_child():
            self.container.remove(self.container.get_first_child())

        self._card_dynamic_boxes.clear()
        now = datetime.now()

        # 1. AKTİF / DEVAM EDEN ÖDEVLER
        active_group = Adw.PreferencesGroup()
        active_group.set_title("📌 Devam Eden Ödevler")
        active_group.set_description("Teslim süresi devam eden veya değerlendirme bekleyen ödevler")

        # 2. TAMAMLANAN VEYA GEÇMİŞ ÖDEVLER
        completed_group = Adw.PreferencesGroup()
        completed_group.set_title("✅ Geçmiş &amp; Tamamlanan Ödevler")

        active_count = 0
        completed_count = 0

        if not self._cached_homeworks:
            empty_row = Adw.ActionRow()
            empty_row.set_title("Henüz verilmiş bir ödev bulunmuyor.")
            empty_row.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))
            active_group.add(empty_row)
            self.container.append(active_group)
            return

        for hw in self._cached_homeworks:
            hw_id = hw.get("id")
            title = hw.get("title", "Başlıksız Ödev").strip()
            lesson = hw.get("lesson", "Ders").strip()
            teacher = hw.get("teaNameSurname", "").strip()
            end_date = hw.get("endDate", "").strip()
            status_name = hw.get("statusName", "Belirtilmedi").strip()
            is_active = hw.get("isActive", False)
            status_code = hw.get("status", 0)
            attach_count = hw.get("attachFileCount", 0)
            has_attach = hw.get("hasAttachFile", False)
            has_answer = hw.get("hasAnswerFile", False)
            answer_count = int(hw.get("answerFileCount", 0) or 0)

            # Filtreleme
            if self.current_filter == "active" and not is_active:
                continue
            if self.current_filter == "completed" and is_active:
                continue

            # Ana Kart
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            card.add_css_class("homework-card")
            card.set_hexpand(True)

            # 1. Satır: Ders Rozeti + Ek Dosya Rozeti + Kalan Gün + Durum Rozeti
            top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            
            lesson_badge = Gtk.Label()
            lesson_badge.set_markup(f"<span weight='bold' size='small' foreground='#3b82f6'>📖 {lesson}</span>")
            lesson_badge.set_halign(Gtk.Align.START)
            lesson_badge.set_hexpand(True)
            top_bar.append(lesson_badge)

            # Ek dosya rozeti
            if attach_count > 0 or has_attach:
                cnt = attach_count if attach_count > 0 else 1
                att_badge = Gtk.Label(label=f"📎 {cnt} Ek Dosya")
                att_badge.add_css_class("badge-primary")
                top_bar.append(att_badge)

            # Cevap anahtarı rozeti
            if has_answer or answer_count > 0:
                ans_badge = Gtk.Label(label="🔑 Çözüm Dosyası")
                ans_badge.add_css_class("badge-success")
                top_bar.append(ans_badge)

            # Kalan gün hesabı
            if is_active and end_date:
                try:
                    target_dt = None
                    if "." in end_date:
                        target_dt = datetime.strptime(end_date.split()[0], "%d.%m.%Y")
                    elif "-" in end_date:
                        target_dt = datetime.strptime(end_date.split()[0], "%Y-%m-%d")
                    if target_dt:
                        diff_days = (target_dt.date() - now.date()).days
                        days_badge = Gtk.Label()
                        if diff_days < 0:
                            days_badge.set_text("Süresi Doldu")
                            days_badge.add_css_class("badge-failed")
                        elif diff_days == 0:
                            days_badge.set_text("Bugün Son!")
                            days_badge.add_css_class("badge-primary")
                        elif diff_days == 1:
                            days_badge.set_text("Yarın Son")
                            days_badge.add_css_class("badge-upcoming")
                        else:
                            days_badge.set_text(f"{diff_days} gün kaldı")
                            days_badge.add_css_class("badge-upcoming")
                        top_bar.append(days_badge)
                except Exception:
                    pass

            # Durum rozeti
            status_badge = Gtk.Label(label=status_name)
            s_lower = status_name.lower()
            if "yapıldı" in s_lower or "tamamlandı" in s_lower or status_code == 1:
                status_badge.add_css_class("badge-hw-completed")
            elif "eksik" in s_lower:
                status_badge.add_css_class("badge-hw-incomplete")
            elif "yapılmadı" in s_lower or status_code == 3:
                status_badge.add_css_class("badge-hw-missing")
            else:
                status_badge.add_css_class("badge-hw-unevaluated")
            top_bar.append(status_badge)

            card.append(top_bar)

            # 2. Satır: Ödev Başlığı
            title_lbl = Gtk.Label()
            title_lbl.set_markup(f"<span weight='bold' size='medium'>{title}</span>")
            title_lbl.set_halign(Gtk.Align.START)
            title_lbl.set_wrap(True)
            title_lbl.set_wrap_mode(2)  # PANGO_WRAP_WORD_CHAR
            card.append(title_lbl)

            # 3. Satır: Dinamik Açıklama ve Ekler Kutusu
            dynamic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self._card_dynamic_boxes[hw_id] = dynamic_box
            card.append(dynamic_box)

            # Eğer detay önbellekte zaten varsa hemen çiz, yoksa yükleniyor göster
            if hw_id in self._cached_details:
                self._populate_dynamic_detail(dynamic_box, hw_id, self._cached_details[hw_id])
            else:
                loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                loading_lbl = Gtk.Label()
                loading_lbl.set_markup("<span size='small' foreground='#a8a8a8'><i>Açıklama ve ek belgeler yükleniyor...</i></span>")
                loading_lbl.set_halign(Gtk.Align.START)
                loading_box.append(loading_lbl)
                dynamic_box.append(loading_box)

            # 4. Satır: Öğretmen, Tarihler ve Detay Butonu
            bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            meta_box.set_hexpand(True)

            if teacher:
                tea_lbl = Gtk.Label()
                tea_lbl.set_markup(f"<span size='small' foreground='#b8b8b8'>👤 {teacher}</span>")
                tea_lbl.set_halign(Gtk.Align.START)
                meta_box.append(tea_lbl)

            if end_date:
                date_lbl = Gtk.Label()
                date_lbl.set_markup(f"<span size='small' foreground='#a8a8a8'>📅 Son: {end_date}</span>")
                date_lbl.set_halign(Gtk.Align.START)
                meta_box.append(date_lbl)

            bottom_bar.append(meta_box)

            # Detay Butonu
            detail_btn = Gtk.Button(label="Ödev Detayı &amp; Belgeler")
            detail_btn.set_icon_name("document-properties-symbolic")
            detail_btn.add_css_class("suggested-action")
            detail_btn.connect("clicked", lambda _, item=hw: self.open_homework_detail(item))
            bottom_bar.append(detail_btn)

            card.append(bottom_bar)

            # Karta tıklandığında da detay penceresi açılsın
            click_gesture = Gtk.GestureClick.new()
            click_gesture.connect("released", lambda _g, _n, _x, _y, item=hw: self.open_homework_detail(item))
            card.add_controller(click_gesture)

            if is_active:
                active_group.add(card)
                active_count += 1
            else:
                completed_group.add(card)
                completed_count += 1

        if (self.current_filter in ("all", "active")) and active_count == 0:
            empty_act = Adw.ActionRow()
            empty_act.set_title("Şu anda teslim süresi süren bekleyen ödeviniz yok.")
            empty_act.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))
            active_group.add(empty_act)

        if self.current_filter in ("all", "active"):
            self.container.append(active_group)

        if self.current_filter in ("all", "completed") and completed_count > 0:
            self.container.append(completed_group)

    def _update_card_with_detail(self, hw_id, detail):
        """Arka plandan detay gelince kartın dinamik alanını doldurur."""
        box = self._card_dynamic_boxes.get(hw_id)
        if not box:
            return
        while box.get_first_child():
            box.remove(box.get_first_child())
        self._populate_dynamic_detail(box, hw_id, detail)

    def _populate_dynamic_detail(self, container_box, hw_id, detail):
        """Ödev kartı içerisindeki açıklama ve ek dosyaları çizer."""
        desc = (detail.get("description") or "").strip()
        konu = (detail.get("konuAd") or "").strip()
        teacher_comment = (detail.get("teacherComment") or "").strip()
        attach_files = detail.get("attachFiles") or []
        answer_files = detail.get("answerFiles") or []

        # 1. Konu Başlığı (Varsa)
        if konu:
            konu_lbl = Gtk.Label()
            konu_lbl.set_markup(f"<span size='small' weight='600' foreground='#d0d0d0'>📌 Konu: {konu}</span>")
            konu_lbl.set_halign(Gtk.Align.START)
            container_box.append(konu_lbl)

        # 2. Açıklama Metni Kutusu
        if desc:
            desc_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            desc_box.add_css_class("homework-desc-box")

            desc_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            d_icon = Gtk.Image.new_from_icon_name("accessories-dictionary-symbolic")
            d_icon.set_pixel_size(14)
            desc_hdr.append(d_icon)
            d_lbl_title = Gtk.Label()
            d_lbl_title.set_markup("<span size='small' weight='700' foreground='#b8b8b8'>ÖĞRETMEN AÇIKLAMASI</span>")
            d_lbl_title.set_halign(Gtk.Align.START)
            desc_hdr.append(d_lbl_title)
            desc_box.append(desc_hdr)

            desc_txt = Gtk.Label()
            desc_txt.set_text(desc)
            desc_txt.set_wrap(True)
            desc_txt.set_wrap_mode(2)  # PANGO_WRAP_WORD_CHAR
            desc_txt.set_selectable(True)
            desc_txt.set_halign(Gtk.Align.START)
            desc_txt.set_xalign(0.0)
            desc_txt.add_css_class("homework-desc-text")
            desc_box.append(desc_txt)

            container_box.append(desc_box)

        # 3. Ek Dosyalar (Öğretmen Belgeleri)
        if attach_files:
            att_flow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            att_flow.set_margin_top(2)

            att_hdr_lbl = Gtk.Label()
            att_hdr_lbl.set_markup("<span size='small' weight='700' foreground='#b8b8b8'>EKLER:</span>")
            att_flow.append(att_hdr_lbl)

            for f in attach_files:
                fname = f.get("fileName", "Ek Dosya")

                btn = Gtk.Button()
                btn.add_css_class("homework-attach-chip")
                btn.set_tooltip_text(f"Ek Dosyayı Aç: {fname}")

                btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                f_ico = Gtk.Image.new_from_icon_name("mail-attachment-symbolic")
                f_ico.set_pixel_size(14)
                btn_content.append(f_ico)

                f_name_lbl = Gtk.Label(label=fname)
                f_name_lbl.set_ellipsize(3)
                btn_content.append(f_name_lbl)

                btn.set_child(btn_content)
                btn.connect("clicked", lambda _, fo=f, hid=hw_id, b=btn: self._download_and_open_file(fo, hid, b))
                att_flow.append(btn)

            container_box.append(att_flow)

        # 4. Cevap Anahtarları (Çözüm Dosyaları)
        if answer_files:
            ans_flow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            ans_flow.set_margin_top(2)

            ans_hdr_lbl = Gtk.Label()
            ans_hdr_lbl.set_markup("<span size='smaller' weight='700' foreground='#10b981'>ÇÖZÜM:</span>")
            ans_flow.append(ans_hdr_lbl)

            for f in answer_files:
                fname = f.get("fileName", "Cevap Anahtarı")

                btn = Gtk.Button()
                btn.add_css_class("homework-answer-chip")
                btn.set_tooltip_text(f"Cevap Anahtarını Aç: {fname}")

                btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                f_ico = Gtk.Image.new_from_icon_name("emblem-documents-symbolic")
                f_ico.set_pixel_size(14)
                btn_content.append(f_ico)

                f_name_lbl = Gtk.Label(label=f"🔑 {fname}")
                f_name_lbl.set_ellipsize(3)
                btn_content.append(f_name_lbl)

                btn.set_child(btn_content)
                btn.connect("clicked", lambda _, fo=f, hid=hw_id, b=btn: self._download_and_open_file(fo, hid, b, file_type="answerFiles"))
                ans_flow.append(btn)

            container_box.append(ans_flow)

        # 5. Öğretmen Notu / Dönütü
        if teacher_comment:
            note_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            note_box.add_css_class("homework-note-box")
            n_ico = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
            note_box.append(n_ico)
            n_lbl = Gtk.Label()
            n_lbl.set_markup(f"<b>Öğretmen Dönütü:</b> {teacher_comment}")
            n_lbl.set_wrap(True)
            note_box.append(n_lbl)
            container_box.append(note_box)

    def _download_and_open_file(self, file_obj, hw_id, button_widget=None, file_type="attachFiles", parent_window=None):
        """Ek dosyayı veya cevap anahtarını indirip dahili PDF görüntüleyicide veya sistemde açar."""
        if button_widget:
            button_widget.set_sensitive(False)

        fid = file_obj.get("fileId")
        fhash = file_obj.get("fileHash")
        fname = file_obj.get("fileName", "Belge")

        def worker():
            file_bytes, err = download_homework_attachment(hw_id, fid, file_hash=fhash, file_type=file_type)

            def on_done():
                if button_widget:
                    button_widget.set_sensitive(True)

                if file_bytes:
                    suffix = (Path(fname).suffix or ".pdf").lower()
                    root_win = parent_window or self.get_root()
                    if suffix == ".pdf":
                        open_pdf_viewer(root_win, file_bytes, title=f"Ödev Eki: {fname}")
                    else:
                        try:
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                            tmp.write(file_bytes)
                            tmp.close()
                            open_file_external(tmp.name)
                        except Exception as e:
                            print(f"Dosya açma hatası: {e}")
                else:
                    root_win = parent_window or self.get_root()
                    alert = Adw.AlertDialog.new("İndirme Hatası", err or "Ek dosya sunucudan indirilemedi.")
                    alert.add_response("ok", "Tamam")
                    alert.present(root_win)

            GLib.idle_add(on_done)

        threading.Thread(target=worker, daemon=True).start()

    def open_homework_detail(self, hw):
        """Ödevin tüm ayrıntılarını, tam metin açıklamasını ve ek belgelerini gösteren zengin modal."""
        hw_id = hw.get("id")

        dialog = Adw.Window()
        root_window = self.get_root()
        if root_window:
            dialog.set_transient_for(root_window)
            dialog.set_modal(True)

        apply_theme_to_window(dialog)

        dialog.set_title(f"Ödev Detayı — {hw.get('title', 'Ödev')}")
        dialog.set_default_size(680, 580)
        dialog.set_resizable(True)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header_bar = Adw.HeaderBar()
        win_title = Adw.WindowTitle(
            title=hw.get("title", "Ödev Detayı"),
            subtitle=f"{hw.get('lesson', '')}  •  {hw.get('teaNameSurname', '')}".strip(" •")
        )
        header_bar.set_title_widget(win_title)

        close_btn = Gtk.Button(label="Kapat")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda _: dialog.close())
        header_bar.pack_end(close_btn)
        main_box.append(header_bar)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_top(18)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(20)
        content_box.set_margin_end(20)

        # 1. Genel Bilgiler Grubu
        info_group = Adw.PreferencesGroup()
        info_group.set_title("Ödev Bilgileri")

        teacher_row = Adw.ActionRow()
        teacher_row.set_title("Ders ve Öğretmen")
        teacher_row.set_subtitle(f"{hw.get('lesson', '-')}  —  {hw.get('teaNameSurname', '-')}")
        teacher_row.add_prefix(Gtk.Image.new_from_icon_name("avatar-default-symbolic"))
        info_group.add(teacher_row)

        date_row = Adw.ActionRow()
        date_row.set_title("Tarih Aralığı")
        date_row.set_subtitle(f"Başlangıç: {hw.get('startDate', '-')}  •  Son Teslim: {hw.get('endDate', '-')}")
        date_row.add_prefix(Gtk.Image.new_from_icon_name("appointment-soon-symbolic"))
        info_group.add(date_row)

        status_row = Adw.ActionRow()
        status_row.set_title("Teslim ve Değerlendirme Durumu")
        score_val = hw.get("score")
        status_sub = f"{hw.get('statusName', '-')}"
        if score_val and str(score_val) not in ("-", "None", ""):
            status_sub += f"  (Puan: {score_val})"
        status_row.set_subtitle(status_sub)
        status_row.add_prefix(Gtk.Image.new_from_icon_name("emblem-documents-symbolic"))
        info_group.add(status_row)

        content_box.append(info_group)

        # 2. Açıklama Bölümü
        desc_group = Adw.PreferencesGroup()
        desc_group.set_title("Öğretmen Açıklaması &amp; Ödev Metni")

        desc_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        desc_card.add_css_class("card")
        desc_card.set_margin_top(4)

        desc_label = Gtk.Label()
        desc_label.set_wrap(True)
        desc_label.set_wrap_mode(2)
        desc_label.set_selectable(True)
        desc_label.set_xalign(0.0)
        desc_label.set_margin_top(16)
        desc_label.set_margin_bottom(16)
        desc_label.set_margin_start(16)
        desc_label.set_margin_end(16)
        desc_label.set_text("Açıklama yükleniyor...")
        desc_card.append(desc_label)
        desc_group.add(desc_card)
        content_box.append(desc_group)

        # 3. Ek Dosyalar Grubu (attachFiles)
        attachment_group = Adw.PreferencesGroup()
        content_box.append(attachment_group)

        # 4. Cevap Anahtarları Grubu (answerFiles)
        answer_group = Adw.PreferencesGroup()
        content_box.append(answer_group)

        # 5. Öğrenci Teslim Dosyaları Grubu (studentAttachFiles)
        student_files_group = Adw.PreferencesGroup()
        content_box.append(student_files_group)

        scroll.set_child(content_box)
        main_box.append(scroll)
        dialog.set_content(main_box)
        dialog.present()

        def apply_detail_data(detail):
            if not detail:
                desc_label.set_text("Öğretmen tarafından yazılı bir açıklama eklenmemiş.")
                return

            desc = detail.get("description") or "Öğretmen tarafından yazılı bir açıklama eklenmemiş."
            konu = detail.get("konuAd")
            teacher_note = detail.get("teacherComment", "")
            attach_files = detail.get("attachFiles") or []
            answer_files = detail.get("answerFiles") or []
            student_files = detail.get("studentAttachFiles") or []

            desc_label.set_text(desc)

            if konu:
                konu_row = Adw.ActionRow()
                konu_row.set_title("Ödev Konusu")
                konu_row.set_subtitle(konu)
                konu_row.add_prefix(Gtk.Image.new_from_icon_name("starred-symbolic"))
                info_group.add(konu_row)

            if teacher_note:
                note_row = Adw.ActionRow()
                note_row.set_title("Öğretmen Dönütü / Notu")
                note_row.set_subtitle(teacher_note)
                note_row.add_prefix(Gtk.Image.new_from_icon_name("dialog-information-symbolic"))
                info_group.add(note_row)

            # Ek Dosyalar
            if attach_files:
                attachment_group.set_title(f"Ödev Ek Dosyaları ({len(attach_files)})")
                attachment_group.set_description("Öğretmen tarafından eklenen çalışma kâğıtları ve materyaller")
                for f in attach_files:
                    fname = f.get("fileName", "Ek Dosya")
                    frow = Adw.ActionRow()
                    frow.set_title(fname)
                    frow.set_subtitle("Görüntülemek veya indirmek için tıklayın")
                    frow.add_prefix(Gtk.Image.new_from_icon_name("mail-attachment-symbolic"))
                    frow.set_activatable(True)

                    dl_btn = Gtk.Button(label="Aç / İndir")
                    dl_btn.add_css_class("suggested-action")
                    dl_btn.connect("clicked", lambda _, fo=f, hid=hw_id, b=dl_btn: self._download_and_open_file(fo, hid, b, parent_window=dialog))
                    frow.connect("activated", lambda _, fo=f, hid=hw_id, b=dl_btn: self._download_and_open_file(fo, hid, b, parent_window=dialog))
                    frow.add_suffix(dl_btn)
                    attachment_group.add(frow)

            # Cevap Anahtarları
            if answer_files:
                answer_group.set_title(f"Çözüm &amp; Cevap Anahtarı Dosyaları ({len(answer_files)})")
                answer_group.set_description("Ödevin çözümleri veya yanıt anahtarı")
                for f in answer_files:
                    fname = f.get("fileName", "Cevap Anahtarı")
                    arow = Adw.ActionRow()
                    arow.set_title(fname)
                    arow.set_subtitle("Çözüm dosyasını görüntülemek için tıklayın")
                    arow.add_prefix(Gtk.Image.new_from_icon_name("emblem-documents-symbolic"))
                    arow.set_activatable(True)

                    ans_btn = Gtk.Button(label="Çözümü Aç")
                    ans_btn.add_css_class("suggested-action")
                    ans_btn.connect("clicked", lambda _, fo=f, hid=hw_id, b=ans_btn: self._download_and_open_file(fo, hid, b, file_type="answerFiles", parent_window=dialog))
                    arow.connect("activated", lambda _, fo=f, hid=hw_id, b=ans_btn: self._download_and_open_file(fo, hid, b, file_type="answerFiles", parent_window=dialog))
                    arow.add_suffix(ans_btn)
                    answer_group.add(arow)

            # Öğrenci Teslim Dosyaları
            if student_files:
                student_files_group.set_title(f"Öğrencinin Yüklediği Belgeler ({len(student_files)})")
                for f in student_files:
                    fname = f.get("fileName", "Öğrenci Dosyası")
                    srow = Adw.ActionRow()
                    srow.set_title(fname)
                    srow.set_subtitle("Yüklenen ödev dosyasını görüntülemek için tıklayın")
                    srow.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))
                    srow.set_activatable(True)

                    s_btn = Gtk.Button(label="Görüntüle")
                    s_btn.connect("clicked", lambda _, fo=f, hid=hw_id, b=s_btn: self._download_and_open_file(fo, hid, b, file_type="studentAttachFiles", parent_window=dialog))
                    srow.connect("activated", lambda _, fo=f, hid=hw_id, b=s_btn: self._download_and_open_file(fo, hid, b, file_type="studentAttachFiles", parent_window=dialog))
                    srow.add_suffix(s_btn)
                    student_files_group.add(srow)

        # Eğer detay zaten önbellekte varsa hemen uygula
        if hw_id in self._cached_details:
            apply_detail_data(self._cached_details[hw_id])
        else:
            def fetch_worker():
                detail = fetch_homework_detail(hw_id)
                if detail:
                    self._cached_details[hw_id] = detail
                GLib.idle_add(apply_detail_data, detail)

            threading.Thread(target=fetch_worker, daemon=True).start()
