package com.kagan.limeobs

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Otomatik güncelleme: GitHub'daki "android" sürümünde duran surum.json'a bakar; daha yeni bir derleme varsa
 * APK'yı indirip Android'in kurulum ekranını açar. (Play Store olmadığı için kurulumu kullanıcı onaylar.)
 */
data class YeniSurum(val kod: Int, val ad: String, val notlar: String, val apk: String)

object Guncelleme {
    /** Bulunan yeni sürüm; iletişim kutusu bunu gösterir (açılışta ya da "Güncellemeleri denetle"den). */
    val bulunan = mutableStateOf<YeniSurum?>(null)

    private const val TABAN = "https://github.com/kefy266/LimeOBS/releases/download/android-guncel"
    private val http = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS).build()

    fun mevcutKod(ctx: Context): Long =
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).longVersionCode

    /** Daha yeni sürüm varsa döner; yoksa ya da bağlantı yoksa null. Günde en fazla bir kez sorar. */
    suspend fun denetle(ctx: Context, zorla: Boolean = false): YeniSurum? = withContext(Dispatchers.IO) {
        val prefs = ctx.getSharedPreferences("limeobs_guncelleme", Context.MODE_PRIVATE)
        if (!zorla && System.currentTimeMillis() - prefs.getLong("son", 0) < 6 * 3_600_000L) return@withContext null
        val metin = runCatching {
            http.newCall(Request.Builder().url("$TABAN/surum.json?t=${System.currentTimeMillis()}").build()).execute()
                .use { if (it.isSuccessful) it.body?.string() else null }
        }.getOrNull() ?: return@withContext null
        prefs.edit().putLong("son", System.currentTimeMillis()).apply()
        val j = runCatching { JSONObject(metin) }.getOrNull() ?: return@withContext null
        val kod = j.optInt("versionCode")
        if (kod <= mevcutKod(ctx) || (!zorla && kod == prefs.getInt("atlanan", -1))) return@withContext null
        YeniSurum(kod, j.optString("versionName"), j.optString("notes"), j.optString("apk", "$TABAN/LimeOBS-Android.apk"))
    }

    fun atla(ctx: Context, kod: Int) =
        ctx.getSharedPreferences("limeobs_guncelleme", Context.MODE_PRIVATE).edit().putInt("atlanan", kod).apply()

    suspend fun indir(ctx: Context, s: YeniSurum, ilerleme: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val klasor = File(ctx.cacheDir, "guncelleme").apply { mkdirs(); listFiles()?.forEach { it.delete() } }
        val dosya = File(klasor, "LimeOBS-${s.kod}.apk")
        http.newCall(Request.Builder().url(s.apk).build()).execute().use { r ->
            if (!r.isSuccessful) throw IllegalStateException("İndirme başarısız (HTTP ${r.code}).")
            val govde = r.body ?: throw IllegalStateException("İndirme başarısız.")
            val toplam = govde.contentLength().coerceAtLeast(1)
            var okunan = 0L
            govde.byteStream().use { giris ->
                dosya.outputStream().use { cikis ->
                    val tampon = ByteArray(64 * 1024)
                    while (true) {
                        val n = giris.read(tampon)
                        if (n < 0) break
                        cikis.write(tampon, 0, n)
                        okunan += n
                        withContext(Dispatchers.Main) { ilerleme(okunan.toFloat() / toplam) }
                    }
                }
            }
        }
        dosya
    }

    /** Kurulum ekranını açar; "bilinmeyen kaynak" izni yoksa önce ayar sayfasını açar ve false döner. */
    fun kur(ctx: Context, apk: File): Boolean {
        if (!ctx.packageManager.canRequestPackageInstalls()) {
            ctx.startActivity(
                Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${ctx.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
            return false
        }
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.dosyalar", apk)
        ctx.startActivity(
            Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        )
        return true
    }
}

/** Açılışta sessizce denetler; yeni sürüm varsa iletişim kutusu gösterir. */
@Composable
fun GuncellemeDenetleyici() {
    val ctx = LocalContext.current
    val kapsam = rememberCoroutineScope()
    var yeni by Guncelleme.bulunan
    var ilerleme by remember { mutableStateOf<Float?>(null) }
    var hazir by remember { mutableStateOf<File?>(null) }
    var hata by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) { Guncelleme.denetle(ctx)?.let { yeni = it } }

    val s = yeni ?: return
    AlertDialog(
        onDismissRequest = { if (ilerleme == null || hazir != null) yeni = null },
        title = { Text("Yeni sürüm: ${s.ad}") },
        text = {
            Column {
                Text(s.notlar.ifBlank { "LimeOBS'un yeni sürümü hazır." })
                ilerleme?.let {
                    Spacer(Modifier.height(16.dp))
                    LinearProgressIndicator(progress = { it })
                }
                hata?.let {
                    Spacer(Modifier.height(12.dp))
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
                if (hazir != null && !ctx.packageManager.canRequestPackageInstalls()) {
                    Spacer(Modifier.height(12.dp))
                    Text("Kurulum için açılan ayarda \"Bu kaynaktan izin ver\"i aç, sonra geri dönüp Kur'a bas.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = ilerleme == null || hazir != null, onClick = {
                hazir?.let { Guncelleme.kur(ctx, it); return@TextButton }
                hata = null
                ilerleme = 0f
                kapsam.launch {
                    try {
                        val dosya = Guncelleme.indir(ctx, s) { ilerleme = it }
                        hazir = dosya
                        Guncelleme.kur(ctx, dosya)
                    } catch (e: Exception) {
                        ilerleme = null
                        hata = e.message ?: "İndirme başarısız."
                    }
                }
            }) { Text(if (hazir != null) "Kur" else "Güncelle") }
        },
        dismissButton = {
            if (ilerleme == null) TextButton(onClick = { Guncelleme.atla(ctx, s.kod); yeni = null }) { Text("Bu sürümü atla") }
        },
    )
}

fun surumAdi(ctx: Context): String =
    runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: "?"
