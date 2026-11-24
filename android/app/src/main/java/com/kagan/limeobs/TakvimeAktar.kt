package com.kagan.limeobs

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.provider.CalendarContract
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * Sınav ve ödev teslimlerini telefonun takvimine ekler.
 * - Tek kayıt: takvim uygulamasının "etkinlik ekle" ekranını açar (izin gerekmez).
 * - Toplu aktarma: takvim izniyle doğrudan ana takvime tüm gün etkinlik olarak yazar; daha önce
 *   aktarılanlar tekrar eklenmez. Etkinlik bir gün önce saat 18:00'de hatırlatılır.
 */
object TakvimeAktar {
    data class Kayit(val anahtar: String, val baslik: String, val tarih: LocalDate, val aciklama: String)

    private fun gunBasi(t: LocalDate) = t.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()

    fun tekEkle(ctx: Context, baslik: String, tarih: LocalDate, aciklama: String = "") {
        val niyet = Intent(Intent.ACTION_INSERT, CalendarContract.Events.CONTENT_URI)
            .putExtra(CalendarContract.Events.TITLE, baslik)
            .putExtra(CalendarContract.Events.DESCRIPTION, aciklama)
            .putExtra(CalendarContract.EXTRA_EVENT_ALL_DAY, true)
            .putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, gunBasi(tarih))
            .putExtra(CalendarContract.EXTRA_EVENT_END_TIME, gunBasi(tarih.plusDays(1)))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { ctx.startActivity(niyet) }.onFailure {
            android.widget.Toast.makeText(ctx, "Telefonda takvim uygulaması bulunamadı.", android.widget.Toast.LENGTH_SHORT).show()
        }
    }

    /** Yaklaşan sınavlar ve teslim bekleyen ödevler. */
    suspend fun kayitlar(ctx: Context): List<Kayit> {
        val obs = Obs.al(ctx)
        val bugun = LocalDate.now()
        val sinavlar = runCatching { obs.anaVeri().sinavlar }.getOrDefault(emptyList()).mapNotNull { s ->
            val t = tarihCoz(s.tarih)?.takeIf { !it.isBefore(bugun) } ?: return@mapNotNull null
            Kayit("sinav|${s.ad}|$t", "📝 ${s.ad}", t, listOf(s.tur, "LimeOBS").filter { it.isNotBlank() }.joinToString(" • "))
        }
        val odevler = runCatching { obs.odevler() }.getOrDefault(emptyList())
            .filter { it.aktif && it.durumKod == 0 }
            .mapNotNull { o ->
                val t = tarihCoz(o.bitis)?.takeIf { !it.isBefore(bugun) } ?: return@mapNotNull null
                Kayit("odev|${o.id}", "📚 ${guzelAd(o.ders)}: ${o.baslik}", t, "Ödev teslimi • ${guzelAd(o.ogretmen)} • LimeOBS")
            }
        return sinavlar + odevler
    }

    /** Yazılabilir ana takvimin kimliği (yoksa ilk yazılabilir takvim). */
    private fun takvimKimligi(ctx: Context): Long? {
        val sutunlar = arrayOf(CalendarContract.Calendars._ID, CalendarContract.Calendars.IS_PRIMARY)
        val kosul = "${CalendarContract.Calendars.VISIBLE} = 1 AND ${CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL} >= ${CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR}"
        ctx.contentResolver.query(CalendarContract.Calendars.CONTENT_URI, sutunlar, kosul, null, null)?.use { c ->
            var ilk: Long? = null
            while (c.moveToNext()) {
                val id = c.getLong(0)
                if (ilk == null) ilk = id
                if (c.getInt(1) == 1) return id
            }
            return ilk
        }
        return null
    }

    /** Telefonda hiç takvim hesabı yoksa (ör. Google hesabı açılmamış) cihazda yerel "LimeOBS" takvimi oluşturur. */
    private fun yerelTakvimOlustur(ctx: Context): Long? {
        val hesap = "LimeOBS"
        val uri = CalendarContract.Calendars.CONTENT_URI.buildUpon()
            .appendQueryParameter(CalendarContract.CALLER_IS_SYNCADAPTER, "true")
            .appendQueryParameter(CalendarContract.Calendars.ACCOUNT_NAME, hesap)
            .appendQueryParameter(CalendarContract.Calendars.ACCOUNT_TYPE, CalendarContract.ACCOUNT_TYPE_LOCAL)
            .build()
        val degerler = ContentValues().apply {
            put(CalendarContract.Calendars.ACCOUNT_NAME, hesap)
            put(CalendarContract.Calendars.ACCOUNT_TYPE, CalendarContract.ACCOUNT_TYPE_LOCAL)
            put(CalendarContract.Calendars.NAME, "LimeOBS")
            put(CalendarContract.Calendars.CALENDAR_DISPLAY_NAME, "LimeOBS")
            put(CalendarContract.Calendars.CALENDAR_COLOR, 0xFF3F8F34.toInt())
            put(CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL, CalendarContract.Calendars.CAL_ACCESS_OWNER)
            put(CalendarContract.Calendars.OWNER_ACCOUNT, hesap)
            put(CalendarContract.Calendars.VISIBLE, 1)
            put(CalendarContract.Calendars.SYNC_EVENTS, 1)
            put(CalendarContract.Calendars.CALENDAR_TIME_ZONE, java.util.TimeZone.getDefault().id)
        }
        return runCatching { ctx.contentResolver.insert(uri, degerler)?.lastPathSegment?.toLongOrNull() }.getOrNull()
    }

    /** Döner: eklenen etkinlik sayısı. Takvim izni önceden alınmış olmalı. */
    suspend fun hepsiniAktar(ctx: Context): Int = withContext(Dispatchers.IO) {
        val takvim = takvimKimligi(ctx) ?: yerelTakvimOlustur(ctx)
            ?: throw IllegalStateException("Telefonda yazılabilir bir takvim bulunamadı.")
        val prefs = ctx.getSharedPreferences("limeobs", Context.MODE_PRIVATE)
        val aktarilan = prefs.getStringSet("takvimeAktarilan", emptySet())!!.toMutableSet()
        var sayi = 0
        kayitlar(ctx).filter { it.anahtar !in aktarilan }.forEach { k ->
            val degerler = ContentValues().apply {
                put(CalendarContract.Events.CALENDAR_ID, takvim)
                put(CalendarContract.Events.TITLE, k.baslik)
                put(CalendarContract.Events.DESCRIPTION, k.aciklama)
                put(CalendarContract.Events.ALL_DAY, 1)
                put(CalendarContract.Events.DTSTART, gunBasi(k.tarih))
                put(CalendarContract.Events.DTEND, gunBasi(k.tarih.plusDays(1)))
                put(CalendarContract.Events.EVENT_TIMEZONE, "UTC")
                put(CalendarContract.Events.HAS_ALARM, 1)
            }
            val uri = ctx.contentResolver.insert(CalendarContract.Events.CONTENT_URI, degerler) ?: return@forEach
            val etkinlik = uri.lastPathSegment?.toLongOrNull() ?: return@forEach
            ctx.contentResolver.insert(CalendarContract.Reminders.CONTENT_URI, ContentValues().apply {
                put(CalendarContract.Reminders.EVENT_ID, etkinlik)
                put(CalendarContract.Reminders.METHOD, CalendarContract.Reminders.METHOD_ALERT)
                put(CalendarContract.Reminders.MINUTES, 6 * 60) // önceki gün 18:00
            })
            aktarilan += k.anahtar
            sayi++
        }
        prefs.edit().putStringSet("takvimeAktarilan", aktarilan).apply()
        sayi
    }
}
