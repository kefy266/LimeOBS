# 🍋 LimeOBS — Modern Öğrenci & Veli Masaüstü İstemcisi

> **ÖNEMLİ YASAL VE RESMİ BİLGİLENDİRME (DISCLAIMER):**  
> **LimeOBS**, Akbim OBS altyapısını kullanan okulların öğrenci ve velileri için bağımsız ve açık kaynaklı bir masaüstü arayüzü olarak geliştirilmiştir.  
> Bu projenin **Akbim**, okul yönetimleri veya ilgili kurumlar ile hiçbir ticari, kurumsal ya da resmi bağlantısı **YOKTUR**. Tamamen isteğe bağlı ve üçüncü taraf bir istemci (client) yazılımıdır. Kullanıcılar hesap bilgileri ve oturumlarını kendi sorumluluklarında kullanırlar.

---

## ✨ Özellikler

* 🧊 **Liquid Glass Tasarımı:** macOS / modern cam tasarımından ilham alan nötr buzlu cam (frosted glass) ve şeffaf kart katmanları.
* 🎨 **3 Farklı Tema Desteği:**
  * **Liquid Glass:** Nötr, derin ve şeffaf buzlu cam arayüzü.
  * **Koyu (Dark):** Göz yormayan, kontrastı dengeli karanlık tema.
  * **Beyaz (Light):** Kristal netliğinde, aydınlık ve ferah açık tema.
* 🔘 **Tam Yuvarlatılmış Geometri:** Modern pill butonlar, akıcı köşe radyanları ve zarif kenarlıklar.
* 👨‍👩‍👧 **Akıllı Veli Paneli & Kolay Geçiş:**
  * Veli girişi yapıldığında karmaşık listeler yerine öğrencinin temiz özet kartı (Fotoğraf, Devamsızlık, Yaklaşan Sınavlar, Aktif Ödevler).
  * Tek tıkla detaylı öğrenci görünümüne geçiş ve geri dönüş imkanı.
* ✉️ **Öğretmenlere Mesaj Gönderme & Posta Kutusu:**
  * Gelen ve giden mesajları okuma, ek dosyaları görüntüleme.
  * Öğretmenler sekmesinden veya arama kutusundan isimle öğretmen bularak anında mesaj iletme ve yanıtlama.
* 📅 **Canlı Ders Sayacı & Program:** Günün aktif dersini ve sıradaki dersin kalan süresini canlı gösteren geri sayım rozetleri.
* 📚 **Ödevler & Ek Dosyalar:** Teslim durumları, öğretmen notları ve ekli ödev dosyalarını tek tıkla indirme.
* 📊 **Devamsızlık & Sınavlar:** Ayrıntılı devamsızlık saatleri, karne ve sınav notları takibi.
* 📑 **Dahili PDF Görüntüleyici:** Ödev veya mesaj eklerindeki PDF dosyalarını harici bir programa ihtiyaç duymadan uygulama içinde sayfa gezinmeli ve zoom destekli okuma.
* 🍲 **Yemekhane Menüsü:** Günün yemek listesi ve kalori bilgileri.
* 🏫 **Çoklu Okul / Sunucu Desteği:** Tedem Koleji ve Akbim altyapısını kullanan tüm okulların OBS sunucu adresleriyle uyumlu.

---

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
* **Linux:** Python 3.10+, GTK4, Libadwaita (`libadwaita-1`)
* Python Paketleri: `requirements.txt` içinde (`PyGObject`, `requests`, `beautifulsoup4`, `keyring`, `pypdf` …)

### Kaynak Koddan Çalıştırma
```bash
# Bağımlılıkları yükleyin
python -m venv venv
./venv/bin/pip install -r requirements.txt

# Örnek ayar dosyasını kopyalayın
cp akbim_config.example.json akbim_config.json

# Uygulamayı başlatın
python akbim_frontend/main.py
# veya sanal ortam ile:
./venv/bin/python akbim_frontend/main.py
```

---

## 📦 Dağıtım ve Paketleme (Packaging)

### 1. Linux İkili Dosyası & AppImage
PyInstaller ile tek dosya derlemesi:
```bash
./venv/bin/pyinstaller --noconfirm --onedir --windowed \
  --name "LimeOBS" \
  --icon "akbim_frontend/app_icon.png" \
  --add-data "akbim_frontend/style.css:." \
  --add-data "akbim_frontend/app_icon.png:." \
  --add-data "akbim_frontend/views:views" \
  akbim_frontend/main.py
```

### 2. Masaüstü Kısayolu (.desktop)
Sisteme uygulama başlatıcı olarak eklemek için:
```bash
cp akbim_frontend/app_icon.png ~/.local/share/icons/hicolor/256x256/apps/com.kagan.limeobs.png
cp com.kagan.limeobs.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

### 3. macOS (Apple Silicon M1/M2/M3/M4 & Intel)
macOS üzerinde LimeOBS'u çalıştırmak için:
1. Homebrew ile GTK4 ve Libadwaita yükleyin:
   ```bash
   brew install python@3.11 gtk4 libadwaita pygobject3 poppler adwaita-icon-theme
   ```
2. Tek komutla kurun ve başlatın:
   ```bash
   ./setup_mac.sh
   ```
* macOS için `Command + K` (⌘K) hızlı komut paleti, AppleScript yerel bildirimleri ve yerel PDF açıcı entegredir.
* macOS uygulama simgesi: `akbim_frontend/app_icon.icns`

### 4. Windows (10 / 11)
Windows üzerinde LimeOBS'u çalıştırmak için:
1. `setup_windows.bat` veya PowerShell ile `setup_windows.ps1` dosyasını çift tıklayarak çalıştırın.
2. Windows için yerel Toast bildirimleri (PowerShell / Action Center), `os.startfile` yerel PDF/dosya açıcı ve `Ctrl + K` komut paleti tam uyumludur.
3. Windows simgesi: `akbim_frontend/app_icon.ico`
4. Bağımsız `.exe` oluşturmak için:
   ```cmd
   pyinstaller --noconfirm --onedir --windowed --name LimeOBS --icon akbim_frontend/app_icon.ico akbim_frontend/main.py
   ```

---

## 🔒 Gizlilik ve Güvenlik
* LimeOBS hiçbir verinizi üçüncü şahıslara veya harici sunuculara göndermez.
* Tüm istekler doğrudan okulunuzun resmi OBS sunucusuna şifreli (HTTPS) olarak iletilir.
* Oturum çerezleri yalnızca yerel cihazınızda (`akbim_session.pkl`) saklanır.
* "Beni Hatırla" seçildiğinde TC ve şifre düz metin olarak değil, işletim sisteminin anahtarlığında (GNOME Keyring / KWallet, macOS Keychain, Windows Credential Manager) `keyring` ile saklanır.
* `akbim_config.json`, `*.pkl` ve bildirim durumu dosyaları `.gitignore` ile depodan hariç tutulur; asla commit etmeyin.
