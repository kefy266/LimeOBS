"""
LimeOBS Qt Quick arayüzünün Python arka ucu.

OBS ile ilgili her şey mevcut modüllerde (akbim_frontend/api_bridge.py, food_menu.py, ai_assistant.py);
bu sınıf yalnızca onları arka planda çağırır ve sonuçları QML'in doğrudan gösterebileceği
basit listelere/sözlüklere çevirir. Ağ işleri iş parçacığında yapılır, sonuç ana iş parçacığına
_resultReady sinyaliyle döner.
"""
import html
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

import akbim_api
import api_bridge
import ai_assistant
from food_menu import parse_day_date_obj, parse_food_menu

DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
          "Eylül", "Ekim", "Kasım", "Aralık"]


def tr_title(text):
    def word(w):
        low = w.replace("I", "ı").replace("İ", "i").lower()
        if low in ("ve", "ile", "veya"):
            return low
        return {"i": "İ", "ı": "I"}.get(low[:1], low[:1].upper()) + low[1:]
    return " ".join(word(w) for w in (text or "").split())


def fmt_day(d):
    return f"{d.day} {MONTHS[d.month - 1]} {DAY_NAMES[d.weekday()]}"


def fmt_short(d):
    return f"{d.day} {MONTHS[d.month - 1]}"


def next_school_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def greeting(now):
    if now.hour < 12:
        return "Günaydın"
    if now.hour < 18:
        return "İyi günler"
    return "İyi akşamlar"


class Backend(QObject):
    # QML'e açılan durum değişiklikleri
    loggedInChanged = Signal()
    busyChanged = Signal()
    profileChanged = Signal()
    themeModeChanged = Signal()
    dataChanged = Signal(str)          # hangi sayfanın verisi yenilendi
    loadingChanged = Signal()

    loginFailed = Signal(str)
    toast = Signal(str)
    mailLoaded = Signal("QVariantMap")
    assistantDelta = Signal(str)
    assistantDone = Signal()
    assistantFailed = Signal(str)

    # iş parçacıklarından ana iş parçacığına
    _resultReady = Signal(str, "QVariant")
    _loginResult = Signal(bool, str)

    def __init__(self, root_dir):
        super().__init__()
        self._root = Path(root_dir)
        self._logged_in = False
        self._busy = False
        self._profile = {}
        self._data = {}
        self._loading = set()
        self._theme_mode = api_bridge.get_saved_theme() if api_bridge.get_saved_theme() in ("system", "light", "dark") else "system"
        self._conversation = ai_assistant.Conversation()
        self._resultReady.connect(self._on_result)
        self._loginResult.connect(self._on_login_result)
        akbim_api.BASEURL = api_bridge.get_saved_base_url()

    # ------------------------------------------------------------------ özellikler

    def _get_logged_in(self):
        return self._logged_in

    loggedIn = Property(bool, _get_logged_in, notify=loggedInChanged)

    def _get_busy(self):
        return self._busy

    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_profile(self):
        return self._profile

    profile = Property("QVariantMap", _get_profile, notify=profileChanged)

    def _get_theme_mode(self):
        return self._theme_mode

    def _set_theme_mode(self, mode):
        if mode != self._theme_mode:
            self._theme_mode = mode
            api_bridge.save_theme(mode)
            self.themeModeChanged.emit()

    themeMode = Property(str, _get_theme_mode, _set_theme_mode, notify=themeModeChanged)

    def _get_loading(self):
        return sorted(self._loading)

    loadingPages = Property("QVariantList", _get_loading, notify=loadingChanged)

    @Slot(str, result="QVariant")
    def page(self, name):
        return self._data.get(name)

    # ------------------------------------------------------------------ giriş

    def _set_busy(self, value):
        self._busy = value
        self.busyChanged.emit()

    @Slot()
    def tryAutoLogin(self):
        """Kayıtlı oturum ya da anahtarlıktaki bilgilerle sessizce giriş dener."""
        self._set_busy(True)

        def worker():
            ok = False
            try:
                akbim_api.load_session()
                ok = api_bridge.ensure_valid_session()
            except Exception:
                ok = False
            self._loginResult.emit(ok, "")
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, str, bool)
    def login(self, tc, password, remember):
        tc, password = tc.strip(), password.strip()
        if not tc or not password:
            self.loginFailed.emit("T.C. kimlik numaranızı ve şifrenizi girin.")
            return
        api_bridge.clear_active_session(clear_saved_login=False)
        self._set_busy(True)

        def worker():
            try:
                result = akbim_api.login(tc, password)
            except Exception:
                self._loginResult.emit(False, "Okul sunucusuna bağlanılamadı. İnternet bağlantınızı kontrol edin.")
                return
            if not result.get("success"):
                self._loginResult.emit(False, result.get("msg") or "T.C. kimlik numarası ya da şifre yanlış.")
                return
            if remember:
                akbim_api.save_session()
                api_bridge.save_credentials(tc, password)
            else:
                api_bridge.clear_saved_credentials()
                Path(akbim_api.COOKIE_FILE).unlink(missing_ok=True)
            api_bridge.reset_session_expired_flag()
            self._loginResult.emit(True, "")
        threading.Thread(target=worker, daemon=True).start()

    def _on_login_result(self, ok, message):
        self._set_busy(False)
        if not ok:
            if message:
                self.loginFailed.emit(message)
            return
        self._logged_in = True
        self.loggedInChanged.emit()
        self.refresh("profile")
        self.refresh("home")

    @Slot()
    def logout(self):
        api_bridge.clear_active_session(clear_saved_login=True)
        self._conversation.reset()
        self._data.clear()
        self._profile = {}
        self._logged_in = False
        self.profileChanged.emit()
        self.loggedInChanged.emit()

    # ------------------------------------------------------------------ veri yükleme

    @Slot(str)
    def refresh(self, name):
        loader = getattr(self, f"_load_{name}", None)
        if loader is None or name in self._loading:
            return
        self._loading.add(name)
        self.loadingChanged.emit()

        def worker():
            try:
                result = loader()
            except Exception as e:
                print(f"[LimeOBS] {name} yüklenemedi: {type(e).__name__}: {e}")
                result = {"error": "Veriler alınamadı. Bağlantınızı kontrol edip yenileyin."}
            self._resultReady.emit(name, result)
        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, name, result):
        self._loading.discard(name)
        self.loadingChanged.emit()
        if name == "profile":
            if not (result or {}).get("error"):
                self._profile = result or {}
                self.profileChanged.emit()
        self._data[name] = result
        self.dataChanged.emit(name)

    def _load_profile(self):
        prof = api_bridge.get_adaptive_profile_data() or {}
        meta = api_bridge.get_school_metadata() or {}
        is_parent = prof.get("role") == "Veli"
        name = (prof.get("parent_name") if is_parent else prof.get("student_name")) or "Öğrenci"
        parts = [p for p in (prof.get("student_class") and f"Sınıf {prof['student_class']}",
                             prof.get("student_no") and f"No {prof['student_no']}") if p]
        photo = prof.get("photo_bytes")
        photo_url = ""
        if photo:
            cache = self._root / ".cache"
            cache.mkdir(exist_ok=True)
            (cache / "photo.jpg").write_bytes(photo)
            photo_url = (cache / "photo.jpg").as_uri() + f"?{len(photo)}"

        # OBS profil alanları ('student_' önekli kopyalar hariç)
        raw = prof.get("raw_fields") or {}
        fields = [{"label": k, "value": tr_title(v) if k == "İsim Soyisim" else str(v)}
                  for k, v in raw.items() if not k.startswith(("student_", "parent_")) and v]
        if prof.get("parent_name") and not is_parent:
            fields.append({"label": "Veli", "value": tr_title(prof["parent_name"])})
        fields += [{"label": "Okul", "value": meta.get("school_name") or "Akbim OBS"}]
        if meta.get("academic_term"):
            fields.append({"label": "Eğitim dönemi", "value": meta["academic_term"]})

        return {
            "name": tr_title(name),
            "initial": tr_title(name)[:1],
            "subtitle": "Veli hesabı" if is_parent else " • ".join(parts),
            "school": meta.get("school_name") or "Akbim OBS",
            "term": meta.get("academic_term") or "",
            "photoUrl": photo_url,
            "fields": fields,
        }

    # --- yardımcılar

    def _index(self):
        return (api_bridge.get_adaptive_index_data() or {}).get("data") or {}

    @staticmethod
    def _lessons(index, day):
        sched = (index.get("lessonSchedule") or {}).get("data") or {}
        x_info = sched.get("xInfo") or []
        out = []
        for cell in sorted(sched.get("data") or [], key=lambda c: c.get("x") or 0):
            if cell.get("y") != day.isoweekday():
                continue
            text = cell.get("text") or []
            x = cell.get("x") or 0
            slot = x_info[x - 1][0] if 0 < x <= len(x_info) and x_info[x - 1] else ""
            out.append({
                "time": slot.replace(" ", ""),
                "lesson": tr_title(text[1] if len(text) > 1 else (text[0] if text else "")),
                "teacher": tr_title(text[0]) if len(text) > 1 else "",
            })
        return out

    @staticmethod
    def _menus():
        data = api_bridge.fetch_food_list_data()
        return parse_food_menu(data.get("pdf_bytes")) if data.get("pdf_bytes") else []

    @staticmethod
    def _homeworks():
        today = date.today()
        out = []
        for h in api_bridge.fetch_homeworks_list() or []:
            try:
                end = datetime.strptime(h.get("endDate", ""), "%Y-%m-%d").date()
            except ValueError:
                end = None
            done = h.get("status") == 1
            days_left = (end - today).days if end else None
            out.append({
                "id": h.get("id"),
                "title": h.get("title", ""),
                "lesson": tr_title(h.get("lesson", "")),
                "teacher": tr_title(h.get("teaNameSurname", "")),
                "status": h.get("statusName", ""),
                "done": done,
                "end": fmt_short(end) if end else "",
                "endDate": end.isoformat() if end else "",
                "daysLeft": days_left if days_left is not None else 9999,
                "due": ("Bugün" if days_left == 0 else "Yarın" if days_left == 1 else
                        f"{days_left} gün" if days_left and days_left > 0 else "Süresi geçti") if end else "",
                "hasFile": bool(h.get("hasAttachFile")),
            })
        return out

    # --- sayfalar

    @staticmethod
    def _status_text(now):
        wd = now.weekday()
        if wd == 0:
            return "Yeni hafta başlıyor!"
        if wd == 1:
            return "Hafta hızlanıyor, tempoya ayak uydur!"
        if wd == 2:
            return "Hafta ortasındasın, iyi gidiyorsun!"
        if wd == 3:
            return "Hafta bitiyor, iyi dinlen!"
        if wd == 4 and (now.hour, now.minute) < (16, 30):
            return "Haftanın son dersleri, gayret!"
        return "Bu hafta bitti, haftaya hazırlan!"

    def _load_home(self):
        now = datetime.now()
        today = now.date()
        index = self._index()
        # GTK ile aynı kural: gün 16:30'da biter, hafta sonu Pazartesi'ye bakılır
        eff = api_bridge.get_effective_school_date(now)
        if eff == today:
            eff_label = "Bugün"
        elif eff == today + timedelta(days=1):
            eff_label = "Yarın"
        else:
            eff_label = DAY_NAMES[eff.weekday()]

        today_lessons = self._lessons(index, today) if today.weekday() < 5 else []
        eff_lessons = self._lessons(index, eff)

        meals = []
        for week in self._menus():
            for d in week["days"]:
                if parse_day_date_obj(d["date"], default_year=today.year) == eff:
                    meals = [tr_title(m) for m in d["meals"] if m.strip().lower() not in ("bardak su", "su")]
        main_dish = next((m for m in meals[1:] if "çorba" not in m.lower()), meals[0] if meals else "")
        rest = [m for m in meals if m != main_dish]

        pending = sorted([h for h in self._homeworks() if not h["done"] and h["daysLeft"] >= 0],
                         key=lambda h: h["daysLeft"])
        if pending:
            hw_sub = f"En yakın: {pending[0]['title']} ({pending[0]['due'].lower()})"
        else:
            hw_sub = "Bekleyen ödev yok 🎉"

        unique_books = []
        for lesson in eff_lessons:
            if lesson["lesson"] and lesson["lesson"] not in unique_books:
                unique_books.append(lesson["lesson"])

        exams = [e for e in self._exam_records(with_reports=False) if e["kind"] == "deneme"][-3:]

        first = (self._profile.get("name") or "").split(" ")[0]
        return {
            "title": f"Merhaba {first}" if first else "Merhaba",
            "status": self._status_text(now),
            "date": f"{today.day} {MONTHS[today.month - 1]} {today.year} {DAY_NAMES[today.weekday()]}",
            "todaySlots": [{"lesson": l["lesson"], "start": l["time"].split("-")[0], "end": l["time"].split("-")[-1]}
                           for l in today_lessons if "-" in l["time"]],
            "bagTitle": f"{eff_label} ({DAY_NAMES[eff.weekday()]})" if eff_label in ("Bugün", "Yarın") else f"{eff_label} günü",
            "bagLessons": unique_books,
            "foodTitle": {"Bugün": "Bugünün ana yemeği", "Yarın": "Yarının ana yemeği"}.get(eff_label, f"{eff_label} ana yemeği"),
            "mainDish": main_dish,
            "restMenu": " • ".join(rest),
            "homeworkCount": len(pending),
            "homeworkSub": hw_sub,
            "scheduleTitle": f"Ders Programı • {DAY_NAMES[eff.weekday()]}",
            "scheduleBadge": eff_label,
            "lessons": eff_lessons,
            "exams": list(reversed(exams)),
        }

    def _load_schedule(self):
        index = self._index()
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        if today.weekday() >= 5:
            monday += timedelta(days=7)
        days = []
        for i in range(5):
            d = monday + timedelta(days=i)
            days.append({"name": DAY_NAMES[i], "date": fmt_short(d), "isToday": d == today,
                         "lessons": self._lessons(index, d)})
        return {"days": days}

    def _load_homework(self):
        items = self._homeworks()
        pending = sorted([h for h in items if not h["done"] and h["daysLeft"] >= 0], key=lambda h: h["daysLeft"])
        past = sorted([h for h in items if h["done"] or h["daysLeft"] < 0], key=lambda h: h["endDate"], reverse=True)
        return {"pending": pending, "past": past[:40]}

    _LESSONS = ["Türkçe", "Matematik", "Din Kültürü", "Fen Bilimleri", "Sosyal Bilgiler", "İngilizce"]
    _LESSON_ALIASES = {"türkçe": "Türkçe", "matematik": "Matematik", "din": "Din Kültürü", "fen": "Fen Bilimleri",
                       "sosyal": "Sosyal Bilgiler", "ingilizce": "İngilizce", "inkılap": "İnkılap Tarihi"}

    @classmethod
    def _lesson_name(cls, raw):
        low = (raw or "").replace("I", "ı").replace("İ", "i").lower()
        for key, name in cls._LESSON_ALIASES.items():
            if low.startswith(key):
                return name
        return tr_title(raw)

    @staticmethod
    def _num(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _exam_records(self, with_reports=True):
        """Sınavları eskiden yeniye; with_reports=True ise denemelerin ders bazlı karnesini de ekler."""
        from concurrent.futures import ThreadPoolExecutor

        raw = api_bridge.fetch_all_student_exams() or []
        reports = {}
        if with_reports:
            ids = [e.get("examId") for e in raw if not e.get("isTarama") and e.get("examId")]
            with ThreadPoolExecutor(max_workers=4) as pool:
                for eid, rep in zip(ids, pool.map(lambda i: api_bridge.fetch_exam_report(i, "SBS"), ids)):
                    reports[eid] = (rep or {}).get("data") or {}

        out = []
        for e in raw:
            try:
                d = datetime.strptime(e.get("examDate", ""), "%d.%m.%Y").date()
            except ValueError:
                continue
            name = tr_title(e.get("examName", ""))
            kind = "tarama" if e.get("isTarama") else ("deneme" if "deneme" in name.lower() else "diger")
            lessons = []
            if e.get("isTarama"):
                for l in e.get("dasLessons") or []:
                    q, dg, yn = (self._num(l.get(k)) or 0 for k in ("questionCount", "dogru", "yanlis"))
                    lessons.append({"name": self._lesson_name(l.get("lesson")), "q": q, "d": dg, "y": yn,
                                    "b": max(0, q - dg - yn), "net": self._num(l.get("net")) or 0})
            elif reports.get(e.get("examId")):
                rep = reports[e["examId"]]
                for i, lname in enumerate(self._LESSONS, start=1):
                    if rep.get(f"N{i}") is None:
                        continue
                    # BO{i} boş sayısı değil başarı yüzdesi; boş = soru - doğru - yanlış
                    q, dg, yn = (self._num(rep.get(f"{k}{i}")) or 0 for k in ("SR", "D", "Y"))
                    lessons.append({"name": lname, "q": q, "d": dg, "y": yn, "b": max(0, q - dg - yn),
                                    "net": self._num(rep.get(f"N{i}")) or 0})
            out.append({
                "id": str(e.get("examId") or ""), "name": name, "date": fmt_short(d), "sort": d.isoformat(),
                "kind": kind, "point": round(self._num(e.get("point")) or 0, 2),
                "net": round(self._num(e.get("net")) or 0, 2), "dogru": e.get("dogru") or 0,
                "yanlis": e.get("yanlis") or 0, "bos": e.get("bos") or 0, "q": e.get("questionCount") or 0,
                "rate": e.get("successRate") or 0, "classRank": self._num(e.get("SD")) or 0,
                "schoolRank": self._num(e.get("GD")) or 0, "lessons": lessons,
            })
        out.sort(key=lambda x: x["sort"])
        return out

    def _load_exams(self):
        return {"exams": list(reversed(self._exam_records()))}

    def _load_food(self):
        today = date.today()
        weeks = []
        current = 0
        for w in self._menus():
            days = []
            for d in w["days"]:
                dd = parse_day_date_obj(d["date"], default_year=today.year)
                days.append({"date": d["date"], "isToday": dd == today,
                             "meals": [tr_title(m) for m in d["meals"] if m.strip().lower() not in ("bardak su", "su")]})
                if dd and dd >= today and not current:
                    current = len(weeks)
            weeks.append({"title": f"{w['week_num']}. Hafta", "days": days})
        return {"weeks": weeks, "current": current}

    def _load_messages(self):
        inbox, sent, _ = api_bridge.fetch_messages_data()
        def row(m, outgoing):
            return {"id": str(m.get("id")), "who": m.get("sender", "") if not outgoing else "Siz",
                    "title": m.get("mailTitle", ""), "preview": m.get("mailPreview", ""),
                    "date": (m.get("sendDate") or "").split(" ")[0], "unread": not outgoing and not m.get("readDate")}
        return {"inbox": [row(m, False) for m in inbox or []], "sent": [row(m, True) for m in sent or []]}

    @Slot(str)
    def openMail(self, mail_id):
        def worker():
            content = api_bridge.fetch_mail_content(mail_id) or {}
            body = content.get("mailContent") or content.get("content") or ""
            body = re.sub(r"<br\s*/?>|</p>", "\n", body)
            body = html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
            self._resultReady.emit("mail", {"id": mail_id, "title": content.get("mailTitle", ""),
                                            "who": content.get("sender", ""), "body": body})
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, str, str)
    def changePassword(self, old, new, new_again):
        def worker():
            try:
                res = api_bridge.change_user_password(old, new, new_again)
            except Exception:
                res = {"success": False, "message": "Okul sunucusuna bağlanılamadı."}
            self._resultReady.emit("password", {"ok": bool(res.get("success")), "message": res.get("message", "")})
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ asistan

    @Slot(result=bool)
    def assistantAvailable(self):
        return ai_assistant.service_configured()

    @Slot(str)
    def ask(self, question):
        question = question.strip()
        if not question:
            return

        def worker():
            try:
                self._conversation.ask(question, self.assistantDelta.emit)
                self.assistantDone.emit()
            except ai_assistant.AssistantError as e:
                self.assistantFailed.emit(str(e))
            except Exception as e:
                print(f"[LimeOBS] asistan hatası: {type(e).__name__}: {e}")
                self.assistantFailed.emit("Beklenmeyen bir hata oluştu. Tekrar deneyin.")
        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def resetChat(self):
        self._conversation.reset()
