# AkbimOBS Mantığı

> Kişisel notlar: Akbim öğrenci panelinin arka planda nasıl çalıştığı. Genel olarak yapı basit; geliştiriciler kendi kolaylıkları için sade tutmuş. `AKBIMURLSI.com` yerine okulun gerçek alan adı gelir.

**Durum etiketleri:** ✅ Biliniyor · ⚠️ Tahmin / emin değilim · ❓ Çözülmedi

---

## 1. Genel Akış

```
TC + Şifre
    ↓
login.php
    ↓
PHPSESSID (cookie)
    ↓
Cookie ile diğer endpoint'ler
```

Her istekte `PHPSESSID` cookie'si gönderilmesi gerekiyor. Uzun süre (yaklaşık 1 saat) istek atılmazsa oturum düşüyor ve tekrar giriş yapmak gerekiyor.

---

## 2. Giriş

**Endpoint:** `https://AKBIMURLSI.com/require/class/login.php` **Metod:** `POST`

### Gönderilen alanlar

|Alan|Değer|Durum|Açıklama|
|---|---|---|---|
|`request`|`login`|✅|İşlem adı. Hep `login.php`'ye gittiği için `login`|
|`loginAs`|`standard`|⚠️|Öğrenci girişi için `standard`. `admin` / `teacher` gibi değerler olabilir|
|`isRegister`|`0`|❓|Kayıt işlemi mi? Kayıtları okul yapıyor olabilir, o yüzden hep 0|
|`username`|TC kimlik no|✅||
|`password`|Şifre|✅||
|`newUser`|`0`|❓|`isRegister` kadar gizemli|

### Başarılı cevap

```json
{"success":true,"msg":"Tekrar hoşgeldin"}
```

- Bilgiler yanlışsa `msg` içinde hata mesajı geliyor.
- Asıl bakılması gereken alan **`success`** değeri.
- Cevapla birlikte `PHPSESSID` cookie'si set ediliyor.

---

## 3. Ana Veri (`loadIndex`)

**Endpoint:** `https://AKBIMURLSI.com/pages/student/require/indexAction.php` **Metod:** `POST` **Cookie:** `PHPSESSID`

|Alan|Değer|
|---|---|
|`request`|`loadIndex`|

### Gelen veriler

- Duyurular
- Sınavlar (liste)
- Etkinlikler
- Etkinlik / takvim
- Ders programı (`lessonSchedule`)
- Yemek listesi vb.

> ⚠️ Ana ekranın içeriği okul tarafından admin panelinden değiştirilebiliyor (rehberlik ve bazı öğretmenler düzenleyebiliyor). Yani yapı genelde aynı kalsa da bazı alanlar değişebilir. Yemek kısmı çoğu zaman okulun yüklediği bir **PDF'e yönlendiriyor**, yani sabit bir veri yapısı olmayabilir.

---

## 4. Ders Programı (`lessonSchedule`)

### Yapı

```
lessonSchedule
└── data
    ├── xInfo     → ders saatleri
    ├── yInfo     → günler
    └── data      → dersler (array)
```

### `xInfo` — Ders saatleri

|x|Saat|
|---|---|
|1|09:20 - 10:00|
|2|10:10 - 10:50|
|3|11:00 - 11:40|
|...|...|
|8|15:50 - 16:30|

### `yInfo` — Günler

Gün indeksleri (1 = Pazartesi şeklinde, örnekte `y=1` Pazartesi olarak okunuyor).

### `data` — Dersler

Her ders objesinde:

|Alan|Anlamı|
|---|---|
|`x`|Ders saati (xInfo karşılığı)|
|`y`|Gün (yInfo karşılığı)|
|`text[0]`|Öğretmen|
|`text[1]`|Ders adı|

**Örnek:**

```
x = 2
y = 1
text[0] = Hoca
text[1] = Matematik
→ Pazartesi, 2. ders: Matematik (10:10 - 10:50)
```

### `headerTitle` / `headerContent`

Ek bilgi alanları. Programdaki normal dersin yerine özel bir durum olduğunda burada gösteriliyor.

**Örnek:** Her hafta 4 saat deneme saati var. Normalde hücrede "Din Kültürü" yazıyor ve o hoca giriyor, ama o saatte Din görülmüyor, deneme sınavı yapılıyor. Bu durum `headerTitle` içinde "Deneme Sınavı" olarak yazıyor.

> Yani ders adını gösterirken önce `headerTitle` var mı diye bakmak mantıklı.

---

## 5. Sınavlar

> Burası tam çözülmedi ama büyük kısmı çalışıyor.

- Sınav **listesi** `loadIndex` içinde geliyor.
- Sınav **detayı** için `examDashboard.php` kullanılıyor.

### İstek sırası

1. **`getAllGraphsAndSelects`** Sınavları ve diğer seçimleri (dropdown vb.) getirir.
    
2. **`getSchoolReport`** Belirli bir sınavın karnesini getirir. İçeriği:
    
    - Sınav puanı
    - Netler
    - Doğru / yanlış sayıları
    - Cevaplar

### Cevap alanları

|Alan|Anlamı|
|---|---|
|`SC1`, `SC2`, ...|**Cevap anahtarı** (soru-cevap anahtarı)|
|`OC1`, `OC2`, ...|**Öğrencinin cevapları**|

- `SC` / `OC` sonundaki numara **derse göre** değişiyor.
- Örnek: `SC1` Türkçe, `SC2` Sosyal olabiliyor.
- ⚠️ Bu numaralar sabit olmayabilir (`SC2` bazı sınavlarda Matematik olabilir). Ders eşleşmesini sınav tipine göre ayrıca kontrol etmek gerek.
- Boş cevap `" "` (tek boşluk) olarak geliyor.

### Doğru / Yanlış / Boş mantığı

Her soru için aynı index'teki öğrenci cevabı ile anahtar karşılaştırılır:

```
öğrenci cevabı boşsa          → BOŞ
öğrenci cevabı == anahtar     → DOĞRU
aksi halde                    → YANLIŞ
```

**Örnek kod (Python):**

```python
def degerlendir(anahtar: str, ogrenci: str):
    dogru = yanlis = bos = 0
    sonuc = []

    for a, o in zip(anahtar, ogrenci):
        if o.strip() == "":
            bos += 1
            sonuc.append("boş")
        elif o == a:
            dogru += 1
            sonuc.append("doğru")
        else:
            yanlis += 1
            sonuc.append("yanlış")

    return dogru, yanlis, bos, sonuc
```

> Not: Boş kontrolünde `strip()` kullanmak, `" "` gelen cevapları güvenli biçimde yakalar.

---

## 6. Hızlı Özet Tablosu

|İşlem|Endpoint|`request` değeri|
|---|---|---|
|Giriş|`/require/class/login.php`|`login`|
|Ana veri|`/pages/student/require/indexAction.php`|`loadIndex`|
|Sınav seçimleri|`examDashboard.php`|`getAllGraphsAndSelects`|
|Sınav karnesi|`examDashboard.php`|`getSchoolReport`|

---

## 7. Açık Sorular / Yapılacaklar

- [ ] `loginAs` için diğer değerler neler?
- [ ] `isRegister` ve `newUser` gerçekte ne işe yarıyor?
- [ ] `SC` / `OC` numaralarının derslerle eşleşmesi sabit mi?
- [ ] `getSchoolReport` için gereken parametreler (sınav id vb.) dokümante edilecek.
- [ ] Yemek PDF'inin linki hangi alanda geliyor?
- [ ] Oturum süresi tam olarak kaç dakika?