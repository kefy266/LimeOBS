package com.kagan.limeobs

import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import android.text.TextUtils
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/** Haftalık ders programını masaüstündekiyle aynı düzende yatay A4 PDF olarak çizer ve paylaşır. */
object ProgramPdf {
    private val YESIL = Color.parseColor("#3F8F34")
    private val YAZI = Color.parseColor("#24231F")
    private val SOLUK = Color.parseColor("#6B6A64")
    private val CIZGI = Color.parseColor("#DEDBD0")
    private val PALET = listOf("#E3F1DC", "#DCEBF7", "#FBE7D3", "#EFE1F5", "#FBF3CF", "#D9F1EE",
        "#F7DDE2", "#E6E6F7", "#E9F0D5", "#F3E3D7", "#DBEEF7", "#F0ECDF").map(Color::parseColor)

    private fun kalem(boyut: Float, renk: Int, kalin: Boolean = false) = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = boyut
        color = renk
        typeface = Typeface.create(Typeface.SANS_SERIF, if (kalin) Typeface.BOLD else Typeface.NORMAL)
    }

    private fun duzen(metin: String, p: TextPaint, genislik: Int, hiza: Layout.Alignment = Layout.Alignment.ALIGN_NORMAL) =
        StaticLayout.Builder.obtain(metin, 0, metin.length, p, genislik).setAlignment(hiza).build()

    private fun Canvas.yaz(metin: String, p: TextPaint, x: Float, y: Float, genislik: Float,
                           hiza: Layout.Alignment = Layout.Alignment.ALIGN_NORMAL): Float {
        val l = duzen(metin, p, genislik.toInt(), hiza)
        save(); translate(x, y); l.draw(this); restore()
        return l.height.toFloat()
    }

    suspend fun olustur(ctx: Context): File = withContext(Dispatchers.IO) {
        val obs = Obs.al(ctx)
        val program = obs.anaVeri().program
        val profil = runCatching { obs.profil() }.getOrNull()
        val sinif = profil?.sinif.orEmpty().trim().replace(Regex("^[A-ZÇĞİÖŞÜ]+-(?=\\d)"), "")
        val okul = profil?.okul.orEmpty()
        val ogrenci = profil?.ad?.let(::guzelAd).orEmpty()

        val saatler = program.hucreler.filter { it.gun in 1..5 }.map { it.saat }.distinct().sorted()
        if (saatler.isEmpty()) throw IllegalStateException("Ders programında ders bulunamadı.")
        val hucre = program.hucreler.associateBy { it.gun to it.saat }

        val W = 842f; val H = 595f; val kenar = 34f
        val belge = PdfDocument()
        val sayfa = belge.startPage(PdfDocument.PageInfo.Builder(W.toInt(), H.toInt(), 1).create())
        val c = sayfa.canvas
        val dolgu = Paint(Paint.ANTI_ALIAS_FLAG)

        // --- Başlık
        val basH = 46f
        var y = kenar
        var yaziX = kenar
        BitmapFactory.decodeResource(ctx.resources, R.drawable.logo)?.let { bmp ->
            val lw = basH * bmp.width / bmp.height
            c.drawBitmap(bmp, null, RectF(kenar, y, kenar + lw, y + basH), Paint(Paint.FILTER_BITMAP_FLAG))
            yaziX = kenar + lw + 11f
        }
        c.yaz("LimeOBS", kalem(10f, YESIL, true), yaziX, y + 4f, W / 2)
        c.yaz("Ders Programı" + if (sinif.isNotEmpty()) " — $sinif" else "", kalem(20f, YAZI, true), yaziX, y + 17f, W / 2)
        val sag = listOf(
            okul to kalem(12f, YAZI, true),
            listOf(if (sinif.isNotEmpty()) "$sinif sınıfı" else "", profil?.let { donem(it) }.orEmpty())
                .filter { it.isNotEmpty() }.joinToString(" • ") to kalem(10f, YESIL, true),
            ogrenci to kalem(9.5f, SOLUK),
        ).filter { it.first.isNotEmpty() }
        val yukseklik = sag.sumOf { (m, p) -> duzen(m, p, 400).height } .toFloat()
        var ty = y + (basH - yukseklik) / 2
        sag.forEach { (m, p) -> ty += c.yaz(m, p, W / 2, ty, W / 2 - kenar, Layout.Alignment.ALIGN_OPPOSITE) }
        y += basH + 8f
        c.drawLine(kenar, y, W - kenar, y, Paint(Paint.ANTI_ALIAS_FLAG).apply { color = YESIL; strokeWidth = 1.7f })
        y += 14f

        // --- Tablo
        val saatW = 68f; val gunH = 25f; val bosluk = 4f; val altH = 22f
        val sutunW = (W - 2 * kenar - saatW) / 5
        val satirH = minOf(62f, (H - y - kenar - altH - gunH) / saatler.size)
        val gunKalem = kalem(10.5f, Color.WHITE, true)
        for (i in 0 until 5) {
            val r = RectF(kenar + saatW + i * sutunW + bosluk / 2, y, kenar + saatW + (i + 1) * sutunW - bosluk / 2, y + gunH - bosluk)
            dolgu.color = YESIL; dolgu.style = Paint.Style.FILL
            c.drawRoundRect(r, 4.5f, 4.5f, dolgu)
            val ad = GUN_ADLARI[i]
            c.drawText(ad, r.centerX() - gunKalem.measureText(ad) / 2, r.centerY() + 3.8f, gunKalem)
        }
        y += gunH

        val renkler = LinkedHashMap<String, Int>()
        val adKalemleri = listOf(10.5f, 9.5f, 8.5f).map { kalem(it, YAZI, true) }
        val ogrKalem = kalem(8f, SOLUK)
        val saatKalem = kalem(8f, SOLUK)
        val noKalem = kalem(9f, SOLUK, true)
        saatler.forEachIndexed { k, saat ->
            val ry = y + k * satirH
            val aralik = program.saatler.getOrNull(saat - 1).orEmpty().replace(" ", "").replace("-", " – ")
            c.yaz("$saat. ders", noKalem, kenar, ry + satirH / 2 - 12f, saatW - 6f, Layout.Alignment.ALIGN_OPPOSITE)
            c.yaz(aralik, saatKalem, kenar, ry + satirH / 2, saatW - 6f, Layout.Alignment.ALIGN_OPPOSITE)
            for (g in 1..5) {
                val r = RectF(kenar + saatW + (g - 1) * sutunW + bosluk / 2, ry + bosluk / 2,
                    kenar + saatW + g * sutunW - bosluk / 2, ry + satirH - bosluk / 2)
                val h = hucre[g to saat]
                if (h == null || h.ders.isBlank()) {
                    c.drawRoundRect(r, 4.5f, 4.5f, Paint(Paint.ANTI_ALIAS_FLAG).apply {
                        color = CIZGI; style = Paint.Style.STROKE; strokeWidth = 0.7f
                        pathEffect = DashPathEffect(floatArrayOf(4f, 3f), 0f)
                    })
                    continue
                }
                val ders = guzelAd(h.ders)
                dolgu.color = renkler.getOrPut(ders) { PALET[renkler.size % PALET.size] }
                dolgu.style = Paint.Style.FILL
                c.drawRoundRect(r, 4.5f, 4.5f, dolgu)
                val icW = r.width() - 14f
                val ogretmen = if (h.ogretmen.isBlank()) "" else
                    TextUtils.ellipsize(guzelAd(h.ogretmen), ogrKalem, icW, TextUtils.TruncateAt.END).toString()
                val ogrH = if (ogretmen.isEmpty()) 0f else ogrKalem.fontSpacing
                val adDuzen = adKalemleri.map { duzen(ders, it, icW.toInt()) }
                    .firstOrNull { it.height <= (r.height() - 8f) * (if (ogretmen.isEmpty()) 1f else 0.62f) }
                    ?: duzen(ders, adKalemleri.last(), icW.toInt())
                val ust = r.top + maxOf(4f, (r.height() - adDuzen.height - ogrH - 2f) / 2)
                c.save(); c.translate(r.left + 7f, ust); adDuzen.draw(c); c.restore()
                if (ogretmen.isNotEmpty()) c.drawText(ogretmen, r.left + 7f, ust + adDuzen.height + 2f - ogrKalem.ascent(), ogrKalem)
            }
        }

        c.yaz("LimeOBS ile oluşturuldu • ${LocalDate.now().format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))}",
            kalem(8f, SOLUK), kenar, H - kenar - 10f, W / 2)
        belge.finishPage(sayfa)

        val klasor = File(ctx.cacheDir, "paylas").apply { mkdirs() }
        val dosya = File(klasor, "LimeOBS Ders Programı.pdf")
        dosya.outputStream().use { belge.writeTo(it) }
        belge.close()
        dosya
    }

    private fun donem(p: Profil): String =
        p.alanlar.firstOrNull { it.first.contains("dönem", true) }?.second
            ?: LocalDate.now().let { d -> if (d.monthValue >= 8) "${d.year}-${d.year + 1}" else "${d.year - 1}-${d.year}" }

    fun paylas(ctx: Context, dosya: File) {
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.dosyalar", dosya)
        val gonder = Intent(Intent.ACTION_SEND).setType("application/pdf")
            .putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        ctx.startActivity(Intent.createChooser(gonder, "Ders programını paylaş").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
