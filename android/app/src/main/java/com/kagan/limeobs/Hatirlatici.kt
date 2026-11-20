package com.kagan.limeobs

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * Ders hatırlatıcısı: her dersten 5 dakika önce bildirim. Her seferinde yalnızca bir sonraki ders için alarm
 * kurulur; alarm çalınca bildirim gösterilir ve sıradaki ders için yeni alarm kurulur.
 */
object DersHatirlatici {
    private const val KANAL = "ders"
    private const val ONCE_DK = 5L

    fun acikMi(ctx: Context) = ctx.getSharedPreferences("limeobs", Context.MODE_PRIVATE).getBoolean("dersHatirlatici", false)

    fun ayarla(ctx: Context, acik: Boolean) {
        ctx.getSharedPreferences("limeobs", Context.MODE_PRIVATE).edit().putBoolean("dersHatirlatici", acik).apply()
        if (acik) planla(ctx) else iptal(ctx)
    }

    private fun niyet(ctx: Context, d: Ozet.Ders? = null) = PendingIntent.getBroadcast(
        ctx, 7,
        Intent(ctx, HatirlaticiAlici::class.java).apply {
            if (d != null) {
                putExtra("ders", d.ad); putExtra("ogretmen", d.ogretmen); putExtra("saat", d.baslangic.toString())
            }
        },
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    fun planla(ctx: Context) {
        if (!acikMi(ctx) || !Obs.al(ctx).kayitliGirisVar) return iptal(ctx)
        val simdi = LocalDateTime.now()
        // Bildirim zamanı geçmiş derslere değil, 5 dakikadan uzak olan ilk derse kur
        val (gun, d) = Ozet.sonrakiDers(ctx, simdi.plusMinutes(ONCE_DK)) ?: return iptal(ctx)
        val zaman = gun.atTime(d.baslangic).minusMinutes(ONCE_DK).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        val alarm = ctx.getSystemService(AlarmManager::class.java)
        // Tam zamanında çalan alarm (USE_EXACT_ALARM); izin yoksa en fazla 3 dakika gecikebilen pencere
        val pi = niyet(ctx, d)
        if (Build.VERSION.SDK_INT < 31 || alarm.canScheduleExactAlarms()) {
            alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, zaman, pi)
        } else {
            alarm.setWindow(AlarmManager.RTC_WAKEUP, zaman, 3 * 60_000L, pi)
        }
    }

    fun iptal(ctx: Context) {
        ctx.getSystemService(AlarmManager::class.java).cancel(niyet(ctx))
    }

    fun kanalOlustur(ctx: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val kanal = NotificationChannel(KANAL, "Ders hatırlatıcısı", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Dersten 5 dakika önce hangi ders olduğunu bildirir"
            }
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(kanal)
        }
    }

    @SuppressLint("MissingPermission")
    fun goster(ctx: Context, ders: String, ogretmen: String, saat: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        kanalOlustur(ctx)
        val ac = PendingIntent.getActivity(
            ctx, 2, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val bildirim = NotificationCompat.Builder(ctx, KANAL)
            .setSmallIcon(R.drawable.ic_bildirim)
            .setContentTitle("$ONCE_DK dk sonra: ${guzelAd(ders)}")
            .setContentText(listOf(saat, guzelAd(ogretmen)).filter { it.isNotBlank() }.joinToString(" • "))
            .setContentIntent(ac)
            .setAutoCancel(true)
            .setTimeoutAfter(15 * 60_000L)
            .build()
        runCatching { NotificationManagerCompat.from(ctx).notify(4242, bildirim) }
    }
}

/** Telefon açılınca ve uygulama güncellenince alarmlar yeniden kurulur (Android alarmları bu durumlarda siler). */
class AcilisAlici : BroadcastReceiver() {
    override fun onReceive(ctx: Context, niyet: Intent) {
        if (niyet.action == Intent.ACTION_BOOT_COMPLETED || niyet.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            DersHatirlatici.planla(ctx)
            LimeWidget.guncelle(ctx)
        }
    }
}

class HatirlaticiAlici : BroadcastReceiver() {
    override fun onReceive(ctx: Context, niyet: Intent) {
        val ders = niyet.getStringExtra("ders")
        if (ders != null && DersHatirlatici.acikMi(ctx)) {
            DersHatirlatici.goster(ctx, ders, niyet.getStringExtra("ogretmen").orEmpty(), niyet.getStringExtra("saat").orEmpty())
        }
        LimeWidget.guncelle(ctx)
        DersHatirlatici.planla(ctx)
    }
}
