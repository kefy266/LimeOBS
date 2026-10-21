# Akbim OBS API & Entegrasyon Rehberi

Bu doküman, Akbim OBS sisteminden veri çekmek için kullanılan endpoint'leri, oturum yönetimini, veri şemalarını ve örnek kod bloklarını içerir.

---

## 1. Temel Yapılandırma ve Oturum Yönetimi

Sistem PHP oturum çerezleri (`PHPSESSID`) üzerinden çalışır. Oturumu diske `pickle` ile kaydedip saklamak her seferinde tekrar kimlik doğrulama yapma ihtiyacını ortadan kaldırır.

### Temel Değişkenler

- **BASEURL:** `https://tedemkolejiobs.com`
- **Cookie Dosyası:** `akbim_session.pkl`

---

## 2. API Endpoint ve İstek Tablosu

| İşlem | URL / Yol | Metot | POST Body Parametreleri | Yanıt Tipi |
| :--- | :--- | :--- | :--- | :--- |
| **Giriş Yapma** | `/require/class/login.php` | `POST` | `request=login`<br>`loginAs=standard`<br>`isRegister=0`<br>`username={TC}`<br>`password={SIFRE}`<br>`newUser=0` | JSON (`{"success": true}`) |
| **Oturum / Menü Kontrolü** | `/require/menuLoader.php` | `GET` | Yok | HTML / JS (`window.obsNavData`) |
| **Ana Veriler (Ders/Sınav/Duyuru)** | `/pages/student/require/indexAction.php` | `POST` | `request=loadIndex` | JSON |
| **Profil Sayfası** | `/pages/student/profile.php` | `GET` | Yok | HTML (Scraping gerekir) |
| **Yemek Listesi Hash** | `/pages/student/require/foodListAction.php` | `POST` | `request=get-food-list` | JSON (`{"success": true, "hash": "..."}`) |
| **Dosya / PDF İndirme** | `/download.php?file={hash}` | `GET` | URL query (`&view` tarayıcıda açar) | Binary (PDF) |

---

## 3. Veri Yapıları ve JSON Şemaları

### 3.1. Sınavlar (`examList`)

`data["data"]["examList"]` bir liste döner:

```json
[
  {
    "sinavKod": "GLK7-1",
    "sinavAd": "7. SINIF DAS 1",
    "sinavTarih": "01.10.2026",
    "examType": "DBS"
  }
]
```

### 3.2. Haftalık Ders Programı (`lessonSchedule`)

`data["data"]["lessonSchedule"]["data"]` matris yapısındadır:

- **`xInfo`** (Saatler / Sütunlar): `[["09:20 - 10:00"], ["10:10 - 10:50"], ...]`
- **`yInfo`** (Günler / Satırlar): `[["Pazartesi", "05.10.2026"], ["Salı", "06.10.2026"], ...]`
- **`data`** (Hücreler):
  - `x`: Saat indeksi (1 tabanlı; `xInfo[x-1]`)
  - `y`: Gün indeksi (1 tabanlı; `yInfo[y-1]`)
  - `text[0]`: Öğretmen Adı
  - `text[1]`: Ders Adı


---

## 4. Modüler Kod Kütüphanesi

### `akbim_api.py` (Çekirdek Modül)

Tüm istekleri ve oturumu yöneten temel dosya:

```python
import os
import pickle
import requests

BASEURL = "https://tedemkolejiobs.com"
COOKIE_FILE = "akbim_session.pkl"

session = requests.Session()

def save_session():
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(session.cookies, f)

def load_session():
    if not os.path.exists(COOKIE_FILE):
        return False
    with open(COOKIE_FILE, "rb") as f:
        session.cookies.update(pickle.load(f))
    return True

def check_session():
    try:
        res = session.get(f"{BASEURL}/require/menuLoader.php")
        return "window.obsNavData = " in res.text
    except Exception:
        return False

def login(tc, password):
    payload = {
        "request": "login",
        "loginAs": "standard",
        "isRegister": "0",
        "username": tc,
        "password": password,
        "newUser": "0"
    }
    res = session.post(f"{BASEURL}/require/class/login.php", data=payload)
    data = res.json()
    if data.get("success"):
        save_session()
    return data

def ensure_login():
    load_session()
    if check_session():
        return True

    print("Oturum bulunamadı veya süresi dolmuş.")
    tc = input("TC Kimlik No: ")
    password = input("Şifre: ")
    res = login(tc, password)
    return bool(res.get("success"))

def load_index():
    res = session.post(
        f"{BASEURL}/pages/student/require/indexAction.php",
        data={"request": "loadIndex"}
    )
    return res.json()
```

---

## 5. Özellik Bazlı Kullanım Kodları

### 5.1. Sınavları ve Duyuruları Listeleme

```python
from akbim_api import ensure_login, load_index

if not ensure_login():
    exit("Giriş yapılamadı.")

data = load_index().get("data", {})

# Sınavlar
for s in data.get("examList", []):
    print(f"[{s['examType']}] {s['sinavAd']} | Tarih: {s['sinavTarih']} | Kod: {s['sinavKod']}")

# Duyurular
for d in data.get("announcementList", []):
    print(f"Duyuru: {d}")
```

### 5.2. Ders Programı Matrisini Çözme

```python
from akbim_api import ensure_login, load_index

if not ensure_login():
    exit("Giriş yapılamadı.")

schedule = load_index().get("data", {}).get("lessonSchedule", {}).get("data", {})
x_info = schedule.get("xInfo", [])
y_info = schedule.get("yInfo", [])
lessons = schedule.get("data", [])

for day_index, (day_name, day_date) in enumerate(y_info, start=1):
    print(f"\n--- {day_name} ({day_date}) ---")

    # Günün derslerini filtrele ve x sırasına diz
    day_lessons = sorted([l for l in lessons if l["y"] == day_index], key=lambda item: item["x"])

    for l in day_lessons:
        slot = x_info[l["x"] - 1][0]
        teacher, subject = l["text"][0], l["text"][1]
        print(f"{slot} | {subject:<20} | {teacher}")
```

### 5.3. Yemek Listesi PDF'ini İndirme ve Açma

```python
import os
import subprocess
import tempfile
from akbim_api import ensure_login, session, BASEURL

if not ensure_login():
    exit("Giriş yapılamadı.")

res = session.post(
    f"{BASEURL}/pages/student/require/foodListAction.php",
    data={"request": "get-food-list"}
).json()

if res.get("success") and res.get("hash"):
    pdf_url = f"{BASEURL}/download.php?file={res['hash']}"
    pdf_bytes = session.get(pdf_url).content

    target_path = os.path.join(tempfile.gettempdir(), "yemek_listesi.pdf")
    with open(target_path, "wb") as f:
        f.write(pdf_bytes)

    # Linux varsayılan PDF görüntüleyicisinde aç
    subprocess.run(["xdg-open", target_path])
else:
    print("Yemek listesi bulunamadı.")
```

### 5.4. Profil Bilgilerini Kazıma (Scraping)

```python
from bs4 import BeautifulSoup
from akbim_api import ensure_login, session, BASEURL

if not ensure_login():
    exit("Giriş yapılamadı.")

res = session.get(f"{BASEURL}/pages/student/profile.php")
soup = BeautifulSoup(res.text, "html.parser")

profile_data = {}
for dt in soup.find_all("dt"):
    label = dt.get_text(strip=True)
    dd = dt.find_next_sibling("dd")
    if dd:
        profile_data[label] = dd.get_text(strip=True)

print("İsim Soyisim :", profile_data.get("İsim Soyisim"))
print("Sınıf Kodu   :", profile_data.get("Sınıf Kodu"))
```
