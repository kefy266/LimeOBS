package com.kagan.limeobs

import android.graphics.BitmapFactory
import android.os.Build
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// ---------- Tema ----------

val Limon = Color(0xFF7CC243)
val Yaprak = Color(0xFF2E8B3E)

private val Acik = lightColorScheme(
    primary = Color(0xFF3B6E11), onPrimary = Color.White,
    primaryContainer = Color(0xFFBCF08A), onPrimaryContainer = Color(0xFF0D2000),
    secondary = Color(0xFF55624B), secondaryContainer = Color(0xFFD9E7CA), onSecondaryContainer = Color(0xFF131F0C),
    tertiary = Color(0xFF386664), tertiaryContainer = Color(0xFFBBECE9),
    background = Color(0xFFF8FBF0), surface = Color(0xFFF8FBF0),
    surfaceContainer = Color(0xFFECEFE4), surfaceContainerHigh = Color(0xFFE6E9DF), surfaceContainerLow = Color(0xFFF2F5EA),
)
private val Koyu = darkColorScheme(
    primary = Color(0xFFA1D371), onPrimary = Color(0xFF1B3700),
    primaryContainer = Color(0xFF2A5000), onPrimaryContainer = Color(0xFFBCF08A),
    secondary = Color(0xFFBDCBAF), secondaryContainer = Color(0xFF3E4A35), onSecondaryContainer = Color(0xFFD9E7CA),
    tertiary = Color(0xFFA0CFCC), tertiaryContainer = Color(0xFF1F4E4C),
    background = Color(0xFF11140E), surface = Color(0xFF11140E),
    surfaceContainer = Color(0xFF1E211A), surfaceContainerHigh = Color(0xFF282B24), surfaceContainerLow = Color(0xFF191D16),
)

@Composable
fun LimeTema(icerik: @Composable () -> Unit) {
    val koyu = isSystemInDarkTheme()
    val ctx = LocalContext.current
    val renkler: ColorScheme = when {
        Build.VERSION.SDK_INT >= 31 -> if (koyu) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        koyu -> Koyu
        else -> Acik
    }
    MaterialTheme(colorScheme = renkler, content = icerik)
}

/** Oturum tamamen düşünce giriş ekranına dönmek için */
val LocalOturumDustu = compositionLocalOf<() -> Unit> { {} }

// ---------- Yükleme kalıbı ----------

private sealed interface Durum<out T> {
    data object Yukleniyor : Durum<Nothing>
    data class Hata(val mesaj: String) : Durum<Nothing>
    data class Hazir<T>(val veri: T) : Durum<T>
}

/**
 * Veriyi yükler; yükleniyor/hata/hazır durumlarını ve aşağı çekip yenilemeyi yönetir.
 * [icerik] bir LazyColumn gövdesidir.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun <T> Yukle(
    anahtar: Any?,
    yukle: suspend (zorla: Boolean) -> T,
    ust: PaddingValues = PaddingValues(0.dp),
    icerik: LazyListScope.(T) -> Unit,
) {
    var durum by remember(anahtar) { mutableStateOf<Durum<T>>(Durum.Yukleniyor) }
    var tetik by remember(anahtar) { mutableIntStateOf(0) }
    var yenileniyor by remember(anahtar) { mutableStateOf(false) }
    val oturumDustu = LocalOturumDustu.current
    val ctx = LocalContext.current

    LaunchedEffect(anahtar, tetik) {
        val zorla = tetik > 0
        try {
            durum = Durum.Hazir(yukle(zorla))
        } catch (e: OturumHatasi) {
            oturumDustu()
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            if (durum !is Durum.Hazir) durum = Durum.Hata(e.message ?: "Bilinmeyen hata")
            else android.widget.Toast.makeText(ctx, "Yenilenemedi: ${e.message}", android.widget.Toast.LENGTH_SHORT).show()
        } finally {
            yenileniyor = false
        }
    }

    PullToRefreshBox(
        isRefreshing = yenileniyor,
        onRefresh = { yenileniyor = true; tetik++ },
        modifier = Modifier.fillMaxSize(),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = ust.calculateTopPadding() + 8.dp, bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when (val d = durum) {
                is Durum.Yukleniyor -> item {
                    Box(Modifier.fillMaxWidth().padding(top = 120.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                }
                is Durum.Hata -> item { HataKutusu(d.mesaj) { durum = Durum.Yukleniyor; tetik++ } }
                is Durum.Hazir -> icerik(d.veri)
            }
        }
    }
}

@Composable
fun HataKutusu(mesaj: String, tekrar: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(top = 80.dp, start = 24.dp, end = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Outlined.CloudOff, null, Modifier.size(48.dp), tint = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(12.dp))
        Text("Yüklenemedi", style = MaterialTheme.typography.titleMedium)
        Text(mesaj, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        Spacer(Modifier.height(16.dp))
        Button(onClick = tekrar) { Text("Tekrar dene") }
    }
}

// ---------- Küçük bileşenler ----------

@Composable
fun Kart(modifier: Modifier = Modifier, renk: Color = MaterialTheme.colorScheme.surfaceContainer, icerik: @Composable () -> Unit) {
    Surface(modifier = modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), color = renk) {
        Column(Modifier.padding(18.dp)) { icerik() }
    }
}

@Composable
fun BolumBasligi(metin: String, alt: String? = null) {
    Column(Modifier.padding(top = 8.dp, start = 4.dp)) {
        Text(metin, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (alt != null) Text(alt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun Rozet(metin: String, renk: Color = MaterialTheme.colorScheme.secondaryContainer, yazi: Color = MaterialTheme.colorScheme.onSecondaryContainer) {
    Box(Modifier.clip(RoundedCornerShape(50)).background(renk).padding(horizontal = 10.dp, vertical = 4.dp)) {
        Text(metin, color = yazi, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

@Composable
fun Avatar(ad: String, foto: ByteArray?, boyut: Dp = 56.dp) {
    val bitmap = remember(foto) { foto?.let { runCatching { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }.getOrNull() } }
    if (bitmap != null) {
        Image(bitmap, null, Modifier.size(boyut).clip(CircleShape), contentScale = ContentScale.Crop)
    } else {
        Box(
            Modifier.size(boyut).clip(CircleShape).background(Brush.linearGradient(listOf(Limon, Yaprak))),
            contentAlignment = Alignment.Center,
        ) {
            Text(basHarfler(ad), color = Color.White, fontWeight = FontWeight.Bold, fontSize = (boyut.value * 0.36f).sp)
        }
    }
}

fun basHarfler(ad: String) = ad.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }.ifBlank { "L" }

/** "KAĞAN EFE" → "Kağan Efe" */
fun guzelAd(ad: String) = ad.lowercase(java.util.Locale("tr")).split(' ').joinToString(" ") { s ->
    s.replaceFirstChar { it.titlecase(java.util.Locale("tr")) }
}

@Composable
fun BilgiSatiri(baslik: String, deger: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(baslik, Modifier.width(130.dp), color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        Text(deger, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun BosDurum(baslik: String, alt: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(baslik, style = MaterialTheme.typography.titleMedium)
        Text(alt, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

/** Ders adına göre sabit, hoş bir renk */
fun dersRengi(ders: String): Color {
    val palet = listOf(0xFFE5484D, 0xFF3574F0, 0xFF2EA043, 0xFFE88C1E, 0xFF8E4EC6, 0xFF0096A0, 0xFFD63384, 0xFF546278, 0xFF966E3C, 0xFF12A594)
    return Color(palet[Math.floorMod(ders.trim().uppercase().hashCode(), palet.size)])
}
