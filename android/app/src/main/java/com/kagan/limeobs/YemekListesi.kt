package com.kagan.limeobs

import android.content.Context
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import com.tom_roush.pdfbox.text.TextPosition
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.LocalDate
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Okulun aylık yemek listesi PDF'ini gün gün yemeklere ayırır (masaüstündeki akbim_frontend/food_menu.py ile
 * aynı yaklaşım): her sayfa bir hafta; gün başlıklarının konumundan sütunlar, satır aralıklarından yemekler çıkarılır.
 */
object YemekListesi {
    data class Gun(val baslik: String, val tarih: LocalDate?, val yemekler: List<String>)

    private data class Kelime(val x0: Float, val x1: Float, val y: Float, val metin: String) {
        val orta get() = (x0 + x1) / 2
    }

    private val AYLAR = listOf("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık")
    private val GUNLER = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

    @Volatile private var son: Pair<Int, List<Gun>>? = null

    private fun kucuk(s: String) = s.replace('İ', 'i').replace('I', 'ı').lowercase()

    private fun tarihMi(s: String): Boolean {
        if (GUNLER.take(5).any { s.contains(it, ignoreCase = true) }) return true
        return kucuk(s).split(' ').any { it in AYLAR }
    }

    fun tarihCoz(s: String, varsayilanYil: Int = LocalDate.now().year): LocalDate? {
        var gun: Int? = null; var ay: Int? = null; var yil = varsayilanYil
        s.trim().split(Regex("\\s+")).forEach { p ->
            val sayi = p.toIntOrNull()
            when {
                sayi != null && sayi in 1..31 && gun == null -> gun = sayi
                sayi != null && sayi > 2000 -> yil = sayi
                kucuk(p) in AYLAR -> ay = AYLAR.indexOf(kucuk(p)) + 1
            }
        }
        return if (gun != null && ay != null) runCatching { LocalDate.of(yil, ay!!, gun!!) }.getOrNull() else null
    }

    /** PDF'teki kısaltmaları ve harf harf bölünmüş kelimeleri düzeltir. */
    fun temizle(ham: String): String {
        var t = ham.replace(Regex("\\s+"), " ").trim()
        // Tek harflik parçaları sonraki kelimeyle birleştir ("T AVUK" → "TAVUK"); rakamlar hariç
        val parca = t.split(' ').toMutableList()
        var i = 0
        while (i < parca.size - 1) {
            val p = parca[i]
            if (p.length == 1 && p[0].isLetter() && parca[i + 1].firstOrNull()?.isLetter() == true && p != "&") {
                parca[i] = p + parca[i + 1]; parca.removeAt(i + 1)
            } else i++
        }
        t = parca.joinToString(" ")
        t = t.replace(Regex("(?<!\\S)Z\\s*\\.\\s*Y(?:AĞLI)?(?!\\S)"), "ZEYTİNYAĞLI")
            .replace(Regex("(?<!\\S)T\\s*\\.\\s*Y(?:AĞLI)?(?!\\S)"), "TEREYAĞLI")
        listOf("TA V A" to "TAVA", "TA VA" to "TAVA", "TA V UK" to "TAVUK", "TA VUK" to "TAVUK", "PİLA VI" to "PİLAVI",
            "Pİ LA VI" to "PİLAVI", "PİLA V" to "PİLAV", "Pİ LA V" to "PİLAV", "ZY " to "ZEYTİNYAĞLI ").forEach { (a, b) -> t = t.replace(a, b) }
        return t
    }

    private class Toplayici : PDFTextStripper() {
        var yukseklik = 0f
        val kelimeler = mutableListOf<Kelime>()
        override fun writeString(text: String, pos: List<TextPosition>) {
            if (text.isBlank() || pos.isEmpty()) return
            // PDFBox kelime kelime verir; büyük boşluklu parçaları ayrı kelime say
            var bas = 0
            for (i in 1..pos.size) {
                val bitti = i == pos.size || pos[i].xDirAdj - (pos[i - 1].xDirAdj + pos[i - 1].widthDirAdj) > 12f
                if (bitti) {
                    val parca = pos.subList(bas, i)
                    val metin = parca.joinToString("") { it.unicode }.trim()
                    if (metin.isNotEmpty()) {
                        val a = parca.first(); val b = parca.last()
                        kelimeler.add(Kelime(a.xDirAdj, b.xDirAdj + b.widthDirAdj, yukseklik - a.yDirAdj, metin))
                    }
                    bas = i
                }
            }
        }
    }

    private fun sayfaCoz(k: List<Kelime>, h: Float): List<Gun> {
        // 1. Gün başlık satırı: tarih benzeri kelimelerin en kalabalık olduğu satır (sayfanın üst kısmında)
        val tarihli = k.filter { tarihMi(it.metin) && it.y >= h * 0.4f }
        if (tarihli.isEmpty()) return emptyList()
        val refY = tarihli.map { it.y.roundToInt() }.distinct().maxBy { y -> tarihli.count { abs(it.y - y) < 8 } }
        val satir = k.filter { abs(it.y - refY) < 8 }.sortedBy { it.x0 }
        // Yan yana kelimeleri başlık gruplarına topla (sütunlar arası boşluk kelime boşluğundan büyük)
        val gruplar = mutableListOf<MutableList<Kelime>>()
        satir.forEach { w ->
            val son = gruplar.lastOrNull()?.last()
            if (son != null && w.x0 - son.x1 < 15f) gruplar.last().add(w) else gruplar.add(mutableListOf(w))
        }
        val basliklar = gruplar.map { g ->
            Kelime(g.first().x0, g.last().x1, g.minOf { it.y }, g.joinToString(" ") { it.metin }.replace(Regex("(\\d) (\\d)(?=\\D|$)"), "$1$2"))
        }.filter { tarihMi(it.metin) }
        if (basliklar.size < 2) return emptyList()

        // 2. Sütun sınırları: başlık ortalarının orta noktaları
        val ortalar = basliklar.map { it.orta }
        val enAltBaslik = basliklar.minOf { it.y }
        val sutunlar = List(basliklar.size) { mutableListOf<Kelime>() }
        k.filter { it.y < enAltBaslik - 10 && it.y >= h * 0.08f }.forEach { w ->
            val i = ortalar.indices.minBy { abs(ortalar[it] - w.orta) }
            sutunlar[i].add(w)
        }

        // 3. Satırları birleştir, büyük satır aralığı yeni yemek demek
        return basliklar.mapIndexed { i, b ->
            val satirlar = sutunlar[i].groupBy { (it.y / 3f).roundToInt() }.entries
                .sortedByDescending { it.key }
                .map { (_, ws) -> ws.maxOf { it.y } to ws.sortedBy { it.x0 }.joinToString(" ") { it.metin } }
            val yemekler = mutableListOf<String>()
            var simdiki = mutableListOf<String>()
            var sonY: Float? = null
            satirlar.forEach { (y, metin) ->
                if (sonY != null && abs(sonY!! - y) > 20f && simdiki.isNotEmpty()) {
                    temizle(simdiki.joinToString(" ")).takeIf { it.length > 1 }?.let(yemekler::add)
                    simdiki = mutableListOf()
                }
                simdiki.add(metin); sonY = y
            }
            if (simdiki.isNotEmpty()) temizle(simdiki.joinToString(" ")).takeIf { it.length > 1 }?.let(yemekler::add)
            val tarih = tarihCoz(b.metin)
            var baslik = b.metin.replace(Regex("\\s+"), " ").trim()
            if (GUNLER.none { baslik.contains(it, ignoreCase = true) } && tarih != null) baslik += " " + GUNLER[tarih.dayOfWeek.value - 1]
            Gun(baslik, tarih, yemekler)
        }
    }

    /** Döner: bütün günler (sayfa sırasıyla); ayrıştırılamazsa boş liste. */
    suspend fun coz(ctx: Context, pdf: ByteArray): List<Gun> = withContext(Dispatchers.Default) {
        val anahtar = pdf.size * 31 + pdf.take(4096).hashCode()
        son?.takeIf { it.first == anahtar }?.let { return@withContext it.second }
        val sonuc = runCatching {
            PDFBoxResourceLoader.init(ctx.applicationContext)
            PDDocument.load(pdf).use { dok ->
                (1..dok.numberOfPages).flatMap { s ->
                    val t = Toplayici().apply {
                        startPage = s; endPage = s
                        yukseklik = dok.getPage(s - 1).mediaBox.height
                    }
                    t.getText(dok)
                    sayfaCoz(t.kelimeler, t.yukseklik)
                }
            }
        }.getOrDefault(emptyList())
        son = anahtar to sonuc
        sonuc
    }

    /** Verilen günün yemekleri (liste yoksa ya da o gün yoksa null). */
    fun gunun(gunler: List<Gun>, gun: LocalDate) = gunler.firstOrNull { it.tarih == gun && it.yemekler.isNotEmpty() }
}
