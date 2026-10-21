import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import fetch_exam_lesson_answers


LESSON_NAMES = [
    (1, "TÜRKÇE"),
    (2, "MATEMATİK"),
    (4, "DİN KÜLTÜRÜ"),
    (5, "FEN VE TEKNOLOJİ"),
    (8, "SOSYAL BİLGİLER"),
    (11, "İNGİLİZCE / Y. DİL"),
]


class ExamReportWindow(Adw.Window):
    def __init__(self, parent, exam_title, report_json, exam_index=0, exam_type="SBS"):
        super().__init__()
        self.exam_title = exam_title
        self.report_json = report_json
        self.exam_index = exam_index
        self.exam_type = exam_type

        self.set_title(f"Sınav Karnesi &amp; Detaylar — {exam_title}")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(840, 720)

        from api_bridge import apply_theme_to_window
        apply_theme_to_window(self)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # HeaderBar
        header_bar = Adw.HeaderBar()
        header_bar.set_show_start_title_buttons(True)
        header_bar.set_show_end_title_buttons(True)
        header_bar.set_title_widget(Adw.WindowTitle(title="Sınav Karnesi & Netler", subtitle=exam_title))
        main_box.append(header_bar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(780)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.content_box.set_margin_top(20)
        self.content_box.set_margin_bottom(25)
        self.content_box.set_margin_start(16)
        self.content_box.set_margin_end(16)

        data = report_json.get("data", {})
        subanal = report_json.get("subanal", [])

        # 1. BÜYÜK BAŞARI VE PUAN KARTI
        score_group = Adw.PreferencesGroup()
        score_group.set_title("🏆 Sınav Puanı ve Başarı Özeti")

        puan = data.get("Puan", "-")
        toplam_net = data.get("N7", "-")
        toplam_dogru = data.get("D7", "-")
        toplam_yanlis = data.get("Y7", "-")
        sinif_derece = data.get("SD", "-")
        genel_derece = data.get("GD", "-")

        # Puan ve Net Satırı
        row_puan = Adw.ActionRow()
        row_puan.set_title(f"Sınav Puanı: {puan}")
        row_puan.set_subtitle(f"Toplam Net: {toplam_net}  •  Doğru: {toplam_dogru}  •  Yanlış: {toplam_yanlis}")
        row_puan.set_icon_name("starred-symbolic")
        
        badge_puan = Gtk.Label(label=f"{puan} Puan")
        badge_puan.add_css_class("badge-primary")
        row_puan.add_suffix(badge_puan)
        score_group.add(row_puan)

        # Derece Satırı
        row_derece = Adw.ActionRow()
        row_derece.set_title("Sıralama ve Dereceler")
        row_derece.set_subtitle(f"Sınıf Derecesi: {sinif_derece}.  •  Genel Derece: {genel_derece}.")
        row_derece.set_icon_name("emblem-documents-symbolic")
        score_group.add(row_derece)

        self.content_box.append(score_group)

        # 2. DERS BAŞINA DETAYLI NETLER
        lessons_group = Adw.PreferencesGroup()
        lessons_group.set_title("📊 Ders Başına Detaylı Net ve Doğru/Yanlış Karnesi")
        lessons_group.set_description("Tüm derslerin soru sayısı, doğru, yanlış ve hesaplanan net puanları")

        lesson_stat_indices = [
            ("1", "TÜRKÇE"),
            ("2", "MATEMATİK"),
            ("3", "DİN KÜLTÜRÜ"),
            ("4", "FEN VE TEKNOLOJİ"),
            ("5", "SOSYAL BİLGİLER"),
            ("6", "İNGİLİZCE / Y. DİL"),
        ]

        for idx, l_name in lesson_stat_indices:
            sr = data.get(f"SR{idx}")
            d = data.get(f"D{idx}")
            y = data.get(f"Y{idx}")
            n = data.get(f"N{idx}")

            if sr is not None or n is not None:
                l_row = Adw.ActionRow()
                l_row.set_title(l_name)
                l_row.set_subtitle(f"Doğru: {d}  •  Yanlış: {y}  •  Toplam Soru: {sr}")
                l_row.set_icon_name("appointment-soon-symbolic")

                net_badge = Gtk.Label(label=f"{n} Net")
                net_badge.add_css_class("badge-primary")
                l_row.add_suffix(net_badge)
                lessons_group.add(l_row)

        self.content_box.append(lessons_group)

        # 3. CEVAP ANAHTARI & SORU ANALİZİ (AÇILIR KAPANIR / TIKLANINCA GÖSTERİLİR)
        self.answers_group = Adw.PreferencesGroup()
        self.answers_group.set_title("📝 Cevap Anahtarı &amp; Soru Analizi")
        self.answers_group.set_description("Hangi soru doğru, hangisi yanlış ve cevap anahtarını görmek için butona tıklayın")

        # Aç / Kapat Butonu Satırı
        self.toggle_row = Adw.ActionRow()
        self.toggle_row.set_title("Soru Bazlı Cevap Anahtarını İncele")
        self.toggle_row.set_subtitle("Kitapçık türü, soru bazlı doğru/yanlış ve cevap harfleri")
        self.toggle_row.set_icon_name("find-location-symbolic")
        self.toggle_row.set_activatable(True)

        self.answers_visible = False
        self.toggle_btn = Gtk.Button(label="Aç / İncele ▼")
        self.toggle_btn.add_css_class("suggested-action")
        self.toggle_btn.connect("clicked", lambda _: self.toggle_answers_visibility())
        self.toggle_row.add_suffix(self.toggle_btn)
        self.toggle_row.connect("activated", lambda _: self.toggle_answers_visibility())

        self.answers_group.add(self.toggle_row)

        # Gizlenebilir / Gösterilebilir İçerik Alanı
        self.collapsible_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.collapsible_container.set_visible(False)
        self.collapsible_container.set_margin_top(8)

        # Ders Seçici Segmented Butonlar
        lessons_scroll = Gtk.ScrolledWindow()
        lessons_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.lesson_btns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lesson_btns_box.add_css_class("segmented-bar")
        lessons_scroll.set_child(self.lesson_btns_box)
        self.collapsible_container.append(lessons_scroll)

        # Cevap Tablosu Kapsayıcısı
        self.answer_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.answer_details_box.set_margin_top(12)
        self.collapsible_container.append(self.answer_details_box)

        self.answers_group.add(self.collapsible_container)
        self.content_box.append(self.answers_group)

        # 4. DETAYLI KONU ANALİZİ (TÜM KAZANIMLAR)
        if subanal:
            topic_group = Adw.PreferencesGroup()
            topic_group.set_title("🔍 Detaylı Konu ve Kazanım Analizi")
            topic_group.set_description(f"Toplam {len(subanal)} konu bazlı başarı ve analiz sonuçları")

            for topic in subanal:
                konu_ad = topic.get("konuAd", "-")
                ders = topic.get("lesson", "")
                dogru = topic.get("Dog", 0)
                yanlis = topic.get("Yan", 0)
                basari = topic.get("Bas", 0)

                t_row = Adw.ActionRow()
                t_row.set_title(f"[{ders}] {konu_ad}")
                t_row.set_subtitle(f"Doğru: {dogru}  •  Yanlış: {yanlis}  •  Başarı Oranı: %{basari}")
                
                t_badge = Gtk.Label(label=f"%{basari}")
                try:
                    b_val = float(basari)
                    if b_val >= 80:
                        t_badge.add_css_class("badge-active")
                    elif b_val >= 50:
                        t_badge.add_css_class("badge-primary")
                    else:
                        t_badge.add_css_class("error-text")
                except Exception:
                    t_badge.add_css_class("badge-primary")

                t_row.add_suffix(t_badge)
                topic_group.add(t_row)

            self.content_box.append(topic_group)

        clamp.set_child(self.content_box)
        scrolled.set_child(clamp)
        main_box.append(scrolled)

        self.set_content(main_box)

        # İlk dersin cevap anahtarını hazırla (Türkçe: place=1)
        self.current_place = 1
        self.setup_lesson_buttons()

    def toggle_answers_visibility(self):
        self.answers_visible = not self.answers_visible
        self.collapsible_container.set_visible(self.answers_visible)
        if self.answers_visible:
            self.toggle_btn.set_label("Kapat ▲")
            self.toggle_btn.remove_css_class("suggested-action")
            self.toggle_btn.add_css_class("flat")
            if not self.answer_details_box.get_first_child():
                self.load_answers_for_lesson(self.current_place)
        else:
            self.toggle_btn.set_label("Aç / İncele ▼")
            self.toggle_btn.add_css_class("suggested-action")
            self.toggle_btn.remove_css_class("flat")

    def setup_lesson_buttons(self):
        while self.lesson_btns_box.get_first_child():
            self.lesson_btns_box.remove(self.lesson_btns_box.get_first_child())

        for place, name in LESSON_NAMES:
            btn = Gtk.Button(label=name)
            if place == self.current_place:
                btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda _, p=place: self.on_lesson_selected(p))
            self.lesson_btns_box.append(btn)

    def on_lesson_selected(self, place):
        self.current_place = place
        self.setup_lesson_buttons()
        self.load_answers_for_lesson(place)

    def load_answers_for_lesson(self, place):
        while self.answer_details_box.get_first_child():
            self.answer_details_box.remove(self.answer_details_box.get_first_child())

        loading_lbl = Gtk.Label(label="Cevap anahtarı ve öğrenci yanıtları yükleniyor...")
        loading_lbl.add_css_class("dim-label")
        loading_lbl.set_halign(Gtk.Align.CENTER)
        loading_lbl.set_margin_top(12)
        loading_lbl.set_margin_bottom(12)
        self.answer_details_box.append(loading_lbl)

        def worker():
            res = fetch_exam_lesson_answers(self.exam_index, place, self.exam_type)
            GLib.idle_add(self.render_answers_table, res)

        threading.Thread(target=worker, daemon=True).start()

    def render_answers_table(self, data):
        while self.answer_details_box.get_first_child():
            self.answer_details_box.remove(self.answer_details_box.get_first_child())

        if not data:
            empty_lbl = Gtk.Label(label="Bu ders için cevap anahtarı veya optik veri bulunamadı.")
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_halign(Gtk.Align.CENTER)
            empty_lbl.set_margin_top(12)
            self.answer_details_box.append(empty_lbl)
            return

        paper_code = data.get("paperCode", "-")
        paper_ans = data.get("paper", "")  # Cevap anahtarı harfleri (örn: CCBD...)
        stu_ans = data.get("student", "")  # Öğrenci işaretlemeleri (örn: CC D...)

        # Özet Bilgi Kartı
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        info_box.set_halign(Gtk.Align.CENTER)
        info_box.set_margin_bottom(8)

        kitapcik_lbl = Gtk.Label()
        kitapcik_lbl.set_markup(f"<b>Kitapçık:</b> <span color='#3584e4'>{paper_code}</span>")
        info_box.append(kitapcik_lbl)

        # Doğru, Yanlış, Boş sayılarını hesapla
        total_q = len(paper_ans)
        d_count = 0
        y_count = 0
        b_count = 0

        for i in range(total_q):
            s_char = stu_ans[i] if i < len(stu_ans) else " "
            p_char = paper_ans[i]
            if s_char == " ":
                b_count += 1
            elif s_char == p_char:
                d_count += 1
            else:
                y_count += 1

        stats_lbl = Gtk.Label()
        stats_lbl.set_markup(
            f"<b>Toplam:</b> {total_q} Soru  •  "
            f"<span color='#2ec27e'><b>{d_count} Doğru</b></span>  •  "
            f"<span color='#e01b24'><b>{y_count} Yanlış</b></span>  •  "
            f"<span color='#77767b'><b>{b_count} Boş</b></span>"
        )
        info_box.append(stats_lbl)
        self.answer_details_box.append(info_box)

        # Soru Rozetleri (Her satırda 5-10 soru)
        flow_box = Gtk.FlowBox()
        flow_box.set_valign(Gtk.Align.START)
        flow_box.set_max_children_per_line(10)
        flow_box.set_min_children_per_line(5)
        flow_box.set_selection_mode(Gtk.SelectionMode.NONE)
        flow_box.set_row_spacing(8)
        flow_box.set_column_spacing(8)
        flow_box.set_homogeneous(True)

        for i in range(total_q):
            q_num = i + 1
            p_char = paper_ans[i]
            s_char = stu_ans[i] if i < len(stu_ans) else " "

            is_correct = (s_char == p_char)
            is_empty = (s_char == " ")

            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            card.set_margin_top(4)
            card.set_margin_bottom(4)
            card.set_margin_start(4)
            card.set_margin_end(4)

            # Soru No
            num_lbl = Gtk.Label(label=f"Soru {q_num}")
            num_lbl.set_markup(f"<span size='small' alpha='75%'>Soru {q_num}</span>")
            card.append(num_lbl)

            # Cevap / Karşılaştırma Rozeti
            badge = Gtk.Label()
            if is_empty:
                badge.set_markup(f"<span weight='bold'>[ {p_char} ] Boş</span>")
                badge.add_css_class("badge-upcoming")
            elif is_correct:
                badge.set_markup(f"<span weight='bold'>✓ {p_char}</span>")
                badge.add_css_class("badge-active")
            else:
                badge.set_markup(f"<span weight='bold'>✗ {s_char} ({p_char})</span>")
                badge.add_css_class("badge-failed")

            card.append(badge)
            flow_box.append(card)

        self.answer_details_box.append(flow_box)
