from bs4 import BeautifulSoup
import requests
import json
import os
import pickle


BASEURL = "https://tedemkolejiobs.com"

session = requests.Session()

COOKIE_FILE = "akbim_session.pkl"


# =========================
# SESSION KAYDET
# =========================

def save_session():

    with open(COOKIE_FILE, "wb") as file:
        pickle.dump(session.cookies, file)


# =========================
# SESSION YÜKLE
# =========================

def load_session():

    if not os.path.exists(COOKIE_FILE):
        return False

    with open(COOKIE_FILE, "rb") as file:
        session.cookies.update(pickle.load(file))

    return True


# =========================
# SESSION KONTROL
# =========================

def check_session():

    response = session.get(
        f"{BASEURL}/require/menuLoader.php"
    )

    return "window.obsNavData = " in response.text


# =========================
# GİRİŞ
# =========================

def login(tc, password):

    data = {
        "request": "login",
        "loginAs": "standard",
        "isRegister": "0",
        "username": tc,
        "password": password,
        "newUser": "0"
    }

    response = session.post(
        f"{BASEURL}/require/class/login.php",
        data=data
    )

    return response.json()


# =========================
# ANA VERİLER
# =========================

def load_index():

    response = session.post(
        f"{BASEURL}/pages/student/require/indexAction.php",
        data={
            "request": "loadIndex"
        }
    )

    return response.json()


def ensure_login():
    """Kayıtlı oturumu yükler, gerekirse kullanıcıdan giriş ister."""
    load_session()
    if check_session():
        print("Akbim oturumu geçerli.")
        return True

    print("Akbim oturumu bulunamadı veya süresi dolmuş.")
    tc = input("TC: ")
    password = input("Password: ")
    result = login(tc, password)
    if result.get("success"):
        save_session()
        return True
    print("Giriş başarısız.")
    return False


# =========================
# SALT-OKUNUR VERİ GETİRİCİLERİ (READ-ONLY)
# =========================

def get_student_profile():
    """Öğrenci ve veli profil bilgilerini çeker."""
    try:
        res = session.get(f"{BASEURL}/pages/student/profile.php")
        if not res.ok:
            return {"error": "Profil sayfasına ulaşılamadı."}
        soup = BeautifulSoup(res.text, "html.parser")
        profile = {}

        student_title = next(
            (h3 for h3 in soup.find_all("h3") if "Öğrenci Bilgileri" in h3.get_text(" ", strip=True)),
            None
        )
        if student_title:
            for el in student_title.find_all_next():
                if el.name == "h3" and "Veli Bilgileri" in el.get_text(" ", strip=True):
                    break
                if el.name == "dt":
                    label = el.get_text(strip=True)
                    dd = el.find_next_sibling("dd")
                    if dd:
                        profile[label] = dd.get_text(strip=True)

        parent_title = next(
            (h3 for h3 in soup.find_all("h3") if "Veli Bilgileri" in h3.get_text(" ", strip=True)),
            None
        )
        if parent_title:
            for dt in parent_title.find_all_next("dt"):
                label = "Veli " + dt.get_text(strip=True)
                dd = dt.find_next_sibling("dd")
                if dd:
                    profile[label] = dd.get_text(strip=True)
                break

        return profile
    except Exception as e:
        return {"error": str(e)}


def homeworks():
    response = session.get(f"{BASEURL}/obsapi/homework/getHomeworkList")
    return response.json()


# =========================
# MESAJ / POSTA İŞLEMLERİ
# =========================

def search_receivers(query):
    """
    Öğretmen veya okul yöneticisi arar.
    Örnek dönüş: [{'userType': 3, 'userId': 785, 'nameSurname': 'ALEV KORKMAZ', 'type': 'Öğretmen'}]
    """
    try:
        response = session.get(
            f"{BASEURL}/obsapi/mail/getReceiverList",
            params={"q": query}
        )
        if response.ok:
            return response.json().get("data", [])
    except Exception as e:
        print(f"Alıcı arama hatası: {e}")
    return []


def send_mail(title, content, receiver_user_type, receiver_user_id, reply_id=""):
    """
    Öğretmene veya yöneticiye mesaj/posta gönderir.
    - title: Mesaj başlığı (en az 5, en fazla 100 karakter)
    - content: Mesaj içeriği (en az 10, en fazla 5000 karakter)
    - receiver_user_type: 3 (Öğretmen) veya 4 (Yönetici)
    - receiver_user_id: Öğretmenin sistemdeki userId'si
    - reply_id: Yanıt veriliyorsa önceki mesajın ID'si, yeni mesajsa ""
    """
    receivers_json = json.dumps([
        {"type": str(receiver_user_type), "id": str(receiver_user_id)}
    ])

    data = {
        "title": title,
        "content": content,
        "receivers": receivers_json,
        "canReply": "true",
        "shouldReply": "false",
        "replyId": reply_id
    }

    try:
        response = session.post(
            f"{BASEURL}/obsapi/mail/sendMail",
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if response.ok:
            return response.json()
        return {"success": False, "msg": f"Sunucu hatası: {response.status_code}"}
    except Exception as e:
        return {"success": False, "msg": str(e)}


