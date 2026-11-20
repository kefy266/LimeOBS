# 🍋 LimeOBS — Modern Öğrenci & Veli Masaüstü İstemcisi

> **ÖNEMLİ YASAL VE RESMİ BİLGİLENDİRME (DISCLAIMER):**  
> **LimeOBS**, Akbim OBS altyapısını kullanan okulların öğrenci ve velileri için bağımsız ve açık kaynaklı bir masaüstü arayüzü olarak geliştirilmiştir.  
> Bu projenin **Akbim**, okul yönetimleri veya ilgili kurumlar ile hiçbir ticari, kurumsal ya da resmi bağlantısı **YOKTUR**. Tamamen isteğe bağlı ve üçüncü taraf bir istemci (client) yazılımıdır. Kullanıcılar hesap bilgileri ve oturumlarını kendi sorumluluklarında kullanırlar.

---

## ✨ Özellikler

* 🏠 **Ana sayfa:** canlı ders sayacı, çanta hatırlatıcısı, günün yemeği, aktif ödevler ve son denemeler.
* 🤖 **Yapay zekâ asistanı:** ödev, sınav ve program sorularını OBS verilerine dayanarak cevaplar (Groq, uygulama içinde anahtar gerekmez).
* 🏖️ **Okul takvimi:** MEB ara tatilleri, yarıyıl ve resmî tatiller; tatil haftasında okulun açılacağı haftanın programı gösterilir.
* 📅 **Ders programı:** haftalık program ve logolu, okul/sınıf adlı **PDF çıktısı**.
* 📚 **Ödevler:** teslim durumları, öğretmen notları ve ek dosyalar; ses ve videolar uygulama içinde oynatılır.
* 📊 **Sınavlar:** deneme ve yazılı sonuçları, ders bazlı karne, seçilen sınavların ortalaması.
* ✉️ **Mesajlar:** gelen kutusu, okuma, öğretmenlere yazma ve yanıtlama.
* 🍲 **Yemek listesi**, devamsızlık, etüt/birebir, kütüphane, duyurular, öğretmenler ve profil sayfaları.
* 🖥️ **Sistem tepsisi:** pencere kapatılınca arka planda çalışır, yeni kayıtları masaüstü bildirimiyle haber verir.
* 🌗 Açık / koyu / sistem teması.
* 🔔 **Telefon bildirimleri:** yeni ödev, mesaj, duyuru ve sınav sonuçları kendi Telegram botuna gelir (Profil → Telefon bildirimleri; anahtar yalnızca cihazın anahtar zincirinde tutulur).
* 📱 **Android uygulaması** (`android` dalı): ana ekran widget'ı, ders hatırlatıcısı, çevrimdışı kullanım, tablet düzeni.

---

## 🚀 Kaynak koddan çalıştırma

Gereksinim: Python 3.10+ (sistem GTK'sı vb. gerekmez; arayüz Qt Quick / PySide6).

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python limeobs_qt/main.py
```

Uygulama menüsüne ve KRunner'a eklemek için (Linux):

```bash
./install_desktop.sh
```

---

## 📦 Paketleme

Tüm platformlar tek bir PyInstaller tanımıyla derlenir:

```bash
./venv/bin/pip install pyinstaller
./venv/bin/pyinstaller --noconfirm --clean limeobs.spec
```

* **Linux AppImage:** `./build_appimage.sh` → `dist_appimage/LimeOBS-x86_64.AppImage`
* **macOS .app / .dmg** ve **Windows taşınabilir .zip:** GitHub Actions ("Derleme" iş akışı, `v*` etiketiyle).
* Eski GTK4 sürümü `gtk-legacy` dalında ve `gtk-final` etiketinde saklanır.

---

## 🔒 Gizlilik ve Güvenlik
* **Açık metin şifre saklanmaz:** kimlik bilgileri işletim sisteminin anahtar zincirinde (Linux Secret Service, macOS Keychain, Windows Credential Locker) tutulur.
* OBS istekleri doğrudan okulunun OBS sunucusuna HTTPS ile gider.
* **Asistan:** yalnızca asistana soru sorduğunda; soru ve ondan hesaplanan özet (ödev başlıkları, sınav puanları, ders programı) LimeOBS aracı sunucusu (`lime.kaganefe.com`) üzerinden Groq'a gönderilir. Kimlik bilgileri gönderilmez.
* Resmî tatil listesi `date.nager.at` adresinden alınır (kişisel veri içermez).
* Oturum çerezleri yalnızca cihazında saklanır.
