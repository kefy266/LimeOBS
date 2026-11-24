"""
LimeOBS Qt Quick arayüzünün Python arka ucu.

OBS ile ilgili her şey mevcut modüllerde (akbim_frontend/api_bridge.py, food_menu.py, ai_assistant.py);
bu sınıf yalnızca onları arka planda çağırır ve sonuçları QML'in doğrudan gösterebileceği
basit listelere/sözlüklere çevirir. Ağ işleri iş parçacığında yapılır, sonuç ana iş parçacığına
_resultReady sinyaliyle döner.
"""
import html
import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

import akbim_api
import api_bridge
import ai_assistant
import school_calendar
import telegram_notify
import updater
from version import VERSION
from food_menu import parse_day_date_obj, parse_food_menu

try:  # QtMultimedia (PySide6-Addons) yoksa ses/video dosyaları harici programda açılır
    from PySide6 import QtMultimedia  # noqa: F401
    MEDIA_OK = True
except ImportError:
    MEDIA_OK = False
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".opus", ".flac", ".wma"}
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".3gp", ".mpeg", ".mpg"}

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
    return school_calendar.next_school_day(d)


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
    mediaReady = Signal(str, str, bool)  # dosya adresi, ad, yalnızca ses mi
    desktopNotify = Signal(str, str)     # sistem tepsisi bildirimi: başlık, metin
    trayEnabledChanged = Signal()
    updateChanged = Signal()
    _updateFound = Signal("QVariant", bool)
    _updateProgress = Signal(float)
    _updateFailed = Signal(str)
    _quitRequested = Signal()
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
        # Telegram bildirimleri: uygulama açıkken 15 dakikada bir yeni kayıt kontrolü
        self._tg_timer = QTimer(self)
        self._tg_timer.setInterval(telegram_notify.CHECK_INTERVAL_MIN * 60 * 1000)
        self._tg_timer.timeout.connect(self._telegram_check)
        self._tg_waiting = False
        self._tg_waiting_bot = ""
        self._tg_checking = False
        # Sistem tepsisi: pencere kapatılınca arka planda çalışıp yeni kayıtları masaüstüne bildirir
        self._tray_available = False
        self._tray_enabled = self._load_desktop_prefs().get("tray", True)
        self._desk_timer = QTimer(self)
        self._desk_timer.setInterval(15 * 60 * 1000)
        self._desk_timer.timeout.connect(self._desktop_check)
        self._desk_checking = False
        # Otomatik güncelleme: açılıştan kısa süre sonra ve 6 saatte bir denetlenir
        self._update_info = {}
        self._update_state = ""       # "", "indiriliyor", "kuruluyor"
        self._update_progress = 0.0
        self._update_checking = False
        self._updateFound.connect(self._on_update_found)
        self._updateProgress.connect(self._on_update_progress)
        self._updateFailed.connect(self._on_update_failed)
        self._quitRequested.connect(self._quit_app)
        self._upd_timer = QTimer(self)
        self._upd_timer.setInterval(6 * 3600 * 1000)
        self._upd_timer.timeout.connect(lambda: self.checkUpdates(False))
        self._upd_timer.start()
        QTimer.singleShot(15_000, lambda: self.checkUpdates(False))
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
        if not akbim_api.BASEURL:
            return  # okul adresi henüz girilmemiş: giriş ekranı
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

    schoolUrlChanged = Signal()

    def _get_school_url(self):
        return akbim_api.BASEURL.replace("https://", "").replace("http://", "")

    schoolUrl = Property(str, _get_school_url, notify=schoolUrlChanged)

    def _apply_school(self, url):
        """Akbim OBS kullanan okulun adresini ayarlar (ör. okuladiobs.com). Döner: geçerli mi."""
        url = (url or "").strip()
        if not url or " " in url or "." not in url:
            self.loginFailed.emit("Geçerli bir okul OBS adresi yaz (ör. okuladiobs.com).")
            return False
        api_bridge.clear_active_session(clear_saved_login=False)
        api_bridge.set_base_url(url)
        self.schoolUrlChanged.emit()
        return True

    @Slot(str)
    def setSchoolUrl(self, url):
        self._apply_school(url)

    @Slot(str, str, str, bool)
    def login(self, school, tc, password, remember):
        tc, password, school = tc.strip(), password.strip(), (school or "").strip()
        if not school:
            self.loginFailed.emit("Okulunun OBS adresini yaz (ör. okuladiobs.com).")
            return
        if school.replace("https://", "").replace("http://", "").rstrip("/") != self._get_school_url():
            if not self._apply_school(school):
                return
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
        if telegram_notify.is_linked():
            self._tg_timer.start()
            QTimer.singleShot(60_000, self._telegram_check)
        self._desk_timer.start()
        QTimer.singleShot(90_000, self._desktop_check)

    @Slot()
    def logout(self):
        self._desk_timer.stop()
        try:
            (self._root / "masaustu_gorulen.json").unlink(missing_ok=True)
        except OSError:
            pass
        # Telegram bağlantısı bu hesaba aittir; başka biri giriş yaparsa onun bildirimleri gitmesin
        self._tg_timer.stop()
        if telegram_notify.is_linked():
            threading.Thread(target=self._telegram_forget, daemon=True).start()
        api_bridge.clear_active_session(clear_saved_login=True)
        self._conversation.reset()
        self._data.clear()
        self._profile = {}
        self._logged_in = False
        self.profileChanged.emit()
        self.loggedInChanged.emit()

    # ------------------------------------------------------------------ Telegram bildirimleri

    def _telegram_command(self):
        """Uygulama kapalıyken bildirim kontrolü için çalıştırılacak komut."""
        import os
        import sys
        if getattr(sys, "frozen", False):
            return [os.environ.get("APPIMAGE") or sys.executable, "--bildirim-kontrol"]
        return [sys.executable, str(Path(__file__).resolve().parent / "main.py"), "--bildirim-kontrol"]

    _UNIT = "limeobs-telefon-bildirim"

    def _systemd_dir(self):
        import os
        return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd" / "user"

    def _background_supported(self):
        import shutil
        import sys
        return sys.platform.startswith("linux") and shutil.which("systemctl") is not None

    def _background_enabled(self):
        return (self._systemd_dir() / f"{self._UNIT}.timer").exists()

    def _set_background(self, on):
        import subprocess
        d = self._systemd_dir()
        timer, service = d / f"{self._UNIT}.timer", d / f"{self._UNIT}.service"
        if on:
            d.mkdir(parents=True, exist_ok=True)
            cmd = " ".join(f'"{c}"' for c in self._telegram_command())
            service.write_text(
                "[Unit]\nDescription=LimeOBS telefon bildirimleri (Telegram)\nAfter=network-online.target\n\n"
                f"[Service]\nType=oneshot\nExecStart={cmd}\n", encoding="utf-8")
            timer.write_text(
                "[Unit]\nDescription=LimeOBS telefon bildirimleri (15 dakikada bir)\n\n"
                f"[Timer]\nOnBootSec=3min\nOnUnitActiveSec={telegram_notify.CHECK_INTERVAL_MIN}min\nPersistent=true\n\n"
                "[Install]\nWantedBy=timers.target\n", encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
            subprocess.run(["systemctl", "--user", "enable", "--now", f"{self._UNIT}.timer"], check=False)
        else:
            subprocess.run(["systemctl", "--user", "disable", "--now", f"{self._UNIT}.timer"], check=False)
            timer.unlink(missing_ok=True)
            service.unlink(missing_ok=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

    def _load_telegram(self):
        settings = telegram_notify.load_settings(self._root)
        return {
            "linked": telegram_notify.is_linked(),
            "bot": settings.get("bot", ""),
            "waiting": self._tg_waiting,
            "waitingBot": self._tg_waiting_bot,
            "kinds": [{"key": k, "label": v, "on": k in (settings.get("kinds") or [])}
                      for k, v in telegram_notify.LABELS.items()],
            "backgroundSupported": self._background_supported(),
            "background": self._background_enabled(),
            "interval": telegram_notify.CHECK_INTERVAL_MIN,
        }

    def _telegram_run(self, job, done_message=None):
        def worker():
            try:
                job()
                if done_message:
                    self.toast.emit(done_message)
            except telegram_notify.TelegramError as e:
                self.toast.emit(str(e))
            except Exception as e:
                print(f"[LimeOBS] Telegram: {type(e).__name__}: {e}")
                self.toast.emit("Telegram işlemi başarısız oldu.")
            self._resultReady.emit("telegram", self._load_telegram())
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str)
    def telegramConnect(self, token):
        """Kullanıcının kendi bot anahtarıyla bağlanır."""
        if self._tg_waiting:
            return
        token = (token or "").strip()

        def job():
            bot = telegram_notify.verify_token(token)
            self._tg_waiting, self._tg_waiting_bot = True, bot
            self._resultReady.emit("telegram", self._load_telegram())
            import webbrowser
            webbrowser.open(f"https://t.me/{bot}")
            try:
                chat, name = telegram_notify.wait_for_chat(token, cancelled=lambda: not self._tg_waiting)
            finally:
                self._tg_waiting, self._tg_waiting_bot = False, ""
            if not chat:
                raise telegram_notify.TelegramError(f"@{bot} sohbetinde Başlat'a basılmadı. Tekrar deneyebilirsin.")
            telegram_notify.save(token, chat)
            settings = telegram_notify.load_settings(self._root)
            settings["bot"] = bot
            telegram_notify.save_settings(self._root, settings)
            telegram_notify.mark_all_seen(self._root)
            telegram_notify.send(
                f"✅ <b>LimeOBS bağlandı{', ' + html.escape(name) if name else ''}!</b>\n"
                "Yeni ödev, mesaj, duyuru ve sınav sonuçlarını buradan bildireceğim. 🍋")
        self._telegram_run(job, "Telegram bağlandı! Bildirimler telefonuna gelecek.")

    @Slot()
    def telegramCancel(self):
        self._tg_waiting = False

    @Slot()
    def telegramTest(self):
        self._telegram_run(lambda: telegram_notify.send(
            "🔔 <b>Deneme bildirimi</b>\nLimeOBS bildirimleri bu sohbete geliyor. 🍋"), "Deneme bildirimi gönderildi.")

    @Slot()
    def telegramDisconnect(self):
        self._tg_timer.stop()
        self._telegram_run(self._telegram_forget, "Telegram bağlantısı kaldırıldı.")

    @Slot(str, bool)
    def telegramSetKind(self, kind, on):
        settings = telegram_notify.load_settings(self._root)
        kinds = set(settings.get("kinds") or [])
        (kinds.add if on else kinds.discard)(kind)
        settings["kinds"] = [k for k in telegram_notify.LABELS if k in kinds]
        telegram_notify.save_settings(self._root, settings)

    @Slot(bool)
    def telegramSetBackground(self, on):
        self._telegram_run(lambda: self._set_background(on),
                           "Uygulama kapalıyken de kontrol edilecek." if on else "Arka plan kontrolü kapatıldı.")

    def _telegram_forget(self):
        telegram_notify.clear()
        if self._background_enabled():
            self._set_background(False)

    def _telegram_check(self):
        if self._tg_checking or not telegram_notify.is_linked():
            return
        self._tg_checking = True

        def worker():
            try:
                n = telegram_notify.check_and_notify(self._root)
                if n:
                    print(f"[LimeOBS] Telegram: {n} yeni kayıt bildirildi")
            except Exception as e:
                print(f"[LimeOBS] Telegram kontrolü: {type(e).__name__}: {e}")
            finally:
                self._tg_checking = False
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ otomatik güncelleme

    @Property(str, constant=True)
    def appVersion(self):
        return VERSION

    @Property("QVariantMap", notify=updateChanged)
    def updateInfo(self):
        return self._update_info

    @Property(str, notify=updateChanged)
    def updateState(self):
        return self._update_state

    @Property(float, notify=updateChanged)
    def updateProgress(self):
        return self._update_progress

    @Property(bool, constant=True)
    def updateSupported(self):
        return updater.mode() is not None

    @Slot(bool)
    def checkUpdates(self, manual):
        if self._update_checking or self._update_state:
            return
        self._update_checking = True

        def worker():
            try:
                self._updateFound.emit(updater.check() or {}, manual)
            except Exception as e:
                print(f"[LimeOBS] Güncelleme denetimi: {type(e).__name__}: {e}")
                if manual:
                    self._updateFailed.emit("Güncelleme denetlenemedi. İnternet bağlantını kontrol et.")
            finally:
                self._update_checking = False
        threading.Thread(target=worker, daemon=True).start()

    def _on_update_found(self, info, manual):
        self._update_info = info or {}
        self.updateChanged.emit()
        if manual and not info:
            self.toast.emit(f"LimeOBS güncel (sürüm {VERSION}).")
        if info and self._tray_available and self._tray_enabled:
            self.desktopNotify.emit("LimeOBS güncellemesi hazır", f"Sürüm {info['version']} — uygulamadan güncelleyebilirsin.")

    def _on_update_progress(self, value):
        self._update_progress = value
        self.updateChanged.emit()

    def _on_update_failed(self, message):
        self._update_state = ""
        self.updateChanged.emit()
        self.toast.emit(message)

    @Slot()
    def dismissUpdate(self):
        self._update_info = {}
        self.updateChanged.emit()

    @Slot()
    def installUpdate(self):
        info = self._update_info
        if not info or self._update_state:
            return
        if updater.mode() == "kaynak":
            updater.restart_source()
            self._quit_app()
            return
        self._update_state = "indiriliyor"
        self._update_progress = 0.0
        self.updateChanged.emit()

        def worker():
            try:
                path = updater.download(info, lambda d, t: self._updateProgress.emit(d / t if t else 0.0))
                updater.install_and_restart(path)
                self._quitRequested.emit()
            except Exception as e:
                print(f"[LimeOBS] Güncelleme: {type(e).__name__}: {e}")
                self._updateFailed.emit("Güncelleme indirilemedi ya da kurulamadı. Siteden elle indirebilirsin.")
        threading.Thread(target=worker, daemon=True).start()

    def _quit_app(self):
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.quit()

    # ------------------------------------------------------------------ sistem tepsisi ve masaüstü bildirimleri

    def _load_desktop_prefs(self):
        try:
            return json.loads((self._root / "masaustu.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _get_tray_enabled(self):
        return self._tray_enabled

    def _set_tray_enabled(self, value):
        if value != self._tray_enabled:
            self._tray_enabled = bool(value)
            prefs = self._load_desktop_prefs()
            prefs["tray"] = self._tray_enabled
            (self._root / "masaustu.json").write_text(json.dumps(prefs), encoding="utf-8")
            self.trayEnabledChanged.emit()

    trayEnabled = Property(bool, _get_tray_enabled, _set_tray_enabled, notify=trayEnabledChanged)

    def set_tray_available(self, available):
        self._tray_available = available

    @Property(bool, constant=True)
    def trayAvailable(self):
        return self._tray_available

    def _desktop_check(self):
        """Yeni ödev, mesaj, duyuru ve sınav sonuçlarını tepsi bildirimiyle haber verir (yalnızca tepsi açıkken)."""
        if self._desk_checking or not (self._tray_enabled and self._tray_available and self._logged_in):
            return
        self._desk_checking = True

        def worker():
            try:
                new, merged, path = telegram_notify.diff_items(self._root, "masaustu_gorulen.json",
                                                               set(telegram_notify.LABELS))
                path.write_text(json.dumps(merged), encoding="utf-8")
                for kind, entries in (new or {}).items():
                    if not entries:
                        continue
                    texts = list(entries.values())
                    body = "\n".join(texts[:4]) + (f"\n… ve {len(texts) - 4} tane daha" if len(texts) > 4 else "")
                    self.desktopNotify.emit(telegram_notify.LABELS[kind], body)
            except Exception as e:
                print(f"[LimeOBS] Masaüstü bildirim kontrolü: {type(e).__name__}: {e}")
            finally:
                self._desk_checking = False
        threading.Thread(target=worker, daemon=True).start()

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
        if name == "telegram" and not (result or {}).get("error"):  # zamanlayıcı ana iş parçacığında
            linked = bool((result or {}).get("linked"))
            if linked and not self._tg_timer.isActive():
                self._tg_timer.start()
            elif not linked and self._tg_timer.isActive():
                self._tg_timer.stop()
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
        if school_calendar.day_off_reason(now.date()):
            return "İyi tatiller! 🏖️"
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

        today_lessons = self._lessons(index, today) if school_calendar.is_school_day(today) else []
        off = school_calendar.day_off_reason(today) if today.weekday() < 5 else None
        brk = school_calendar.school_break(today)
        upcoming = [e for e in school_calendar.upcoming(today, 60) if e["start"] > today][:3]
        eff_lessons = self._lessons(index, eff)

        meals = []
        for week in self._menus():
            for d in week["days"]:
                if parse_day_date_obj(d["date"], default_year=today.year) == eff:
                    meals = list(dict.fromkeys(tr_title(m) for m in d["meals"] if m.strip().lower() not in ("bardak su", "su")))
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
            "holiday": (f"Bugün okul yok: {off}" + (f" ({fmt_short(brk[1])} – {fmt_short(brk[2])})" if brk else "")
                        + f". Okul {fmt_day(eff)} başlıyor.") if off else "",
            "upcomingHolidays": [{"name": e["name"], "date": fmt_short(e["start"]) +
                                  (f" – {fmt_short(e['end'])}" if e["end"] != e["start"] else "")} for e in upcoming],
        }

    @staticmethod
    def _day_count(index):
        """Programda dersi olan günlere göre gün sayısı: hafta içi her zaman, Cumartesi/Pazar dersi varsa onlar da."""
        cells = ((index.get("lessonSchedule") or {}).get("data") or {}).get("data") or []
        last = max([c.get("y") or 0 for c in cells] + [5])
        return min(last, 7)

    def _load_schedule(self):
        index = self._index()
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        if today.weekday() >= 5:
            monday += timedelta(days=7)
        # Haftanın tamamı tatilse (ara tatil, yarıyıl) okulun açılacağı haftayı göster
        note = ""
        if not any(school_calendar.is_school_day(monday + timedelta(days=i)) for i in range(5)):
            reason = school_calendar.day_off_reason(monday) or "Tatil"
            first = school_calendar.next_school_day(monday)
            monday = first - timedelta(days=first.weekday())
            note = f"Bu hafta {reason}; okulun açılacağı haftanın programı gösteriliyor."
        days = []
        for i in range(self._day_count(index)):
            d = monday + timedelta(days=i)
            off = school_calendar.day_off_reason(d)
            days.append({"name": DAY_NAMES[i], "date": fmt_short(d), "isToday": d == today,
                         "holiday": off or "", "lessons": [] if off else self._lessons(index, d)})
        return {"days": days, "note": note}

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
                meals = [tr_title(m) for m in d["meals"] if m.strip().lower() not in ("bardak su", "su")]
                days.append({"date": d["date"], "isToday": dd == today,
                             "meals": list(dict.fromkeys(meals))})  # tatil günlerinde "Tatil" 7 kez yazıyor
                if dd and dd >= today and not current:
                    current = len(weeks)
            weeks.append({"title": f"{w['week_num']}. Hafta", "days": days})
        return {"weeks": weeks, "current": current}

    def _load_messages(self):
        inbox, sent, _ = api_bridge.fetch_messages_data()
        def row(m, outgoing):
            return {"id": str(m.get("id")), "who": m.get("sender", "") if not outgoing else "Siz",
                    "title": m.get("mailTitle", ""), "preview": m.get("mailPreview", ""),
                    "date": (m.get("sendDate") or "").split(" ")[0], "unread": not outgoing and not m.get("readDate"),
                    "userType": m.get("userType") or 0, "userId": m.get("userId") or 0,
                    "canReply": not outgoing and bool(m.get("canReply", True)) and bool(m.get("userId"))}
        return {"inbox": [row(m, False) for m in inbox or []], "sent": [row(m, True) for m in sent or []]}

    def _load_attendance(self):
        data = api_bridge.fetch_attendance_data() or {}
        charts = data.get("charts") or {}
        colors = {"Geldi": "#4CAF50", "Gelmedi (Özürsüz)": "#F44336", "Gelmedi (Özürlü)": "#FF9800",
                  "Gelmedi (Faaliyet)": "#03A9F4", "Geç geldi": "#9E9E9E"}
        counts = []
        for series in (charts.get("attendanceGraph5") or {}).get("series") or []:
            for item in series.get("data") or []:
                counts.append({"name": item.get("name", ""), "value": int(self._num(item.get("value")) or 0),
                               "color": colors.get(item.get("name"), "#9E9E9E")})

        def per_category(graph):
            g = charts.get(graph) or {}
            axis = g.get("yAxis") if isinstance(g.get("yAxis"), dict) and (g.get("yAxis") or {}).get("data") else g.get("xAxis")
            names = (axis or {}).get("data") or [] if isinstance(axis, dict) else []
            attended = next((s.get("data") or [] for s in g.get("series") or [] if s.get("name") == "Geldi"), [])
            return [{"name": tr_title(str(n)), "rate": self._num(r) or 0} for n, r in zip(names, attended)]

        absences = [{"date": a.get("absenceDate", ""), "lesson": tr_title(a.get("lesson", "")),
                     "no": str(a.get("lessonNo", "")), "teacher": tr_title(a.get("teaNameSurname", "")),
                     "kind": a.get("description", "Devamsız"), "note": a.get("note") or ""}
                    for a in data.get("absence_list") or []]
        periods = data.get("periods") or []
        return {"period": (periods[0].get("description") or "").strip() if periods else "",
                "counts": counts, "total": sum(c["value"] for c in counts),
                "lessons": per_category("attendanceGraph4"), "teachers": per_category("attendanceGraph6"),
                "absences": absences}

    def _load_etut(self):
        rec = api_bridge.fetch_etut_records() or {}
        dash = api_bridge.fetch_course_dashboard() or {}
        counts = dash.get("courseCounts") or {}
        items = []
        for kind, label in (("etut", "Etüt"), ("birebir", "Birebir"), ("counseling", "Rehberlik")):
            for r in rec.get(kind) or []:
                items.append({"kind": label, "lesson": tr_title(r.get("lesson", "")),
                              "teacher": tr_title(r.get("teaNameSurname", "")), "date": r.get("date", ""),
                              "time": r.get("unitLabel", ""), "place": r.get("hallName") or ""})
        return {"items": items,
                "etutMonth": (counts.get("E") or {}).get("monthly", 0), "etutYear": (counts.get("E") or {}).get("yearly", 0),
                "birebirMonth": (counts.get("B") or {}).get("monthly", 0), "birebirYear": (counts.get("B") or {}).get("yearly", 0)}

    def _load_classical(self):
        data = api_bridge.fetch_classical_exams() or {}
        t3 = ((data.get("tables") or {}).get("classicalExamTable3") or {})

        def rows(period):
            out = []
            for it in (t3.get(period) or {}).get("data") or []:
                out.append({"lesson": tr_title(it.get("lesson") or it.get("ders") or it.get("sinavAd") or "Ders"),
                            "e1": str(it.get("exam1") or it.get("yazili1") or "–"),
                            "e2": str(it.get("exam2") or it.get("yazili2") or "–"),
                            "e3": str(it.get("exam3") or it.get("yazili3") or "–"),
                            "oral": str(it.get("sozlu") or it.get("kanaat") or "–"),
                            "avg": str(it.get("ort") or it.get("average") or it.get("Puan") or "–")})
            return out
        cal = api_bridge.fetch_exam_days_calendar() or {}
        return {"message": "" if data.get("success") else (data.get("msg") or "Yazılı sınav notu bulunamadı."),
                "period1": rows("period1"), "period2": rows("period2"),
                "calendarUrl": cal.get("view_url") or cal.get("download_url") or ""}

    def _load_library(self):
        books = []
        for b in api_bridge.fetch_borrowed_books() or []:
            books.append({"name": b.get("bookName") or b.get("name") or "Kitap", "author": b.get("author") or "",
                          "borrowed": b.get("borrowDate") or "", "returned": b.get("returnDate") or "",
                          "done": bool(b.get("isReturned"))})
        return {"books": books}

    @Slot(str)
    def searchLibrary(self, query):
        def worker():
            res = api_bridge.search_library_books(query) if query.strip() else []
            self._resultReady.emit("librarySearch", {"query": query, "results": [
                {"name": r.get("bookName") or r.get("name") or "Kitap", "author": r.get("author") or "",
                 "available": r.get("status") or r.get("availability") or ""} for r in res or []]})
        threading.Thread(target=worker, daemon=True).start()

    def _load_announcements(self):
        index = self._index()
        anns = [{"title": a.get("title") or a.get("baslik") or "Duyuru",
                 "date": a.get("createDate") or a.get("date") or a.get("tarih") or "",
                 "body": html.unescape(re.sub(r"<[^>]+>", " ", a.get("content") or a.get("description") or a.get("icerik") or "")).strip()}
                for a in index.get("announcementList") or []]
        events = [{"title": e.get("title") or "Etkinlik", "date": e.get("eventDate") or e.get("date") or "",
                   "place": e.get("location") or ""} for e in index.get("eventList") or []]
        for e in api_bridge.fetch_events_data() or []:
            events.append({"title": e.get("title") or "Etkinlik", "date": e.get("eventDate") or e.get("date") or "",
                           "place": e.get("location") or ""})
        return {"announcements": anns, "events": events}

    def _load_teachers(self):
        return {"teachers": sorted(({"name": tr_title(t.get("teaNameSurname", "")), "lesson": tr_title(t.get("lesson", ""))}
                                    for t in api_bridge.fetch_teachers_data() or []), key=lambda t: t["lesson"])}

    # --- mesaj gönderme
    @Slot(str)
    def searchReceivers(self, query):
        def worker():
            res = api_bridge.search_mail_receivers(query) if len(query.strip()) >= 2 else []
            self._resultReady.emit("receivers", {"query": query, "results": [
                {"name": tr_title(r.get("nameSurname", "")), "type": r.get("type") or "",
                 "userType": r.get("userType"), "userId": r.get("userId")} for r in res or []]})
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, str, int, int, str)
    def sendMail(self, title, content, user_type, user_id, reply_id):
        def worker():
            res = api_bridge.send_mail_message(title.strip(), content.strip(), user_type, user_id, reply_id or "")
            ok = bool(res.get("success"))
            self._resultReady.emit("mailSent", {"ok": ok, "message": "Mesaj gönderildi." if ok else
                                                 (res.get("msg") or "Mesaj gönderilemedi.")})
            if ok:
                self._data.pop("messages", None)
        threading.Thread(target=worker, daemon=True).start()

    # --- ödev ayrıntısı ve dosyalar
    @Slot(int)
    def openHomework(self, hw_id):
        def worker():
            d = api_bridge.fetch_homework_detail(hw_id) or {}
            def files(key):
                return [{"name": f.get("fileName") or "Dosya", "fileId": f.get("fileId"), "hash": f.get("fileHash") or "",
                         "kind": key} for f in d.get(key) or []]
            body = html.unescape(re.sub(r"<br\s*/?>|</p>", "\n", d.get("description") or ""))
            self._resultReady.emit("homeworkDetail", {
                "id": hw_id, "title": d.get("title", ""), "lesson": tr_title(d.get("lesson", "")),
                "teacher": tr_title(d.get("teaNameSurname", "")), "start": d.get("startDate", ""), "end": d.get("endDate", ""),
                "status": d.get("statusName", ""), "comment": d.get("teacherComment") or "",
                "body": re.sub(r"<[^>]+>", "", body).strip(),
                "files": files("attachFiles") + files("answerFiles") + files("studentAttachFiles")})
        threading.Thread(target=worker, daemon=True).start()

    @Slot(int, "QVariantMap")
    def openHomeworkFile(self, hw_id, f):
        def worker():
            content, err = api_bridge.download_homework_attachment(hw_id, f.get("fileId"), f.get("hash") or None,
                                                                   f.get("kind") or "attachFiles")
            if not content:
                self.toast.emit(err or "Dosya indirilemedi.")
                return
            self._open_bytes(content, f.get("name") or "dosya")
        threading.Thread(target=worker, daemon=True).start()

    def _open_bytes(self, content, name):
        folder = self._root / ".cache" / "files"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / re.sub(r"[^\w.\- ]", "_", name)
        path.write_bytes(content)
        ext = path.suffix.lower()
        if MEDIA_OK and ext in AUDIO_EXT | VIDEO_EXT:
            self.mediaReady.emit(QUrl.fromLocalFile(str(path)).toString(), name, ext in AUDIO_EXT)
        else:
            api_bridge.open_file_external(path)

    @Slot()
    def exportCalendar(self):
        """Yaklaşan sınavları ve teslim bekleyen ödevleri .ics takvim dosyası olarak kaydeder ve açar
        (Google Takvim, Outlook, Apple Takvim ve Thunderbird içe aktarabilir)."""
        def worker():
            try:
                from PySide6.QtCore import QStandardPaths
                today = date.today()
                events = []
                for e in self._index().get("examList") or []:
                    try:
                        d = datetime.strptime(e.get("sinavTarih", ""), "%d.%m.%Y").date()
                    except ValueError:
                        continue
                    if d >= today:
                        name = (e.get("sinavAd") or "Sınav").strip()
                        events.append((f"sinav-{d.isoformat()}-{abs(hash(name))}", f"📝 {name}", d, "Sınav • LimeOBS"))
                for h in self._homeworks():
                    if h["done"] or not h["endDate"]:
                        continue
                    d = date.fromisoformat(h["endDate"])
                    if d >= today:
                        events.append((f"odev-{h.get('id', h['title'])}", f"📚 {h['lesson']}: {h['title']}", d,
                                       f"Ödev teslimi • {h['teacher']} • LimeOBS"))
                if not events:
                    self.toast.emit("Takvime aktarılacak yaklaşan sınav ya da ödev yok.")
                    return

                def esc(t):
                    return str(t).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
                stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//LimeOBS//TR", "CALSCALE:GREGORIAN",
                         "X-WR-CALNAME:LimeOBS"]
                for uid, title, d, desc in events:
                    lines += ["BEGIN:VEVENT", f"UID:{uid}@limeobs", f"DTSTAMP:{stamp}",
                              f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                              f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(desc)}",
                              # bir gün önce 18:00'de hatırlat
                              "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(title)}", "TRIGGER:-PT6H", "END:VALARM",
                              "END:VEVENT"]
                lines.append("END:VCALENDAR")
                docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or Path.home())
                docs.mkdir(parents=True, exist_ok=True)
                path = docs / "LimeOBS Takvim.ics"
                path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
                self.toast.emit(f"{len(events)} sınav ve ödev kaydedildi: {path}")
                api_bridge.open_file_external(path)
            except Exception as exc:
                self.toast.emit(f"Takvim dosyası oluşturulamadı: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def exportSchedulePdf(self):
        """Haftalık ders programını PDF'e çizer, Belgeler klasörüne kaydeder ve açar."""
        def worker():
            try:
                import schedule_pdf
                from PySide6.QtCore import QStandardPaths

                index = self._index()
                monday = date.today() - timedelta(days=date.today().weekday())
                week = [self._lessons(index, monday + timedelta(days=i)) for i in range(self._day_count(index))]
                raw = api_bridge.get_adaptive_profile_data() or {}
                meta = api_bridge.get_school_metadata() or {}
                cls = re.sub(r"^[A-ZÇĞİÖŞÜ]+-(?=\d)", "", str(raw.get("student_class") or "").strip())
                student = tr_title(raw.get("student_name") or "")
                docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or Path.home())
                docs.mkdir(parents=True, exist_ok=True)
                path = docs / "LimeOBS Ders Programı.pdf"
                schedule_pdf.render(path, week, student, meta.get("school_name") or "", cls, meta.get("academic_term") or "")
                api_bridge.open_file_external(path)
                self.toast.emit(f"PDF kaydedildi: {path}")
            except Exception as exc:
                self.toast.emit(f"PDF oluşturulamadı: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def openFoodPdf(self):
        def worker():
            data = api_bridge.fetch_food_list_data()
            if data.get("pdf_bytes"):
                self._open_bytes(data["pdf_bytes"], "yemek-listesi.pdf")
            else:
                self.toast.emit("Yemek listesi PDF'i bulunamadı.")
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str)
    def openUrl(self, url):
        import webbrowser
        if url:
            webbrowser.open(url)

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
