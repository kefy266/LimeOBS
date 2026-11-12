package com.kagan.limeobs

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.FormBody
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import org.jsoup.Jsoup
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Oturum düştü ve kayıtlı bilgilerle yeniden girilemedi. */
class OturumHatasi(mesaj: String = "Oturumun sona erdi. Lütfen tekrar giriş yap.") : Exception(mesaj)

/** Çerezleri SharedPreferences'ta saklayan basit çerez kavanozu. */
private class KaliciCerez(private val prefs: SharedPreferences) : CookieJar {
    private val cerezler = mutableListOf<Cookie>()

    init {
        val kayit = prefs.getString("cerezler", null)
        if (kayit != null) runCatching {
            val dizi = JSONArray(kayit)
            for (i in 0 until dizi.length()) {
                val o = dizi.getJSONObject(i)
                val b = Cookie.Builder().name(o.getString("n")).value(o.getString("v")).path(o.optString("p", "/"))
                if (o.optBoolean("h")) b.hostOnlyDomain(o.getString("d")) else b.domain(o.getString("d"))
                if (o.optBoolean("s")) b.secure()
                if (o.optBoolean("ho")) b.httpOnly()
                if (o.optBoolean("k")) b.expiresAt(o.getLong("e"))
                cerezler.add(b.build())
            }
        }
    }

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        for (c in cookies) {
            cerezler.removeAll { it.name == c.name && it.domain == c.domain && it.path == c.path }
            cerezler.add(c)
        }
        kaydet()
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val simdi = System.currentTimeMillis()
        cerezler.removeAll { it.expiresAt < simdi }
        return cerezler.filter { it.matches(url) }
    }

    @Synchronized
    fun temizle() {
        cerezler.clear()
        kaydet()
    }

    private fun kaydet() {
        val dizi = JSONArray()
        for (c in cerezler) {
            dizi.put(JSONObject().apply {
                put("n", c.name); put("v", c.value); put("d", c.domain); put("p", c.path)
                put("h", c.hostOnly); put("s", c.secure); put("ho", c.httpOnly)
                put("k", c.persistent); put("e", c.expiresAt)
            })
        }
        prefs.edit().putString("cerezler", dizi.toString()).apply()
    }
}

// ---------- Veri modelleri ----------

data class Profil(
    val ad: String,
    val sinif: String,
    val numara: String,
    val veli: String,
    val rol: String,
    val okul: String,
    val foto: ByteArray?,
    val alanlar: List<Pair<String, String>>,
)

data class DersHucresi(val gun: Int, val saat: Int, val ders: String, val ogretmen: String, val renk: Long)

data class DersProgrami(val saatler: List<String>, val gunler: List<Pair<String, String>>, val hucreler: List<DersHucresi>)

data class YaklasanSinav(val ad: String, val tarih: String, val tur: String)

data class AnaVeri(
    val program: DersProgrami,
    val sinavlar: List<YaklasanSinav>,
    val duyurular: List<String>,
    val etkinlikler: List<String>,
)

data class Odev(
    val id: Int,
    val baslik: String,
    val ders: String,
    val ogretmen: String,
    val tur: String,
    val baslangic: String,
    val bitis: String,
    val durum: String,
    val durumKod: Int,
    val puan: String,
    val aktif: Boolean,
    val ekVar: Boolean,
    val goruldu: Boolean,
)

data class OdevDetay(val aciklama: String, val ogretmenNotu: String, val ekSayisi: Int)

data class Sinav(
    val ad: String,
    val tarih: String,
    val kategori: String,
    val puan: Double,
    val net: Double,
    val dogru: Int,
    val yanlis: Int,
    val bos: Int,
    val soru: Int,
    val basari: Double,
    val genelSira: String,
    val sinifSira: String,
)

data class DersBasari(val ders: String, val oran: Double)

data class SinavOzeti(
    val sinavlar: List<Sinav>,
    val ortalama: Double?,
    val sonPuan: Double?,
    val degisim: Double?,
    val enIyiDers: DersBasari?,
    val enZayifDers: DersBasari?,
    val dersler: List<DersBasari>,
)

data class Mesaj(
    val id: Int,
    val kimden: String,
    val baslik: String,
    val onizleme: String,
    val tarih: String,
    val okundu: Boolean,
    val yanitlanabilir: Boolean,
    val kullaniciTuru: Int,
    val kullaniciId: Int,
)

data class Kutular(val gelen: List<Mesaj>, val giden: List<Mesaj>, val okunmamis: Int)

data class Alici(val ad: String, val tur: String, val kullaniciTuru: Int, val kullaniciId: Int)

data class Devamsizlik(val ozet: List<Pair<String, Int>>, val kayitlar: List<DevamsizlikKaydi>, val donem: String)

data class DevamsizlikKaydi(val tarih: String, val ders: String, val saat: String, val ogretmen: String, val tur: String, val not: String)

data class Ogretmen(val ad: String, val ders: String)

data class Bildirim(val id: Long, val baslik: String, val tur: Int, val tarih: String, val saat: String)

// ---------- İstemci ----------

class Obs private constructor(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("limeobs", Context.MODE_PRIVATE)
    private val kasa = Kasa(ctx)
    private val cerez = KaliciCerez(prefs)
    private val girisKilidi = Mutex()

    private val http = OkHttpClient.Builder()
        .cookieJar(cerez)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .addInterceptor { zincir ->
            zincir.proceed(
                zincir.request().newBuilder()
                    .header("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36 LimeOBS")
                    .header("Accept-Language", "tr-TR,tr;q=0.9")
                    .build()
            )
        }
        .build()

    var adres: String
        get() = prefs.getString("adres", VARSAYILAN_ADRES) ?: VARSAYILAN_ADRES
        set(deger) {
            var a = deger.trim().trimEnd('/')
            if (!a.startsWith("http://") && !a.startsWith("https://")) a = "https://$a"
            prefs.edit().putString("adres", a).apply()
        }

    /** menuLoader.php'den gelen rol yolu: pages/student/ veya pages/parent/ */
    private var taban: String = prefs.getString("taban", "pages/student") ?: "pages/student"
    private var nav: JSONObject? = null

    // Basit bellek önbelleği
    private val onbellek = HashMap<String, Pair<Long, Any>>()

    @Suppress("UNCHECKED_CAST")
    private suspend fun <T : Any> onbellekli(anahtar: String, sureSn: Int, zorla: Boolean, yukle: suspend () -> T): T {
        val simdi = System.currentTimeMillis()
        val kayit = synchronized(onbellek) { onbellek[anahtar] }
        if (!zorla && kayit != null && simdi - kayit.first < sureSn * 1000L) return kayit.second as T
        val deger = yukle()
        synchronized(onbellek) { onbellek[anahtar] = simdi to deger }
        return deger
    }

    fun onbellegiTemizle() = synchronized(onbellek) { onbellek.clear() }

    // ---------- HTTP yardımcıları ----------

    private fun url(yol: String) = if (yol.startsWith("http")) yol else "$adres/${yol.trimStart('/')}"

    private suspend fun getMetin(yol: String): Pair<Int, String> = withContext(Dispatchers.IO) {
        http.newCall(Request.Builder().url(url(yol)).build()).execute().use { it.code to (it.body?.string() ?: "") }
    }

    private suspend fun getBayt(yol: String): ByteArray? = withContext(Dispatchers.IO) {
        http.newCall(Request.Builder().url(url(yol)).build()).execute().use { y ->
            val tur = y.header("Content-Type") ?: ""
            if (y.isSuccessful && !tur.contains("text/html")) y.body?.bytes() else null
        }
    }

    private suspend fun post(yol: String, alanlar: Map<String, String>, xhr: Boolean = true): String = withContext(Dispatchers.IO) {
        val govde = FormBody.Builder().apply { alanlar.forEach { (k, v) -> add(k, v) } }.build()
        val istek = Request.Builder().url(url(yol)).post(govde).apply {
            if (xhr) header("X-Requested-With", "XMLHttpRequest")
        }.build()
        http.newCall(istek).execute().use { it.body?.string() ?: "" }
    }

    private fun jsonMu(metin: String) = metin.trimStart().startsWith("{")

    private fun girisGerekli(metin: String): Boolean {
        if (!jsonMu(metin)) return true
        val o = runCatching { JSONObject(metin) }.getOrNull() ?: return true
        return o.optString("error") == "Login required"
    }

    /** İstek oturum yüzünden başarısız olursa bir kez yeniden giriş yapıp tekrar dener. */
    private suspend fun <T> oturumla(blok: suspend () -> T?): T {
        val ilk = runCatching { blok() }.getOrElse { if (it is IOException) throw it else null }
        if (ilk != null) return ilk
        if (!gecerliOturum()) throw OturumHatasi()
        return blok() ?: throw IOException("Sunucudan beklenen yanıt alınamadı.")
    }

    // ---------- Oturum ----------

    val kayitliGirisVar: Boolean get() = kasa.oku() != null

    suspend fun girisYap(tc: String, sifre: String, okulAdresi: String): String? {
        adres = okulAdresi
        cerez.temizle()
        onbellegiTemizle()
        nav = null
        val yanit = runCatching {
            post(
                "require/class/login.php",
                mapOf("request" to "login", "loginAs" to "standard", "isRegister" to "0", "username" to tc, "password" to sifre, "newUser" to "0"),
                xhr = false,
            )
        }.getOrElse { return "Okul sunucusuna bağlanılamadı: ${it.message}" }
        val o = runCatching { JSONObject(yanit) }.getOrNull() ?: return "Sunucudan beklenmeyen yanıt geldi."
        if (!o.optBoolean("success")) {
            val m = o.optString("msg").ifBlank { o.optString("message") }.ifBlank { o.optString("error") }
            return Jsoup.parse(m.ifBlank { "Giriş başarısız. T.C. kimlik numarası veya şifre hatalı." }).text()
        }
        kasa.yaz(tc, sifre)
        oturumDurumu()
        return null
    }

    /** true: oturum açık, false: süresi dolmuş, null: ağ hatası */
    suspend fun oturumDurumu(): Boolean? {
        val (kod, metin) = runCatching { getMetin("require/menuLoader.php") }.getOrElse { return null }
        if (kod >= 500) return null
        val isaret = "window.obsNavData = "
        if (!metin.contains(isaret)) return false
        runCatching {
            val json = metin.substringAfter(isaret).substringBefore("};") + "}"
            val o = JSONObject(json)
            nav = o
            val anahtar = o.optString("key")
            val altlar = (o.optJSONObject("brand")?.optString("sub").orEmpty() + o.optJSONObject("user")?.optString("sub").orEmpty()).lowercase()
            val veli = anahtar == "parent" || altlar.contains("veli")
            taban = o.optString("base").ifBlank { if (veli) "pages/parent/" else "pages/student/" }.trim('/')
            prefs.edit().putString("taban", taban).apply()
        }
        return true
    }

    /** Oturum düşmüşse kayıtlı bilgilerle sessizce yeniden giriş yapar. */
    suspend fun gecerliOturum(): Boolean = girisKilidi.withLock {
        when (oturumDurumu()) {
            true -> true
            null -> false
            false -> {
                val kayit = kasa.oku() ?: return@withLock false
                girisYap(kayit.first, kayit.second, adres) == null
            }
        }
    }

    fun cikisYap() {
        cerez.temizle()
        kasa.sil()
        onbellegiTemizle()
        nav = null
        prefs.edit().remove("goruleBildirimler").apply()
    }

    // ---------- Veri ----------

    suspend fun anaVeri(zorla: Boolean = false): AnaVeri = onbellekli("ana", 120, zorla) {
        oturumla {
            val metin = post("$taban/require/indexAction.php", mapOf("request" to "loadIndex"))
            if (!jsonMu(metin)) return@oturumla null
            val o = JSONObject(metin)
            if (!o.optBoolean("success")) return@oturumla null
            anaVeriCoz(o.getJSONObject("data"))
        }
    }

    private fun anaVeriCoz(d: JSONObject): AnaVeri {
        val ls = d.optJSONObject("lessonSchedule")?.optJSONObject("data")
        val saatler = mutableListOf<String>()
        val gunler = mutableListOf<Pair<String, String>>()
        val hucreler = mutableListOf<DersHucresi>()
        if (ls != null) {
            ls.optJSONArray("xInfo")?.let { for (i in 0 until it.length()) saatler.add(it.optJSONArray(i)?.optString(0).orEmpty()) }
            ls.optJSONArray("yInfo")?.let {
                for (i in 0 until it.length()) {
                    val g = it.optJSONArray(i)
                    gunler.add((g?.optString(0).orEmpty()) to (g?.optString(1).orEmpty()))
                }
            }
            ls.optJSONArray("data")?.let {
                for (i in 0 until it.length()) {
                    val h = it.optJSONObject(i) ?: continue
                    val t = h.optJSONArray("text") ?: continue
                    val ders = t.optString(1).ifBlank { t.optString(0) }
                    if (ders.isBlank()) continue
                    hucreler.add(
                        DersHucresi(
                            gun = h.optInt("y"), saat = h.optInt("x"), ders = ders.trim(),
                            ogretmen = if (t.length() > 1) t.optString(0).trim() else "",
                            renk = renkCoz(h.optJSONObject("style")?.optString("background").orEmpty()),
                        )
                    )
                }
            }
        }
        val sinavlar = mutableListOf<YaklasanSinav>()
        d.optJSONArray("examList")?.let {
            for (i in 0 until it.length()) {
                val s = it.optJSONObject(i) ?: continue
                sinavlar.add(YaklasanSinav(s.optString("sinavAd").trim(), s.optString("sinavTarih"), s.optString("examType")))
            }
        }
        fun metinler(ad: String): List<String> {
            val l = mutableListOf<String>()
            d.optJSONArray(ad)?.let {
                for (i in 0 until it.length()) {
                    val v = it.opt(i)
                    l.add(
                        when (v) {
                            is JSONObject -> listOf("title", "eventDate", "location", "content").mapNotNull { k -> v.optString(k).takeIf { s -> s.isNotBlank() } }.joinToString(" • ")
                            else -> Jsoup.parse(v.toString()).text()
                        }
                    )
                }
            }
            return l
        }
        return AnaVeri(DersProgrami(saatler, gunler, hucreler), sinavlar, metinler("announcementList"), metinler("eventList"))
    }

    private fun renkCoz(css: String): Long {
        val sayilar = Regex("-?\\d+").findAll(css).map { it.value.toInt().coerceIn(0, 255) }.toList()
        if (css.startsWith("rgb") && sayilar.size >= 3) {
            return 0xFF000000 or (sayilar[0].toLong() shl 16) or (sayilar[1].toLong() shl 8) or sayilar[2].toLong()
        }
        if (css.startsWith("#") && css.length == 7) return 0xFF000000 or css.substring(1).toLong(16)
        return 0xFF5B8C2A
    }

    suspend fun profil(zorla: Boolean = false): Profil = onbellekli("profil", 600, zorla) {
        if (nav == null) gecerliOturum()
        val veli = taban.contains("parent")
        val alanlar = mutableListOf<Pair<String, String>>()
        var html: String? = null
        for (yol in listOf("$taban/profile.php", "pages/student/profile.php")) {
            val (kod, metin) = runCatching { getMetin(yol) }.getOrNull() ?: continue
            if (kod != 200 || !metin.contains("<dt")) continue
            html = metin
            val doc = Jsoup.parse(metin)
            for (dt in doc.select("dt")) {
                val dd = dt.nextElementSibling() ?: continue
                if (dd.tagName() != "dd") continue
                val bolum = dt.parents().firstNotNullOfOrNull { p -> p.previousElementSiblings().firstOrNull { it.tagName().matches(Regex("h[1-5]")) } }?.text()?.lowercase().orEmpty()
                val onek = if (bolum.contains("veli")) "Veli " else ""
                alanlar.add((onek + dt.text().trim()) to dd.text().trim())
            }
            if (alanlar.isNotEmpty()) break
        }
        fun bul(vararg anahtarlar: String, veliAlani: Boolean = false) = alanlar.firstOrNull { (k, _) ->
            k.startsWith("Veli ") == veliAlani && anahtarlar.any { k.contains(it, ignoreCase = true) }
        }?.second.orEmpty()

        val kullanici = nav?.optJSONObject("user")
        val ad = bul("İsim", "Ad Soyad").ifBlank { kullanici?.optString("name").orEmpty() }.ifBlank { "Öğrenci" }
        val marka = nav?.optJSONObject("brand")?.optString("name").orEmpty()
        val okul = when {
            marka.contains("|") -> marka.substringBefore("|").trim()
            marka.isNotBlank() -> marka.substringBefore(" - ").trim()
            else -> adres.removePrefix("https://").removePrefix("http://").substringBefore("/").replace("obs", "").substringBefore(".").replaceFirstChar { it.uppercase() }
        }
        Profil(
            ad = ad,
            sinif = bul("Sınıf"),
            numara = bul("Numara", "No"),
            veli = bul("İsim", "Ad Soyad", veliAlani = true),
            rol = if (veli) "Veli" else "Öğrenci",
            okul = okul,
            foto = fotoIndir(kullanici?.optString("photo"), html),
            alanlar = alanlar,
        )
    }

    private suspend fun fotoIndir(navFoto: String?, html: String?): ByteArray? {
        val adaylar = mutableListOf<String>()
        if (!navFoto.isNullOrBlank() && !navFoto.contains("default", true)) adaylar.add(navFoto)
        if (html != null) {
            Regex("""<img\b[^>]*\bsrc\s*=\s*["']([^"']*(?:studentPhoto|photo|resim)[^"']*)["']""", RegexOption.IGNORE_CASE)
                .find(html)?.groupValues?.get(1)?.takeIf { !it.contains("default", true) }?.let { adaylar.add(it) }
        }
        for (a in adaylar) {
            val b = runCatching { getBayt(a) }.getOrNull()
            if (b != null && b.size > 100) return b
        }
        return null
    }

    suspend fun odevler(zorla: Boolean = false): List<Odev> = onbellekli("odevler", 60, zorla) {
        oturumla {
            val (_, metin) = getMetin("obsapi/homework/getHomeworkList")
            if (girisGerekli(metin)) return@oturumla null
            val o = JSONObject(metin)
            val dizi = o.optJSONArray("data") ?: JSONArray()
            (0 until dizi.length()).mapNotNull { i ->
                val h = dizi.optJSONObject(i) ?: return@mapNotNull null
                Odev(
                    id = h.optInt("id"),
                    baslik = h.optString("title").trim().replace(Regex("\\s+"), " "),
                    ders = h.optString("lesson"),
                    ogretmen = h.optString("teaNameSurname"),
                    tur = h.optString("typeName"),
                    baslangic = h.optString("startDate"),
                    bitis = h.optString("endDate"),
                    durum = h.optString("statusName"),
                    durumKod = h.optInt("status"),
                    puan = h.optString("score"),
                    aktif = h.optBoolean("isActive"),
                    ekVar = h.optBoolean("hasAttachFile"),
                    goruldu = h.optBoolean("seen"),
                )
            }
        }
    }

    suspend fun odevDetay(id: Int): OdevDetay = onbellekli("odev$id", 600, false) {
        oturumla {
            val (_, metin) = getMetin("obsapi/homework/getHomeworkDetail?id=$id")
            if (girisGerekli(metin)) return@oturumla null
            val d = JSONObject(metin).optJSONObject("data") ?: return@oturumla null
            OdevDetay(
                aciklama = htmlMetin(d.optString("description")),
                ogretmenNotu = htmlMetin(d.optString("teacherComment")),
                ekSayisi = d.optJSONArray("attachFiles")?.length() ?: 0,
            )
        }
    }

    suspend fun sinavlar(zorla: Boolean = false): SinavOzeti = onbellekli("sinavlar", 300, zorla) {
        coroutineScope {
            val denemeler = async {
                oturumla {
                    val metin = post("$taban/require/examDashboard.php", mapOf("request" to "getStudentExams", "examType" to "SBS"))
                    if (!jsonMu(metin)) return@oturumla null
                    val o = JSONObject(metin)
                    if (!o.optBoolean("success")) return@oturumla null
                    o
                }
            }
            val taramalar = async { runCatching { taramaSinavlari() }.getOrDefault(emptyList()) }
            val o = denemeler.await()
            val liste = mutableListOf<Sinav>()
            o.optJSONArray("exams")?.let {
                for (i in 0 until it.length()) {
                    val s = it.optJSONObject(i) ?: continue
                    liste.add(
                        Sinav(
                            ad = s.optString("examName").trim(), tarih = s.optString("examDate"), kategori = "Deneme",
                            puan = s.optDouble("point", 0.0), net = s.optDouble("net", 0.0),
                            dogru = s.optInt("dogru"), yanlis = s.optInt("yanlis"), bos = s.optInt("bos"),
                            soru = s.optInt("questionCount"), basari = s.optDouble("successRate", 0.0),
                            genelSira = s.optString("GD"), sinifSira = s.optString("SD"),
                        )
                    )
                }
            }
            liste.addAll(taramalar.await())
            val kpi = o.optJSONObject("kpi")
            fun ders(j: JSONObject?) = j?.let { DersBasari(it.optString("lesson"), it.optDouble("successRate", 0.0)) }
            val dersler = mutableListOf<DersBasari>()
            o.optJSONArray("lessonSuccess")?.let { for (i in 0 until it.length()) ders(it.optJSONObject(i))?.let(dersler::add) }
            SinavOzeti(
                sinavlar = liste.sortedByDescending { tarihSayi(it.tarih) },
                ortalama = kpi?.optDouble("avgPoint")?.takeIf { !it.isNaN() },
                sonPuan = kpi?.optDouble("lastPoint")?.takeIf { !it.isNaN() },
                degisim = kpi?.optDouble("lastPointDelta")?.takeIf { !it.isNaN() },
                enIyiDers = ders(kpi?.optJSONObject("bestLesson")),
                enZayifDers = ders(kpi?.optJSONObject("worstLesson")),
                dersler = dersler,
            )
        }
    }

    private suspend fun taramaSinavlari(): List<Sinav> {
        val alanlar = mapOf(
            "request" to "getStudentGeneralList", "studentList" to "0", "teacherInfo" to "0", "exams" to "0", "dbs" to "2",
            "attendance" to "0", "exam" to "0", "homework" to "0", "course1" to "0", "course2" to "0", "library" to "0",
        )
        val metin = post("$taban/require/studentGeneralList.php", alanlar)
        if (!jsonMu(metin)) return emptyList()
        val ogrenci = JSONObject(metin).optJSONObject("data")?.optJSONArray("students")?.optJSONObject(0) ?: return emptyList()
        val dizi = ogrenci.optJSONObject("dbsInfo")?.optJSONArray("list") ?: return emptyList()
        return (0 until dizi.length()).mapNotNull { i ->
            val s = dizi.optJSONObject(i) ?: return@mapNotNull null
            fun top(on: String) = (1..10).sumOf { s.optString("$on$it").toIntOrNull() ?: 0 }
            val d = top("D"); val y = top("Y"); val ss = top("SS")
            Sinav(
                ad = s.optString("sinavAd").trim(), tarih = s.optString("sinavTarih"), kategori = "Tarama",
                puan = s.optString("Puan").toDoubleOrNull() ?: 0.0, net = Math.round((d - y / 3.0) * 100) / 100.0,
                dogru = d, yanlis = y, bos = maxOf(0, ss - d - y), soru = ss,
                basari = if (ss > 0) d * 100.0 / ss else 0.0, genelSira = s.optString("GD"), sinifSira = s.optString("SD"),
            )
        }
    }

    suspend fun mesajlar(zorla: Boolean = false): Kutular = onbellekli("mesajlar", 60, zorla) {
        oturumla {
            coroutineScope {
                val g = async { getMetin("obsapi/mail/getInbox").second }
                val s = async { getMetin("obsapi/mail/getSentMail").second }
                val gelenMetin = g.await()
                if (girisGerekli(gelenMetin)) return@coroutineScope null
                val gelen = JSONObject(gelenMetin).optJSONObject("data")
                val gidenMetin = s.await()
                val giden = if (jsonMu(gidenMetin)) JSONObject(gidenMetin).optJSONObject("data") else null
                Kutular(
                    gelen = mesajListesi(gelen?.optJSONArray("mail")),
                    giden = mesajListesi(giden?.optJSONArray("mail")),
                    okunmamis = gelen?.optJSONObject("count")?.optJSONObject("received")?.optString("notRead")?.toIntOrNull() ?: 0,
                )
            }
        }
    }

    private fun mesajListesi(dizi: JSONArray?): List<Mesaj> {
        if (dizi == null) return emptyList()
        return (0 until dizi.length()).mapNotNull { i ->
            val m = dizi.optJSONObject(i) ?: return@mapNotNull null
            Mesaj(
                id = m.optInt("id"), kimden = m.optString("sender").trim(), baslik = m.optString("mailTitle").trim(),
                onizleme = htmlMetin(m.optString("mailPreview")), tarih = m.optString("sendDate"),
                okundu = !m.isNull("readDate") && m.optString("readDate").isNotBlank(),
                yanitlanabilir = m.optInt("canReply") == 1, kullaniciTuru = m.optInt("userType"), kullaniciId = m.optInt("userId"),
            )
        }
    }

    suspend fun mesajIcerigi(id: Int): String = onbellekli("mesaj$id", 3600, false) {
        oturumla {
            val metin = post("obsapi/mail/getMailContent", mapOf("mailId" to id.toString()), xhr = false)
            if (girisGerekli(metin)) return@oturumla null
            val d = JSONObject(metin).optJSONObject("data")?.optJSONObject("mailContent") ?: return@oturumla null
            htmlMetin(d.optString("mailContent"))
        }
    }

    suspend fun aliciAra(sorgu: String): List<Alici> = oturumla {
        val (_, metin) = getMetin("obsapi/mail/getReceiverList?q=" + java.net.URLEncoder.encode(sorgu, "UTF-8"))
        if (girisGerekli(metin)) return@oturumla null
        val dizi = JSONObject(metin).optJSONArray("data") ?: JSONArray()
        (0 until dizi.length()).mapNotNull { i ->
            val a = dizi.optJSONObject(i) ?: return@mapNotNull null
            Alici(a.optString("nameSurname"), a.optString("type"), a.optInt("userType"), a.optInt("userId"))
        }
    }

    /** null: gönderildi, aksi halde hata mesajı */
    suspend fun mesajGonder(baslik: String, icerik: String, kullaniciTuru: Int, kullaniciId: Int, yanitId: Int?): String? {
        val alicilar = JSONArray().put(JSONObject().put("type", kullaniciTuru.toString()).put("id", kullaniciId.toString())).toString()
        val metin = runCatching {
            oturumla {
                val m = post(
                    "obsapi/mail/sendMail",
                    mapOf("title" to baslik, "content" to icerik, "receivers" to alicilar, "canReply" to "true", "shouldReply" to "false", "replyId" to (yanitId?.toString() ?: "")),
                )
                if (girisGerekli(m)) null else m
            }
        }.getOrElse { return it.message ?: "Gönderilemedi." }
        val o = JSONObject(metin)
        if (o.optBoolean("success")) {
            synchronized(onbellek) { onbellek.remove("mesajlar") }
            return null
        }
        return o.optString("msg").ifBlank { "Mesaj gönderilemedi." }
    }

    suspend fun devamsizlik(zorla: Boolean = false): Devamsizlik = onbellekli("devamsizlik", 300, zorla) {
        oturumla {
            val yol = "$taban/require/attendanceDashboard.php"
            val metin = post(yol, mapOf("request" to "load-attendance-initial-data"))
            if (!jsonMu(metin)) return@oturumla null
            val o = JSONObject(metin)
            val donem = o.optJSONArray("periods")?.optJSONObject(0)
            val ozet = mutableListOf<Pair<String, Int>>()
            o.optJSONObject("charts")?.optJSONObject("attendanceGraph5")?.optJSONArray("series")?.optJSONObject(0)?.optJSONArray("data")?.let {
                for (i in 0 until it.length()) {
                    val v = it.optJSONObject(i) ?: continue
                    ozet.add(v.optString("name") to (v.optString("value").toIntOrNull() ?: 0))
                }
            }
            val kayitlar = mutableListOf<DevamsizlikKaydi>()
            if (donem != null) {
                val l = post(yol, mapOf("request" to "get-attendance-graph-7", "periodId" to donem.optString("id")))
                if (jsonMu(l)) JSONObject(l).optJSONArray("list")?.let {
                    for (i in 0 until it.length()) {
                        val k = it.optJSONObject(i) ?: continue
                        kayitlar.add(
                            DevamsizlikKaydi(
                                k.optString("absenceDate"), k.optString("lesson"), k.optString("lessonNo"),
                                k.optString("teaNameSurname"), k.optString("description"), k.optString("note"),
                            )
                        )
                    }
                }
            }
            Devamsizlik(ozet, kayitlar, donem?.optString("description")?.trim().orEmpty())
        }
    }

    suspend fun ogretmenler(zorla: Boolean = false): List<Ogretmen> = onbellekli("ogretmenler", 600, zorla) {
        oturumla {
            val metin = post("$taban/require/teacherAction.php", mapOf("request" to "loadMyOwnTeachers"))
            if (!jsonMu(metin)) return@oturumla null
            val o = JSONObject(metin)
            if (!o.optBoolean("success")) return@oturumla null
            val dizi = o.optJSONArray("data") ?: JSONArray()
            (0 until dizi.length()).mapNotNull { i ->
                val t = dizi.optJSONObject(i) ?: return@mapNotNull null
                Ogretmen(t.optString("teaNameSurname").trim(), t.optString("lesson").trim())
            }
        }
    }

    /** Yemek listesi PDF'i (okulun yüklediği dosya) */
    suspend fun yemekPdf(zorla: Boolean = false): ByteArray = onbellekli("yemek", 1800, zorla) {
        oturumla {
            val metin = post("$taban/require/foodListAction.php", mapOf("request" to "get-food-list"))
            if (!jsonMu(metin)) return@oturumla null
            val hash = JSONObject(metin).optString("hash")
            if (hash.isBlank()) throw IOException("Okul henüz yemek listesi yüklememiş.")
            getBayt("download.php?file=$hash&view=")?.takeIf { it.size > 100 }
        }
    }

    suspend fun bildirimler(): List<Bildirim> = oturumla {
        val (_, metin) = getMetin("obsapi/notification/list")
        if (!jsonMu(metin)) return@oturumla null
        val o = JSONObject(metin)
        if (!o.optBoolean("success")) return@oturumla null
        val dizi = o.optJSONObject("result")?.optJSONArray("notifications") ?: JSONArray()
        (0 until dizi.length()).mapNotNull { i ->
            val b = dizi.optJSONObject(i) ?: return@mapNotNull null
            Bildirim(b.optLong("id"), b.optString("title").trim(), b.optInt("moduleType"), b.optString("createDate"), b.optString("createTime"))
        }
    }

    // Arka plan bildirimleri için görülen kimlikler
    var gorulenBildirimler: Set<Long>
        get() = prefs.getString("goruleBildirimler", null)?.split(',')?.mapNotNull { it.toLongOrNull() }?.toSet() ?: emptySet()
        set(v) = prefs.edit().putString("goruleBildirimler", v.sortedDescending().take(300).joinToString(",")).apply()

    val bildirimIlkCalisma: Boolean get() = !prefs.contains("goruleBildirimler")

    var bildirimlerAcik: Boolean
        get() = prefs.getBoolean("bildirimlerAcik", true)
        set(v) = prefs.edit().putBoolean("bildirimlerAcik", v).apply()

    companion object {
        const val VARSAYILAN_ADRES = "https://tedemkolejiobs.com"

        @Volatile
        private var ornek: Obs? = null

        fun al(ctx: Context): Obs = ornek ?: synchronized(this) {
            ornek ?: Obs(ctx.applicationContext).also { ornek = it }
        }

        fun htmlMetin(html: String): String {
            if (html.isBlank()) return ""
            val doc = Jsoup.parse(html.replace(Regex("(?i)<br\\s*/?>"), "\n").replace(Regex("(?i)</p>"), "\n"))
            return doc.wholeText().lines().joinToString("\n") { it.trim() }.replace(Regex("\n{3,}"), "\n\n").trim()
        }

        /** "dd.MM.yyyy" veya "yyyy-MM-dd" → sıralanabilir sayı */
        fun tarihSayi(t: String): Long {
            val p = t.trim().split(' ')[0]
            return when {
                p.matches(Regex("\\d{2}\\.\\d{2}\\.\\d{4}")) -> (p.substring(6) + p.substring(3, 5) + p.substring(0, 2)).toLong()
                p.matches(Regex("\\d{4}-\\d{2}-\\d{2}")) -> p.replace("-", "").toLong()
                else -> 0L
            }
        }
    }
}
