import math
import threading
import cairo
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from api_bridge import (
    get_adaptive_index_data,
    fetch_exam_report,
    fetch_all_student_exams,
    get_cached_exam_dashboard_meta,
    get_saved_theme,
)
from views.exam_report_dialog import ExamReportWindow


class ExamsView(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.set_margin_top(20)
        self.main_box.set_margin_bottom(24)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)

        # Header Box with Title and Refresh Button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_label = Gtk.Label()
        header_label.set_markup("<span size='large' weight='bold'>📝 Sınavlar, Taramalar &amp; Gelişim Analizi</span>")
        header_label.set_halign(Gtk.Align.START)
        header_label.set_hexpand(True)
        header_box.append(header_label)

        btn_refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        btn_refresh.set_tooltip_text("Sınavları Yenile")
        btn_refresh.add_css_class("flat")
        btn_refresh.connect("clicked", lambda _: self.load_data())
        header_box.append(btn_refresh)

        self.main_box.append(header_box)

        self.current_filter = "all"  # "all", "deneme", "tarama"
        self._cached_exams = []
        self._lesson_averages = {}
        self._cached_meta = {}

        # 📊 Sınav, KPI, Trend Grafiği ve Ders Başarı Alanı
        self.summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.main_box.append(self.summary_box)

        # Filtre Seçim Butonları (Tümü / Deneme Sınavları / Tarama Sınavları)
        filter_scroll = Gtk.ScrolledWindow()
        filter_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.filter_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.filter_buttons_box.add_css_class("segmented-bar")
        filter_scroll.set_child(self.filter_buttons_box)
        self.main_box.append(filter_scroll)

        # Sınav Listesi
        self.exams_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.main_box.append(self.exams_container)

        clamp.set_child(self.main_box)
        self.set_child(clamp)

    def reset_state(self):
        """Hesap değiştiğinde ExamsView önbelleğini ve arayüzünü sıfırlar."""
        self.current_filter = "all"
        self._cached_exams = []
        self._lesson_averages.clear()
        self._cached_meta.clear()
        while child := self.summary_box.get_first_child():
            self.summary_box.remove(child)
        while child := self.filter_buttons_box.get_first_child():
            self.filter_buttons_box.remove(child)
        while child := self.exams_container.get_first_child():
            self.exams_container.remove(child)

    def load_data(self):
        def worker():
            try:
                exams = fetch_all_student_exams()
                meta = get_cached_exam_dashboard_meta()
                if not exams:
                    data = get_adaptive_index_data()
                    exams = data.get("data", {}).get("examList", []) or []

                lesson_averages = self._calculate_lesson_averages(exams)
                GLib.idle_add(self.set_exams_data, exams, lesson_averages, meta)
            except Exception as e:
                print(f"Sınavlar yükleme hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _normalize_lesson_name(self, name):
        if not name:
            return ""
        n = name.upper().strip()
        if "TÜRK" in n:
            return "Türkçe"
        if "MAT" in n:
            return "Matematik"
        if "FEN" in n:
            return "Fen Bilimleri"
        if "SOS" in n or "İNK" in n:
            return "Sosyal Bilgiler"
        if "DİN" in n:
            return "Din Kültürü"
        if "İNG" in n or "DİL" in n:
            return "İngilizce"
        return name.title()

    def _calculate_lesson_averages(self, exams):
        """Tüm deneme ve tarama sınavlarından ders bazlı net ortalamalarını paralel derler."""
        from concurrent.futures import ThreadPoolExecutor
        lesson_nets = {}
        sbs_to_fetch = []

        for e in exams:
            if e.get("isTarama"):
                for l in e.get("dasLessons", []):
                    lname = self._normalize_lesson_name(l.get("lesson", ""))
                    if lname and l.get("net") is not None:
                        try:
                            net_val = float(l.get("net"))
                            lesson_nets.setdefault(lname, []).append(net_val)
                        except Exception:
                            pass
            else:
                exam_id = e.get("examId") or e.get("sinavKod")
                exam_type = e.get("examType", "SBS")
                if exam_id:
                    sbs_to_fetch.append((exam_id, exam_type))

        if sbs_to_fetch:
            mapping = [
                (1, "Türkçe"),
                (2, "Matematik"),
                (3, "Din Kültürü"),
                (4, "Fen Bilimleri"),
                (5, "Sosyal Bilgiler"),
                (6, "İngilizce"),
            ]
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(fetch_exam_report, eid, etype) for eid, etype in sbs_to_fetch]
                for fut in futures:
                    try:
                        rep = fut.result()
                        if rep and rep.get("data"):
                            for idx, lname in mapping:
                                n = rep["data"].get(f"N{idx}")
                                if n is not None:
                                    try:
                                        net_val = float(n)
                                        lesson_nets.setdefault(lname, []).append(net_val)
                                    except Exception:
                                        pass
                    except Exception as err:
                        print(f"Ders net hesaplama hatası: {err}")

        desired_order = ["Türkçe", "Matematik", "Fen Bilimleri", "Sosyal Bilgiler", "Din Kültürü", "İngilizce"]
        result = {}
        for l in desired_order:
            if l in lesson_nets and lesson_nets[l]:
                avg = sum(lesson_nets[l]) / len(lesson_nets[l])
                result[l] = {"avg": round(avg, 2), "count": len(lesson_nets[l]), "values": lesson_nets[l]}

        for l, vals in lesson_nets.items():
            if l not in result and vals:
                avg = sum(vals) / len(vals)
                result[l] = {"avg": round(avg, 2), "count": len(vals), "values": vals}

        return result

    def set_exams_data(self, exams, lesson_averages=None, meta=None):
        self._cached_exams = exams or []
        if lesson_averages is not None:
            self._lesson_averages = lesson_averages
        self._cached_meta = meta or {}
        self.render_summary_card()
        self.build_filter_buttons()
        self.render_filtered_exams()

    def render_summary_card(self):
        """Genel KPI Metrikleri, Puan Gelişim Grafiği, Ders Başarı Oranları ve Ortalamaları Çizer."""
        child = self.summary_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.summary_box.remove(child)
            child = next_child

        if not self._cached_exams and not self._cached_meta:
            return

        all_points = [float(e.get("point") or 0) for e in self._cached_exams if e.get("point")]
        deneme_points = [float(e.get("point") or 0) for e in self._cached_exams if not e.get("isTarama") and e.get("point")]
        tarama_points = [float(e.get("point") or 0) for e in self._cached_exams if e.get("isTarama") and e.get("point")]

        all_nets = [float(e.get("net") or 0) for e in self._cached_exams if e.get("net") is not None]
        deneme_nets = [float(e.get("net") or 0) for e in self._cached_exams if not e.get("isTarama") and e.get("net") is not None]
        tarama_nets = [float(e.get("net") or 0) for e in self._cached_exams if e.get("isTarama") and e.get("net") is not None]

        def parse_rank(val):
            try:
                if val is not None and str(val).strip().isdigit():
                    return float(val)
            except Exception:
                pass
            return None

        all_gd = [parse_rank(e.get("GD")) for e in self._cached_exams if parse_rank(e.get("GD")) is not None]
        all_sd = [parse_rank(e.get("SD")) for e in self._cached_exams if parse_rank(e.get("SD")) is not None]

        deneme_gd = [parse_rank(e.get("GD")) for e in self._cached_exams if not e.get("isTarama") and parse_rank(e.get("GD")) is not None]
        deneme_sd = [parse_rank(e.get("SD")) for e in self._cached_exams if not e.get("isTarama") and parse_rank(e.get("SD")) is not None]

        tarama_gd = [parse_rank(e.get("GD")) for e in self._cached_exams if e.get("isTarama") and parse_rank(e.get("GD")) is not None]
        tarama_sd = [parse_rank(e.get("SD")) for e in self._cached_exams if e.get("isTarama") and parse_rank(e.get("SD")) is not None]

        avg_all_puan = (sum(all_points) / len(all_points)) if all_points else 0.0
        avg_deneme_puan = (sum(deneme_points) / len(deneme_points)) if deneme_points else 0.0
        avg_tarama_puan = (sum(tarama_points) / len(tarama_points)) if tarama_points else 0.0

        avg_all_net = (sum(all_nets) / len(all_nets)) if all_nets else 0.0
        avg_deneme_net = (sum(deneme_nets) / len(deneme_nets)) if deneme_nets else 0.0
        avg_tarama_net = (sum(tarama_nets) / len(tarama_nets)) if tarama_nets else 0.0

        avg_all_gd = (sum(all_gd) / len(all_gd)) if all_gd else None
        avg_all_sd = (sum(all_sd) / len(all_sd)) if all_sd else None

        avg_deneme_gd = (sum(deneme_gd) / len(deneme_gd)) if deneme_gd else None
        avg_deneme_sd = (sum(deneme_sd) / len(deneme_sd)) if deneme_sd else None

        avg_tarama_gd = (sum(tarama_gd) / len(tarama_gd)) if tarama_gd else None
        avg_tarama_sd = (sum(tarama_sd) / len(tarama_sd)) if tarama_sd else None

        kpi = self._cached_meta.get("kpi") or {}

        # =========================================================================
        # 1. BÖLÜM: GENEL KPI ANALİTİK KARTI (Arşiv Analitikleri + Genel Sıralamalar)
        # =========================================================================
        main_stat_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_stat_card.add_css_class("exam-summary-card")

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_icon = Gtk.Image.new_from_icon_name("view-continuous-symbolic")
        title_box.append(title_icon)
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='medium' weight='bold'>📊 Genel Sınav Başarısı &amp; Performans Karnesi</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)
        main_stat_card.append(title_box)

        # 8 KPI Kutusu (Grid 4x2)
        kpi_grid = Gtk.Grid()
        kpi_grid.set_column_homogeneous(True)
        kpi_grid.set_row_spacing(10)
        kpi_grid.set_column_spacing(10)

        # KPI 1: Toplam Sınav Sayısı
        exam_count_val = kpi.get("examCount") or len(self._cached_exams)
        tile_count = self._build_kpi_tile(
            title="SINAV SAYISI",
            value_str=f"{exam_count_val} Sınav",
            detail_str="Girilen deneme ve taramalar",
            badge_text=f"{len(deneme_points)}D / {len(tarama_points)}T",
            badge_class="badge-primary"
        )
        kpi_grid.attach(tile_count, 0, 0, 1, 1)

        # KPI 2: Ortalama Puan
        avg_p_val = kpi.get("avgPoint") or avg_all_puan
        tile_avg_p = self._build_kpi_tile(
            title="ORTALAMA PUAN",
            value_str=f"{avg_p_val:.2f}",
            detail_str="Tüm sınavların genel ortalaması",
            badge_text="Ortalama",
            badge_class="badge-primary"
        )
        kpi_grid.attach(tile_avg_p, 1, 0, 1, 1)

        # KPI 3: Son Puan & Değişim
        last_p_val = kpi.get("lastPoint") or (all_points[-1] if all_points else 0.0)
        delta_val = kpi.get("lastPointDelta")
        delta_str = None
        delta_badge_cls = "badge-primary"
        if delta_val is not None:
            if delta_val > 0:
                delta_str = f"+{delta_val:.2f} ↗"
                delta_badge_cls = "badge-success"
            elif delta_val < 0:
                delta_str = f"{delta_val:.2f} ↘"
                delta_badge_cls = "badge-danger"
            else:
                delta_str = "0.00"

        tile_last_p = self._build_kpi_tile(
            title="SON PUAN",
            value_str=f"{last_p_val:.2f}",
            detail_str="Son girilen deneme sınavı",
            badge_text=delta_str,
            badge_class=delta_badge_cls
        )
        kpi_grid.attach(tile_last_p, 2, 0, 1, 1)

        # KPI 4: Ortalama Başarı Oranı
        avg_succ_val = kpi.get("avgSuccess")
        if avg_succ_val is None:
            avg_succ_val = (avg_all_puan / 500.0) * 100.0 if avg_all_puan else 0.0

        tile_succ = self._build_kpi_tile(
            title="GENEL BAŞARI",
            value_str=f"%{avg_succ_val:.1f}",
            detail_str="Müfredat kazanım başarısı",
            badge_text="Net Oranı",
            badge_class="badge-success" if avg_succ_val >= 75 else "badge-primary"
        )
        kpi_grid.attach(tile_succ, 3, 0, 1, 1)

        # KPI 5: En Yüksek Puan
        max_p_val = kpi.get("maxPoint") or (max(all_points) if all_points else 0.0)
        max_p_exam = kpi.get("maxPointExamName") or "En Başarılı Sınav"
        tile_max_p = self._build_kpi_tile(
            title="EN YÜKSEK PUAN",
            value_str=f"{max_p_val:.2f}",
            detail_str=max_p_exam,
            badge_text="Zirve",
            badge_class="badge-active"
        )
        kpi_grid.attach(tile_max_p, 0, 1, 1, 1)

        # KPI 6: En Yüksek Ders
        best_l = kpi.get("bestLesson") or {}
        best_name = self._normalize_lesson_name(best_l.get("lesson") or "Sosyal Bilgiler")
        best_rate = best_l.get("successRate") or 100.0
        tile_best = self._build_kpi_tile(
            title="EN BAŞARILI DERS",
            value_str=f"%{best_rate:.1f}",
            detail_str=best_name,
            badge_text="Lider",
            badge_class="badge-success"
        )
        kpi_grid.attach(tile_best, 1, 1, 1, 1)

        # KPI 7: En Düşük / Geliştirilebilir Ders
        worst_l = kpi.get("worstLesson") or {}
        worst_name = self._normalize_lesson_name(worst_l.get("lesson") or "Matematik")
        worst_rate = worst_l.get("successRate") or 60.0
        tile_worst = self._build_kpi_tile(
            title="GELİŞTİRİLEBİLİR DERS",
            value_str=f"%{worst_rate:.1f}",
            detail_str=worst_name,
            badge_text="Hedef",
            badge_class="badge-upcoming"
        )
        kpi_grid.attach(tile_worst, 2, 1, 1, 1)

        # KPI 8: Ortalama Sıralama (Okul & Sınıf Derecesi)
        rank_parts = []
        if avg_all_gd is not None:
            rank_parts.append(f"🏫 Okul: {avg_all_gd:.1f}.")
        if avg_all_sd is not None:
            rank_parts.append(f"👥 Sınıf: {avg_all_sd:.1f}.")
        rank_display = " • ".join(rank_parts) if rank_parts else "Mevcut Değil"

        tile_rank = self._build_kpi_tile(
            title="ORTALAMA SIRALAMA",
            value_str=rank_display,
            detail_str="Sınav sıralama ortalamaları",
            badge_text="Derece",
            badge_class="badge-primary"
        )
        kpi_grid.attach(tile_rank, 3, 1, 1, 1)

        main_stat_card.append(kpi_grid)

        # Alt Bölüm: 3 Sütunlu Kategori Metrikleri (Tüm Sınavlar | Denemeler | Taramalar)
        sep_cat = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep_cat.set_margin_top(4)
        sep_cat.set_margin_bottom(4)
        main_stat_card.append(sep_cat)

        metrics_flow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        metrics_flow.set_homogeneous(True)

        col_all = self._build_stat_column(
            title="TÜM SINAVLAR",
            badge_text=f"{len(self._cached_exams)} Sınav",
            badge_class="badge-primary",
            puan_avg=avg_all_puan,
            net_avg=avg_all_net,
            gd_avg=avg_all_gd,
            sd_avg=avg_all_sd
        )
        metrics_flow.append(col_all)

        col_deneme = self._build_stat_column(
            title="DENEME SINAVLARI",
            badge_text=f"{len(deneme_points)} Deneme",
            badge_class="badge-active",
            puan_avg=avg_deneme_puan,
            net_avg=avg_deneme_net,
            gd_avg=avg_deneme_gd,
            sd_avg=avg_deneme_sd
        )
        metrics_flow.append(col_deneme)

        col_tarama = self._build_stat_column(
            title="TARAMA / DAS",
            badge_text=f"{len(tarama_points)} Tarama",
            badge_class="badge-upcoming",
            puan_avg=avg_tarama_puan,
            net_avg=avg_tarama_net,
            gd_avg=avg_tarama_gd,
            sd_avg=avg_tarama_sd
        )
        metrics_flow.append(col_tarama)

        main_stat_card.append(metrics_flow)
        self.summary_box.append(main_stat_card)

        # =========================================================================
        # 2. BÖLÜM: PUAN GELİŞİM GRAFİĞİ & ZAMAN ÇİZELGESİ (Archive Trend)
        # =========================================================================
        trend_obj = self._cached_meta.get("trend", {})
        trend_point = trend_obj.get("point", {}) if isinstance(trend_obj, dict) else {}
        trend_series = trend_point.get("series", [{}])[0].get("data", [])
        trend_x = trend_point.get("xAxis", {}).get("data", [])

        # Noktaları ve Etiketleri Hazırla
        trend_points = []
        trend_labels = []
        trend_short_titles = []

        if trend_series:
            for idx, raw_val in enumerate(trend_series):
                try:
                    if raw_val is not None:
                        val = float(raw_val)
                        trend_points.append(val)
                        x_label = trend_x[idx] if idx < len(trend_x) else f"Sınav {idx + 1}"
                        # Etiket "7.SINIF DENEME 1 | 15.09.2026" ise tarih ve kısa adı ayıkla
                        parts = [p.strip() for p in x_label.split("|")]
                        if len(parts) >= 2:
                            trend_labels.append(parts[1])
                            trend_short_titles.append(parts[0])
                        else:
                            trend_labels.append(x_label)
                            trend_short_titles.append(x_label)
                except Exception:
                    pass

        # Eğer meta trend boşsa sınav listesinden kronolojik topla
        if not trend_points:
            sorted_exams = sorted(
                [e for e in self._cached_exams if e.get("point")],
                key=lambda x: str(x.get("examDate") or "")
            )
            for idx, e in enumerate(sorted_exams):
                try:
                    p = float(e.get("point"))
                    trend_points.append(p)
                    trend_labels.append(e.get("examDate") or f"Sınav {idx+1}")
                    trend_short_titles.append(e.get("examName") or f"Sınav {idx+1}")
                except Exception:
                    pass

        if trend_points:
            chart_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            chart_card.add_css_class("exam-chart-card")

            chart_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            chart_ico = Gtk.Image.new_from_icon_name("utilities-system-monitor-symbolic")
            chart_hdr.append(chart_ico)

            chart_title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            c_lbl = Gtk.Label()
            c_lbl.set_markup("<span weight='bold'>📈 Sınav Puan Gelişim Grafiği</span>")
            c_lbl.set_halign(Gtk.Align.START)
            chart_title_box.append(c_lbl)

            c_sub = Gtk.Label()
            c_sub.set_markup("<span size='small' foreground='#b8b8b8'>Kronolojik sınav puan eğilimi ve net değişim basamakları</span>")
            c_sub.set_halign(Gtk.Align.START)
            chart_title_box.append(c_sub)

            chart_hdr.append(chart_title_box)
            chart_card.append(chart_hdr)

            # Cairo Çizim Alanı (Gtk.DrawingArea)
            drawing_area = Gtk.DrawingArea()
            drawing_area.set_content_height(160)
            drawing_area.set_hexpand(True)
            drawing_area.set_draw_func(
                lambda da, cr, w, h: self._draw_trend_chart(cr, w, h, trend_points, trend_labels, trend_short_titles)
            )
            chart_card.append(drawing_area)

            # Zaman Çizelgesi Adımları (Step Chips)
            step_scroll = Gtk.ScrolledWindow()
            step_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            step_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            step_box.set_margin_top(4)

            for i, p_val in enumerate(trend_points):
                chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                chip.add_css_class("timeline-step-chip")

                dot = Gtk.Image.new_from_icon_name("radio-checked-symbolic")
                dot.set_pixel_size(12)
                chip.append(dot)

                txt_v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
                short_name = trend_short_titles[i] if i < len(trend_short_titles) else f"Sınav {i+1}"
                date_txt = trend_labels[i] if i < len(trend_labels) else ""

                lbl_step_name = Gtk.Label()
                lbl_step_name.set_markup(f"<span size='smaller' weight='600'>{short_name}</span>")
                lbl_step_name.set_halign(Gtk.Align.START)
                txt_v.append(lbl_step_name)

                lbl_step_val = Gtk.Label()
                lbl_step_val.set_markup(f"<span size='small' foreground='#b8b8b8'>{date_txt} • <b>{p_val:.2f} Puan</b></span>")
                lbl_step_val.set_halign(Gtk.Align.START)
                txt_v.append(lbl_step_val)

                chip.append(txt_v)

                # Önceki sınava göre delta
                if i > 0:
                    diff = p_val - trend_points[i - 1]
                    diff_badge = Gtk.Label()
                    if diff > 0:
                        diff_badge.set_markup(f"<span size='smaller'><b>+{diff:.2f} ↗</b></span>")
                        diff_badge.add_css_class("badge-success")
                    elif diff < 0:
                        diff_badge.set_markup(f"<span size='smaller'><b>{diff:.2f} ↘</b></span>")
                        diff_badge.add_css_class("badge-danger")
                    else:
                        diff_badge.set_markup("<span size='smaller'><b>0.00</b></span>")
                        diff_badge.add_css_class("badge-primary")
                    chip.append(diff_badge)

                step_box.append(chip)

                if i < len(trend_points) - 1:
                    arrow = Gtk.Label(label="➔")
                    arrow.add_css_class("dim-label")
                    step_box.append(arrow)

            step_scroll.set_child(step_box)
            chart_card.append(step_scroll)

            self.summary_box.append(chart_card)

        # =========================================================================
        # 3. BÖLÜM: DERS BAZINDA BAŞARI ORANLARI & NETLER (Archive Lesson Success)
        # =========================================================================
        lesson_success_list = self._cached_meta.get("lessonSuccess", [])
        if lesson_success_list or self._lesson_averages:
            lesson_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            lesson_card.add_css_class("exam-summary-card")

            l_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            l_ico = Gtk.Image.new_from_icon_name("accessories-dictionary-symbolic")
            l_header.append(l_ico)

            l_title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            l_t = Gtk.Label()
            l_t.set_markup("<span weight='bold'>📚 Müfredat Ders Başarı Dağılımı (% Başarı &amp; Netler)</span>")
            l_t.set_halign(Gtk.Align.START)
            l_title_box.append(l_t)

            l_sub = Gtk.Label()
            l_sub.set_markup("<span size='small' foreground='#b8b8b8'>Ders bazında doğru oranı yüzdeleri ve karne net ortalamaları</span>")
            l_sub.set_halign(Gtk.Align.START)
            l_title_box.append(l_sub)

            l_header.append(l_title_box)
            lesson_card.append(l_header)

            lesson_icons = {
                "Türkçe": "emblem-documents-symbolic",
                "Matematik": "accessories-calculator-symbolic",
                "Fen Bilimleri": "applications-science-symbolic",
                "Sosyal Bilgiler": "system-search-symbolic",
                "Din Kültürü": "starred-symbolic",
                "İngilizce": "preferences-desktop-locale-symbolic",
            }

            # Ders başarı verilerini birleştir
            combined_lessons = {}
            for item in lesson_success_list:
                raw_name = item.get("lesson", "")
                norm_name = self._normalize_lesson_name(raw_name)
                rate = float(item.get("successRate") or 0.0)
                combined_lessons[norm_name] = {"rate": rate, "net": None, "count": None}

            for lname, ldata in self._lesson_averages.items():
                norm_name = self._normalize_lesson_name(lname)
                if norm_name not in combined_lessons:
                    combined_lessons[norm_name] = {"rate": None, "net": ldata.get("avg"), "count": ldata.get("count")}
                else:
                    combined_lessons[norm_name]["net"] = ldata.get("avg")
                    combined_lessons[norm_name]["count"] = ldata.get("count")

            # Dersleri 2 sütunlu şık satırlar halinde listele
            lessons_grid = Gtk.Grid()
            lessons_grid.set_column_homogeneous(True)
            lessons_grid.set_column_spacing(14)
            lessons_grid.set_row_spacing(10)

            col = 0
            row = 0
            desired_order = ["Türkçe", "Matematik", "Fen Bilimleri", "Sosyal Bilgiler", "Din Kültürü", "İngilizce"]
            ordered_keys = [k for k in desired_order if k in combined_lessons]
            for k in combined_lessons:
                if k not in ordered_keys:
                    ordered_keys.append(k)

            for lname in ordered_keys:
                ldata = combined_lessons[lname]
                row_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                row_box.add_css_class("kpi-tile")

                # Başlık ve Rozet Satırı
                top_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                ico_name = lesson_icons.get(lname, "emblem-documents-symbolic")
                icon = Gtk.Image.new_from_icon_name(ico_name)
                icon.set_pixel_size(18)
                top_line.append(icon)

                name_lbl = Gtk.Label()
                name_lbl.set_markup(f"<span weight='600'>{lname}</span>")
                name_lbl.set_halign(Gtk.Align.START)
                name_lbl.set_hexpand(True)
                top_line.append(name_lbl)

                if ldata["net"] is not None:
                    net_badge = Gtk.Label(label=f"{ldata['net']:.2f} Net")
                    net_badge.add_css_class("badge-primary")
                    top_line.append(net_badge)

                if ldata["rate"] is not None:
                    rate_val = ldata["rate"]
                    rate_badge = Gtk.Label(label=f"%{rate_val:.1f}")
                    if rate_val >= 80:
                        rate_badge.add_css_class("badge-success")
                    elif rate_val >= 65:
                        rate_badge.add_css_class("badge-primary")
                    else:
                        rate_badge.add_css_class("badge-upcoming")
                    top_line.append(rate_badge)

                row_box.append(top_line)

                # İlerleme Çubuğu (Progress Bar)
                p_fraction = (ldata["rate"] / 100.0) if ldata["rate"] is not None else 0.0
                p_fraction = max(0.0, min(1.0, p_fraction))

                pbar = Gtk.ProgressBar()
                pbar.set_fraction(p_fraction)
                pbar.add_css_class("exam-progress")
                if ldata["rate"] is not None:
                    if ldata["rate"] >= 80:
                        pbar.add_css_class("success")
                    elif ldata["rate"] < 65:
                        pbar.add_css_class("warning")
                row_box.append(pbar)

                lessons_grid.attach(row_box, col, row, 1, 1)
                col += 1
                if col > 1:
                    col = 0
                    row += 1

            lesson_card.append(lessons_grid)
            self.summary_box.append(lesson_card)

    def _draw_trend_chart(self, cr, width, height, points, labels, short_titles):
        """Cairo ile yüksek çözünürlüklü, antialiased puan eğilimi ve grafiği çizer."""
        if not points:
            return

        is_light = (get_saved_theme() == "light")
        pad_x = 55
        pad_y = 35

        min_val = min(points)
        max_val = max(points)
        spread = max_val - min_val
        if spread < 1.0:
            min_val -= 2.0
            max_val += 2.0
            spread = max_val - min_val
        else:
            min_val -= spread * 0.22
            max_val += spread * 0.22
            spread = max_val - min_val

        coords = []
        n = len(points)
        for i, pt in enumerate(points):
            x = pad_x + (i / max(1, n - 1)) * (width - 2 * pad_x)
            y = height - pad_y - ((pt - min_val) / spread) * (height - 2 * pad_y)
            coords.append((x, y))

        # Kılavuz çizgileri
        cr.set_dash([4.0, 4.0])
        if is_light:
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.08)
        else:
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.move_to(pad_x, pad_y)
        cr.line_to(width - pad_x, pad_y)
        cr.stroke()
        cr.move_to(pad_x, height - pad_y)
        cr.line_to(width - pad_x, height - pad_y)
        cr.stroke()
        cr.set_dash([])

        # Gradyan Alanı
        cr.move_to(coords[0][0], height - pad_y)
        for x, y in coords:
            cr.line_to(x, y)
        cr.line_to(coords[-1][0], height - pad_y)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_y, 0, height - pad_y)
        if is_light:
            pat.add_color_stop_rgba(0, 0.15, 0.39, 0.92, 0.22)
            pat.add_color_stop_rgba(1, 0.15, 0.39, 0.92, 0.02)
        else:
            pat.add_color_stop_rgba(0, 0.22, 0.74, 0.97, 0.28)
            pat.add_color_stop_rgba(1, 0.22, 0.74, 0.97, 0.02)
        cr.set_source(pat)
        cr.fill()

        # Çizgi
        cr.set_line_width(3.0)
        if is_light:
            cr.set_source_rgba(0.15, 0.39, 0.92, 0.95)
        else:
            cr.set_source_rgba(0.22, 0.74, 0.97, 1.0)
        cr.move_to(coords[0][0], coords[0][1])
        for x, y in coords[1:]:
            cr.line_to(x, y)
        cr.stroke()

        # Noktalar ve Yazılar
        for i, (x, y) in enumerate(coords):
            # Dış halka
            if is_light:
                cr.set_source_rgba(0.15, 0.39, 0.92, 1.0)
            else:
                cr.set_source_rgba(0.22, 0.74, 0.97, 1.0)
            cr.arc(x, y, 6, 0, 2 * math.pi)
            cr.fill()

            # İç halka
            if is_light:
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            else:
                cr.set_source_rgba(0.08, 0.12, 0.17, 1.0)
            cr.arc(x, y, 3, 0, 2 * math.pi)
            cr.fill()

            # Puan Değeri
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(12)
            if is_light:
                cr.set_source_rgba(0.10, 0.15, 0.24, 0.90)
            else:
                cr.set_source_rgba(0.95, 0.96, 0.98, 0.95)
            val_str = f"{points[i]:.2f} P"
            ext = cr.text_extents(val_str)
            cr.move_to(x - ext.width / 2, y - 10)
            cr.show_text(val_str)

            # Tarih / Etiket
            if i < len(labels) and labels[i]:
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(10)
                if is_light:
                    cr.set_source_rgba(0.35, 0.40, 0.48, 0.85)
                else:
                    cr.set_source_rgba(0.70, 0.75, 0.82, 0.80)
                lbl_str = labels[i]
                ext2 = cr.text_extents(lbl_str)
                cr.move_to(x - ext2.width / 2, height - pad_y + 18)
                cr.show_text(lbl_str)

    def _build_kpi_tile(self, title, value_str, detail_str=None, badge_text=None, badge_class="badge-primary"):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("kpi-tile")
        box.set_hexpand(True)

        top_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        t_lbl = Gtk.Label()
        t_lbl.add_css_class("kpi-title")
        t_lbl.set_text(title)
        t_lbl.set_halign(Gtk.Align.START)
        t_lbl.set_hexpand(True)
        top_h.append(t_lbl)

        if badge_text:
            badge = Gtk.Label(label=badge_text)
            badge.add_css_class(badge_class)
            top_h.append(badge)

        box.append(top_h)

        v_lbl = Gtk.Label()
        v_lbl.add_css_class("kpi-value")
        v_lbl.set_text(value_str)
        v_lbl.set_halign(Gtk.Align.START)
        box.append(v_lbl)

        if detail_str:
            d_lbl = Gtk.Label()
            d_lbl.add_css_class("kpi-detail")
            d_lbl.set_text(detail_str)
            d_lbl.set_halign(Gtk.Align.START)
            d_lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            box.append(d_lbl)

        return box

    def _build_stat_column(self, title, badge_text, badge_class, puan_avg, net_avg, gd_avg=None, sd_avg=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("exam-stat-pill")

        top_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_lbl = Gtk.Label()
        title_lbl.set_markup(f"<span size='small' weight='700' foreground='#b8b8b8'>{title}</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_hexpand(True)
        top_h.append(title_lbl)

        badge = Gtk.Label(label=badge_text)
        badge.add_css_class(badge_class)
        top_h.append(badge)
        box.append(top_h)

        # Puan Göstergesi
        puan_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        puan_lbl = Gtk.Label()
        puan_lbl.set_markup(f"<span size='x-large' weight='bold'>{puan_avg:.2f}</span> <span size='small' foreground='#b8b8b8'>Puan</span>")
        puan_lbl.set_halign(Gtk.Align.START)
        puan_h.append(puan_lbl)
        box.append(puan_h)

        # Net Göstergesi
        net_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        net_icon = Gtk.Image.new_from_icon_name("appointment-soon-symbolic")
        net_icon.set_pixel_size(14)
        net_h.append(net_icon)

        net_lbl = Gtk.Label()
        net_lbl.set_markup(f"<span size='small'>Ortalama Net: <b>{net_avg:.2f}</b></span>")
        net_lbl.set_halign(Gtk.Align.START)
        net_h.append(net_lbl)
        box.append(net_h)

        # Sıralama Göstergeleri (Okul & Sınıf)
        if gd_avg is not None or sd_avg is not None:
            rank_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            rank_box.set_margin_top(4)

            if gd_avg is not None:
                gd_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                gd_lbl = Gtk.Label()
                gd_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>🏫 Okul: <b>{gd_avg:.1f}</b>.</span>")
                gd_lbl.set_halign(Gtk.Align.START)
                gd_h.append(gd_lbl)
                rank_box.append(gd_h)

            if sd_avg is not None:
                sd_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                sd_lbl = Gtk.Label()
                sd_lbl.set_markup(f"<span size='small' foreground='#d0d0d0'>👥 Sınıf: <b>{sd_avg:.1f}</b>.</span>")
                sd_lbl.set_halign(Gtk.Align.START)
                sd_h.append(sd_lbl)
                rank_box.append(sd_h)

            box.append(rank_box)

        return box

    def build_filter_buttons(self):
        while self.filter_buttons_box.get_first_child():
            self.filter_buttons_box.remove(self.filter_buttons_box.get_first_child())

        total = len(self._cached_exams)
        deneme_count = sum(1 for e in self._cached_exams if not e.get("isTarama", False))
        tarama_count = sum(1 for e in self._cached_exams if e.get("isTarama", False))

        btn_all = Gtk.Button(label=f"Tümü ({total})")
        if self.current_filter == "all":
            btn_all.add_css_class("suggested-action")
        btn_all.connect("clicked", lambda _: self.on_filter_changed("all"))
        self.filter_buttons_box.append(btn_all)

        btn_deneme = Gtk.Button(label=f"📑 Denemeler ({deneme_count})")
        if self.current_filter == "deneme":
            btn_deneme.add_css_class("suggested-action")
        btn_deneme.connect("clicked", lambda _: self.on_filter_changed("deneme"))
        self.filter_buttons_box.append(btn_deneme)

        btn_tarama = Gtk.Button(label=f"🎯 Taramalar / DAS ({tarama_count})")
        if self.current_filter == "tarama":
            btn_tarama.add_css_class("suggested-action")
        btn_tarama.connect("clicked", lambda _: self.on_filter_changed("tarama"))
        self.filter_buttons_box.append(btn_tarama)

    def on_filter_changed(self, new_filter):
        self.current_filter = new_filter
        self.build_filter_buttons()
        self.render_filtered_exams()

    def render_filtered_exams(self):
        child = self.exams_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.exams_container.remove(child)
            child = next_child

        exams_group = Adw.PreferencesGroup()
        exams_group.set_title("Planlanan ve Girilen Sınavlar &amp; Taramalar")
        exams_group.set_description("Puan, net ve soru detaylarını görmek için sınava tıklayın")

        visible_exams = []
        for e in self._cached_exams:
            is_tarama = e.get("isTarama", False)
            if self.current_filter == "deneme" and is_tarama:
                continue
            if self.current_filter == "tarama" and not is_tarama:
                continue
            visible_exams.append(e)

        if not visible_exams:
            row = Adw.ActionRow()
            row.set_title("Seçilen kategoride kayıtlı sınav veya tarama bulunamadı.")
            exams_group.add(row)
        else:
            for idx, s in enumerate(visible_exams):
                category = s.get("examCategory", "Sınav")
                ad = s.get("examName") or s.get("sinavAd", "-")
                tarih = s.get("examDate") or s.get("sinavTarih", "-")
                puan = s.get("point") or s.get("Puan")
                net = s.get("net")
                is_tarama = s.get("isTarama", False)

                row = Adw.ActionRow()
                row.set_title(f"[{category}] {ad}")

                sub_parts = [f"Tarih: {tarih}"]
                if puan:
                    sub_parts.append(f"Puan: {puan}")
                if net is not None:
                    sub_parts.append(f"Net: {net}")
                if s.get("GD") is not None:
                    sub_parts.append(f"Okul Sıra: {s.get('GD')}")
                if s.get("SD") is not None:
                    sub_parts.append(f"Sınıf Sıra: {s.get('SD')}")

                row.set_subtitle("  •  ".join(sub_parts))
                row.set_icon_name("starred-symbolic" if is_tarama else "emblem-documents-symbolic")
                row.set_activatable(True)

                if puan:
                    p_badge = Gtk.Label(label=f"{puan} Puan")
                    p_badge.add_css_class("badge-active" if is_tarama else "badge-primary")
                    row.add_suffix(p_badge)

                # Karneyi incele butonu
                btn = Gtk.Button(label="Karne & Netler")
                btn.add_css_class("suggested-action")
                btn.connect("clicked", lambda _, item=s, eidx=idx: self.on_exam_item_clicked(item, eidx))
                row.add_suffix(btn)

                # Satır tıklaması
                row.connect("activated", lambda _, item=s, eidx=idx: self.on_exam_item_clicked(item, eidx))

                exams_group.add(row)

        self.exams_container.append(exams_group)

    def on_exam_item_clicked(self, exam_item, exam_index=0):
        exam_id = exam_item.get("examId") or exam_item.get("sinavKod")
        exam_type = exam_item.get("examType", "SBS")
        exam_title = exam_item.get("examName") or exam_item.get("sinavAd", "Sınav")
        is_tarama = exam_item.get("isTarama", False)

        if is_tarama:
            das_lessons = exam_item.get("dasLessons", [])
            report_synthetic = {
                "success": True,
                "data": {
                    "Puan": exam_item.get("point"),
                    "N7": exam_item.get("net"),
                    "D7": exam_item.get("dogru"),
                    "Y7": exam_item.get("yanlis"),
                    "SD": exam_item.get("SD"),
                    "GD": exam_item.get("GD"),
                    "sinavAd": exam_title,
                    "sinavKod": exam_id,
                    "sinavTarih": exam_item.get("examDate"),
                },
                "subanal": [
                    {
                        "lesson": l.get("lesson"),
                        "konuAd": f"Tarama Başarısı (Soru: {l.get('questionCount')})",
                        "Dog": l.get("dogru"),
                        "Yan": l.get("yanlis"),
                        "Bas": round((float(l.get("dogru") or 0) / float(l.get("questionCount") or 1)) * 100, 1)
                    }
                    for l in das_lessons
                ]
            }
            for l_idx, l_obj in enumerate(das_lessons, start=1):
                report_synthetic["data"][f"SR{l_idx}"] = l_obj.get("questionCount")
                report_synthetic["data"][f"D{l_idx}"] = l_obj.get("dogru")
                report_synthetic["data"][f"Y{l_idx}"] = l_obj.get("yanlis")
                report_synthetic["data"][f"N{l_idx}"] = l_obj.get("net")

            self.show_report_dialog(exam_title, report_synthetic, exam_index, exam_type="DAS")
            return

        def worker():
            try:
                report = fetch_exam_report(exam_id, exam_type)
                if report and report.get("success"):
                    GLib.idle_add(self.show_report_dialog, exam_title, report, exam_index, exam_type)
                else:
                    GLib.idle_add(self.show_not_ready_dialog, exam_title)
            except Exception as e:
                print(f"Karne açma hatası: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def show_report_dialog(self, exam_title, report_json, exam_index=0, exam_type="SBS"):
        root_window = self.get_root()
        dialog = ExamReportWindow(root_window, exam_title, report_json, exam_index=exam_index, exam_type=exam_type)
        dialog.present()

    def show_not_ready_dialog(self, exam_title):
        root_window = self.get_root()
        alert = Adw.AlertDialog.new(
            "Karne Henüz Yüklenmedi",
            f"'{exam_title}' sınavının sonuçları ve karnesi okul tarafından henüz sisteme işlenmemiş."
        )
        alert.add_response("ok", "Tamam")
        alert.present(root_window)
