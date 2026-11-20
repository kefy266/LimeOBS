package com.kagan.limeobs

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.temporal.ChronoUnit
import java.util.concurrent.TimeUnit

/**
 * Widget ve ders hatırlatıcısı için ders programı ile ödevlerin küçük bir özeti.
 * Uygulama veri yükledikçe güncellenir; internet olmadan da okunabilir.
 */
object Ozet {
    private const val DOSYA = "limeobs_ozet"

    data class Ders(val gun: Int, val saat: Int, val ad: String, val ogretmen: String, val baslangic: LocalTime, val bitis: LocalTime)
    data class KisaOdev(val baslik: String, val ders: String, val bitis: String)

    fun programKaydet(ctx: Context, p: DersProgrami) {
        val dizi = JSONArray()
        p.hucreler.forEach { h ->
            val aralik = saatAraligi(p.saatler.getOrNull(h.saat - 1).orEmpty()) ?: return@forEach
            dizi.put(
                JSONObject().put("gun", h.gun).put("saat", h.saat).put("ad", h.ders).put("ogretmen", h.ogretmen)
                    .put("bas", aralik.first.toString()).put("bit", aralik.second.toString())
            )
        }
        ctx.getSharedPreferences(DOSYA, Context.MODE_PRIVATE).edit().putString("program", dizi.toString()).apply()
        LimeWidget.guncelle(ctx)
        DersHatirlatici.planla(ctx)
    }

    fun odevlerKaydet(ctx: Context, odevler: List<Odev>) {
        val dizi = JSONArray()
        odevler.filter { it.aktif && it.durumKod == 0 }.sortedBy { Obs.tarihSayi(it.bitis) }.take(5).forEach {
            dizi.put(JSONObject().put("baslik", it.baslik).put("ders", it.ders).put("bitis", it.bitis))
        }
        ctx.getSharedPreferences(DOSYA, Context.MODE_PRIVATE).edit().putString("odevler", dizi.toString()).apply()
        LimeWidget.guncelle(ctx)
    }

    fun sil(ctx: Context) {
        ctx.getSharedPreferences(DOSYA, Context.MODE_PRIVATE).edit().clear().apply()
        LimeWidget.guncelle(ctx)
    }

    fun dersler(ctx: Context): List<Ders> = runCatching {
        val dizi = JSONArray(ctx.getSharedPreferences(DOSYA, Context.MODE_PRIVATE).getString("program", null) ?: return emptyList())
        (0 until dizi.length()).map { dizi.getJSONObject(it) }.map {
            Ders(it.getInt("gun"), it.getInt("saat"), it.getString("ad"), it.optString("ogretmen"),
                LocalTime.parse(it.getString("bas")), LocalTime.parse(it.getString("bit")))
        }.sortedWith(compareBy({ it.gun }, { it.baslangic }))
    }.getOrDefault(emptyList())

    fun odevler(ctx: Context): List<KisaOdev> = runCatching {
        val dizi = JSONArray(ctx.getSharedPreferences(DOSYA, Context.MODE_PRIVATE).getString("odevler", null) ?: return emptyList())
        (0 until dizi.length()).map { dizi.getJSONObject(it) }.map { KisaOdev(it.getString("baslik"), it.getString("ders"), it.getString("bitis")) }
    }.getOrDefault(emptyList())

    /** Şu andan sonraki ilk ders ve tarihi (tatil ve hafta sonları atlanır). */
    fun sonrakiDers(ctx: Context, simdi: LocalDateTime = LocalDateTime.now()): Pair<LocalDate, Ders>? {
        val dersler = dersler(ctx)
        if (dersler.isEmpty()) return null
        var gun = simdi.toLocalDate()
        repeat(21) {
            if (Takvim.okulGunuMu(gun)) {
                dersler.filter { it.gun == gun.dayOfWeek.value }
                    .firstOrNull { gun.atTime(it.baslangic).isAfter(simdi) }
                    ?.let { return gun to it }
            }
            gun = gun.plusDays(1)
        }
        return null
    }
}

class LimeWidget : AppWidgetProvider() {
    override fun onUpdate(ctx: Context, yonetici: AppWidgetManager, kimlikler: IntArray) {
        ciz(ctx, yonetici, kimlikler)
        WidgetIscisi.hemen(ctx)
    }

    override fun onEnabled(ctx: Context) = WidgetIscisi.planla(ctx)
    override fun onDisabled(ctx: Context) = WidgetIscisi.iptal(ctx)

    companion object {
        fun guncelle(ctx: Context) {
            val yonetici = AppWidgetManager.getInstance(ctx)
            val kimlikler = yonetici.getAppWidgetIds(ComponentName(ctx, LimeWidget::class.java))
            if (kimlikler.isNotEmpty()) ciz(ctx, yonetici, kimlikler)
        }

        private fun ciz(ctx: Context, yonetici: AppWidgetManager, kimlikler: IntArray) {
            val g = gorunum(ctx)
            kimlikler.forEach { yonetici.updateAppWidget(it, g) }
        }

        private fun gorunum(ctx: Context): RemoteViews {
            val v = RemoteViews(ctx.packageName, R.layout.widget_limeobs)
            val simdi = LocalDateTime.now()
            val bugun = simdi.toLocalDate()
            v.setTextViewText(R.id.widget_tarih, "${GUN_ADLARI[bugun.dayOfWeek.value - 1]} ${bugun.dayOfMonth}")

            val dersler = Ozet.dersler(ctx)
            val suanki = if (Takvim.okulGunuMu(bugun)) dersler.firstOrNull {
                it.gun == bugun.dayOfWeek.value && !simdi.toLocalTime().isBefore(it.baslangic) && simdi.toLocalTime().isBefore(it.bitis)
            } else null
            val sonraki = Ozet.sonrakiDers(ctx, simdi)
            val tatil = Takvim.okulTatili(bugun)?.ad ?: Takvim.okulYokNedeni(bugun)?.takeIf { bugun.dayOfWeek.value <= 5 }
            when {
                dersler.isEmpty() -> {
                    v.setTextViewText(R.id.widget_ust, "LimeOBS")
                    v.setTextViewText(R.id.widget_ana, if (Obs.al(ctx).kayitliGirisVar) "Hazırlanıyor…" else "Giriş yap")
                    v.setTextViewText(R.id.widget_alt, "Ders programını görmek için uygulamayı aç")
                }
                suanki != null -> {
                    v.setTextViewText(R.id.widget_ust, "Şu an derstesin")
                    v.setTextViewText(R.id.widget_ana, guzelAd(suanki.ad))
                    val kalan = ChronoUnit.MINUTES.between(simdi.toLocalTime(), suanki.bitis)
                    val sonra = sonraki?.takeIf { it.first == bugun }?.second?.let { " • Sonra: ${guzelAd(it.ad)}" } ?: " • Günün son dersi"
                    v.setTextViewText(R.id.widget_alt, "Bitmesine $kalan dk$sonra")
                }
                sonraki != null -> {
                    val (gun, d) = sonraki
                    val fark = ChronoUnit.DAYS.between(bugun, gun)
                    v.setTextViewText(
                        R.id.widget_ust,
                        when {
                            tatil != null -> "${tatil.replaceFirstChar { it.uppercase() }} • okul ${GUN_ADLARI[gun.dayOfWeek.value - 1]}"
                            fark == 0L -> "Sıradaki ders"
                            fark == 1L -> "Yarın ilk ders"
                            else -> "${GUN_ADLARI[gun.dayOfWeek.value - 1]} ilk ders"
                        }
                    )
                    v.setTextViewText(R.id.widget_ana, guzelAd(d.ad))
                    val dk = ChronoUnit.MINUTES.between(simdi, gun.atTime(d.baslangic))
                    val ne = if (fark == 0L && dk < 120) "$dk dk sonra" else d.baslangic.toString()
                    v.setTextViewText(R.id.widget_alt, ne + if (d.ogretmen.isNotBlank()) " • ${guzelAd(d.ogretmen)}" else "")
                }
                else -> {
                    v.setTextViewText(R.id.widget_ust, "Ders programı")
                    v.setTextViewText(R.id.widget_ana, "Yakında ders yok")
                    v.setTextViewText(R.id.widget_alt, "")
                }
            }

            val odevler = Ozet.odevler(ctx)
            val satirlar = listOf(R.id.widget_odev1, R.id.widget_odev2)
            satirlar.forEachIndexed { i, id ->
                val o = odevler.getOrNull(i)
                if (o == null) {
                    v.setViewVisibility(id, if (i == 0 && dersler.isNotEmpty()) View.VISIBLE else View.GONE)
                    if (i == 0) v.setTextViewText(id, "Teslim bekleyen ödevin yok 🎉")
                } else {
                    v.setViewVisibility(id, View.VISIBLE)
                    val kalan = kalanGun(o.bitis)?.let { " — ${kalanMetni(it).lowercase()}" }.orEmpty()
                    v.setTextViewText(id, "📚 ${guzelAd(o.ders)}: ${o.baslik}$kalan")
                }
            }
            v.setViewVisibility(R.id.widget_cizgi, if (dersler.isEmpty()) View.GONE else View.VISIBLE)

            val ac = PendingIntent.getActivity(
                ctx, 1, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            v.setOnClickPendingIntent(R.id.widget_kok, ac)
            return v
        }
    }
}

/** Widget'ı 15 dakikada bir tazeler (internet varsa yeni veri çeker, yoksa kayıttan çizer). */
class WidgetIscisi(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val obs = Obs.al(applicationContext)
        if (obs.kayitliGirisVar) {
            runCatching { obs.anaVeri(zorla = true) }
            runCatching { obs.odevler(zorla = true) }
        }
        LimeWidget.guncelle(applicationContext)
        return Result.success()
    }

    companion object {
        private const val AD = "limeobs-widget"

        fun planla(ctx: Context) {
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(
                AD, ExistingPeriodicWorkPolicy.KEEP, PeriodicWorkRequestBuilder<WidgetIscisi>(15, TimeUnit.MINUTES).build()
            )
        }

        fun hemen(ctx: Context) {
            WorkManager.getInstance(ctx).enqueueUniqueWork("$AD-hemen", ExistingWorkPolicy.REPLACE, OneTimeWorkRequestBuilder<WidgetIscisi>().build())
        }

        fun iptal(ctx: Context) = WorkManager.getInstance(ctx).cancelUniqueWork(AD).let { }
    }
}
