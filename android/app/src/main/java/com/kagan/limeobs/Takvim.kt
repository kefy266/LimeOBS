package com.kagan.limeobs

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.time.LocalDate
import java.util.concurrent.TimeUnit

/**
 * Okul takvimi: MEB ara tatilleri/yarıyıl (resmi genelge, 2026-2027) ve resmî tatiller (Nager.Date).
 * Masaüstündeki akbim_frontend/school_calendar.py ile aynı kurallar.
 */
data class Tatil(val ad: String, val baslangic: LocalDate, val bitis: LocalDate, val okulTatili: Boolean)

object Takvim {
    // https://www.meb.gov.tr/2026-2027-egitim-ogretim-yili-calisma-takvimi/haber/41057/tr
    private val okulTatilleri = listOf(
        Tatil("1. dönem ara tatili", LocalDate.of(2026, 11, 16), LocalDate.of(2026, 11, 20), true),
        Tatil("Yarıyıl tatili", LocalDate.of(2027, 1, 25), LocalDate.of(2027, 2, 5), true),
        Tatil("2. dönem ara tatili", LocalDate.of(2027, 3, 8), LocalDate.of(2027, 3, 12), true),
    )

    private val yedekResmi = mapOf(
        2026 to listOf(
            "2026-01-01" to "Yılbaşı", "2026-03-20" to "Ramazan Bayramı 1. Gün", "2026-03-21" to "Ramazan Bayramı 2. Gün",
            "2026-03-22" to "Ramazan Bayramı 3. Gün", "2026-04-23" to "Ulusal Egemenlik ve Çocuk Bayramı",
            "2026-05-01" to "İşçi Bayramı", "2026-05-19" to "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
            "2026-05-27" to "Kurban Bayramı 1. Gün", "2026-05-28" to "Kurban Bayramı 2. Gün",
            "2026-05-29" to "Kurban Bayramı 3. Gün", "2026-05-30" to "Kurban Bayramı 4. Gün",
            "2026-07-15" to "Demokrasi ve Millî Birlik Günü", "2026-08-30" to "Zafer Bayramı",
            "2026-10-29" to "Cumhuriyet Bayramı",
        ),
        2027 to listOf(
            "2027-01-01" to "Yılbaşı", "2027-03-10" to "Ramazan Bayramı 1. Gün", "2027-03-11" to "Ramazan Bayramı 2. Gün",
            "2027-03-12" to "Ramazan Bayramı 3. Gün", "2027-04-23" to "Ulusal Egemenlik ve Çocuk Bayramı",
            "2027-05-01" to "İşçi Bayramı", "2027-05-16" to "Kurban Bayramı 1. Gün", "2027-05-17" to "Kurban Bayramı 2. Gün",
            "2027-05-18" to "Kurban Bayramı 3. Gün", "2027-05-19" to "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
            "2027-07-15" to "Demokrasi ve Millî Birlik Günü", "2027-08-30" to "Zafer Bayramı",
            "2027-10-29" to "Cumhuriyet Bayramı",
        ),
    )

    @Volatile
    private var resmi: Map<Int, Map<LocalDate, String>> = emptyMap()

    private fun yilTatilleri(yil: Int): Map<LocalDate, String> =
        resmi[yil] ?: (yedekResmi[yil] ?: emptyList()).associate { (t, ad) -> LocalDate.parse(t) to ad }

    /** Resmî tatilleri Nager.Date'ten çeker (30 gün telefonda saklanır); başarısız olursa yedek liste kullanılır. */
    suspend fun hazirla(ctx: Context) = withContext(Dispatchers.IO) {
        val prefs = ctx.getSharedPreferences("limeobs_takvim", Context.MODE_PRIVATE)
        val bugun = LocalDate.now()
        val sonuc = HashMap(resmi)
        for (yil in setOf(bugun.year, bugun.plusDays(120).year)) {
            if (sonuc.containsKey(yil)) continue
            val zaman = prefs.getLong("zaman-$yil", 0)
            var metin = prefs.getString("tatiller-$yil", null)
            if (metin == null || System.currentTimeMillis() - zaman > 30L * 86_400_000) {
                metin = runCatching {
                    val http = OkHttpClient.Builder().callTimeout(8, TimeUnit.SECONDS).build()
                    http.newCall(Request.Builder().url("https://date.nager.at/api/v3/PublicHolidays/$yil/TR").build())
                        .execute().use { if (it.isSuccessful) it.body?.string() else null }
                }.getOrNull()?.also {
                    prefs.edit().putString("tatiller-$yil", it).putLong("zaman-$yil", System.currentTimeMillis()).apply()
                } ?: metin
            }
            metin?.let { m ->
                runCatching {
                    val dizi = JSONArray(m)
                    val harita = LinkedHashMap<LocalDate, String>()
                    for (i in 0 until dizi.length()) {
                        val o = dizi.getJSONObject(i)
                        val gun = LocalDate.parse(o.getString("date"))
                        val ad = o.getString("localName").replace(" (Tentative Date)", "")
                        harita[gun] = harita[gun]?.let { "$it / $ad" } ?: ad
                    }
                    sonuc[yil] = harita
                }
            }
        }
        resmi = sonuc
    }

    fun okulTatili(gun: LocalDate): Tatil? = okulTatilleri.firstOrNull { !gun.isBefore(it.baslangic) && !gun.isAfter(it.bitis) }

    /** Hafta içi bir günde okul yoksa nedeni; okul günüyse null. */
    fun okulYokNedeni(gun: LocalDate): String? = okulTatili(gun)?.ad ?: yilTatilleri(gun.year)[gun]

    fun okulGunuMu(gun: LocalDate) = gun.dayOfWeek.value <= 5 && okulYokNedeni(gun) == null

    fun sonrakiOkulGunu(gun: LocalDate): LocalDate {
        var g = gun.plusDays(1)
        repeat(120) { if (okulGunuMu(g)) return g; g = g.plusDays(1) }
        return g
    }

    /** Bugün süren ve önümüzdeki [gun] gün içindeki tatiller. */
    fun yaklasan(bugun: LocalDate = LocalDate.now(), gun: Long = 90): List<Tatil> {
        val sinir = bugun.plusDays(gun)
        val okul = okulTatilleri.filter { !it.bitis.isBefore(bugun) && !it.baslangic.isAfter(sinir) }
        val resmiler = setOf(bugun.year, sinir.year).flatMap { y -> yilTatilleri(y).entries }
            .filter { (g, _) -> !g.isBefore(bugun) && !g.isAfter(sinir) && okulTatili(g) == null }
            .map { (g, ad) -> Tatil(ad, g, g, false) }
        return (okul + resmiler).sortedBy { it.baslangic }
    }
}
