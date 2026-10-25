import json
import re
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import akbim_api
try:
    import security
except ImportError:
    from akbim_frontend import security

import os
import sys
import threading
import time
from pathlib import Path

# Robust connection pooling and automatic retry for socket drops / RemoteDisconnected
_retry_strategy = Retry(
    total=3,
    connect=3,
    read=2,
    status=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
_adapter = HTTPAdapter(
    max_retries=_retry_strategy,
    pool_connections=25,
    pool_maxsize=25
)
akbim_api.session.mount("https://", _adapter)
akbim_api.session.mount("http://", _adapter)

akbim_api.session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
})

# Bellek içi fotoğraf önbelleği
_CACHED_PHOTO_BYTES = None

if getattr(sys, 'frozen', False):
    if sys.platform.startswith("win"):
        CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "LimeOBS"
    else:
        CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "limeobs"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE = CONFIG_DIR / "akbim_config.json"
else:
    CONFIG_FILE = Path(__file__).resolve().parent.parent / "akbim_config.json"


def get_saved_base_url():
    """Kayıtlı okul sunucu adresini döner, varsayılan https://tedemkolejiobs.com"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = cfg.get("base_url")
                if url:
                    return url.strip().rstrip("/")
        except Exception:
            pass
    return "https://tedemkolejiobs.com"


def set_base_url(url):
    """Okul sunucusu adresini ayarlar ve config'e kaydeder."""
    clean_url = url.strip().rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"
    akbim_api.BASEURL = clean_url
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["base_url"] = clean_url
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Config kaydetme hatası: {e}")
    return clean_url


def save_credentials(tc, password):
    """Beni Hatırla seçiliyse kimlik bilgilerini Windows DPAPI ve HMAC bütünlük kontrolüyle şifreleyerek kasaya kaydeder."""
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        
        # Düz metin kimlik bilgilerini temizle
        if "saved_creds" in cfg:
            del cfg["saved_creds"]
            
        # Güvenli kriptografik kasa oluştur (DPAPI + HMAC-SHA256)
        vault_payload = security.generate_vault_payload({"tc": tc, "password": password})
        cfg["secure_vault"] = vault_payload
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Güvenlik] Kimlik bilgisi kaydetme hatası: {e}")


def get_saved_credentials():
    """Kayıtlı kimlik bilgilerini kriptografik kasadan çözer ve HMAC bütünlüğünü doğrular."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            
            # Kriptografik Kasa (DPAPI + HMAC) kontrolü
            if "secure_vault" in cfg:
                creds = security.unpack_vault_payload(cfg["secure_vault"])
                if creds:
                    return creds
                else:
                    print("[Güvenlik Uyarısı] Kasa açılamadı veya HMAC doğrulaması başarısız oldu!")
            
            # Eski düz metin konfigürasyon varsa otomatik güvenli kasaya dönüştür (Migrate)
            if "saved_creds" in cfg:
                legacy = cfg.pop("saved_creds")
                tc = legacy.get("tc")
                pwd = legacy.get("password")
                if tc and pwd:
                    print("[Güvenlik] Eski düz metin kimlik bilgisi tespit edildi, DPAPI kasasına dönüştürülüyor...")
                    cfg["secure_vault"] = security.generate_vault_payload({"tc": tc, "password": pwd})
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                    return {"tc": tc, "password": pwd}
        except Exception as e:
            print(f"[Güvenlik] Kimlik bilgisi okuma hatası: {e}")
    return None


def clear_saved_credentials():
    """Oturum kapatıldığında kayıtlı kasa, bilgiler ve Linux/macOS anahtarlığını temizler."""
    try:
        security.clear_system_keyring()
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            changed = False
            if "saved_creds" in cfg:
                del cfg["saved_creds"]
                changed = True
            if "secure_vault" in cfg:
                del cfg["secure_vault"]
                changed = True
            if changed:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_session_expired_callbacks = []
_session_expired_notified = False


def add_session_expired_callback(cb):
    """Oturum sona erdiğinde çağrılacak geri çağırma fonksiyonunu kaydeder."""
    if cb not in _session_expired_callbacks:
        _session_expired_callbacks.append(cb)


def reset_session_expired_flag():
    """Giriş yapıldığında oturum düşme bildirim bayrağını sıfırlar."""
    global _session_expired_notified
    _session_expired_notified = False


def notify_session_expired(reason="Oturumunuz sona erdi. Lütfen tekrar giriş yapın."):
    """Oturumun düştüğünü veya bittiğini arayüze bildirir ve geçersiz oturumu temizler."""
    global _session_expired_notified
    if _session_expired_notified:
        return
    _session_expired_notified = True

    print(f"[LimeOBS] Oturum sona erdi: {reason}")
    clear_cache()
    try:
        from pathlib import Path
        if hasattr(akbim_api, "COOKIE_FILE"):
            cookie_path = Path(akbim_api.COOKIE_FILE)
            if cookie_path.exists():
                cookie_path.unlink()
        akbim_api.session.cookies.clear()
    except Exception:
        pass

    for cb in list(_session_expired_callbacks):
        try:
            cb(reason)
        except Exception as e:
            print(f"Session expired callback error: {e}")


_session_check_lock = threading.Lock()
_last_session_check_time = 0.0
_last_session_status = None


def check_session_status(force=False):
    """
    Oturum durumunu kontrol eder (20 saniyelik dahili önbellekleme ile sunucu boğulmasını engeller):
      True  -> Oturum geçerli ve aktif
      False -> Oturum süresi DOLMUŞ (sunucu 200 döndü ama oturum yok / login.php menüsü döndü)
      None  -> Ağ hatası / Bağlantı kurulamadı (sunucuya ulaşılamadı)
    """
    global _last_session_check_time, _last_session_status
    with _session_check_lock:
        now = time.time()
        if not force and _last_session_status is True and (now - _last_session_check_time < 20):
            return True

        try:
            res = akbim_api.session.get(f"{akbim_api.BASEURL}/require/menuLoader.php", timeout=8)
            if res.ok:
                if "window.obsNavData = " in res.text:
                    _last_session_status = True
                    _last_session_check_time = now
                    return True
                else:
                    _last_session_status = False
                    _last_session_check_time = now
                    return False
            if res.status_code in (401, 403) or "login.php" in res.url:
                _last_session_status = False
                _last_session_check_time = now
                return False
            _last_session_status = False
            _last_session_check_time = now
            return False
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return None
        except Exception:
            return None


def is_session_active():
    """Geriye uyumluluk: Sadece oturum kesinlikle aktifse True döner."""
    return check_session_status() is True


_ensure_session_lock = threading.Lock()


def ensure_valid_session():
    """
    Oturum süresi dolmuşsa kayıtlı kimlik bilgileriyle otomatik olarak arka planda yeniden giriş yapar.
    Ağ bağlantı hatası varsa oturumu düşürmez / çerezleri silmez.
    """
    with _ensure_session_lock:
        status = check_session_status()
        if status is True:
            return True
        elif status is None:
            return False

        # status is False -> Sunucu aktif olarak oturumun süresinin dolduğunu bildirdi
        creds = get_saved_credentials()
        if creds and creds.get("tc") and creds.get("password"):
            try:
                res = akbim_api.login(creds["tc"], creds["password"])
                if res.get("success"):
                    akbim_api.save_session()
                    reset_session_expired_flag()
                    global _last_session_status, _last_session_check_time
                    _last_session_status = True
                    _last_session_check_time = time.time()
                    return True
                else:
                    notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                    return False
            except Exception:
                return False
        else:
            notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
            return False


def get_saved_theme():
    """Kayıtlı tema modunu döner: 'dark', 'light' veya 'liquid' (varsayılan: 'liquid')"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                theme = cfg.get("theme")
                if theme in ["dark", "light", "liquid"]:
                    return theme
        except Exception:
            pass
    return "liquid"



def save_theme(theme_name):
    """Tema tercihini kaydeder."""
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["theme"] = theme_name
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Tema ayarı kaydetme hatası: {e}")


def apply_theme_to_window(window):
    """Herhangi bir popup pencereye veya dialoga (Adw.Window) kayıtlı temayı uygular."""
    if not window:
        return
    cur_theme = get_saved_theme()
    for t in ["theme-liquid", "theme-light", "theme-dark"]:
        window.remove_css_class(t)
    window.add_css_class(f"theme-{cur_theme}")


# Başlangıçta kayıtlı URL'yi ayarla
akbim_api.BASEURL = get_saved_base_url()


# Aktif görüntüleme modu (Veli oturumunda veli özeti veya öğrenci detay modu)
_CURRENT_VIEW_MODE = None  # None (otomatik), 'parent' veya 'student'


def get_current_view_mode():
    return "student"


def set_current_view_mode(mode):
    global _CURRENT_VIEW_MODE
    _CURRENT_VIEW_MODE = mode
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["view_mode"] = mode
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"View mode kaydetme hatası: {e}")


_CACHED_EXAM_DASHBOARD_META = {}
_CACHED_NAV_METADATA = None
_CACHED_SCHOOL_METADATA = None


def clear_cache():
    global _CACHED_PHOTO_BYTES, _CURRENT_VIEW_MODE, _CACHED_EXAM_DASHBOARD_META, _CACHED_NAV_METADATA, _CACHED_SCHOOL_METADATA
    _CACHED_PHOTO_BYTES = None
    _CURRENT_VIEW_MODE = None
    _CACHED_EXAM_DASHBOARD_META = {}
    _CACHED_NAV_METADATA = None
    _CACHED_SCHOOL_METADATA = None


def clear_active_session(clear_saved_login=False):
    """
    Tüm aktif oturum çerezlerini, diskteki session dosyasını ve önbellekleri sıfırlar.
    clear_saved_login=True verilirse kayıtlı TC/şifreyi de (akbim_config.json) siler.
    """
    clear_cache()
    reset_session_expired_flag()
    try:
        akbim_api.session.cookies.clear()
    except Exception:
        pass
    try:
        if hasattr(akbim_api, "COOKIE_FILE"):
            cookie_path = Path(akbim_api.COOKIE_FILE)
            if cookie_path.exists():
                cookie_path.unlink()
    except Exception:
        pass
    if clear_saved_login:
        clear_saved_credentials()


def get_cached_exam_dashboard_meta():
    """Son çekilen sınav dashboard metriklerini (kpi, lessonSuccess, trend) döner."""
    return _CACHED_EXAM_DASHBOARD_META or {}



def get_school_metadata():
    """Bağlı okul adını ve aktif eğitim dönemini tespit eder."""
    global _CACHED_SCHOOL_METADATA
    if _CACHED_SCHOOL_METADATA:
        return _CACHED_SCHOOL_METADATA

    school_name = "Akbim OBS"
    academic_term = "2026-2027"

    try:
        nav = get_nav_metadata()
        brand_name = nav.get("raw", {}).get("brand", {}).get("name", "")
        if brand_name:
            # "Tedem Koleji | Online Bilgi Sistemi" -> "Tedem Koleji"
            if "|" in brand_name:
                school_name = brand_name.split("|")[0].strip()
            elif "-" in brand_name:
                school_name = brand_name.split("-")[0].strip()
            else:
                school_name = brand_name.strip()
        else:
            # Domain adından çıkar
            domain = akbim_api.BASEURL.replace("https://", "").replace("http://", "").split("/")[0]
            clean_dom = domain.replace("obs.", "").replace("obs", "")
            school_name = clean_dom.split(".")[0].capitalize()

        # Dönem tespiti: index exam tarihlerinden veya güncel yıldan
        from datetime import datetime
        now_year = datetime.now().year
        academic_term = f"{now_year}-{now_year+1}"
    except Exception as e:
        print(f"Okul metadata tespit hatası: {e}")

    _CACHED_SCHOOL_METADATA = {
        "school_name": school_name,
        "academic_term": academic_term
    }
    return _CACHED_SCHOOL_METADATA


def get_nav_metadata(force_refresh=False):
    """menuLoader.php'den aktif oturumun rolünü ('parent'/'student') ve 'base' yolunu çeker (sonucu oturum süresince önbelleğe alır)."""
    global _CACHED_NAV_METADATA
    if not force_refresh and _CACHED_NAV_METADATA:
        return _CACHED_NAV_METADATA

    try:
        # 1. Öncelik: menuLoader.php üzerinden kontrol (en kesin yöntem)
        res = akbim_api.session.get(f"{akbim_api.BASEURL}/require/menuLoader.php")
        if "window.obsNavData = " in res.text:
            json_text = res.text.split("window.obsNavData = ", 1)[1].split("};", 1)[0] + "}"
            data = json.loads(json_text)
            key = data.get("key")
            brand_sub = data.get("brand", {}).get("sub", "").lower()
            user_sub = data.get("user", {}).get("sub", "").lower()
            if key == "parent" or "veli" in brand_sub or "veli" in user_sub:
                key = "parent"
            else:
                key = "student"
            base = data.get("base", f"pages/{key}/")
            _CACHED_NAV_METADATA = {"key": key, "base": base, "raw": data}
            return _CACHED_NAV_METADATA
        else:
            # Oturum geçersiz veya düşmüş olabilir, oturumu yenilemeyi dene
            if ensure_valid_session():
                res2 = akbim_api.session.get(f"{akbim_api.BASEURL}/require/menuLoader.php")
                if "window.obsNavData = " in res2.text:
                    json_text = res2.text.split("window.obsNavData = ", 1)[1].split("};", 1)[0] + "}"
                    data = json.loads(json_text)
                    key = "parent" if data.get("key") == "parent" else "student"
                    base = data.get("base", f"pages/{key}/")
                    _CACHED_NAV_METADATA = {"key": key, "base": base, "raw": data}
                    return _CACHED_NAV_METADATA

        # 2. Öncelik: Sayfa bazlı doğrulama
        for candidate_key in ["student", "parent"]:
            chk = akbim_api.session.get(f"{akbim_api.BASEURL}/pages/{candidate_key}/profile.php")
            if chk.ok and "Kullanıcı Profili" in chk.text and "login.php" not in chk.url:
                _CACHED_NAV_METADATA = {"key": candidate_key, "base": f"pages/{candidate_key}/", "raw": {}}
                return _CACHED_NAV_METADATA
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        print(f"menuLoader bağlantı uyarısı: {e}")
    except Exception as e:
        print(f"menuLoader okuma hatası: {e}")

    fallback = {"key": "student", "base": "pages/student/", "raw": {}}
    return fallback


def get_adaptive_index_data():
    """Hem Veli (pages/parent/) hem de Öğrenci (pages/student/) için doğru indexAction endpoint'ine istek atar."""
    # akbim_api.load_index()'i de doğrudan kullan
    try:
        data = akbim_api.load_index()
        if data and data.get("success") and "data" in data:
            return data
    except Exception:
        pass

    nav = get_nav_metadata()
    base = nav.get("base", "pages/student/").strip("/")

    candidate_urls = [
        f"{akbim_api.BASEURL}/{base}/require/indexAction.php",
        f"{akbim_api.BASEURL}/pages/student/require/indexAction.php",
        f"{akbim_api.BASEURL}/pages/parent/require/indexAction.php",
    ]

    seen = set()
    for url in candidate_urls:
        if url in seen:
            continue
        seen.add(url)

        try:
            res = akbim_api.session.post(
                url,
                data={"request": "loadIndex"},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if res.ok:
                data = res.json()
                if data.get("success") and "data" in data:
                    return data
        except Exception:
            continue

    return {"success": False, "data": {"examList": [], "announcementList": [], "eventList": [], "lessonSchedule": {"data": {}}}}



def fetch_student_photo_bytes():
    """Öğrenci vesikalık fotoğrafını çeker ve ikili (bytes) olarak döner."""
    global _CACHED_PHOTO_BYTES
    if _CACHED_PHOTO_BYTES:
        return _CACHED_PHOTO_BYTES

    # 1. Öncelik: profile.php HTML içerisindeki <img> etiketi
    candidate_profile_pages = [
        f"{akbim_api.BASEURL}/pages/student/profile.php",
        f"{akbim_api.BASEURL}/pages/parent/profile.php"
    ]

    headers = {
        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Referer": f"{akbim_api.BASEURL}/pages/student/profile.php"
    }

    for p_url in candidate_profile_pages:
        try:
            p_res = akbim_api.session.get(p_url)
            if p_res.ok and "login.php" not in p_res.url:
                # Regex 1: studentPhoto.php içeren img etiketleri
                match = re.search(r'<img\b[^>]*\bsrc\s*=\s*["\']([^"\']*studentPhoto\.php[^"\']*)["\']', p_res.text, re.IGNORECASE)
                if not match:
                    # Regex 2: Herhangi bir photo / vesikalık / profil img src'si
                    match = re.search(r'<img\b[^>]*\bsrc\s*=\s*["\']([^"\']*(?:studentPhoto|photo|resim)[^"\']*)["\']', p_res.text, re.IGNORECASE)
                
                if match:
                    rel_src = match.group(1).lstrip("/")
                    full_url = rel_src if rel_src.startswith("http") else f"{akbim_api.BASEURL}/{rel_src}"
                    img_res = akbim_api.session.get(full_url, headers=headers)
                    if img_res.ok and len(img_res.content) > 100:
                        _CACHED_PHOTO_BYTES = img_res.content
                        return _CACHED_PHOTO_BYTES
        except Exception as e:
            print(f"HTML fotoğraf çekme hatası: {e}")

    # 2. Öncelik: Doğrudan bilinen endpoint'ler
    direct_photo_urls = [
        f"{akbim_api.BASEURL}/pages/student/require/studentPhoto.php",
        f"{akbim_api.BASEURL}/pages/student/studentPhoto.php",
        f"{akbim_api.BASEURL}/require/studentPhoto.php"
    ]
    for d_url in direct_photo_urls:
        try:
            d_res = akbim_api.session.get(d_url, headers=headers)
            if d_res.ok and len(d_res.content) > 100 and "text/html" not in d_res.headers.get("Content-Type", ""):
                _CACHED_PHOTO_BYTES = d_res.content
                return _CACHED_PHOTO_BYTES
        except Exception:
            pass

    # 3. Öncelik: menuLoader.php içerisindeki user.photo alanı
    try:
        nav = get_nav_metadata()
        photo_rel = nav.get("raw", {}).get("user", {}).get("photo")
        if photo_rel:
            full_url = photo_rel if photo_rel.startswith("http") else f"{akbim_api.BASEURL}/{photo_rel.lstrip('/')}"
            img_res = akbim_api.session.get(full_url, headers=headers)
            if img_res.ok and len(img_res.content) > 100:
                _CACHED_PHOTO_BYTES = img_res.content
                return _CACHED_PHOTO_BYTES
    except Exception as e:
        print(f"menuLoader fotoğraf çekme hatası: {e}")

    return None


def get_adaptive_profile_data():
    """Hem Veli hem Öğrenci hesaplarının profil bilgilerini ve vesikalık fotoğrafını çözer."""
    nav = get_nav_metadata()
    role_key = nav.get("key", "student")
    is_parent = (role_key == "parent")

    profile_result = {
        "role": "Veli" if is_parent else "Öğrenci",
        "student_name": None,
        "student_class": None,
        "student_no": None,
        "student_prog": None,
        "parent_name": None,
        "photo_bytes": None,
        "raw_fields": {}
    }

    # 1. Öncelik: Öğrenci hesabı ise akbim_api.get_student_profile() çağrısı ile student profilini al
    if not is_parent:
        try:
            api_profile = akbim_api.get_student_profile()
            if isinstance(api_profile, dict) and not api_profile.get("error"):
                for k, v in api_profile.items():
                    profile_result["raw_fields"][k] = v
                    k_lower = k.lower()
                    if "veli" in k_lower and ("isim" in k_lower or "ad" in k_lower):
                        profile_result["parent_name"] = v
                    elif "isim" in k_lower or "ad soyad" in k_lower:
                        if not profile_result["student_name"]:
                            profile_result["student_name"] = v
                    elif "sınıf" in k_lower:
                        profile_result["student_class"] = v
                    elif "no" in k_lower or "numara" in k_lower:
                        profile_result["student_no"] = v
                    elif "program" in k_lower:
                        profile_result["student_prog"] = v
        except Exception:
            pass

    # 2. Öncelik: Sayfa bazlı tarama
    # Veli oturumunda pages/parent/profile.php içinde hem Öğrenci hem Veli bilgileri yer alır!
    candidate_urls = [
        f"{akbim_api.BASEURL}/pages/parent/profile.php"
    ] if is_parent else [
        f"{akbim_api.BASEURL}/pages/student/profile.php",
        f"{akbim_api.BASEURL}/pages/parent/profile.php"
    ]

    seen = set()
    for url in candidate_urls:
        if profile_result["student_name"] and profile_result["student_class"]:
            break
        if url in seen:
            continue
        seen.add(url)

        try:
            res = akbim_api.session.get(url)
            if not res.ok or "login.php" in res.url:
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            # dl-horizontal bloklarını doğrudan tara
            dl_blocks = soup.find_all("dl", class_="dl-horizontal")
            for dl in dl_blocks:
                prev_h = dl.find_previous(["h1", "h2", "h3", "h4", "h5", "header"])
                h_text = prev_h.get_text(" ", strip=True).lower() if prev_h else ""
                is_student_block = ("öğrenci" in h_text)
                is_parent_block = ("veli" in h_text)

                for dt in dl.find_all("dt"):
                    dd = dt.find_next_sibling("dd")
                    if not dd:
                        continue
                    label = dt.get_text(strip=True)
                    val = dd.get_text(strip=True)
                    
                    if is_student_block or (not is_parent_block and not profile_result["student_name"]):
                        profile_result["raw_fields"][f"student_{label}"] = val
                        if label == "İsim Soyisim" and not profile_result["student_name"]:
                            profile_result["student_name"] = val
                        elif label == "Sınıf Kodu" and not profile_result["student_class"]:
                            profile_result["student_class"] = val
                        elif ("Numara" in label or "No" in label) and not profile_result["student_no"]:
                            profile_result["student_no"] = val
                        elif "Program" in label and not profile_result["student_prog"]:
                            profile_result["student_prog"] = val
                    elif is_parent_block:
                        profile_result["raw_fields"][f"parent_{label}"] = val
                        if label == "İsim Soyisim":
                            profile_result["parent_name"] = val

            # Genel dt/dd araması fallback
            if not profile_result["student_name"]:
                for dt in soup.find_all("dt"):
                    label = dt.get_text(strip=True)
                    dd = dt.find_next_sibling("dd")
                    if not dd:
                        continue
                    val = dd.get_text(strip=True)
                    if label == "İsim Soyisim":
                        profile_result["student_name"] = val
                    elif label == "Sınıf Kodu":
                        profile_result["student_class"] = val
                    elif "Numara" in label or "No" in label:
                        profile_result["student_no"] = val
        except Exception as e:
            print(f"Profil sayfası kazıma hatası ({url}): {e}")
            continue

    # 3. Öncelik: nav metadata'sındaki user.name
    user_info = nav.get("raw", {}).get("user", {})
    if is_parent:
        if not profile_result["parent_name"] and user_info.get("name"):
            profile_result["parent_name"] = user_info["name"]
    else:
        if not profile_result["student_name"] and user_info.get("name"):
            profile_result["student_name"] = user_info["name"]

    # 4. Normalize and populate all standard field variants from raw_fields
    raw = profile_result.get("raw_fields", {})
    for k, v in raw.items():
        k_clean = str(k).lower().replace("ı", "i").replace("İ", "i").replace("ğ", "g").replace("ö", "o").replace("ü", "u").replace("ş", "s")
        if "veli" in k_clean:
            if not profile_result.get("parent_name"):
                profile_result["parent_name"] = v
        elif "isim" in k_clean or "ad" in k_clean:
            if not profile_result.get("student_name"):
                profile_result["student_name"] = v
        elif "sinif" in k_clean:
            if not profile_result.get("student_class"):
                profile_result["student_class"] = v
        elif "numara" in k_clean or "no" in k_clean:
            if not profile_result.get("student_no"):
                profile_result["student_no"] = v
        elif "program" in k_clean:
            if not profile_result.get("student_prog"):
                profile_result["student_prog"] = v

    # Common standard aliases for convenience
    profile_result["name"] = profile_result.get("student_name") or "Öğrenci"
    profile_result["class_code"] = profile_result.get("student_class") or ""
    profile_result["class"] = profile_result.get("student_class") or ""
    profile_result["student_no"] = profile_result.get("student_no") or ""

    # Fotoğrafı çek
    profile_result["photo_bytes"] = fetch_student_photo_bytes()

    return profile_result


def fetch_all_student_exams(exam_type="SBS"):
    """
    Öğrencinin girdiği tüm sınavların (Denemeler & DBS/DAS Taramalar) listesini çeker.
    Hem examDashboard'dan SBS denemelerini hem de öğrenci genel raporundaki DAS taramalarını birleştirir.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return []

    combined_exams = []

    # 1. Deneme Sınavları (SBS)
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    candidate_urls = [
        f"{akbim_api.BASEURL}/{role_base}/require/examDashboard.php",
        f"{akbim_api.BASEURL}/pages/student/require/examDashboard.php",
        f"{akbim_api.BASEURL}/pages/parent/require/examDashboard.php",
    ]
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/index.php"
    }
    payload = {"request": "getStudentExams", "examType": exam_type or "SBS"}

    for attempt in range(2):
        for url in candidate_urls:
            try:
                res = akbim_api.session.post(url, data=payload, headers=headers)
                if res.ok and res.text.strip().startswith("{"):
                    data = res.json()
                    if data.get("success"):
                        global _CACHED_EXAM_DASHBOARD_META
                        _CACHED_EXAM_DASHBOARD_META = {
                            "kpi": data.get("kpi", {}),
                            "lessonSuccess": data.get("lessonSuccess", []),
                            "trend": data.get("trend", {}),
                            "lessons": data.get("lessons", []),
                        }
                        sbs_list = data.get("exams", [])
                        for item in sbs_list:
                            item["examCategory"] = "Deneme Sınavı"
                            item["isTarama"] = False
                        combined_exams.extend(sbs_list)
                        break
            except Exception:
                pass
        if combined_exams:
            break
        if attempt == 0 and not ensure_valid_session():
            break

    # 2. Tarama Sınavları (DAS / DBS)
    try:
        gen_rep = get_student_general_report()
        if gen_rep:
            das_list = gen_rep.get("dbsInfo", {}).get("list", []) or []
            for das in das_list:
                s_name = das.get("sinavAd", "Tarama Sınavı")
                s_date = das.get("sinavTarih", "")
                puan_str = das.get("Puan", "0")
                try:
                    puan_val = float(puan_str)
                except Exception:
                    puan_val = 0.0

                # Doğru, Yanlış ve Soru Sayılarını topla
                t_d = sum(int(das.get(f"D{i}") or 0) for i in range(1, 11) if str(das.get(f"D{i}", "")).isdigit())
                t_y = sum(int(das.get(f"Y{i}") or 0) for i in range(1, 11) if str(das.get(f"Y{i}", "")).isdigit())
                t_ss = sum(int(das.get(f"SS{i}") or 0) for i in range(1, 11) if str(das.get(f"SS{i}", "")).isdigit())
                net_val = round(t_d - (t_y / 3.0), 2)

                # Ders listesi
                das_lessons = []
                for i in range(1, 11):
                    l_title = das.get(f"lesson{i}")
                    if l_title:
                        ss_i = das.get(f"SS{i}", 0)
                        d_i = das.get(f"D{i}", 0)
                        y_i = das.get(f"Y{i}", 0)
                        das_lessons.append({
                            "lesson": l_title,
                            "questionCount": ss_i,
                            "dogru": d_i,
                            "yanlis": y_i,
                            "net": round(float(d_i) - (float(y_i) / 3.0), 2) if str(d_i).isdigit() and str(y_i).isdigit() else 0
                        })

                combined_exams.append({
                    "examId": s_name,
                    "examName": s_name,
                    "examDate": s_date,
                    "examType": "DAS",
                    "examCategory": "Tarama / DAS",
                    "isTarama": True,
                    "point": puan_val,
                    "net": net_val,
                    "dogru": t_d,
                    "yanlis": t_y,
                    "bos": max(0, t_ss - t_d - t_y),
                    "questionCount": t_ss,
                    "GD": das.get("GD"),
                    "SD": das.get("SD"),
                    "dasDetail": das,
                    "dasLessons": das_lessons
                })
    except Exception as e:
        print(f"Tarama sınavları çekme hatası: {e}")

    return combined_exams


def fetch_exam_report(exam_id, exam_type="SBS"):
    """Belirli bir sınavın karnesini, netlerini ve konu analizini Akbim'den çeker."""
    profile = get_adaptive_profile_data()
    stu_no = profile.get("student_no") or "20669"
    class_id = profile.get("student_class") or "K-7-E"

    endpoints = [
        f"{akbim_api.BASEURL}/pages/student/require/examDashboard.php",
        f"{akbim_api.BASEURL}/pages/parent/require/examDashboard.php",
    ]

    payload = {
        "request": "getSchoolReport",
        "examType": exam_type or "SBS",
        "examId": exam_id,
        "stuNo": stu_no,
        "classId": class_id,
    }

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/pages/student/index.php"
    }

    for attempt in range(2):
        for ep in endpoints:
            try:
                res = akbim_api.session.post(ep, data=payload, headers=headers)
                if res.ok:
                    data = res.json()
                    if data.get("success"):
                        return data
            except Exception as e:
                print(f"Karne çekme hatası ({ep}): {e}")
        if attempt == 0:
            if not ensure_valid_session():
                break

    return None


def fetch_exam_lesson_answers(exam_index, lesson_place, exam_type="SBS"):
    """
    Belirli bir sınav ve ders için optik cevap anahtarı ve öğrenci işaretlemelerini çeker.
    (Hangi soru doğru, hangi soru yanlış, boş, cevap anahtarı harfleri ve kitapçık kodu)
    """
    profile = get_adaptive_profile_data()
    stu_no = profile.get("student_no") or "20669"

    url = f"{akbim_api.BASEURL}/pages/student/require/examDashboard.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/pages/student/index.php"
    }
    payload = {
        "request": "getDetailsOfExamAnswer",
        "examType": exam_type or "SBS",
        "examIndex": exam_index,
        "lesson": lesson_place,
        "stuNo": stu_no,
    }

    try:
        res = akbim_api.session.post(url, data=payload, headers=headers)
        if res.ok:
            data = res.json()
            if data.get("success"):
                return data.get("data", {})
    except Exception as e:
        print(f"Soru detayları çekme hatası: {e}")

    return None


def fetch_food_list_data():
    """Yemek listesi hash'ini ve binary PDF içeriğini çeker."""
    if not akbim_api.check_session():
        if not akbim_api.ensure_login():
            return {"success": False, "hash": None, "pdf_bytes": None}

    nav = get_nav_metadata()
    base = nav.get("base", "pages/student/").strip("/")
    candidate_urls = [
        f"{akbim_api.BASEURL}/{base}/require/foodListAction.php",
        f"{akbim_api.BASEURL}/pages/student/require/foodListAction.php",
    ]

    seen = set()
    for action_url in candidate_urls:
        if action_url in seen:
            continue
        seen.add(action_url)

        try:
            res = akbim_api.session.post(
                action_url,
                data={"request": "get-food-list"},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if res.ok:
                data = res.json()
                f_hash = data.get("hash")
                if f_hash:
                    dl_res = akbim_api.session.get(
                        f"{akbim_api.BASEURL}/download.php",
                        params={"file": f_hash, "view": ""}
                    )
                    if dl_res.ok and len(dl_res.content) > 100:
                        return {
                            "success": True,
                            "hash": f_hash,
                            "pdf_bytes": dl_res.content
                        }
        except Exception:
            continue

    return {"success": False, "hash": None, "pdf_bytes": None}


def change_user_password(old_password, new_password, new_password_re):
    """
    Akbim OBS kullanıcısının şifresini değiştirir.
    pages/student/require/changePassword.php veya pages/parent/require/changePassword.php
    Dönüş formatı: {"success": bool, "message": str}
    """
    if not old_password or not new_password or not new_password_re:
        return {"success": False, "message": "Boş alan bıraktınız."}

    if len(new_password) < 6:
        return {"success": False, "message": "Yeni şifreniz en az 6 haneli olmalıdır."}

    if len(new_password) > 30:
        return {"success": False, "message": "Yeni şifreniz en fazla 30 haneli olabilir."}

    if new_password != new_password_re:
        return {"success": False, "message": "Şifreleriniz eşleşmiyor."}

    if old_password == new_password:
        return {"success": False, "message": "Yeni şifreniz mevcut olanla aynı."}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")

    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/changePassword.php",
        f"{akbim_api.BASEURL}/pages/student/require/changePassword.php",
        f"{akbim_api.BASEURL}/pages/parent/require/changePassword.php",
    ]

    payload = {
        "password": old_password,
        "passwordNew": new_password,
        "passwordReNew": new_password_re,
        "request": "editPassword",
    }

    seen = set()
    for ep in candidate_endpoints:
        if ep in seen:
            continue
        seen.add(ep)

        try:
            res = akbim_api.session.post(ep, data=payload)
            if res.ok:
                resp_text = res.text.strip()
                if resp_text == "success":
                    return {"success": True, "message": "Şifreniz başarıyla değiştirildi."}
                elif resp_text == "wrongPassword":
                    return {"success": False, "message": "Mevcut şifrenizi yanlış girdiniz."}
                elif resp_text == "requestDenied":
                    return {"success": False, "message": "Ancak 1 saatte 1 kere şifre değişikliği yapabilirsiniz."}
                elif resp_text == "shortPass":
                    return {"success": False, "message": "Yeni şifreniz en az 6 haneli olmalıdır."}
                elif resp_text == "longPass":
                    return {"success": False, "message": "Yeni şifreniz en fazla 30 haneli olabilir."}
                elif resp_text == "notEqual":
                    return {"success": False, "message": "Şifreleriniz eşleşmiyor."}
                elif resp_text == "samePass":
                    return {"success": False, "message": "Yeni şifreniz mevcut olanla aynı."}
                elif resp_text == "empty":
                    return {"success": False, "message": "Boş alan bıraktınız."}
                else:
                    return {"success": False, "message": f"Sistem yanıtı: {resp_text}"}
        except Exception as e:
            print(f"Şifre değiştirme isteği hatası ({ep}): {e}")
            continue

    return {"success": False, "message": "Şifre değiştirme servisine ulaşılamadı."}


def fetch_teachers_data():
    """Öğrencinin dersine giren öğretmenlerin listesini ve fotoğraflarını çeker."""
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    
    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/teacherAction.php",
        f"{akbim_api.BASEURL}/pages/student/require/teacherAction.php",
    ]

    for attempt in range(2):
        for ep in candidate_endpoints:
            try:
                res = akbim_api.session.post(
                    ep,
                    data={"request": "loadMyOwnTeachers"},
                    headers={"X-Requested-With": "XMLHttpRequest"}
                )
                if res.ok and res.text.strip().startswith("{"):
                    data = res.json()
                    if data.get("success"):
                        return data.get("data", [])
            except Exception:
                pass

        if attempt == 0:
            if not ensure_valid_session():
                break

    return []


def fetch_events_data():
    """Okul etkinlikleri listesini çeker."""
    index_data = get_adaptive_index_data()
    return index_data.get("data", {}).get("eventList", []) or []


def fetch_messages_data(box_type=None):
    """Gelen kutusu ve gönderilen postaları çeker (oturum düşerse otomatik yeniler)."""
    inbox_data = {}
    sent_data = {}
    for attempt in range(2):
        try:
            inbox_res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/mail/getInbox")
            if inbox_res.ok:
                inbox_data = inbox_res.json()
                if isinstance(inbox_data, dict) and inbox_data.get("error") == "Login required":
                    if attempt == 0 and ensure_valid_session():
                        continue
                    else:
                        notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                        break

            sent_res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/mail/getSentMail")
            if sent_res.ok:
                sent_data = sent_res.json()
            break
        except Exception as e:
            print(f"Mesaj listesi çekme hatası: {e}")
            if attempt == 0 and not ensure_valid_session():
                break

    inbox_mails = inbox_data.get("data", {}).get("mail", []) if isinstance(inbox_data, dict) else []
    sent_mails = sent_data.get("data", {}).get("mail", []) if isinstance(sent_data, dict) else []
    counts = inbox_data.get("data", {}).get("count", {}) if isinstance(inbox_data, dict) else {}

    if box_type in ("inbox", "gelen"):
        return inbox_mails
    elif box_type in ("sent", "outbox", "giden"):
        return sent_mails

    return inbox_mails, sent_mails, counts


def fetch_mail_content(mail_id):
    """
    Belirli bir postanın tam metnini ve ek dosya bilgilerini çeker (oturum düşerse otomatik yeniler).
    POST /obsapi/mail/getMailContent with {"mailId": mail_id}
    """
    for attempt in range(2):
        try:
            res = akbim_api.session.post(
                f"{akbim_api.BASEURL}/obsapi/mail/getMailContent",
                data={"mailId": mail_id}
            )
            if res.ok:
                data = res.json()
                if data.get("success"):
                    return data.get("data", {}).get("mailContent", {})
                elif data.get("error") == "Login required":
                    if attempt == 0 and ensure_valid_session():
                        continue
                    else:
                        notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                        break
        except Exception as e:
            print(f"Mail içeriği çekme hatası: {e}")
            break
    return None


def search_mail_receivers(query):
    """Öğretmen veya okul yöneticisi arar."""
    try:
        return akbim_api.search_receivers(query)
    except Exception as e:
        print(f"Alıcı arama köprüsü hatası: {e}")
        return []


def send_mail_message(title, content, receiver_user_type, receiver_user_id, reply_id=""):
    """Öğretmene veya yöneticiye mesaj gönderir (oturum düşerse otomatik yeniler)."""
    for attempt in range(2):
        try:
            res = akbim_api.send_mail(
                title=title,
                content=content,
                receiver_user_type=receiver_user_type,
                receiver_user_id=receiver_user_id,
                reply_id=reply_id
            )
            if res.get("success"):
                return res
            elif attempt == 0 and ("500" in str(res.get("msg")) or "oturum" in str(res.get("msg")).lower()):
                if ensure_valid_session():
                    continue
            return res
        except Exception as e:
            if attempt == 0 and ensure_valid_session():
                continue
            return {"success": False, "msg": str(e)}
    return {"success": False, "msg": "Mesaj gönderilemedi."}



def fetch_homeworks_list():
    """Ödevler listesini çeker (akbim_api.homeworks() kullanarak, oturum düşerse otomatik yeniler)."""
    for attempt in range(2):
        try:
            res = akbim_api.homeworks()
            if isinstance(res, dict):
                if res.get("success"):
                    return res.get("data", [])
                elif res.get("error") == "Login required":
                    if attempt == 0 and ensure_valid_session():
                        continue
                    else:
                        notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                        break
            elif isinstance(res, list):
                return res
        except Exception as e:
            print(f"Ödevler listesi çekme hatası: {e}")
            if attempt == 0 and not ensure_valid_session():
                break
    return []


def fetch_homework_detail(homework_id):
    """Belirli bir ödevin detaylarını ve açıklamalarını çeker (oturum düşerse otomatik yeniler)."""
    for attempt in range(2):
        try:
            res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/homework/getHomeworkDetail?id={homework_id}")
            if res.ok:
                data = res.json()
                if data.get("success"):
                    return data.get("data", {})
                elif data.get("error") == "Login required":
                    if attempt == 0 and ensure_valid_session():
                        continue
                    else:
                        notify_session_expired("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.")
                        break
        except Exception as e:
            print(f"Ödev detay çekme hatası: {e}")
            break
    return None


def download_homework_attachment(homework_id, file_id, file_hash=None, file_type="attachFiles"):
    """
    Ödev ek dosyasını indirir ve (dosya_içeriği_bytes, hata_mesajı) döner.
    file_hash varsa doğrudan download.php üzerinden hızlıca çeker, gerekirse token yöntemine geri döner.
    """
    try:
        # 1. Hızlı ve doğrudan hash yöntemi (Arşiv swift istemcisi standardı)
        if file_hash:
            dl_res = akbim_api.session.get(f"{akbim_api.BASEURL}/download.php?file={file_hash}")
            if dl_res.ok and len(dl_res.content) > 0:
                return dl_res.content, None

        # 2. Token tabanlı yöntem (Fallback)
        params = {
            "homeworkId": homework_id,
            "fileId": file_id,
            "fileType": file_type
        }
        token_res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/homework/getHomeworkFileToken", params=params)
        if token_res.ok:
            token_data = token_res.json()
            token = token_data.get("token")
            if token:
                dl_url = f"{akbim_api.BASEURL}/obsapi/public/downloadFileByToken?f={token}"
                dl_res = akbim_api.session.get(dl_url)
                if dl_res.ok and len(dl_res.content) > 0:
                    return dl_res.content, None

        return None, "Dosya sunucudan indirilemedi."
    except Exception as e:
        return None, str(e)


def fetch_attendance_data():
    """Öğrencinin devamsızlık özetini ve listesini çeker."""
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    endpoint = f"{akbim_api.BASEURL}/{role_base}/require/attendanceDashboard.php"

    for attempt in range(2):
        try:
            init_res = akbim_api.session.post(
                endpoint,
                data={"request": "load-attendance-initial-data"},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if init_res.ok and init_res.text.strip().startswith("{"):
                init_data = init_res.json()
                periods = init_data.get("periods", [])
                period_id = periods[0].get("id") if periods else None
                
                # Devamsızlık detay listesini çek (varsa)
                absence_list = []
                if period_id is not None:
                    list_res = akbim_api.session.post(
                        endpoint,
                        data={"request": "get-attendance-graph-7", "periodId": period_id},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    if list_res.ok and list_res.text.strip().startswith("{"):
                        absence_list = list_res.json().get("list", []) or []

                return {
                    "success": True,
                    "periods": periods,
                    "charts": init_data.get("charts", {}),
                    "absence_list": absence_list
                }
        except Exception:
            pass

        if attempt == 0:
            if not ensure_valid_session():
                break

    return {"success": False, "periods": [], "charts": {}, "absence_list": []}


def get_student_general_report():
    """
    Veli Paneli için kapsamlı Öğrenci Durum Raporunu çeker.
    (Deneme sınavları, DAS puanları, ders bazlı ödev tamamlama sayıları, devamsızlık ve öğretmen bilgileri)
    """
    payload = {
        "request": "getStudentGeneralList",
        "studentList": 0,
        "teacherInfo": 2,
        "exams": 2,
        "dbs": 2,
        "attendance": 2,
        "exam": 2,
        "homework": 2,
        "course1": 2,
        "course2": 2,
        "library": 2
    }
    endpoints = [
        f"{akbim_api.BASEURL}/pages/student/require/studentGeneralList.php",
        f"{akbim_api.BASEURL}/pages/parent/require/studentGeneralList.php"
    ]
    for attempt in range(2):
        for ep in endpoints:
            try:
                res = akbim_api.session.post(ep, data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
                if res.ok and res.text.strip().startswith("{"):
                    data = res.json()
                    if data.get("success"):
                        students = data.get("data", {}).get("students", [])
                        if students:
                            return students[0]
            except Exception:
                pass
        if attempt == 0:
            if not ensure_valid_session():
                break

    return None


def open_file_external(file_path):
    """
    Çapraz platform (macOS, Linux, Windows) harici dosya / PDF açıcı.
    macOS: 'open'
    Linux: 'xdg-open'
    Windows: 'os.startfile'
    """
    import sys
    import subprocess
    import os

    try:
        p_str = str(file_path)
        if sys.platform == "darwin":
            subprocess.Popen(["open", p_str])
        elif sys.platform.startswith("win"):
            os.startfile(p_str)
        else:
            subprocess.Popen(["xdg-open", p_str])
        return True
    except Exception as e:
        print(f"Harici dosya açma hatası ({file_path}): {e}")
        return False


def fetch_system_notifications():
    """
    Okul sisteminin anlık canlı bildirimlerini çeker (/obsapi/notification/list).
    Ödev, sınav ve etkinlik bildirimlerini içerir.
    """
    for attempt in range(2):
        try:
            res = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/notification/list")
            if res.ok:
                data = res.json()
                if data.get("success"):
                    return data.get("result", {}).get("notifications", [])
                elif attempt == 0 and ensure_valid_session():
                    continue
        except Exception as e:
            print(f"Bildirim çekme hatası: {e}")
            if attempt == 0 and ensure_valid_session():
                continue
    return []


def fetch_borrowed_books():
    """
    Öğrencinin kütüphaneden ödünç aldığı kitapların listesini çeker.
    """
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/libraryAction.php",
        f"{akbim_api.BASEURL}/pages/student/require/libraryAction.php",
        f"{akbim_api.BASEURL}/pages/parent/require/libraryAction.php",
    ]
    for attempt in range(2):
        for ep in candidate_endpoints:
            try:
                res = akbim_api.session.post(
                    ep,
                    data={"request": "loadBorrowedBookList"},
                    headers={"X-Requested-With": "XMLHttpRequest"}
                )
                if res.ok and res.text.strip().startswith("{"):
                    data = res.json()
                    if data.get("success"):
                        return data.get("data", [])
            except Exception:
                pass
        if attempt == 0 and not ensure_valid_session():
            break
    return []


def search_library_books(query):
    """
    Okul kütüphane kataloğunda kitap arar.
    """
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/libraryAction.php",
        f"{akbim_api.BASEURL}/pages/student/require/libraryAction.php",
        f"{akbim_api.BASEURL}/pages/parent/require/libraryAction.php",
    ]
    for ep in candidate_endpoints:
        try:
            res = akbim_api.session.post(
                ep,
                data={"request": "searchBook", "query": query},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if res.ok and res.text.strip().startswith("{"):
                data = res.json()
                if data.get("success"):
                    return data.get("data", [])
        except Exception:
            pass
    return []


def fetch_course_dashboard():
    """
    Öğrencinin etüt ve birebir ders analizlerini çeker.
    """
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/courseDashboard.php",
        f"{akbim_api.BASEURL}/pages/student/require/courseDashboard.php",
        f"{akbim_api.BASEURL}/pages/parent/require/courseDashboard.php",
    ]
    for attempt in range(2):
        for ep in candidate_endpoints:
            try:
                res = akbim_api.session.post(
                    ep,
                    data={"request": "loadCourseDashboard"},
                    headers={"X-Requested-With": "XMLHttpRequest"}
                )
                if res.ok and res.text.strip().startswith("{"):
                    data = res.json()
                    if data.get("success"):
                        return data.get("data", {})
            except Exception:
                pass
        if attempt == 0 and not ensure_valid_session():
            break
    return {}


def fetch_etut_records():
    """
    Öğrencinin kayıtlı etüt ve birebir ders listesini çeker.
    """
    records = {"etut": [], "birebir": [], "counseling": []}
    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    candidate_endpoints = [
        f"{akbim_api.BASEURL}/{role_base}/require/indexData.php",
        f"{akbim_api.BASEURL}/pages/student/require/indexData.php",
        f"{akbim_api.BASEURL}/pages/parent/require/indexData.php",
    ]
    for attempt in range(2):
        for ep in candidate_endpoints:
            try:
                # Etüt listesi
                if not records["etut"]:
                    r_etut = akbim_api.session.post(
                        ep,
                        data={"data": "etut"},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    if r_etut.ok and r_etut.text.strip().startswith("{"):
                        d = r_etut.json()
                        if d.get("success"):
                            records["etut"] = d.get("data", [])

                # Birebir listesi
                if not records["birebir"]:
                    r_bir = akbim_api.session.post(
                        ep,
                        data={"data": "birebir"},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    if r_bir.ok and r_bir.text.strip().startswith("{"):
                        d = r_bir.json()
                        if d.get("success"):
                            records["birebir"] = d.get("data", [])

                # Rehberlik / Görüşmeler
                if not records["counseling"]:
                    r_coun = akbim_api.session.post(
                        ep,
                        data={"data": "counseling"},
                        headers={"X-Requested-With": "XMLHttpRequest"}
                    )
                    if r_coun.ok and r_coun.text.strip().startswith("{"):
                        d = r_coun.json()
                        if d.get("success"):
                            records["counseling"] = d.get("data", [])
            except Exception:
                pass
        if records["etut"] or records["birebir"] or records["counseling"]:
            return records
        if attempt == 0 and not ensure_valid_session():
            break
    return records


def fetch_birebir_form_metadata():
    """
    Etüt / Birebir alma sayfasındaki program, ders ve tür seçeneklerini döner.
    """
    for attempt in range(2):
        try:
            r = akbim_api.session.get(f"{akbim_api.BASEURL}/pages/student/birebir.php")
            if r.ok:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(r.text, "html.parser")
                programs = [{"id": o["value"], "title": o.text.strip()} for o in soup.select("#optprogram option") if o.get("value")]
                lessons = [{"id": o["value"], "title": o.text.strip()} for o in soup.select("#optlesson option") if o.get("value")]
                return {
                    "programs": programs,
                    "lessons": lessons
                }
        except Exception as e:
            print(f"Birebir form bilgisi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break
    return {"programs": [], "lessons": []}


def fetch_birebir_teachers(lesson_id):
    """
    Seçilen derse ait öğretmen listesini çeker.
    """
    for attempt in range(2):
        try:
            r = akbim_api.session.post(
                f"{akbim_api.BASEURL}/pages/student/require/teacherlist.php",
                data={"lessonid": str(lesson_id)},
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if r.ok:
                data = r.json()
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            print(f"Öğretmen listesi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break
    return []


def fetch_birebir_schedule(lesson_id, teacher_id, program_id="3", week="-1", year="-1", course_type="0"):
    """
    Seçilen ders ve öğretmen için etüt/birebir takvimini çeker.
    course_type: '0' -> Etüt, '1' -> Birebir
    """
    for attempt in range(2):
        try:
            r = akbim_api.session.post(
                f"{akbim_api.BASEURL}/pages/student/require/loadbirebir.php",
                data={
                    "lessonid": str(lesson_id),
                    "teacherid": str(teacher_id),
                    "programId": str(program_id),
                    "week": str(week),
                    "year": str(year),
                    "courseType": str(course_type)
                },
                headers={"X-Requested-With": "XMLHttpRequest"}
            )
            if r.ok and r.text.strip():
                data = r.json()
                if data.get("success"):
                    return data
        except Exception as e:
            print(f"Etüt takvimi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break
    return {}


def get_effective_school_date(dt=None):
    """
    Kullanıcı Kuralı: Gün saat 16:30'da biter.
    Pazartesi 16:30'dan sonra Salı, Cuma 16:30'dan sonra Pazartesi,
    Hafta sonu ise Pazartesi aktif okul tarihi kabul edilir.
    """
    from datetime import datetime, time, timedelta
    if dt is None:
        dt = datetime.now()
    cur_time = dt.time()
    cur_date = dt.date()
    weekday = dt.weekday()  # 0: Pzt, 1: Salı, 2: Çarş, 3: Perş, 4: Cuma, 5: Cts, 6: Paz

    day_ended = (cur_time >= time(16, 30))

    if 0 <= weekday <= 3:  # Pzt - Perş
        if day_ended:
            return cur_date + timedelta(days=1)
        return cur_date
    elif weekday == 4:  # Cuma
        if day_ended:
            return cur_date + timedelta(days=3)  # Pazartesi
        return cur_date
    elif weekday == 5:  # Cumartesi
        return cur_date + timedelta(days=2)  # Pazartesi
    else:  # Pazar (6)
        return cur_date + timedelta(days=1)  # Pazartesi


def get_effective_school_day_idx(dt=None):
    """
    1..5 arasında okul günü index'i döner:
    1: Pazartesi, 2: Salı, 3: Çarşamba, 4: Perşembe, 5: Cuma.
    Saat 16:30'dan sonra otomatik olarak bir sonraki okul gününe geçer.
    """
    effective_date = get_effective_school_date(dt)
    return effective_date.isoweekday()


def fetch_classical_exams():
    """
    MEB Klasik Yazılı Sınav Notlarını (classicalExamDashboard.php) çeker.
    1. Dönem ve 2. Dönem yazılı notları, sınıf ortalamaları ve ders bazlı sonuçları döner.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    url = f"{akbim_api.BASEURL}/{role_base}/require/classicalExamDashboard.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/classicalExamDashboard.php"
    }
    payload = {"request": "get-classical-exam-initial-data"}

    try:
        res = akbim_api.session.post(url, data=payload, headers=headers, timeout=8)
        if res.ok and res.text.strip().startswith("{"):
            return res.json()
    except Exception:
        pass
    return {}


def fetch_teacher_notes(show="me", page=0):
    """
    Öğretmenlerin ve rehberliğin öğrenci hakkındaki görüş ve bülten notlarını çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {"comments": [], "counts": {}, "teachers": []}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    url = f"{akbim_api.BASEURL}/{role_base}/require/teacherNotes.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/teacherNotes.php"
    }

    comments = []
    counts = {}
    teachers = []

    for attempt in range(2):
        try:
            # 1. Notları çek
            r1 = akbim_api.session.post(
                url,
                data={"request": "loadComment", "show": show, "page": page},
                headers=headers,
                timeout=8
            )
            if r1.ok and r1.text.strip().startswith("{"):
                d1 = r1.json()
                if d1.get("success"):
                    comments = d1.get("data", [])

            # 2. Sayımları çek
            r2 = akbim_api.session.post(
                url,
                data={"request": "loadCount", "show": show},
                headers=headers,
                timeout=8
            )
            if r2.ok and r2.text.strip().startswith("{"):
                d2 = r2.json()
                if d2.get("success"):
                    counts = d2.get("data", {})

            # 3. Genel rapordaki notları da destekleyici olarak al
            try:
                gen = get_student_general_report()
                if gen:
                    for k in ["studentNoteAuthorType0", "studentNoteAuthorType1", "studentNoteAuthorType2"]:
                        for n in gen.get(k, []) or []:
                            if n not in comments:
                                comments.append(n)
            except Exception:
                pass

            return {"comments": comments, "counts": counts, "teachers": teachers}
        except Exception as e:
            print(f"Öğretmen görüşleri çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return {"comments": [], "counts": {}, "teachers": []}


def fetch_club_info():
    """
    Öğrencinin kayıtlı olduğu okul kulübü ve etkinlik bilgilerini çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {"clubs": [], "message": "Oturum açılamadı."}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    url = f"{akbim_api.BASEURL}/{role_base}/require/clubAction.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/club.php"
    }

    for attempt in range(2):
        try:
            r = akbim_api.session.post(url, data={"request": "load-student-clubs"}, headers=headers, timeout=8)
            if r.ok and r.text.strip().startswith("{"):
                d = r.json()
                if d.get("navigate"):
                    return {"clubs": [], "message": "Üye olduğunuz bir öğrenci kulübü bulunmuyor."}
                if d.get("data"):
                    return {"clubs": d.get("data", []), "message": ""}
                return {"clubs": [], "message": d.get("msg", "Kulüp bilgisi bulunamadı.")}
        except Exception as e:
            print(f"Kulüp bilgisi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return {"clubs": [], "message": "Kulüp bilgisi alınamadı."}


def fetch_service_list_info():
    """
    Okul servis listesi dosya durumunu ve indirme bağlantısını çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    url = f"{akbim_api.BASEURL}/{role_base}/require/fileFromHash.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/serviceList.php"
    }

    for attempt in range(2):
        try:
            r = akbim_api.session.post(url, data={"dataId": 3}, headers=headers, timeout=8)
            if r.ok and r.text.strip().startswith("{"):
                d = r.json()
                if d.get("data") and d.get("data", {}).get("url"):
                    return {"has_file": True, "url": d["data"]["url"], "msg": ""}
                return {"has_file": False, "url": None, "msg": d.get("msg", "Henüz servis listesi yüklenmemiş.")}
        except Exception as e:
            print(f"Servis listesi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return {"has_file": False, "url": None, "msg": "Servis listesi kontrol edilemedi."}


def fetch_exam_days_calendar():
    """
    Okulun resmi Sınav Günleri takvimini (PDF hash) çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {}

    nav = get_nav_metadata()
    role_base = nav.get("base", "pages/student/").strip("/")
    url = f"{akbim_api.BASEURL}/{role_base}/require/examDaysAction.php"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{akbim_api.BASEURL}/{role_base}/examDays.php"
    }

    for attempt in range(2):
        try:
            r = akbim_api.session.post(url, data={"request": "get-examday-list"}, headers=headers, timeout=8)
            if r.ok and r.text.strip().startswith("{"):
                d = r.json()
                h = d.get("hash")
                if h:
                    download_url = f"{akbim_api.BASEURL}/download.php?file={h}"
                    view_url = f"{akbim_api.BASEURL}/download.php?file={h}&view"
                    return {"has_file": True, "hash": h, "download_url": download_url, "view_url": view_url}
                return {"has_file": False, "hash": None, "msg": d.get("msg", "Sınav günleri listesi henüz yüklenmemiş.")}
        except Exception as e:
            print(f"Sınav günleri takvimi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return {"has_file": False, "hash": None, "msg": "Sınav günleri takvimi alınamadı."}


def fetch_appointments_data():
    """
    Öğrenci ve veli randevu kayıtlarını, uygun görüşülecek öğretmen ve idarecileri çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {"appointments": [], "types": [], "hosts": {}}

    headers = {"X-Requested-With": "XMLHttpRequest"}
    res = {"appointments": [], "types": [], "hosts": {}}

    for attempt in range(2):
        try:
            # 1. Randevu listesi
            r1 = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/appointment/client/getList", headers=headers, timeout=8)
            if r1.ok and r1.text.strip().startswith("{"):
                d1 = r1.json()
                if d1.get("success"):
                    res["appointments"] = d1.get("data", [])

            # 2. Randevu türleri
            r2 = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/appointment/client/getType", headers=headers, timeout=8)
            if r2.ok and r2.text.strip().startswith("{"):
                d2 = r2.json()
                if d2.get("success"):
                    res["types"] = d2.get("result", [])

            # 3. Görüşülebilir rehberlik & öğretmen listesi
            r3 = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/appointment/client/hosts", headers=headers, timeout=8)
            if r3.ok and r3.text.strip().startswith("{"):
                d3 = r3.json()
                if d3.get("success"):
                    res["hosts"] = d3.get("result", {})

            return res
        except Exception as e:
            print(f"Randevu verileri çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return res


def fetch_surveys_data():
    """
    Okul anketlerini ve öğretmen değerlendirme anketlerini çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return {"surveys": [], "teacherSurveys": []}

    headers = {"X-Requested-With": "XMLHttpRequest"}
    for attempt in range(2):
        try:
            r = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/survey/list", headers=headers, timeout=8)
            if r.ok and r.text.strip().startswith("{"):
                d = r.json()
                if d.get("success"):
                    return d.get("result", {"surveys": [], "teacherSurveys": []})
        except Exception as e:
            print(f"Anket listesi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return {"surveys": [], "teacherSurveys": []}


def fetch_newsletters_data():
    """
    Okul bülten ve güncelerini çeker.
    """
    if not akbim_api.check_session():
        if not ensure_valid_session():
            return []

    headers = {"X-Requested-With": "XMLHttpRequest"}
    for attempt in range(2):
        try:
            r = akbim_api.session.get(f"{akbim_api.BASEURL}/obsapi/newsletter/getList", headers=headers, timeout=8)
            if r.ok and r.text.strip().startswith("{"):
                d = r.json()
                if d.get("success"):
                    return d.get("result", [])
        except Exception as e:
            print(f"Bülten listesi çekme hatası: {e}")
        if attempt == 0 and not ensure_valid_session():
            break

    return []


# Aliases for PyQt6 and general frontend convenience
fetch_homework_data = fetch_homeworks_list
fetch_exams_data = fetch_all_student_exams

