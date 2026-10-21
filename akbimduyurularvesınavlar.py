from akbim_api import ensure_login, load_index

if not ensure_login():
    print("Giriş yapılamadı!")
    exit()

data = load_index()


def sinavlar():
    liste = data.get("data", {}).get("examList", []) or []
    print("\n=== SINAVLAR ===")

    if not liste:
        print("Sınav bulunamadı.")
        return

    for sinav in liste:
        ad = sinav.get("sinavAd")
        tarih = sinav.get("sinavTarih")
        kod = sinav.get("sinavKod")
        tur = sinav.get("examType")
        print(f"[{tur}] {ad} | Tarih: {tarih} | Kod: {kod}")


def duyurular():
    liste = data.get("data", {}).get("announcementList", []) or []
    print("\n=== DUYURULAR ===")

    if not liste:
        print("Duyuru bulunamadı.")
        return

    for duyuru in liste:
        print(duyuru)


MENU = {
    "s": ("Sınavlar", sinavlar),
    "d": ("Duyurular", duyurular),
}

while True:
    print("\n--- MENÜ ---")
    for tus, (ad, _) in MENU.items():
        print(f"{tus}) {ad}")
    print("q) Çıkış")

    secim = input("Seçim: ").strip().lower()

    if secim == "q":
        print("Görüşürüz!")
        break
    elif secim in MENU:
        MENU[secim][1]()
    else:
        print("Geçersiz seçim.")