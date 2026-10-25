# LimeOBS — Windows GTK4 & Libadwaita Teknik Rehberi ve Bilgilendirme

Bu doküman, LimeOBS'un Windows 10/11 üzerinde yerel **GTK4** ve **Libadwaita** teknolojileriyle sorunsuz, akıcı ve piksel-mükemmel (native) çalışmasını sağlayan mimariyi, başlatma yöntemlerini, font/ikon optimizasyonlarını ve yeni sürümlerin Windows'a nasıl uyarlanacağını açıklar.

---

## 1. Mimari Genel Bakış

LimeOBS Windows sürümü, sanal makine veya WSL gerektirmeden, **MSYS2 UCRT64** yerel C çalışma zamanı üzerinde çalışır:

* **Python Yürütücüsü:** `C:\msys64\ucrt64\bin\pythonw.exe` (Konsol penceresiz arka plan modu) veya `python.exe`
* **GTK Sürümü:** GTK 4.24+ (`gi.repository.Gtk`)
* **Libadwaita Sürümü:** Libadwaita 1.10+ (`gi.repository.Adw`)
* **Pencere ve Grafik:** Native Win32 (`GdkWin32Toplevel`), Cairo / Direct Composition
* **Görev Çubuğu:** Windows Shell `SetCurrentProcessExplicitAppUserModelID("com.kagan.limeobs")`
* **Pencere İkonu:** Win32 `WM_SETICON` mesajı ile doğrudan `app_icon.ico` (16x16 ve 32x32)

---

## 2. Nasıl Başlatılır?

### A. Masaüstü Kısayolu (Önerilen)
Masaüstünüzde bulunan **LimeOBS** veya **LimeOBS GTK4** kısayoluna çift tıklayarak uygulamayı anında açabilirsiniz.

### B. Batch Dosyası (`LimeOBS_Baslat.bat`)
Proje kök dizinindeki `LimeOBS_Baslat.bat` dosyası tüm ortam değişkenlerini hazırlar ve uygulamayı sessizce başlatır:
```bat
@echo off
chcp 65001 >nul
title LimeOBS - GTK4 & Libadwaita Edition
cd /d "%~dp0"

set "PATH=C:\msys64\ucrt64\bin;%PATH%"
set "GSETTINGS_SCHEMA_DIR=C:\msys64\ucrt64\share\glib-2.0\schemas"
set "XDG_DATA_DIRS=%~dp0akbim_frontend\icons;C:\msys64\ucrt64\share"
set "FREETYPE_PROPERTIES=truetype:interpreter-version=40"
set "FONTCONFIG_PATH=C:\msys64\ucrt64\etc\fonts"

start "" "C:\msys64\ucrt64\bin\pythonw.exe" "akbim_frontend\main.py"
exit /b 0
```

### C. Komut Satırı / Debug Modu
Hata ve konsol çıktılarını doğrudan görmek için:
```powershell
C:\msys64\ucrt64\bin\python.exe akbim_frontend\main.py
```
Tüm konsol logları otomatik olarak proje kökündeki `gtk_debug.log` dosyasına da kaydedilir.

---

## 3. Windows Native Tipografi ve Font Optimizasyonları

Windows'ta Linux font motorunun (FreeType/Fontconfig) bulanık, pikselli veya kesik kesik görünmesini engellemek için şu ayarlar zorunludur:

### 1. Fontconfig Subpixel (ClearType) Yapılandırması
* `C:\msys64\ucrt64\etc\fonts\conf.d\10-sub-pixel-rgb.conf` aktif edildi (RGB yatay alt piksel dizilimi).
* `11-lcdfilter-default.conf` aktif edildi.

### 2. GtkSettings Parametreleri (`akbim_frontend/main.py`)
```python
settings = Gtk.Settings.get_default()
settings.set_property("gtk-font-name", "Segoe UI Variable Text 10.5")
settings.set_property("gtk-hint-font-metrics", False)  # Kesirli (fractional) DirectWrite metrikleri
settings.set_property("gtk-font-rendering", 0)        # Otomatik / Native OS render motoru
settings.set_property("gtk-xft-antialias", 1)
settings.set_property("gtk-xft-hinting", 1)
settings.set_property("gtk-xft-hintstyle", "hintslight")
settings.set_property("gtk-xft-rgba", "rgb")
```

### 3. CSS Kuralı (`akbim_frontend/style.css`)
```css
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
    font-feature-settings: "kern" 1;
}

window, .background, label, button, entry, headerbar, popover, dialog, list, row {
    font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
}
```

---

## 4. İkon ve Simge Mimarisi

GNOME Adwaita 51 sürümünde bazı geleneksel sembolik simgeler taşınmış veya isim değiştirmiştir. Windows üzerinde hiçbir ikonun kırık/boş kutu görünmemesi için:

1. **Özel İkon Dizini:** `akbim_frontend/icons/hicolor/scalable/actions/`
   * `notifications-symbolic.svg` (Alarm/Zil simgesi)
   * `food-symbolic.svg` (Çatal-bıçak simgesi)
   * `mail-inbox-symbolic.svg` (Mektup simgesi)
   * `emblem-documents-symbolic.svg` (Doküman simgesi)
   * `emblem-favorite-symbolic.svg` (Yıldız simgesi)
   * `chat-symbolic.svg` (Mesaj balonu simgesi)
   * `emblem-default-symbolic.svg` (Hesap makinesi / not simgesi)
2. **Uygulama Logosu (`limeobs`):**
   * `akbim_frontend/icons/hicolor/256x256/apps/limeobs.png`
   * `akbim_frontend/limeobs.png`
   * `akbim_frontend/app_icon.ico`
3. **XDG_DATA_DIRS Tanımı:**
   `akbim_frontend/icons` dizini başlatıcıda ve `main.py` içinde `XDG_DATA_DIRS` başına eklenir. Böylece GTK `Gtk.IconTheme` aramalarında yerel simgeleri Adwaita sistem simgelerinden önce bulur.

---

## 5. Kodlama Kuralları (Windows Uyumluluk Standartları)

Linux'tan yeni bir kod çekildiğinde veya yeni bir ekran yazıldığında dikkat edilmesi gereken hayati kurallar:

### Kural 1: Pango Markup'ta Ampersand (`&`) Mutlaka Escape Edilmelidir
Ders isimleri ("Beden Eğitimi & Spor") veya yemek menüleri ("Köfte & Pilav") gibi değişkenler `set_markup()` içine verilirken doğrudan verilirse `GMarkupError` hatası fırlatır ve etiket ekrandan tamamen silinir.
* **Hatalı:** `label.set_markup(f"<b>{ders_adi}</b>")`
* **Doğru:** `label.set_markup(f"<b>{GLib.markup_escape_text(ders_adi)}</b>")`

### Kural 2: Ham Emojiler Yerine GTK Vektör İkonları Kullanılmalıdır
Windows GDI font eşleyicisi Pango üzerinden renkli unicode emojilerini (`🍴`, `📚`, `🔔`, `🎒`, `📊`) render edemez; ekranda kırık kare (`□`) gösterir.
* **Hatalı:** `icon_lbl = Gtk.Label(label="🍴")`
* **Doğru:** `icon_img = Gtk.Image.new_from_icon_name("emoji-food-symbolic"); icon_img.set_pixel_size(18)`

### Kural 3: Türkçe Tarih Formatlama
Windows'ta `now.strftime("%d %B %Y %A")` İngilizce döner ("25 October 2026 Sunday"). Tarih etiketleri için Türkçe sözlük kullanılmalıdır:
```python
months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
days_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
formatted_date = f"{now.day} {months_tr[now.month - 1]} {now.year} {days_tr[now.weekday()]}"
```

### Kural 4: `alpha` (Saydamlık) Maskeleri Yerine Opak Renkler
Pango etiketlerinde `alpha='70%'` kullanmak harflerin alt piksel kenarlarını silikleştirip koyu temada tırtıklanmaya sebep olur. Bunun yerine opak renkler (`foreground='#b8b8b8'` veya `#d0d0d0`) tercih edilmelidir.

### Kural 5: Suni Kalınlaştırma Yapılmamalıdır
Segoe UI fontunda `weight='heavy'` veya `weight='800'` bulunmadığı için GTK harfleri çeperlerinden suni olarak genişletip bulandırır. Başlık ve rozetlerde Windows Fluent standardı olan **`weight='bold'` / `font-weight: 600` (Segoe UI Semibold)** kullanılmalıdır.

---

## 6. GitHub'dan Yeni Sürüm Çekildiğinde Yapılacaklar

GitHub'dan yeni kod çekildiğinde (`git pull` veya zip indirme):
1. `akbim_frontend/main.py` başındaki Windows bootstrap bloklarının korunduğundan emin olun.
2. `akbim_frontend/icons` dizininin korunduğundan emin olun.
3. Yeni eklenen menü veya butonlarda eksik sembolik ikon adı varsa bu rehberin 4. maddesindeki gibi `icons/` dizinine alias ekleyin veya Adwaita standart adına eşleyin.
4. Başlatıcı `LimeOBS_Baslat.bat` üzerinden uygulamayı test edin.
