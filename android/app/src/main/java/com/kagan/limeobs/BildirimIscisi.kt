package com.kagan.limeobs

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * Uygulama kapalıyken 30 dakikada bir okulun bildirim listesini kontrol eder ve
 * yeni ödev/sınav/duyuru geldiğinde telefona bildirim düşer.
 */
class BildirimIscisi(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        val obs = Obs.al(applicationContext)
        if (!obs.kayitliGirisVar || !obs.bildirimlerAcik) return Result.success()
        val liste = runCatching { obs.bildirimler() }.getOrElse { return Result.retry() }
        val gorulen = obs.gorulenBildirimler
        val ilk = obs.bildirimIlkCalisma
        val yeniler = liste.filter { it.id !in gorulen }
        obs.gorulenBildirimler = gorulen + liste.map { it.id }
        if (!ilk) yeniler.take(5).forEach { goster(applicationContext, it) }
        return Result.success()
    }

    companion object {
        private const val KANAL = "okul"
        private const val IS_ADI = "limeobs-bildirim"

        fun kanalOlustur(ctx: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val kanal = NotificationChannel(KANAL, "Okul bildirimleri", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Yeni ödev, sınav, mesaj ve duyurular"
                }
                ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(kanal)
            }
        }

        fun planla(ctx: Context) {
            val istek = PeriodicWorkRequestBuilder<BildirimIscisi>(30, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(IS_ADI, ExistingPeriodicWorkPolicy.KEEP, istek)
        }

        fun iptal(ctx: Context) {
            WorkManager.getInstance(ctx).cancelUniqueWork(IS_ADI)
        }

        private fun turAdi(tur: Int) = when (tur) {
            1 -> "Sınav"
            2 -> "Yeni ödev"
            3 -> "Mesaj"
            else -> "Okul bildirimi"
        }

        @SuppressLint("MissingPermission")
        fun goster(ctx: Context, b: Bildirim) {
            if (Build.VERSION.SDK_INT >= 33 &&
                ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
            ) return
            val ac = PendingIntent.getActivity(
                ctx, 0,
                Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE,
            )
            val bildirim = NotificationCompat.Builder(ctx, KANAL)
                .setSmallIcon(R.drawable.ic_bildirim)
                .setContentTitle(turAdi(b.tur))
                .setContentText(b.baslik)
                .setStyle(NotificationCompat.BigTextStyle().bigText(b.baslik))
                .setContentIntent(ac)
                .setAutoCancel(true)
                .build()
            runCatching { NotificationManagerCompat.from(ctx).notify((b.id % Int.MAX_VALUE).toInt(), bildirim) }
        }
    }
}
