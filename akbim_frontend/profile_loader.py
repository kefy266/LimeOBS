import json
from bs4 import BeautifulSoup
import akbim_api


def get_user_role():
    """menuLoader.php üzerinden kullanıcının 'student' mı 'parent' mı olduğunu anlar."""
    try:
        res = akbim_api.session.get(f"{akbim_api.BASEURL}/require/menuLoader.php")
        if "window.obsNavData = " in res.text:
            json_text = res.text.split("window.obsNavData = ", 1)[1].split("};", 1)[0] + "}"
            data = json.loads(json_text)
            return data.get("key", "student")
    except Exception:
        pass
    return "student"


def get_full_profile():
    """Hem Veli (parent) hem de Öğrenci (student) hesaplarına uyumlu profil çıkarıcı."""
    role = get_user_role()
    is_parent = (role == "parent")

    urls = [
        f"{akbim_api.BASEURL}/pages/parent/profile.php" if is_parent else f"{akbim_api.BASEURL}/pages/student/profile.php",
        f"{akbim_api.BASEURL}/pages/student/profile.php",
        f"{akbim_api.BASEURL}/pages/parent/profile.php"
    ]

    profile_data = {
        "role": "Veli" if is_parent else "Öğrenci",
        "student_name": None,
        "student_class": None,
        "student_no": None,
        "student_prog": None,
        "parent_name": None,
        "raw_fields": {}
    }

    for url in urls:
        try:
            res = akbim_api.session.get(url)
            if not res.ok or "Kullanıcı Profili" not in res.text:
                continue

            soup = BeautifulSoup(res.text, "html.parser")

            # 1. Öğrenci Bilgileri Bölümü
            student_h3 = next(
                (h3 for h3 in soup.find_all("h3") if "Öğrenci" in h3.get_text(" ", strip=True)),
                None
            )
            if student_h3:
                for el in student_h3.find_all_next():
                    if el.name == "h3" and "Veli" in el.get_text(" ", strip=True):
                        break
                    if el.name == "dt":
                        label = el.get_text(strip=True)
                        dd = el.find_next_sibling("dd")
                        if dd:
                            val = dd.get_text(strip=True)
                            profile_data["raw_fields"][f"student_{label}"] = val
                            if label == "İsim Soyisim":
                                profile_data["student_name"] = val
                            elif label == "Sınıf Kodu":
                                profile_data["student_class"] = val
                            elif "Numara" in label or "No" in label:
                                profile_data["student_no"] = val
                            elif "Program" in label:
                                profile_data["student_prog"] = val

            # 2. Veli Bilgileri Bölümü
            parent_h3 = next(
                (h3 for h3 in soup.find_all("h3") if "Veli" in h3.get_text(" ", strip=True)),
                None
            )
            if parent_h3:
                for el in parent_h3.find_all_next():
                    if el.name == "h3" and "Hesap" in el.get_text(" ", strip=True):
                        break
                    if el.name == "dt":
                        label = el.get_text(strip=True)
                        dd = el.find_next_sibling("dd")
                        if dd:
                            val = dd.get_text(strip=True)
                            profile_data["raw_fields"][f"parent_{label}"] = val
                            if label == "İsim Soyisim":
                                profile_data["parent_name"] = val

            # Eğer veri bulunduysa döngüden çık
            if profile_data["student_name"] or profile_data["parent_name"]:
                break
        except Exception:
            continue

    return profile_data
