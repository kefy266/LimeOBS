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


def get_lesson_schedule():
    """Haftalık ders programını gün ve saatlerine göre düzenli metin olarak döner."""
    try:
        data = load_index()
        schedule = data.get("data", {}).get("lessonSchedule", {}).get("data", {})
        x_info = schedule.get("xInfo", [])
        y_info = schedule.get("yInfo", [])
        lessons = schedule.get("data", [])

        if not lessons or not y_info:
            return "Ders programı verisi bulunamadı veya boş."

        days_output = []
        for day_index, day_data in enumerate(y_info, start=1):
            day_name = day_data[0] if len(day_data) > 0 else f"Gün {day_index}"
            day_date = day_data[1] if len(day_data) > 1 else ""
            date_str = f" ({day_date})" if day_date else ""

            day_lessons = sorted(
                [l for l in lessons if l.get("y") == day_index],
                key=lambda item: item.get("x", 0)
            )

            day_lines = [f"[{day_name}{date_str}]"]
            if not day_lessons:
                day_lines.append("  Ders bulunmuyor.")
            else:
                for l in day_lessons:
                    x_idx = l.get("x", 1) - 1
                    slot = x_info[x_idx][0] if 0 <= x_idx < len(x_info) else "??:??"
                    texts = l.get("text", [])
                    teacher = texts[0] if len(texts) > 0 else "-"
                    subject = texts[1] if len(texts) > 1 else "-"
                    day_lines.append(f"  Saat: {slot} | Ders: {subject} | Öğretmen: {teacher}")

            days_output.append("\n".join(day_lines))

        return "\n\n".join(days_output)
    except Exception as e:
        return f"Ders programı alınırken hata: {e}"


def get_exam_list():
    """Yaklaşan ve kayıtlı sınavların listesini döner."""
    try:
        data = load_index()
        exams = data.get("data", {}).get("examList", []) or []
        if not exams:
            return "Kayıtlı sınav bulunamadı."

        lines = []
        for s in exams:
            tur = s.get("examType", "Sınav")
            ad = s.get("sinavAd", "-")
            tarih = s.get("sinavTarih", "-")
            kod = s.get("sinavKod", "-")
            lines.append(f"[{tur}] {ad} | Tarih: {tarih} | Kod: {kod}")
        return "\n".join(lines)
    except Exception as e:
        return f"Sınavlar alınırken hata: {e}"


def get_announcement_list():
    """Okul duyurularını döner."""
    try:
        data = load_index()
        announcements = data.get("data", {}).get("announcementList", []) or []
        if not announcements:
            return "Yayınlanmış duyuru bulunamadı."
        return "\n".join([f"- {a}" for a in announcements])
    except Exception as e:
        return f"Duyurular alınırken hata: {e}"


def get_event_list():
    """Okul etkinlik takvimini döner."""
    try:
        data = load_index()
        events = data.get("data", {}).get("eventList", []) or []
        if not events:
            return "Planlanmış etkinlik bulunamadı."
        return str(events)
    except Exception as e:
        return f"Etkinlikler alınırken hata: {e}"


def get_all_student_data():
    """Bot için tüm Akbim verilerini tek bir bağlamda (context) birleştirir."""
    profile = get_student_profile()
    profile_str = "\n".join([f"  {k}: {v}" for k, v in profile.items()]) if isinstance(profile, dict) else str(profile)
    schedule_str = get_lesson_schedule()
    exams_str = get_exam_list()
    announcements_str = get_announcement_list()
    events_str = get_event_list()

    return f"""=== ÖĞRENCİ VE VELİ PROFİLİ ===
{profile_str}

=== HAFTALIK DERS PROGRAMI ===
{schedule_str}

=== SINAVLAR ===
{exams_str}

=== DUYURULAR ===
{announcements_str}

=== ETKİNLİKLER ===
{events_str}
"""


# =========================
# PROGRAM BAŞLANGICI
# =========================

if __name__ == "__main__":
    if not ensure_login():
        print("Giriş başarısız.")
        exit()

    print("\n========== AKBIMOBS ==========")
    print("Giriş durumu : Başarılı")


    # =========================
    # MENU / ROLE
    # =========================

    menu_response = session.get(
        f"{BASEURL}/require/menuLoader.php"
    )

    menu_text = menu_response.text


    if "window.obsNavData = " not in menu_text:

        print("Rol bilgisi alınamadı.")
        exit()


    json_text = menu_text.split(
        "window.obsNavData = ",
        1
    )[1]

    json_text = json_text.split(
        "};",
        1
    )[0] + "}"


    try:

        obs_data = json.loads(json_text)

    except json.JSONDecodeError:

        print("Menü verisi okunamadı.")
        exit()


    role = obs_data.get("key")


    # =========================
    # ROL
    # =========================

    if role == "parent":

        print("Rol          : Veli")

    elif role == "student":

        print("Rol          : Öğrenci")

    else:

        print("Rol          :", role)


    # =========================
    # PROFILE URL
    # =========================

    if role == "student":

        profile_url = (
            f"{BASEURL}/pages/student/profile.php"
        )

    elif role == "parent":

        profile_url = (
            f"{BASEURL}/pages/parent/profile.php"
        )

    else:

        profile_url = None


    # =========================
    # PROFİL
    # =========================

    if profile_url:

        profile_response = session.get(
            profile_url
        )

        soup = BeautifulSoup(
            profile_response.text,
            "html.parser"
        )


        # =========================
        # ÖĞRENCİ BİLGİLERİ
        # =========================

        student_title = next(
            (
                h3 for h3 in soup.find_all("h3")
                if "Öğrenci Bilgileri"
                in h3.get_text(" ", strip=True)
            ),
            None
        )

        student_name = None
        student_class = None


        if student_title:

            for element in student_title.find_all_next():

                # Veli bölümüne geldiysek dur
                if (
                    element.name == "h3"
                    and "Veli Bilgileri"
                    in element.get_text(" ", strip=True)
                ):

                    break


                if element.name != "dt":

                    continue


                label = element.get_text(
                    strip=True
                )

                dd = element.find_next_sibling(
                    "dd"
                )


                if not dd:

                    continue


                value = dd.get_text(
                    strip=True
                )


                if label == "İsim Soyisim":

                    student_name = value


                elif label == "Sınıf Kodu":

                    student_class = value


        if student_name:

            print(
                "Öğrenci Ad Soyad:",
                student_name
            )

        else:

            print(
                "Öğrenci Ad Soyad: Bulunamadı."
            )


        if student_class:

            print(
                "Sınıf             :",
                student_class
            )

        else:

            print(
                "Sınıf             : Bulunamadı."
            )


        # =========================
        # VELİ BİLGİLERİ
        # =========================

        parent_title = next(
            (
                h3 for h3 in soup.find_all("h3")
                if "Veli Bilgileri"
                in h3.get_text(" ", strip=True)
            ),
            None
        )

        parent_name = None


        if parent_title:

            for dt in parent_title.find_all_next("dt"):

                if (
                    dt.get_text(strip=True)
                    == "İsim Soyisim"
                ):

                    dd = dt.find_next_sibling(
                        "dd"
                    )


                    if dd:

                        parent_name = (
                            dd.get_text(
                                strip=True
                            )
                        )


                    break


            if parent_name:

                print(
                    "Veli Ad Soyad   :",
                    parent_name
                )

            else:

                print(
                    "Veli Ad Soyad   : Bulunamadı."
                )


        else:

            print(
                "Profil desteği bulunamadı."
            )


    print("================================")

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


def get_mail_content(mail_id):
    """
    Gelen veya giden mesajın detayını çeker.
    """
    try:
        response = session.post(
            f"{BASEURL}/obsapi/mail/getMailContent",
            data={"mailId": mail_id},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Mesaj okuma hatası: {e}")
    return {"success": False}

