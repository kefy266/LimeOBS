package com.kagan.limeobs

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.material.icons.outlined.PictureAsPdf
import androidx.compose.material3.FilledTonalButton
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.CalendarMonth
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
import java.time.LocalDate
import java.time.LocalDateTime
import java.util.Locale

// ================= Ders programı =================

@Composable
fun ProgramEkrani() {
    val obs = Obs.al(LocalContext.current)
    val genis = androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp >= 840
    var secili by rememberSaveable { mutableStateOf(etkinOkulGunu().dayOfWeek.value) }
    val ctx = LocalContext.current
    val kapsam = rememberCoroutineScope()
    var pdfHazirlaniyor by remember { mutableStateOf(false) }
    var pdfHata by remember { mutableStateOf<String?>(null) }
    Yukle(anahtar = "program", yukle = { obs.anaVeri(it).program }) { p ->
        val gunSayisi = maxOf(5, p.hucreler.maxOfOrNull { it.gun } ?: 5).coerceAtMost(7)
        // Gösterilen hafta: tatil/hafta sonunda okulun açılacağı hafta (OBS'nin tarihleri içinde bulunulan haftayı gösterir)
        val pazartesi = etkinOkulGunu().with(java.time.DayOfWeek.MONDAY)
        val gunTarihi = { g: Int -> pazartesi.plusDays((g - 1).toLong()) }
        val ayFormat = java.time.format.DateTimeFormatter.ofPattern("d MMMM", Locale("tr"))
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    pdfHata ?: "${gunTarihi(1).format(ayFormat)} haftası",
                    Modifier.weight(1f),
                    color = if (pdfHata != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
                FilledTonalButton(enabled = !pdfHazirlaniyor, onClick = {
                    pdfHazirlaniyor = true
                    pdfHata = null
                    kapsam.launch {
                        runCatching { ProgramPdf.olustur(ctx) }
                            .onSuccess { ProgramPdf.paylas(ctx, it) }
                            .onFailure { pdfHata = it.message ?: "PDF oluşturulamadı." }
                        pdfHazirlaniyor = false
                    }
                }) {
                    Icon(Icons.Outlined.PictureAsPdf, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text(if (pdfHazirlaniyor) "Hazırlanıyor…" else "PDF olarak paylaş")
                }
            }
        }
        if (genis) {
            item { HaftalikTablo(p, gunSayisi, gunTarihi) }
            return@Yukle
        }
        item {
            // Programdaki bütün günler (hafta sonu dersi varsa o da) tek satıra sığar
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (g in 1..gunSayisi) {
                    val tarih = gunTarihi(g)
                    val tatil = g <= 5 && Takvim.okulYokNedeni(tarih) != null
                    val sec = secili == g
                    Surface(
                        onClick = { secili = g }, modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(14.dp),
                        color = if (sec) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent,
                        border = if (sec) null else androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                    ) {
                        Column(Modifier.padding(vertical = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                listOf("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")[g - 1], fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.labelLarge,
                                color = if (tarih == LocalDate.now()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                            )
                            Text(
                                "%02d.%02d".format(tarih.dayOfMonth, tarih.monthValue), style = MaterialTheme.typography.labelSmall,
                                color = if (tatil) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                                textDecoration = if (tatil) androidx.compose.ui.text.style.TextDecoration.LineThrough else null,
                            )
                        }
                    }
                }
            }
        }
        val seciliTarih = gunTarihi(secili)
        val tatilNedeni = Takvim.okulYokNedeni(seciliTarih)?.takeIf { secili <= 5 }
        val dersler = if (tatilNedeni != null) emptyList() else p.hucreler.filter { it.gun == secili }.sortedBy { it.saat }
        if (tatilNedeni != null) item { BosDurum("Okul yok", "${seciliTarih.format(ayFormat)} ${GUN_ADLARI[secili - 1]}: $tatilNedeni") }
        else if (dersler.isEmpty()) item { BosDurum("Ders yok", "${GUN_ADLARI[secili - 1]} için programda ders görünmüyor.") }
        val simdi = LocalDateTime.now()
        val bugun = simdi.toLocalDate() == seciliTarih
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

/** Tablet: bütün hafta tek tabloda (satırlar ders saatleri, sütunlar günler). */
@Composable
private fun HaftalikTablo(p: DersProgrami, gunSayisi: Int, gunTarihi: (Int) -> LocalDate) {
    val gunler = (1..gunSayisi).filter { g -> g <= 5 || p.hucreler.any { it.gun == g } }
    val saatSayisi = maxOf(p.saatler.size, p.hucreler.maxOfOrNull { it.saat } ?: 0)
    val bugun = LocalDate.now()
    val ayrac = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
    Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Spacer(Modifier.width(64.dp))
                gunler.forEach { g ->
                    val t = gunTarihi(g)
                    val tatil = if (g <= 5) Takvim.okulYokNedeni(t) else null
                    Column(Modifier.weight(1f).padding(vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            GUN_ADLARI[g - 1], fontWeight = FontWeight.Bold,
                            color = if (t == bugun) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                        )
                        Text(
                            tatil ?: "%02d.%02d".format(t.dayOfMonth, t.monthValue), maxLines = 1, overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (tatil != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            for (saat in 1..saatSayisi) {
                val aralik = p.saatler.getOrNull(saat - 1).orEmpty()
                Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Column(Modifier.width(64.dp).padding(top = 6.dp)) {
                        Text("$saat. ders", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(aralik.substringBefore(" -").trim(), fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                    }
                    gunler.forEach { g ->
                        val tatil = g <= 5 && Takvim.okulYokNedeni(gunTarihi(g)) != null
                        val d = p.hucreler.firstOrNull { it.gun == g && it.saat == saat }
                        val renk = d?.let { Color(it.renk) }
                        Box(
                            Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(14.dp))
                                .background(
                                    when {
                                        d == null -> ayrac.copy(alpha = 0.15f)
                                        tatil -> renk!!.copy(alpha = 0.06f)
                                        else -> renk!!.copy(alpha = 0.18f)
                                    }
                                )
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                        ) {
                            if (d != null) Column {
                                Text(
                                    guzelAd(d.ders), fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (tatil) MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f) else MaterialTheme.colorScheme.onSurface,
                                )
                                if (d.ogretmen.isNotBlank()) Text(
                                    guzelAd(d.ogretmen), maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
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
        val ctxOdev = LocalContext.current
        tarihCoz(o.bitis)?.let { t ->
            androidx.compose.material3.TextButton(onClick = {
                TakvimeAktar.tekEkle(ctxOdev, "📚 ${guzelAd(o.ders)}: ${o.baslik}", t, "Ödev teslimi • ${guzelAd(o.ogretmen)}")
            }) {
                Icon(Icons.Outlined.CalendarMonth, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Teslim gününü takvime ekle")
            }
        }
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
                if (detay!!.ekler.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    Text("Ekler", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    detay!!.ekler.forEach { ek -> EkSatiri(o.id, ek) }
                }
            }
            hata != null -> Text(hata!!, color = MaterialTheme.colorScheme.error)
            else -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
        }
    }
}

@Composable
private fun EkSatiri(odevId: Int, ek: EkDosya) {
    val ctx = LocalContext.current
    val obs = Obs.al(ctx)
    val kapsam = rememberCoroutineScope()
    var bekliyor by remember { mutableStateOf(false) }
    fun yap(kaydet: Boolean) {
        if (bekliyor) return
        bekliyor = true
        kapsam.launch {
            runCatching {
                val veri = obs.ekIndir(odevId, ek)
                if (kaydet) Dosyalar.indirilenlereKaydet(ctx, ek.ad, veri) else Dosyalar.ac(ctx, ek.ad, veri)
            }.onSuccess { mesaj -> mesaj?.let { android.widget.Toast.makeText(ctx, it, android.widget.Toast.LENGTH_SHORT).show() } }
                .onFailure { android.widget.Toast.makeText(ctx, it.message ?: "Dosya indirilemedi.", android.widget.Toast.LENGTH_SHORT).show() }
            bekliyor = false
        }
    }
    Surface(
        shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceContainer,
        onClick = { yap(false) }, modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
    ) {
        Row(Modifier.padding(start = 14.dp, end = 4.dp, top = 4.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Dosyalar.ikon(ek.ad), null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(12.dp))
            Text(ek.ad, Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
            if (bekliyor) CircularProgressIndicator(Modifier.padding(12.dp).size(22.dp), strokeWidth = 2.dp)
            else IconButton(onClick = { yap(true) }) { Icon(Icons.Outlined.Download, "İndir") }
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
fun PuanGrafigi(puanlar: List<Float>) {
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
