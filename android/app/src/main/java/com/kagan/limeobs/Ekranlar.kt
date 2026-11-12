package com.kagan.limeobs

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AttachFile
import androidx.compose.material.icons.outlined.TrendingDown
import androidx.compose.material.icons.outlined.TrendingUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.time.LocalDateTime
import java.util.Locale

// ================= Ders programı =================

@Composable
fun ProgramEkrani() {
    val obs = Obs.al(LocalContext.current)
    var secili by rememberSaveable { mutableStateOf(etkinOkulGunu().dayOfWeek.value) }
    Yukle(anahtar = "program", yukle = { obs.anaVeri(it).program }) { p ->
        val gunSayisi = maxOf(5, p.hucreler.maxOfOrNull { it.gun } ?: 5).coerceAtMost(7)
        item {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (g in 1..gunSayisi) {
                    val tarih = p.gunler.getOrNull(g - 1)?.second.orEmpty()
                    FilterChip(
                        selected = secili == g, onClick = { secili = g },
                        label = { Text(GUN_ADLARI[g - 1].take(3) + if (tarih.length >= 5) " " + tarih.take(5) else "") },
                    )
                }
            }
        }
        val dersler = p.hucreler.filter { it.gun == secili }.sortedBy { it.saat }
        if (dersler.isEmpty()) item { BosDurum("Ders yok", "${GUN_ADLARI[secili - 1]} için programda ders görünmüyor.") }
        val simdi = LocalDateTime.now()
        val bugun = simdi.dayOfWeek.value == secili
        items(dersler) { d ->
            val araligi = p.saatler.getOrNull(d.saat - 1).orEmpty()
            val ss = saatAraligi(araligi)
            val suan = bugun && ss != null && simdi.toLocalTime() >= ss.first && simdi.toLocalTime() < ss.second
            val gecti = bugun && ss != null && simdi.toLocalTime() >= ss.second
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.width(58.dp)) {
                    Text("${d.saat}. ders", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(araligi.substringBefore(" -").trim(), fontWeight = FontWeight.Bold)
                    Text(araligi.substringAfter("- ", "").trim(), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                val renk = Color(d.renk)
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = if (suan) renk else renk.copy(alpha = if (gecti) 0.10f else 0.16f),
                    modifier = Modifier.weight(1f),
                ) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.width(5.dp).height(38.dp).clip(RoundedCornerShape(50)).background(if (suan) Color.White else renk))
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                guzelAd(d.ders), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium,
                                color = if (suan) Color.White else MaterialTheme.colorScheme.onSurface,
                            )
                            if (d.ogretmen.isNotBlank()) Text(
                                guzelAd(d.ogretmen), style = MaterialTheme.typography.bodyMedium,
                                color = if (suan) Color.White.copy(alpha = 0.9f) else MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (suan) Rozet("ŞU AN", renk = Color.White.copy(alpha = 0.25f), yazi = Color.White)
                    }
                }
            }
        }
    }
}

// ================= Ödevler =================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OdevlerEkrani() {
    val obs = Obs.al(LocalContext.current)
    var filtre by rememberSaveable { mutableStateOf(0) }
    var secili by remember { mutableStateOf<Odev?>(null) }
    Yukle(anahtar = "odevler", yukle = { obs.odevler(it) }) { liste ->
        val aktif = liste.filter { it.aktif && it.durumKod == 0 }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(filtre == 0, { filtre = 0 }, { Text("Bekleyen (${aktif.size})") })
                FilterChip(filtre == 1, { filtre = 1 }, { Text("Değerlendirilen") })
                FilterChip(filtre == 2, { filtre = 2 }, { Text("Tümü (${liste.size})") })
            }
        }
        val gosterilen = when (filtre) {
            0 -> aktif.sortedBy { Obs.tarihSayi(it.bitis) }
            1 -> liste.filter { it.durumKod != 0 }
            else -> liste
        }
        if (gosterilen.isEmpty()) item { BosDurum("Burada ödev yok", if (filtre == 0) "Teslim bekleyen ödevin kalmamış." else "Liste boş.") }
        items(gosterilen, key = { it.id }) { o -> OdevKarti(o) { secili = o } }
    }
    secili?.let { o ->
        ModalBottomSheet(onDismissRequest = { secili = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            OdevDetaySayfasi(o)
        }
    }
}

@Composable
private fun OdevKarti(o: Odev, tikla: () -> Unit) {
    val renk = dersRengi(o.ders)
    Surface(shape = RoundedCornerShape(22.dp), color = MaterialTheme.colorScheme.surfaceContainer, onClick = tikla, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp)) {
            Box(Modifier.width(5.dp).height(56.dp).clip(RoundedCornerShape(50)).background(renk))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(guzelAd(o.ders), style = MaterialTheme.typography.labelLarge, color = renk, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    if (o.ekVar) Icon(Icons.Outlined.AttachFile, "Ekli dosya", Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (!o.goruldu) {
                        Spacer(Modifier.width(6.dp))
                        Rozet("YENİ", renk = MaterialTheme.colorScheme.primary, yazi = MaterialTheme.colorScheme.onPrimary)
                    }
                }
                Text(o.baslik, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Rozet(o.tur.lowercase(Locale("tr")).replaceFirstChar { it.titlecase(Locale("tr")) })
                    if (o.durumKod == 0) {
                        kalanGun(o.bitis)?.let { g ->
                            Rozet(
                                if (g < 0) "Süresi doldu" else "Teslim: ${kalanMetni(g)}",
                                renk = if (g <= 1) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.tertiaryContainer,
                                yazi = if (g <= 1) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onTertiaryContainer,
                            )
                        }
                    } else {
                        Rozet(o.durum + if (o.puan.isNotBlank() && o.puan != "-") " • ${o.puan}" else "")
                    }
                }
            }
        }
    }
}

@Composable
private fun OdevDetaySayfasi(o: Odev) {
    val obs = Obs.al(LocalContext.current)
    var detay by remember { mutableStateOf<OdevDetay?>(null) }
    var hata by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(o.id) {
        runCatching { obs.odevDetay(o.id) }.onSuccess { detay = it }.onFailure { hata = it.message }
    }
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 32.dp).navigationBarsPadding()) {
        Text(guzelAd(o.ders), color = dersRengi(o.ders), fontWeight = FontWeight.Bold)
        Text(o.baslik, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))
        BilgiSatiri("Öğretmen", guzelAd(o.ogretmen))
        BilgiSatiri("Tür", o.tur)
        BilgiSatiri("Veriliş", o.baslangic)
        BilgiSatiri("Son teslim", o.bitis + (kalanGun(o.bitis)?.let { "  (${kalanMetni(it)})" } ?: ""))
        BilgiSatiri("Durum", o.durum + if (o.puan.isNotBlank() && o.puan != "-") " • Puan ${o.puan}" else "")
        Spacer(Modifier.height(12.dp))
        when {
            detay != null -> {
                Kart {
                    Text("Açıklama", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(4.dp))
                    SelectionContainer { Text(detay!!.aciklama.ifBlank { "Öğretmen açıklama eklememiş." }) }
                }
                if (detay!!.ogretmenNotu.isNotBlank()) {
                    Spacer(Modifier.height(10.dp))
                    Kart(renk = MaterialTheme.colorScheme.primaryContainer) {
                        Text("Öğretmen notu", style = MaterialTheme.typography.labelLarge)
                        Text(detay!!.ogretmenNotu)
                    }
                }
                if (detay!!.ekSayisi > 0) {
                    Spacer(Modifier.height(10.dp))
                    Text("${detay!!.ekSayisi} ekli dosya var — indirmek için okul OBS sitesini kullan.", style = MaterialTheme.typography.bodySmall)
                }
            }
            hata != null -> Text(hata!!, color = MaterialTheme.colorScheme.error)
            else -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
        }
    }
}

// ================= Sınavlar =================

@Composable
fun SinavlarEkrani() {
    val obs = Obs.al(LocalContext.current)
    Yukle(anahtar = "sinavlar", yukle = { obs.sinavlar(it) }) { oz ->
        if (oz.sinavlar.isEmpty()) {
            item { BosDurum("Henüz sınav yok", "Girdiğin deneme ve tarama sınavları burada görünecek.") }
            return@Yukle
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Ozet("Son puan", oz.sonPuan?.let { "%.1f".format(it) } ?: "-", Modifier.weight(1f), oz.degisim)
                Ozet("Ortalama", oz.ortalama?.let { "%.1f".format(it) } ?: "-", Modifier.weight(1f))
                Ozet("Sınav", "${oz.sinavlar.size}", Modifier.weight(1f))
            }
        }
        val denemeler = oz.sinavlar.filter { it.kategori == "Deneme" }.sortedBy { Obs.tarihSayi(it.tarih) }
        if (denemeler.size >= 2) {
            item {
                Kart {
                    Text("Puan gidişatı", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("Deneme sınavların", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(12.dp))
                    PuanGrafigi(denemeler.map { it.puan.toFloat() })
                }
            }
        }
        if (oz.dersler.isNotEmpty()) {
            item {
                Kart {
                    Text("Derslere göre başarı", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    oz.dersler.sortedByDescending { it.oran }.forEach { d ->
                        Spacer(Modifier.height(10.dp))
                        Row {
                            Text(guzelAd(d.ders), Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            Text("%%%.0f".format(d.oran), fontWeight = FontWeight.Bold)
                        }
                        Spacer(Modifier.height(4.dp))
                        LinearProgressIndicator(
                            progress = { (d.oran / 100.0).toFloat().coerceIn(0f, 1f) },
                            modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(50)),
                            color = dersRengi(d.ders), trackColor = dersRengi(d.ders).copy(alpha = 0.15f), strokeCap = StrokeCap.Round,
                        )
                    }
                }
            }
        }
        item { BolumBasligi("Tüm sınavlar") }
        items(oz.sinavlar) { s -> SinavKarti(s) }
    }
}

@Composable
private fun Ozet(baslik: String, deger: String, modifier: Modifier, degisim: Double? = null) {
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceContainer) {
        Column(Modifier.padding(14.dp)) {
            Text(baslik, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(deger, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black)
            if (degisim != null && degisim != 0.0) {
                val artis = degisim > 0
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (artis) Icons.Outlined.TrendingUp else Icons.Outlined.TrendingDown, null, Modifier.size(16.dp),
                        tint = if (artis) Color(0xFF2EA043) else MaterialTheme.colorScheme.error,
                    )
                    Text(
                        (if (artis) "+" else "") + "%.1f".format(degisim), style = MaterialTheme.typography.labelMedium,
                        color = if (artis) Color(0xFF2EA043) else MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

@Composable
private fun PuanGrafigi(puanlar: List<Float>) {
    val ana = MaterialTheme.colorScheme.primary
    val izgara = MaterialTheme.colorScheme.outlineVariant
    Canvas(Modifier.fillMaxWidth().height(140.dp)) {
        val enAz = (puanlar.min() - 20f).coerceAtLeast(0f)
        val enCok = puanlar.max() + 10f
        val adim = size.width / (puanlar.size - 1)
        fun y(p: Float) = size.height - (p - enAz) / (enCok - enAz) * size.height
        for (i in 0..3) {
            val yy = size.height * i / 3f
            drawLine(izgara, Offset(0f, yy), Offset(size.width, yy), strokeWidth = 1f)
        }
        val cizgi = Path()
        val alan = Path()
        puanlar.forEachIndexed { i, p ->
            val x = i * adim
            if (i == 0) {
                cizgi.moveTo(x, y(p)); alan.moveTo(x, size.height); alan.lineTo(x, y(p))
            } else {
                val px = (i - 1) * adim
                val ox = (px + x) / 2
                cizgi.cubicTo(ox, y(puanlar[i - 1]), ox, y(p), x, y(p))
                alan.cubicTo(ox, y(puanlar[i - 1]), ox, y(p), x, y(p))
            }
        }
        alan.lineTo(size.width, size.height)
        alan.close()
        drawPath(alan, Brush.verticalGradient(listOf(ana.copy(alpha = 0.35f), Color.Transparent)))
        drawPath(cizgi, ana, style = Stroke(width = 6f, cap = StrokeCap.Round))
        puanlar.forEachIndexed { i, p ->
            drawCircle(Color.White, 9f, Offset(i * adim, y(p)))
            drawCircle(ana, 6f, Offset(i * adim, y(p)))
        }
    }
}

@Composable
private fun SinavKarti(s: Sinav) {
    Kart {
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Rozet(s.kategori, renk = if (s.kategori == "Deneme") MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.tertiaryContainer)
                    Rozet(s.tarih)
                }
                Spacer(Modifier.height(6.dp))
                Text(s.ad, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                Text("%.2f".format(s.puan), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Black, color = MaterialTheme.colorScheme.primary)
                Text("puan", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Sayi("Net", "%.2f".format(s.net), Modifier.weight(1f))
            Sayi("Doğru", "${s.dogru}", Modifier.weight(1f), Color(0xFF2EA043))
            Sayi("Yanlış", "${s.yanlis}", Modifier.weight(1f), MaterialTheme.colorScheme.error)
            Sayi("Boş", "${s.bos}", Modifier.weight(1f))
        }
        if (s.soru > 0) {
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(50))) {
                if (s.dogru > 0) Box(Modifier.weight(s.dogru.toFloat()).height(8.dp).background(Color(0xFF2EA043)))
                if (s.yanlis > 0) Box(Modifier.weight(s.yanlis.toFloat()).height(8.dp).background(MaterialTheme.colorScheme.error))
                if (s.bos > 0) Box(Modifier.weight(s.bos.toFloat()).height(8.dp).background(MaterialTheme.colorScheme.outlineVariant))
            }
        }
        val siralar = listOfNotNull(
            s.sinifSira.takeIf { it.isNotBlank() && it != "0" && it != "null" }?.let { "Sınıf sırası $it" },
            s.genelSira.takeIf { it.isNotBlank() && it != "0" && it != "null" }?.let { "Genel sıra $it" },
        )
        if (siralar.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Text(siralar.joinToString(" • "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun Sayi(ad: String, deger: String, modifier: Modifier, renk: Color = MaterialTheme.colorScheme.onSurface) {
    Column(modifier.clip(RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surfaceContainerHigh).padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(deger, fontWeight = FontWeight.Bold, color = renk)
        Text(ad, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
