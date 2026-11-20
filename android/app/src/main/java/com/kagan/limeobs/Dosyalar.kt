package com.kagan.limeobs

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Audiotrack
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Movie
import androidx.compose.material.icons.outlined.PictureAsPdf
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** Ödev eklerini açma (telefonun uygun uygulamasıyla) ve İndirilenler klasörüne kaydetme. */
object Dosyalar {
    private fun uzanti(ad: String) = ad.substringAfterLast('.', "").lowercase()

    fun mimeTuru(ad: String): String =
        MimeTypeMap.getSingleton().getMimeTypeFromExtension(uzanti(ad)) ?: "application/octet-stream"

    fun ikon(ad: String): ImageVector {
        val mime = mimeTuru(ad)
        return when {
            mime == "application/pdf" -> Icons.Outlined.PictureAsPdf
            mime.startsWith("image/") -> Icons.Outlined.Image
            mime.startsWith("video/") -> Icons.Outlined.Movie
            mime.startsWith("audio/") -> Icons.Outlined.Audiotrack
            else -> Icons.Outlined.Description
        }
    }

    private fun guvenliAd(ad: String) = ad.replace(Regex("[\\\\/:*?\"<>|]"), "_").ifBlank { "dosya" }

    /** Dosyayı geçici klasöre yazar ve uygun uygulamayla açar (video/ses telefonun oynatıcısında). */
    suspend fun ac(ctx: Context, ad: String, veri: ByteArray): String? {
        val dosya = withContext(Dispatchers.IO) {
            File(ctx.cacheDir, "paylas").apply { mkdirs() }.resolve(guvenliAd(ad)).apply { writeBytes(veri) }
        }
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.dosyalar", dosya)
        val niyet = Intent(Intent.ACTION_VIEW).setDataAndType(uri, mimeTuru(ad))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            ctx.startActivity(Intent.createChooser(niyet, ad).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            null
        } catch (e: android.content.ActivityNotFoundException) {
            "Bu dosyayı açabilecek bir uygulama yok. İndir düğmesiyle kaydedebilirsin."
        }
    }

    /** İndirilenler klasörüne kaydeder; kullanıcıya gösterilecek mesajı döner. */
    suspend fun indirilenlereKaydet(ctx: Context, ad: String, veri: ByteArray): String = withContext(Dispatchers.IO) {
        val temiz = guvenliAd(ad)
        if (Build.VERSION.SDK_INT >= 29) {
            val degerler = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, temiz)
                put(MediaStore.Downloads.MIME_TYPE, mimeTuru(ad))
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/LimeOBS")
            }
            val uri = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, degerler)
                ?: throw java.io.IOException("Dosya kaydedilemedi.")
            ctx.contentResolver.openOutputStream(uri)?.use { it.write(veri) } ?: throw java.io.IOException("Dosya kaydedilemedi.")
            "İndirilenler/LimeOBS klasörüne kaydedildi"
        } else {
            // Android 8–9: uygulamanın kendi indirme klasörü (izin gerektirmez)
            val klasor = ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: ctx.filesDir
            klasor.resolve(temiz).writeBytes(veri)
            "Kaydedildi: ${klasor.absolutePath}"
        }
    }
}
