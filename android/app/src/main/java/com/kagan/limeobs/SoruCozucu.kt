package com.kagan.limeobs

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material.icons.outlined.School
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Soru çözücü: fotoğrafı çekilen ya da yazılan tek bir soruyu yapay zekâ adım adım çözer.
 * Fotoğraf yalnızca çöz düğmesine basınca LimeOBS aracı sunucusu üzerinden Groq'a gönderilir; saklanmaz.
 */
object SoruCozucuServisi {
    private const val ADRES = "https://lime.kaganefe.com/v1/solve"
    private val http = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).build()

    /** Fotoğrafı en uzun kenarı 1600 px olacak şekilde küçültüp JPEG'e çevirir (döndürme bilgisi uygulanır). */
    suspend fun hazirla(ctx: Context, uri: Uri): Bitmap = withContext(Dispatchers.IO) {
        val enFazla = 1600
        if (Build.VERSION.SDK_INT >= 28) {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(ctx.contentResolver, uri)) { dec, bilgi, _ ->
                val (g, y) = bilgi.size.width to bilgi.size.height
                val oran = minOf(1f, enFazla.toFloat() / maxOf(g, y))
                dec.setTargetSize((g * oran).toInt().coerceAtLeast(1), (y * oran).toInt().coerceAtLeast(1))
                dec.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
            }
        } else {
            val sinir = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            ctx.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, sinir) }
            var ornek = 1
            while (maxOf(sinir.outWidth, sinir.outHeight) / (ornek * 2) >= enFazla) ornek *= 2
            ctx.contentResolver.openInputStream(uri).use {
                BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = ornek })
            } ?: throw IllegalStateException("Fotoğraf açılamadı.")
        }
    }

    suspend fun coz(metin: String, resim: Bitmap?, parca: suspend (String) -> Unit) = withContext(Dispatchers.IO) {
        val govde = JSONObject()
        if (metin.isNotBlank()) govde.put("text", metin.trim())
        if (resim != null) {
            val cikti = ByteArrayOutputStream()
            resim.compress(Bitmap.CompressFormat.JPEG, 85, cikti)
            govde.put("image", "data:image/jpeg;base64," + Base64.encodeToString(cikti.toByteArray(), Base64.NO_WRAP))
        }
        val istek = Request.Builder().url(ADRES).post(govde.toString().toRequestBody("application/json".toMediaType())).build()
        val cevap = try {
            http.newCall(istek).execute()
        } catch (e: Exception) {
            throw IllegalStateException("Soru çözücüye bağlanılamadı. İnternet bağlantını kontrol et.")
        }
        cevap.use { r ->
            when {
                r.code == 429 -> throw IllegalStateException("Kısa sürede çok fazla soru gönderdin. Biraz bekleyip tekrar dene.")
                r.code == 413 -> throw IllegalStateException("Fotoğraf çok büyük.")
                !r.isSuccessful -> throw IllegalStateException("Soru çözücü şu an cevap veremiyor (HTTP ${r.code}).")
            }
            val kaynak = r.body!!.source()
            while (!kaynak.exhausted()) {
                val satir = kaynak.readUtf8Line() ?: break
                if (!satir.startsWith("data:")) continue
                val veri = satir.substring(5).trim()
                if (veri == "[DONE]") break
                val p = runCatching {
                    JSONObject(veri).getJSONArray("choices").getJSONObject(0).optJSONObject("delta")?.optString("content").orEmpty()
                }.getOrDefault("")
                if (p.isNotEmpty()) withContext(Dispatchers.Main) { parca(p) }
            }
        }
    }

    /** Modelin bazen kullandığı LaTeX işaretlerini sade metne çevirir. */
    fun sadelestir(m: String) = m
        .replace(Regex("\\\\(frac)\\{([^}]*)\\}\\{([^}]*)\\}"), "$2/$3")
        .replace("\\times", "×").replace("\\cdot", "·").replace("\\div", "÷").replace("\\sqrt", "√")
        .replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
        .replace("$", "")
}

@Composable
fun SoruCozucuEkrani() {
    val ctx = LocalContext.current
    val kapsam = rememberCoroutineScope()
    var resim by remember { mutableStateOf<Bitmap?>(null) }
    var metin by remember { mutableStateOf("") }
    var cevap by remember { mutableStateOf("") }
    var hata by remember { mutableStateOf<String?>(null) }
    var mesgul by remember { mutableStateOf(false) }
    val kameraDosyasi = remember { File(ctx.cacheDir, "paylas").apply { mkdirs() }.resolve("soru.jpg") }
    val kameraUri = remember { FileProvider.getUriForFile(ctx, "${ctx.packageName}.dosyalar", kameraDosyasi) }

    fun yukle(uri: Uri) {
        kapsam.launch {
            runCatching { SoruCozucuServisi.hazirla(ctx, uri) }
                .onSuccess { resim = it; cevap = ""; hata = null }
                .onFailure { hata = "Fotoğraf açılamadı." }
        }
    }
    val kamera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { tamam -> if (tamam) yukle(kameraUri) }
    val galeri = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri -> uri?.let(::yukle) }

    fun coz() {
        if (mesgul || (resim == null && metin.isBlank())) return
        mesgul = true; cevap = ""; hata = null
        kapsam.launch {
            try {
                SoruCozucuServisi.coz(metin, resim) { p -> cevap += p }
            } catch (e: Exception) {
                hata = e.message ?: "Beklenmeyen bir hata oluştu."
            } finally {
                mesgul = false
            }
        }
    }

    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (resim == null && cevap.isEmpty()) {
            Kart(renk = MaterialTheme.colorScheme.primaryContainer) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.School, null)
                    Spacer(Modifier.width(10.dp))
                    Text("Takıldığın soruyu çöz", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(6.dp))
                Text("Sorunun fotoğrafını çek ya da yaz; adım adım, nedenleriyle açıklayarak çözeyim. Tek seferde tek soru gönder, fotoğraf net olsun.")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            FilledTonalButton(onClick = { kamera.launch(kameraUri) }, modifier = Modifier.weight(1f), enabled = !mesgul) {
                Icon(Icons.Outlined.PhotoCamera, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Fotoğraf çek")
            }
            FilledTonalButton(
                onClick = { galeri.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                modifier = Modifier.weight(1f), enabled = !mesgul,
            ) {
                Icon(Icons.Outlined.PhotoLibrary, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Galeriden seç")
            }
        }
        resim?.let { r ->
            Box {
                Image(
                    r.asImageBitmap(), "Soru fotoğrafı",
                    Modifier.fillMaxWidth().heightIn(max = 320.dp).clip(RoundedCornerShape(16.dp)), contentScale = ContentScale.Fit,
                )
                Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surface.copy(alpha = 0.85f), modifier = Modifier.align(Alignment.TopEnd).padding(8.dp)) {
                    IconButton(onClick = { resim = null }, enabled = !mesgul) { Icon(Icons.Outlined.Close, "Fotoğrafı kaldır") }
                }
            }
        }
        OutlinedTextField(
            value = metin, onValueChange = { metin = it.take(4000) }, modifier = Modifier.fillMaxWidth(),
            label = { Text(if (resim == null) "Soruyu yaz" else "Not ekle (isteğe bağlı, ör. \"3. soru\")") },
            minLines = if (resim == null) 4 else 1, maxLines = 8, shape = RoundedCornerShape(16.dp),
        )
        Button(onClick = ::coz, enabled = !mesgul && (resim != null || metin.isNotBlank()), modifier = Modifier.fillMaxWidth().height(52.dp)) {
            if (mesgul && cevap.isEmpty()) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
            else Text(if (cevap.isEmpty()) "Çöz" else "Tekrar çöz")
        }
        hata?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (cevap.isNotEmpty()) {
            Kart {
                SelectionContainer { Text(mdMetin(SoruCozucuServisi.sadelestir(cevap)), style = MaterialTheme.typography.bodyLarge) }
            }
            Text(
                "Yapay zekâ hata yapabilir; çözümü kontrol et ve mantığını anlamaya çalış.",
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
