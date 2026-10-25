import threading
from datetime import datetime, time, timedelta
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from api_bridge import (
    get_adaptive_profile_data,
    get_adaptive_index_data,
    fetch_homeworks_list,
    fetch_all_student_exams,
    fetch_food_list_data,
    get_effective_school_date,
    get_effective_school_day_idx,
)
from views.food_list_view import parse_food_menu, parse_day_date_obj


class HomeView(Gtk.ScrolledWindow):
    def __init__(self, on_navigate_tab=None):
        super().__init__()
        self.on_navigate_tab = on_navigate_tab
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(960)
        clamp.set_tightening_threshold(720)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.main_box.set_margin_top(24)
        self.main_box.set_margin_bottom(36)
        self.main_box.set_margin_start(22)
        self.main_box.set_margin_end(22)

        # 1. Başlık Alanı (Avatar + Merhaba + Durum)
        self.header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.header_hbox.set_halign(Gtk.Align.START)
        self.header_hbox.set_valign(Gtk.Align.CENTER)

        self.avatar = Adw.Avatar()
        self.avatar.set_size(68)
        self.avatar.set_show_initials(True)
        self.header_hbox.append(self.avatar)

        self.header_text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.header_text_box.set_valign(Gtk.Align.CENTER)

        self.greeting_label = Gtk.Label()
        self.greeting_label.set_markup("<span size='xx-large' weight='bold'>Merhaba</span>")
        self.greeting_label.set_halign(Gtk.Align.START)
        self.header_text_box.append(self.greeting_label)

        self.subtitle_label = Gtk.Label()
        self.subtitle_label.set_markup("<span size='medium' weight='500' foreground='#d0d0d0'>Bugün okulda neler var?</span>")
        self.subtitle_label.set_halign(Gtk.Align.START)
        self.header_text_box.append(self.subtitle_label)

        self.date_label = Gtk.Label()
        self.date_label.set_halign(Gtk.Align.START)
        self.header_text_box.append(self.date_label)

        self.header_hbox.append(self.header_text_box)
        self.main_box.append(self.header_hbox)

        # 2. ⏱️ CANLI DERS & TENEFFÜS DURUM KARTI (Geri Sayım & Sayaç)
        self.live_status_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.live_status_container)

        # 3. 🎒 ÇANTA & YARINKİ KİTAPLAR HATIRLATICISI
        self.bag_reminder_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.bag_reminder_container)

        # 4. Üst İki Kart (Günün Ana Yemeği ve Aktif Ödevler)
        self.top_grid = Gtk.Grid()
        self.top_grid.set_column_spacing(16)
        self.top_grid.set_row_spacing(16)
        self.top_grid.set_column_homogeneous(True)
        self.main_box.append(self.top_grid)

        # 5. Sıradaki Ders Programı Kartı
        self.schedule_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.schedule_container)

        # 6. Sınav Karnesi & Gelişim Grafiği Kartı
        self.exam_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_box.append(self.exam_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

        # Cache verileri
        self._cached_index_data = None
        self._cached_exams = None

    def reset_state(self):
        """Hesap değiştiğinde HomeView önbelleğini ve arayüzünü sıfırlar."""
        self._cached_index_data = None
        self._cached_exams = None
        self.greeting_label.set_markup("<span size='xx-large' weight='bold'>Merhaba</span>")
        self.subtitle_label.set_markup("<span size='medium' weight='500' foreground='#d0d0d0'>Yükleniyor...</span>")
        self.date_label.set_text("")
        self.avatar.set_text("K")
        self.avatar.set_custom_image(None)

        for container in [self.live_status_container, self.bag_reminder_container, self.schedule_container, self.exam_container]:
            while child := container.get_first_child():
                container.remove(child)

        while child := self.top_grid.get_first_child():
            self.top_grid.remove(child)

    def load_data(self):
        def worker():
            try:
                profile = get_adaptive_profile_data()
                index_data = get_adaptive_index_data()
                homeworks = fetch_homeworks_list()
                exams = fetch_all_student_exams()
                food_data = fetch_food_list_data()

                GLib.idle_add(
                    self.update_ui,
                    profile,
                    index_data,
                    homeworks,
                    exams,
                    food_data
                )
            except Exception as e:
                print(f"HomeView load_data error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def update_ui(self, profile, index_data, homeworks, exams, food_data):
        self._cached_index_data = index_data
        self._cached_exams = exams
        now = datetime.now()

        # 1. Başlık Bilgileri ve Avatar
        role = profile.get("role", "Öğrenci")
        is_parent = (role == "Veli")
        display_name = profile.get("parent_name") if is_parent else profile.get("student_name")
        display_name = display_name or ("Veli" if is_parent else "Öğrenci")
        first_name = display_name.split()[0].title() if display_name else "Kullanıcı"

        self.avatar.set_text(display_name)
        photo_bytes = profile.get("photo_bytes")
        if photo_bytes:
            try:
                glib_bytes = GLib.Bytes.new(photo_bytes)
                texture = Gdk.Texture.new_from_bytes(glib_bytes)
                self.avatar.set_custom_image(texture)
            except Exception as e:
                print(f"HomeView avatar error: {e}")
                self.avatar.set_custom_image(None)
        else:
            self.avatar.set_custom_image(None)

        self.greeting_label.set_markup(f"<span size='xx-large' weight='bold'>Merhaba {first_name}</span>")
        
        # Gün ve Durum Mesajı
        weekday = now.weekday()  # 0: Pzt .. 6: Paz
        cur_time = now.time()
        cuma_finish = time(16, 30)

        if weekday == 0:
            status_text = "Yeni hafta başlıyor!"
        elif weekday == 1:
            status_text = "Hafta hızlanıyor, tempoya ayak uydur!"
        elif weekday == 2:
            status_text = "Hafta ortasındasın, iyi gidiyorsun!"
        elif weekday == 3:
            status_text = "Hafta bitiyor, iyi dinlen!"
        elif weekday == 4:
            if cur_time >= cuma_finish:
                status_text = "Bu hafta bitti, haftaya hazırlan!"
            else:
                status_text = "Haftanın son dersleri, gayret!"
        else:
            status_text = "Bu hafta bitti, haftaya hazırlan!"

        self.subtitle_label.set_markup(f"<span size='medium' weight='500' foreground='#d0d0d0'>{status_text}</span>")
        months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        days_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        formatted_date = f"{now.day} {months_tr[now.month - 1]} {now.year} {days_tr[now.weekday()]}"
        self.date_label.set_markup(f"<span size='small' foreground='#a8a8a8'>{formatted_date}</span>")

        sched_data = index_data.get("data", {}).get("lessonSchedule", {}).get("data", {})
        x_info = sched_data.get("xInfo", [])
        lessons = sched_data.get("data", [])

        # 2. CANLI DERS / TENEFFÜS SAYACI KARTI
        self.render_live_lesson_status(now, x_info, lessons)

        # 3. YARINKİ ÇANTA & KİTAP HATIRLATICISI
        self.render_bag_reminder(now, lessons)

        # 4. ÜST İKİ KART (Yemek & Ödev)
        while self.top_grid.get_first_child():
            self.top_grid.remove(self.top_grid.get_first_child())

        # A) Yemek Kartı (16:30 kuralı: 16:30'dan sonra ertesi günün yemeği gösterilir)
        main_dish = "Yemek Listesi Belirlenmedi"
        next_menu_desc = "Menü hazırlanıyor"
        card_header_title = "Bugünün Ana Yemeği"

        if food_data and food_data.get("success") and food_data.get("pdf_bytes"):
            weeks = parse_food_menu(food_data["pdf_bytes"])
            all_days = []
            for w in weeks:
                for d in w.get("days", []):
                    all_days.append(d)

            effective_date = get_effective_school_date(now)

            target_day_menu = None
            next_day_menu = None

            for idx, d in enumerate(all_days):
                d_obj = parse_day_date_obj(d.get("date", ""))
                if not d_obj:
                    continue

                if d_obj < effective_date:
                    continue

                if d_obj >= effective_date:
                    target_day_menu = d
                    if idx + 1 < len(all_days):
                        next_day_menu = all_days[idx + 1]
                    break

            if target_day_menu and target_day_menu.get("meals"):
                m_list = target_day_menu["meals"]
                main_dish = m_list[1] if len(m_list) > 1 else m_list[0]
                t_date_obj = parse_day_date_obj(target_day_menu.get("date", ""))

                if t_date_obj == now.date():
                    card_header_title = "Bugünün Ana Yemeği"
                elif t_date_obj == now.date() + timedelta(days=1):
                    card_header_title = "Yarının Ana Yemeği"
                else:
                    card_header_title = "Sıradaki Günün Ana Yemeği"

                if target_day_menu.get("date"):
                    if t_date_obj != now.date():
                        next_menu_desc = f"{target_day_menu.get('date', '')} Menüsü"
                    elif next_day_menu:
                        next_menu_desc = f"Sonraki menü • {next_day_menu.get('date', '')}"
                    else:
                        next_menu_desc = target_day_menu.get("date", "")

        food_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        food_card.add_css_class("gokturk-card")
        food_card.set_hexpand(True)

        food_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        food_icon = Gtk.Image.new_from_icon_name("emoji-food-symbolic")
        food_icon.set_pixel_size(18)
        food_title = Gtk.Label()
        food_title.set_markup(f"<span weight='600' foreground='#d0d0d0'>{card_header_title}</span>")
        food_header.append(food_icon)
        food_header.append(food_title)
        food_card.append(food_header)

        dish_label = Gtk.Label()
        dish_label.set_markup(f"<span size='large' weight='bold'>{GLib.markup_escape_text(main_dish)}</span>")
        dish_label.set_halign(Gtk.Align.START)
        dish_label.set_margin_top(6)
        dish_label.set_wrap(True)
        food_card.append(dish_label)

        sub_food_label = Gtk.Label()
        sub_food_label.set_markup(f"<span size='small' foreground='#a8a8a8'>{GLib.markup_escape_text(next_menu_desc)}</span>")
        sub_food_label.set_halign(Gtk.Align.START)
        food_card.append(sub_food_label)

        food_spacer = Gtk.Box()
        food_spacer.set_vexpand(True)
        food_card.append(food_spacer)

        food_link_btn = Gtk.Button(label="›  Yemek Listesine Git")
        food_link_btn.add_css_class("gokturk-action-link")
        food_link_btn.set_halign(Gtk.Align.START)
        food_link_btn.set_margin_top(14)
        if self.on_navigate_tab:
            food_link_btn.connect("clicked", lambda _: self.on_navigate_tab("food"))
        food_card.append(food_link_btn)

        self.top_grid.attach(food_card, 0, 0, 1, 1)

        # B) Aktif Ödevler Kartı
        active_hws = [
            h for h in (homeworks or [])
            if h.get("isActive") is True or (
                "isActive" not in h
                and h.get("status") not in (1, "1")
                and "yapıldı" not in str(h.get("statusName", "")).lower()
                and "tamamlandı" not in str(h.get("statusName", "")).lower()
            )
        ]
        active_hw_count = len(active_hws)
        total_hw_count = len(homeworks or [])

        hw_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hw_card.add_css_class("gokturk-card")
        hw_card.set_hexpand(True)

        hw_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hw_icon = Gtk.Image.new_from_icon_name("x-office-document-symbolic")
        hw_icon.set_pixel_size(18)
        hw_title = Gtk.Label()
        hw_title.set_markup("<span weight='600' foreground='#d0d0d0'>Aktif Ödevler</span>")
        hw_header.append(hw_icon)
        hw_header.append(hw_title)
        hw_card.append(hw_header)

        hw_count_label = Gtk.Label()
        hw_count_label.set_markup(f"<span size='xx-large' weight='bold'>{active_hw_count}</span>")
        hw_count_label.set_halign(Gtk.Align.START)
        hw_count_label.set_margin_top(4)
        hw_card.append(hw_count_label)

        hw_sub_label = Gtk.Label()
        sub_text = f"aktif ödev (toplam {total_hw_count})" if total_hw_count else "aktif ödev"
        hw_sub_label.set_markup(f"<span size='small' foreground='#a8a8a8'>{sub_text}</span>")
        hw_sub_label.set_halign(Gtk.Align.START)
        hw_card.append(hw_sub_label)

        hw_spacer = Gtk.Box()
        hw_spacer.set_vexpand(True)
        hw_card.append(hw_spacer)

        hw_link_btn = Gtk.Button(label="›  Ödevlere Git")
        hw_link_btn.add_css_class("gokturk-action-link")
        hw_link_btn.set_halign(Gtk.Align.START)
        hw_link_btn.set_margin_top(14)
        if self.on_navigate_tab:
            hw_link_btn.connect("clicked", lambda _: self.on_navigate_tab("homework"))
        hw_card.append(hw_link_btn)

        self.top_grid.attach(hw_card, 1, 0, 1, 1)

        # 5. Sıradaki Ders Programı Kartı
        while self.schedule_container.get_first_child():
            self.schedule_container.remove(self.schedule_container.get_first_child())

        sched_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sched_card.add_css_class("gokturk-card")

        effective_day_idx = get_effective_school_day_idx(now)
        effective_date = get_effective_school_date(now)

        day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
        day_title = day_names[effective_day_idx - 1] if 1 <= effective_day_idx <= len(day_names) else "Pazartesi"

        if effective_date == now.date():
            day_badge = "Bugün"
        elif effective_date == now.date() + timedelta(days=1):
            day_badge = "Yarın"
        else:
            day_badge = "Sıradaki Gün"

        sched_header_label = Gtk.Label()
        sched_header_label.set_markup(f"<span weight='700' size='medium'>Ders Programı • {day_title} ({day_badge})</span>")
        sched_header_label.set_halign(Gtk.Align.START)
        sched_header_label.set_margin_bottom(6)
        sched_card.append(sched_header_label)

        day_lessons = sorted(
            [l for l in lessons if l.get("y") == effective_day_idx],
            key=lambda it: it.get("x", 0)
        )
        if not day_lessons and lessons:
            day_lessons = sorted(
                [l for l in lessons if l.get("y") == 1],
                key=lambda it: it.get("x", 0)
            )

        for l in day_lessons:
            x_pos = l.get("x", 1) - 1
            slot_str = x_info[x_pos][0] if 0 <= x_pos < len(x_info) else ""
            slot_fmt = slot_str.replace(" - ", "–").replace(" ", "")
            teacher_str = l.get("text", ["", ""])[0] if len(l.get("text", [])) > 0 else ""
            subject_str = l.get("text", ["", ""])[1] if len(l.get("text", [])) > 1 else ""

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
            row_box.add_css_class("lesson-schedule-line")

            circle_dot = Gtk.Box()
            circle_dot.add_css_class("lesson-circle-dot")
            circle_dot.set_valign(Gtk.Align.CENTER)
            row_box.append(circle_dot)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            sub_lbl = Gtk.Label()
            sub_lbl.set_markup(f"<span weight='600'>{GLib.markup_escape_text(subject_str)}</span>")
            sub_lbl.set_halign(Gtk.Align.START)
            info_box.append(sub_lbl)

            tea_lbl = Gtk.Label()
            tea_lbl.set_markup(f"<span size='small' foreground='#a8a8a8'>{GLib.markup_escape_text(teacher_str)}</span>")
            tea_lbl.set_halign(Gtk.Align.START)
            info_box.append(tea_lbl)

            row_box.append(info_box)

            time_lbl = Gtk.Label()
            time_lbl.set_markup(f"<span size='small' foreground='#b8b8b8'>{slot_fmt}</span>")
            time_lbl.set_halign(Gtk.Align.END)
            row_box.append(time_lbl)

            sched_card.append(row_box)

        sched_link_btn = Gtk.Button(label="›  Tüm Ders Programına Git")
        sched_link_btn.add_css_class("gokturk-action-link")
        sched_link_btn.set_halign(Gtk.Align.START)
        sched_link_btn.set_margin_top(12)
        if self.on_navigate_tab:
            sched_link_btn.connect("clicked", lambda _: self.on_navigate_tab("schedule"))
        sched_card.append(sched_link_btn)

        self.schedule_container.append(sched_card)

        # 6. Sınav Karnesi & Gelişim Grafiği
        self.render_exam_analytics(exams)

    def render_live_lesson_status(self, now, x_info, lessons):
        """1. Özellik: Canlı ders ve teneffüs sayacı"""
        while self.live_status_container.get_first_child():
            self.live_status_container.remove(self.live_status_container.get_first_child())

        weekday_idx = now.isoweekday()
        if not (1 <= weekday_idx <= 5) or not x_info:
            return  # Hafta sonu sayaç gösterme

        cur_t = now.time()
        cur_lesson = None
        next_lesson = None
        state_type = None  # "in_lesson", "in_break", "before_school", "after_school"
        minutes_left = 0

        parsed_slots = []
        for idx, s in enumerate(x_info):
            slot_str = s[0] if isinstance(s, list) and len(s) > 0 else ""
            if "-" in slot_str:
                try:
                    s_str, e_str = slot_str.split("-")
                    sh, sm = map(int, s_str.strip().split(":"))
                    eh, em = map(int, e_str.strip().split(":"))
                    parsed_slots.append({
                        "idx": idx + 1,
                        "slot": slot_str,
                        "start": time(sh, sm),
                        "end": time(eh, em)
                    })
                except Exception:
                    pass

        if not parsed_slots:
            return

        # Günün derslerini x konumlarına göre haritalandır
        today_lessons = {l.get("x"): l for l in lessons if l.get("y") == weekday_idx}

        first_start = parsed_slots[0]["start"]
        last_end = parsed_slots[-1]["end"]

        now_minutes = cur_t.hour * 60 + cur_t.minute

        if cur_t < first_start:
            state_type = "before_school"
            target_m = first_start.hour * 60 + first_start.minute
            minutes_left = target_m - now_minutes
            next_l_obj = today_lessons.get(parsed_slots[0]["idx"])
            next_lesson = next_l_obj.get("text", ["", ""])[1] if next_l_obj else "1. Ders"
        elif cur_t > last_end:
            state_type = "after_school"
        else:
            for i, slot in enumerate(parsed_slots):
                if slot["start"] <= cur_t <= slot["end"]:
                    state_type = "in_lesson"
                    target_m = slot["end"].hour * 60 + slot["end"].minute
                    minutes_left = max(0, target_m - now_minutes)
                    l_obj = today_lessons.get(slot["idx"])
                    cur_lesson = l_obj.get("text", ["", ""])[1] if l_obj else f"{slot['idx']}. Ders"
                    break
                elif i + 1 < len(parsed_slots):
                    next_slot = parsed_slots[i + 1]
                    if slot["end"] < cur_t < next_slot["start"]:
                        state_type = "in_break"
                        target_m = next_slot["start"].hour * 60 + next_slot["start"].minute
                        minutes_left = max(0, target_m - now_minutes)
                        l_obj = today_lessons.get(next_slot["idx"])
                        next_lesson = l_obj.get("text", ["", ""])[1] if l_obj else f"{next_slot['idx']}. Ders"
                        break

        if not state_type or state_type == "after_school":
            return  # Okul bittikten sonra canlı ders sayacı yerine çanta hatırlatıcısı öne çıkar

        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        banner.add_css_class("live-status-banner")
        if state_type == "in_break":
            banner.add_css_class("live-status-break")

        icon_name = "alarm-symbolic" if state_type == "in_break" else "appointment-soon-symbolic"
        icon_lbl = Gtk.Image.new_from_icon_name(icon_name)
        icon_lbl.set_pixel_size(24)
        banner.append(icon_lbl)

        txt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        txt_box.set_hexpand(True)

        title_lbl = Gtk.Label()
        title_lbl.set_halign(Gtk.Align.START)
        desc_lbl = Gtk.Label()
        desc_lbl.set_halign(Gtk.Align.START)

        if state_type == "in_lesson":
            title_lbl.set_markup(f"<span weight='bold' size='medium'>Şu Anda Canlı Ders: {cur_lesson}</span>")
            desc_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>Teneffüse <b>{minutes_left} dakika</b> kaldı</span>")
        elif state_type == "in_break":
            title_lbl.set_markup("<span weight='bold' size='medium'>Şu Anda Teneffüstesin</span>")
            desc_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>Sonraki ders: <b>{next_lesson}</b> ({minutes_left} dk sonra başlayacak)</span>")
        elif state_type == "before_school":
            title_lbl.set_markup("<span weight='bold' size='medium'>Derslerin Başlamasına Az Kaldı</span>")
            desc_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>İlk ders: <b>{next_lesson}</b> ({minutes_left} dakika kaldı)</span>")

        txt_box.append(title_lbl)
        txt_box.append(desc_lbl)
        banner.append(txt_box)

        badge_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        badge_box.set_valign(Gtk.Align.CENTER)
        countdown_badge = Gtk.Label()
        countdown_badge.set_markup(f"<span weight='bold' size='medium'>{minutes_left} dk</span>")
        countdown_badge.add_css_class("badge-active")
        badge_box.append(countdown_badge)
        banner.append(badge_box)

        self.live_status_container.append(banner)

    def render_bag_reminder(self, now, lessons):
        """Kullanıcı İsteği: Akşam saat 16:30'dan itibaren yarının kitaplarını hatırlat"""
        while self.bag_reminder_container.get_first_child():
            self.bag_reminder_container.remove(self.bag_reminder_container.get_first_child())

        weekday = now.weekday()  # 0: Pzt, 1: Salı, 2: Çarş, 3: Perş, 4: Cuma, 5: Cts, 6: Paz
        cur_t = now.time()

        # Akşam 16:30'dan sonra mı ya da sabah okul öncesi mi?
        is_after_school = (cur_t >= time(16, 30))
        is_early_morning = (cur_t < time(8, 30))

        # Hafta içi ders saatleri içindeyken (08:30 - 16:30) çanta hatırlatması gizlenir
        if not is_after_school and not is_early_morning and weekday in (0, 1, 2, 3, 4):
            return

        effective_day_idx = get_effective_school_day_idx(now)
        effective_date = get_effective_school_date(now)

        day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
        day_name = day_names[effective_day_idx - 1] if 1 <= effective_day_idx <= len(day_names) else "Pazartesi"

        if effective_date == now.date():
            target_day_name = f"Bugün ({day_name})"
        elif effective_date == now.date() + timedelta(days=1):
            target_day_name = f"Yarın ({day_name})"
        else:
            target_day_name = "Pazartesi Günü"

        target_day_idx = effective_day_idx

        # O günün derslerindeki benzersiz ders adlarını topla
        day_lessons = [l for l in lessons if l.get("y") == target_day_idx]
        distinct_books = []
        for l in sorted(day_lessons, key=lambda x: x.get("x", 0)):
            subj = l.get("text", ["", ""])[1].strip()
            if subj and subj not in ("-", "") and subj not in distinct_books:
                distinct_books.append(subj)

        if not distinct_books:
            return

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("bag-reminder-card")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_lbl = Gtk.Image.new_from_icon_name("user-home-symbolic")
        icon_lbl.set_pixel_size(20)
        top_row.append(icon_lbl)

        title_lbl = Gtk.Label()
        title_lbl.set_markup(f"<span weight='bold' size='medium'>Çantanı Hazırla: {target_day_name} Hangi Kitaplar Lazım?</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_hexpand(True)
        top_row.append(title_lbl)
        card.append(top_row)

        desc_lbl = Gtk.Label()
        desc_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>{target_day_name} programında olan dersler için kitap ve defterlerini unutma:</span>")
        desc_lbl.set_halign(Gtk.Align.START)
        card.append(desc_lbl)

        # Kitap etiketleri (Flow / Grid)
        chips_box = Gtk.FlowBox()
        chips_box.set_selection_mode(Gtk.SelectionMode.NONE)
        chips_box.set_max_children_per_line(6)
        chips_box.set_row_spacing(6)
        chips_box.set_column_spacing(6)
        chips_box.set_homogeneous(False)

        for book in distinct_books:
            chip = Gtk.Label(label=f"📖 {book.title()}")
            chip.add_css_class("book-tag")
            chips_box.append(chip)

        card.append(chips_box)
        self.bag_reminder_container.append(card)

    def render_exam_analytics(self, exams):
        """2. Özellik: Sınav Karnesi & Başarı Gelişim Grafiği (Mini Analytics)"""
        while self.exam_container.get_first_child():
            self.exam_container.remove(self.exam_container.get_first_child())

        exam_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        exam_card.add_css_class("gokturk-card")

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_icon = Gtk.Image.new_from_icon_name("view-continuous-symbolic")
        header_icon.set_pixel_size(18)
        header_lbl = Gtk.Label()
        header_lbl.set_markup("<span weight='700' size='medium'>Sınav Karnesi &amp; Başarı Gelişimi</span>")
        header_lbl.set_hexpand(True)
        header_lbl.set_halign(Gtk.Align.START)
        header_box.append(header_icon)
        header_box.append(header_lbl)
        exam_card.append(header_box)

        if not exams:
            no_exam_lbl = Gtk.Label(label="Henüz girilen bir deneme sınavı bulunmuyor.")
            no_exam_lbl.add_css_class("dim-label")
            no_exam_lbl.set_halign(Gtk.Align.START)
            exam_card.append(no_exam_lbl)
        else:
            # 1. En Son Sınav Özeti
            last_exam = exams[0]
            e_name = last_exam.get("examName", "Deneme Sınavı")
            e_date = last_exam.get("examDate", "-")
            e_point = last_exam.get("point", 0.0)
            e_net = last_exam.get("net", 0)
            e_dogru = last_exam.get("dogru", 0)
            e_yanlis = last_exam.get("yanlis", 0)

            content_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            left_box.set_hexpand(True)

            name_lbl = Gtk.Label()
            name_lbl.set_markup(f"<span weight='700'>{e_name}</span> <span size='small' foreground='#a8a8a8'>({e_date})</span>")
            name_lbl.set_halign(Gtk.Align.START)
            left_box.append(name_lbl)

            stats_lbl = Gtk.Label()
            stats_lbl.set_markup(f"<span size='small' foreground='#b8b8b8'>Net: <b>{e_net:.2f}</b>   •   Doğru: {e_dogru}   •   Yanlış: {e_yanlis}</span>")
            stats_lbl.set_halign(Gtk.Align.START)
            left_box.append(stats_lbl)

            content_hbox.append(left_box)

            right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            right_box.set_halign(Gtk.Align.END)
            right_box.set_valign(Gtk.Align.CENTER)

            point_str = f"{float(e_point):.2f}".replace(".", ",")
            point_lbl = Gtk.Label()
            point_lbl.set_markup(f"<span size='xx-large' weight='bold'>{point_str}</span>")
            point_lbl.set_halign(Gtk.Align.END)
            right_box.append(point_lbl)

            point_sub = Gtk.Label()
            point_sub.set_markup("<span size='small' foreground='#a8a8a8'>Puan</span>")
            point_sub.set_halign(Gtk.Align.END)
            right_box.append(point_sub)

            content_hbox.append(right_box)
            exam_card.append(content_hbox)

            # 2. Deneme Sınavları Gelişim Çubukları (Grafik Çizelgesi)
            chart_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            chart_group.set_margin_top(8)

            chart_title = Gtk.Label()
            chart_title.set_markup("<span size='small' weight='600' foreground='#b8b8b8'>Sınav Net Gelişim Trendi:</span>")
            chart_title.set_halign(Gtk.Align.START)
            chart_group.append(chart_title)

            # Ters kronolojik sınavları kronolojik sıraya al
            chart_exams = list(reversed(exams[:4]))
            max_net = max([float(e.get("net", 1) or 1) for e in chart_exams] + [90.0])

            for e in chart_exams:
                row_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                
                short_name = e.get("examName", "Sınav")[:22]
                lbl_name = Gtk.Label(label=short_name)
                lbl_name.set_size_request(140, -1)
                lbl_name.set_halign(Gtk.Align.START)
                lbl_name.add_css_class("caption")
                row_bar.append(lbl_name)

                # Progress Bar
                progress = Gtk.ProgressBar()
                progress.set_hexpand(True)
                progress.set_valign(Gtk.Align.CENTER)
                val = float(e.get("net", 0) or 0)
                progress.set_fraction(min(1.0, max(0.0, val / max_net)))
                row_bar.append(progress)

                net_lbl = Gtk.Label()
                net_lbl.set_markup(f"<span size='small' weight='bold'>{val:.1f} Net</span>")
                net_lbl.set_size_request(60, -1)
                net_lbl.set_halign(Gtk.Align.END)
                row_bar.append(net_lbl)

                chart_group.append(row_bar)

            exam_card.append(chart_group)

        exam_link_btn = Gtk.Button(label="›  Tüm Sınav Raporlarına Git")
        exam_link_btn.add_css_class("gokturk-action-link")
        exam_link_btn.set_halign(Gtk.Align.START)
        exam_link_btn.set_margin_top(10)
        if self.on_navigate_tab:
            exam_link_btn.connect("clicked", lambda _: self.on_navigate_tab("exams"))
        exam_card.append(exam_link_btn)

        self.exam_container.append(exam_card)
