package com.kagan.limeobs

import android.graphics.Bitmap
import android.graphics.Color as AColor
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.automirrored.outlined.Reply
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.Campaign
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.EventBusy
import androidx.compose.material.icons.outlined.Groups
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Restaurant
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

// ================= Mesajlar =================

/** Yeni mesaj veya yanıt için hazırlanan taslak */
data class Taslak(val alici: Alici?, val baslik: String = "", val yanitId: Int? = null)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MesajlarEkrani() {
    val obs = Obs.al(LocalContext.current)
    var kutu by rememberSaveable { mutableStateOf(0) }
    var acik by remember { mutableStateOf<Mesaj?>(null) }
    var taslak by remember { mutableStateOf<Taslak?>(null) }
    var yenile by remember { mutableStateOf(0) }

    Box(Modifier.fillMaxSize()) {
        Column {
            PrimaryTabRow(selectedTabIndex = kutu, containerColor = MaterialTheme.colorScheme.background) {
                Tab(kutu == 0, { kutu = 0 }, text = { Text("Gelen") })
                Tab(kutu == 1, { kutu = 1 }, text = { Text("Gönderilen") })
            }
            Yukle(anahtar = "mesajlar$yenile", yukle = { obs.mesajlar(it || yenile > 0) }) { k ->
                val liste = if (kutu == 0) k.gelen else k.giden
                if (liste.isEmpty()) item { BosDurum("Mesaj yok", if (kutu == 0) "Gelen kutun boş." else "Henüz mesaj göndermedin.") }
                items(liste, key = { it.id }) { m ->
                    Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceContainer, onClick = { acik = m }, modifier = Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
                            Avatar(m.kimden, null, 44.dp)
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        guzelAd(m.kimden), Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                                        fontWeight = if (!m.okundu && kutu == 0) FontWeight.Black else FontWeight.SemiBold,
                                    )
                                    Text(m.tarih.take(10), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Text(m.baslik, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
                                Text(m.onizleme, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (!m.okundu && kutu == 0) {
                                Spacer(Modifier.width(6.dp))
                                Box(Modifier.padding(top = 6.dp).size(10.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primary))
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(72.dp)) }
            }
        }
        ExtendedFloatingActionButton(
            onClick = { taslak = Taslak(null) },
            icon = { Icon(Icons.Outlined.Edit, null) }, text = { Text("Yeni mesaj") },
            modifier = Modifier.align(Alignment.BottomEnd).padding(20.dp).navigationBarsPadding(),
        )
    }

    acik?.let { m ->
        ModalBottomSheet(onDismissRequest = { acik = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            MesajOku(m, gelen = kutu == 0) {
                acik = null
                taslak = Taslak(Alici(m.kimden, "", m.kullaniciTuru, m.kullaniciId), "Ynt: " + m.baslik.removePrefix("Ynt: "), m.id)
            }
        }
    }
    taslak?.let { t ->
        MesajYaz(t, kapat = { gonderildi -> taslak = null; if (gonderildi) yenile++ })
    }
}

@Composable
private fun MesajOku(m: Mesaj, gelen: Boolean, yanitla: () -> Unit) {
    val obs = Obs.al(LocalContext.current)
    var icerik by remember { mutableStateOf<String?>(null) }
    var hata by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(m.id) { runCatching { obs.mesajIcerigi(m.id) }.onSuccess { icerik = it }.onFailure { hata = it.message } }
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 24.dp).navigationBarsPadding()) {
        Text(m.baslik, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(m.kimden, null, 36.dp)
            Spacer(Modifier.width(10.dp))
            Column {
                Text(guzelAd(m.kimden), fontWeight = FontWeight.SemiBold)
                Text(m.tarih, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        HorizontalDivider(Modifier.padding(vertical = 14.dp))
        when {
            icerik != null -> SelectionContainer {
                Text(icerik!!, style = MaterialTheme.typography.bodyLarge)
            }
            hata != null -> Text(hata!!, color = MaterialTheme.colorScheme.error)
            else -> CircularProgressIndicator()
        }
        if (gelen && m.yanitlanabilir) {
            Spacer(Modifier.height(18.dp))
            FilledTonalButton(onClick = yanitla) {
                Icon(Icons.AutoMirrored.Outlined.Reply, null)
                Spacer(Modifier.width(8.dp))
                Text("Yanıtla")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MesajYaz(t: Taslak, kapat: (gonderildi: Boolean) -> Unit) {
    val ctx = LocalContext.current
    val obs = Obs.al(ctx)
    val kapsam = rememberCoroutineScope()
    var alici by remember { mutableStateOf(t.alici) }
    var arama by remember { mutableStateOf("") }
    var sonuclar by remember { mutableStateOf<List<Alici>>(emptyList()) }
    var baslik by remember { mutableStateOf(t.baslik) }
    var icerik by remember { mutableStateOf("") }
    var gonderiliyor by remember { mutableStateOf(false) }
    var hata by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(arama) {
        if (arama.length < 2) { sonuclar = emptyList(); return@LaunchedEffect }
        delay(350)
        sonuclar = runCatching { obs.aliciAra(arama) }.getOrDefault(emptyList())
    }

    ModalBottomSheet(onDismissRequest = { kapat(false) }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 24.dp).imePadding().navigationBarsPadding()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(if (t.yanitId != null) "Yanıtla" else "Yeni mesaj", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            val a = alici
            if (a != null) {
                Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.secondaryContainer) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Avatar(a.ad, null, 32.dp)
                        Spacer(Modifier.width(10.dp))
                        Text(guzelAd(a.ad), Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                        if (t.yanitId == null) TextButton(onClick = { alici = null }) { Text("Değiştir") }
                    }
                }
            } else {
                OutlinedTextField(arama, { arama = it }, label = { Text("Öğretmen ara") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                sonuclar.take(6).forEach { s ->
                    Surface(onClick = { alici = s; arama = "" }, shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.surfaceContainerLow) {
                        ListItem(
                            headlineContent = { Text(guzelAd(s.ad)) }, supportingContent = { Text(s.tur) },
                            leadingContent = { Avatar(s.ad, null, 36.dp) },
                            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
                        )
                    }
                }
            }
            OutlinedTextField(baslik, { baslik = it.take(100) }, label = { Text("Konu") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(icerik, { icerik = it.take(5000) }, label = { Text("Mesajın") }, minLines = 5, modifier = Modifier.fillMaxWidth())
            if (hata != null) Text(hata!!, color = MaterialTheme.colorScheme.error)
            Button(
                enabled = !gonderiliyor && alici != null && baslik.trim().length >= 5 && icerik.trim().length >= 10,
                onClick = {
                    val hedef = alici ?: return@Button
                    gonderiliyor = true
                    kapsam.launch {
                        val sonuc = obs.mesajGonder(baslik.trim(), icerik.trim(), hedef.kullaniciTuru, hedef.kullaniciId, t.yanitId)
                        gonderiliyor = false
                        if (sonuc == null) {
                            Toast.makeText(ctx, "Mesaj gönderildi", Toast.LENGTH_SHORT).show()
                            kapat(true)
                        } else hata = sonuc
                    }
                },
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (gonderiliyor) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                else {
                    Icon(Icons.AutoMirrored.Outlined.Send, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Gönder")
                }
            }
            Text("Konu en az 5, mesaj en az 10 karakter olmalı.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ================= Yemek listesi =================

private suspend fun pdfSayfalari(ctx: android.content.Context, pdf: ByteArray): List<ImageBitmap> = withContext(Dispatchers.IO) {
    val dosya = File(ctx.cacheDir, "yemek.pdf").apply { writeBytes(pdf) }
    ParcelFileDescriptor.open(dosya, ParcelFileDescriptor.MODE_READ_ONLY).use { fd ->
        PdfRenderer(fd).use { r ->
            (0 until r.pageCount).map { i ->
                r.openPage(i).use { s ->
                    val genislik = 1600
                    val bmp = Bitmap.createBitmap(genislik, (genislik.toFloat() * s.height / s.width).toInt(), Bitmap.Config.ARGB_8888)
                    bmp.eraseColor(AColor.WHITE)
                    s.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    bmp.asImageBitmap()
                }
            }
        }
    }
}

@Composable
fun YemekEkrani() {
    val ctx = LocalContext.current
    val obs = Obs.al(ctx)
    var buyuk by remember { mutableStateOf<ImageBitmap?>(null) }
    Yukle(anahtar = "yemek", yukle = { pdfSayfalari(ctx, obs.yemekPdf(it)) }) { sayfalar ->
        item {
            Text(
                "Okulunun yüklediği yemek listesi. Yakınlaştırmak için sayfaya dokun.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        items(sayfalar) { s ->
            Surface(shape = RoundedCornerShape(16.dp), onClick = { buyuk = s }, modifier = Modifier.fillMaxWidth()) {
                Image(s, "Yemek listesi sayfası", Modifier.fillMaxWidth(), contentScale = ContentScale.FillWidth)
            }
        }
    }
    buyuk?.let { YakinlastirilabilirResim(it) { buyuk = null } }
}

@Composable
private fun YakinlastirilabilirResim(resim: ImageBitmap, kapat: () -> Unit) {
    var olcek by remember { mutableFloatStateOf(1f) }
    var kayma by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
    val durum = rememberTransformableState { z, k, _ ->
        olcek = (olcek * z).coerceIn(1f, 6f)
        kayma += k
    }
    Dialog(onDismissRequest = kapat, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize().background(Color.Black).transformable(durum), contentAlignment = Alignment.Center) {
            Image(
                resim, null,
                Modifier.fillMaxWidth().graphicsLayer(scaleX = olcek, scaleY = olcek, translationX = kayma.x, translationY = kayma.y),
                contentScale = ContentScale.FillWidth,
            )
            TextButton(onClick = kapat, modifier = Modifier.align(Alignment.TopEnd).padding(16.dp)) { Text("Kapat", color = Color.White) }
        }
    }
}

// ================= Devamsızlık =================

@Composable
fun DevamsizlikEkrani() {
    val obs = Obs.al(LocalContext.current)
    Yukle(anahtar = "devamsizlik", yukle = { obs.devamsizlik(it) }) { d ->
        val toplam = d.ozet.sumOf { it.second }
        val gelmedi = d.ozet.filter { it.first != "Geldi" }.sumOf { it.second }
        item {
            Kart(renk = if (d.kayitlar.isEmpty()) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainer) {
                Text(d.donem.ifBlank { "Bu dönem" }, style = MaterialTheme.typography.labelLarge)
                Text(
                    if (d.kayitlar.isEmpty()) "Devamsızlığın yok" else "${d.kayitlar.size} ders saati devamsızlık",
                    style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
                )
                if (toplam > 0) {
                    Text(
                        "Yoklama alınan $toplam ders saatinin %%%.1f'inde derstesin.".format((toplam - gelmedi) * 100.0 / toplam),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Spacer(Modifier.height(12.dp))
                    Row(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(50))) {
                        d.ozet.filter { it.second > 0 }.forEach { (ad, n) ->
                            Box(Modifier.weight(n.toFloat()).height(10.dp).background(devamRengi(ad)))
                        }
                    }
                    Spacer(Modifier.height(10.dp))
                    d.ozet.filter { it.second > 0 }.forEach { (ad, n) ->
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 2.dp)) {
                            Box(Modifier.size(10.dp).clip(CircleShape).background(devamRengi(ad)))
                            Spacer(Modifier.width(8.dp))
                            Text(ad, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                            Text("$n", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
        if (d.kayitlar.isNotEmpty()) item { BolumBasligi("Yoklama kayıtları") }
        items(d.kayitlar) { k ->
            Kart {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("${guzelAd(k.ders)} • ${k.saat}. ders", fontWeight = FontWeight.SemiBold)
                        Text(
                            listOf(k.tarih, guzelAd(k.ogretmen), k.not).filter { it.isNotBlank() && it != "-" }.joinToString(" • "),
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (k.tur.isNotBlank()) Rozet(k.tur)
                }
            }
        }
    }
}

private fun devamRengi(ad: String) = when {
    ad == "Geldi" -> Color(0xFF4CAF50)
    ad.contains("Özürsüz") -> Color(0xFFF44336)
    ad.contains("Özürlü") -> Color(0xFFFF9800)
    ad.contains("Faaliyet") -> Color(0xFF03A9F4)
    else -> Color(0xFF9E9E9E)
}

// ================= Öğretmenler =================

@Composable
fun OgretmenlerEkrani() {
    val obs = Obs.al(LocalContext.current)
    var taslak by remember { mutableStateOf<Taslak?>(null) }
    var araniyor by remember { mutableStateOf(false) }
    val kapsam = rememberCoroutineScope()
    val ctx = LocalContext.current
    Yukle(anahtar = "ogretmenler", yukle = { obs.ogretmenler(it) }) { liste ->
        if (liste.isEmpty()) item { BosDurum("Öğretmen bulunamadı", "Derslerine giren öğretmenler burada listelenir.") }
        items(liste) { o ->
            Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceContainer, modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Avatar(o.ad, null, 46.dp)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(guzelAd(o.ad), fontWeight = FontWeight.SemiBold)
                        Text(guzelAd(o.ders), style = MaterialTheme.typography.bodySmall, color = dersRengi(o.ders))
                    }
                    TextButton(enabled = !araniyor, onClick = {
                        araniyor = true
                        kapsam.launch {
                            val bulunan = runCatching { obs.aliciAra(o.ad) }.getOrDefault(emptyList()).firstOrNull()
                            araniyor = false
                            if (bulunan != null) taslak = Taslak(bulunan)
                            else Toast.makeText(ctx, "Bu öğretmene mesaj gönderilemiyor.", Toast.LENGTH_SHORT).show()
                        }
                    }) { Text("Mesaj") }
                }
            }
        }
    }
    taslak?.let { t -> MesajYaz(t) { taslak = null } }
}

// ================= Duyurular =================

@Composable
fun DuyurularEkrani() {
    val obs = Obs.al(LocalContext.current)
    Yukle(anahtar = "duyurular", yukle = { obs.anaVeri(it) }) { a ->
        item { BolumBasligi("Okul duyuruları", "${a.duyurular.size} duyuru") }
        if (a.duyurular.isEmpty()) item { BosDurum("Duyuru yok", "Okul yönetimi henüz duyuru yayınlamamış.") }
        items(a.duyurular) { d -> Kart { SelectionContainer { Text(d) } } }
        item { BolumBasligi("Etkinlikler", "${a.etkinlikler.size} etkinlik") }
        if (a.etkinlikler.isEmpty()) item { BosDurum("Etkinlik yok", "Planlanan etkinlikler burada görünür.") }
        items(a.etkinlikler) { e -> Kart { Text(e) } }
    }
}

// ================= Profil =================

@Composable
fun ProfilEkrani(cikis: () -> Unit) {
    val obs = Obs.al(LocalContext.current)
    var sor by remember { mutableStateOf(false) }
    Yukle(anahtar = "profil", yukle = { obs.profil(it) }) { p ->
        item {
            Column(Modifier.fillMaxWidth().padding(vertical = 16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Avatar(p.ad, p.foto, 108.dp)
                Spacer(Modifier.height(12.dp))
                Text(guzelAd(p.ad), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(listOf(p.rol, p.sinif, p.okul).filter { it.isNotBlank() }.joinToString(" • "), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item {
            Kart {
                p.alanlar.distinctBy { it.first }.forEach { (k, v) -> BilgiSatiri(k, v) }
                if (p.alanlar.isEmpty()) {
                    BilgiSatiri("Numara", p.numara)
                    BilgiSatiri("Sınıf", p.sinif)
                }
            }
        }
        item {
            FilledTonalButton(onClick = { sor = true }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.AutoMirrored.Outlined.Logout, null)
                Spacer(Modifier.width(8.dp))
                Text("Çıkış yap")
            }
        }
    }
    if (sor) CikisSorusu({ sor = false }, cikis)
}

@Composable
private fun CikisSorusu(vazgec: () -> Unit, cikis: () -> Unit) {
    AlertDialog(
        onDismissRequest = vazgec,
        title = { Text("Çıkış yapılsın mı?") },
        text = { Text("Kayıtlı giriş bilgilerin bu telefondan silinir ve bildirimler durur.") },
        confirmButton = { TextButton(onClick = { vazgec(); cikis() }) { Text("Çıkış yap") } },
        dismissButton = { TextButton(onClick = vazgec) { Text("Vazgeç") } },
    )
}

// ================= Daha =================

@Composable
fun DahaEkrani(ac: (Sayfa) -> Unit, cikis: () -> Unit) {
    val ctx = LocalContext.current
    val obs = Obs.al(ctx)
    var bildirim by remember { mutableStateOf(obs.bildirimlerAcik) }
    var sor by remember { mutableStateOf(false) }
    var hakkinda by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Grup {
            Satir(Icons.Outlined.Person, "Profil", "Öğrenci ve veli bilgileri") { ac(Sayfa.PROFIL) }
            Satir(Icons.Outlined.Mail, "Mesajlar", "Öğretmenlerinle yazış") { ac(Sayfa.MESAJLAR) }
            Satir(Icons.Outlined.Restaurant, "Yemek listesi", "Bu ayın menüsü") { ac(Sayfa.YEMEK) }
            Satir(Icons.Outlined.EventBusy, "Devamsızlık", "Yoklama kayıtların") { ac(Sayfa.DEVAMSIZLIK) }
            Satir(Icons.Outlined.Groups, "Öğretmenlerim", "Derslerine girenler") { ac(Sayfa.OGRETMENLER) }
            Satir(Icons.Outlined.Campaign, "Duyuru ve etkinlikler", "Okuldan haberler") { ac(Sayfa.DUYURULAR) }
        }
        Grup {
            ListItem(
                headlineContent = { Text("Bildirimler") },
                supportingContent = { Text("Yeni ödev, sınav ve mesajlarda haber ver") },
                leadingContent = { Icon(Icons.Outlined.Notifications, null) },
                trailingContent = {
                    Switch(bildirim, { acik ->
                        bildirim = acik
                        obs.bildirimlerAcik = acik
                        if (acik) BildirimIscisi.planla(ctx) else BildirimIscisi.iptal(ctx)
                    })
                },
                colors = ListItemDefaults.colors(containerColor = Color.Transparent),
            )
            Satir(Icons.Outlined.Info, "LimeOBS hakkında", "Sürüm ve yasal bilgi") { hakkinda = true }
            Satir(Icons.AutoMirrored.Outlined.Logout, "Çıkış yap", null) { sor = true }
        }
    }
    if (sor) CikisSorusu({ sor = false }, cikis)
    if (hakkinda) {
        val surum = runCatching { ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName }.getOrNull() ?: ""
        AlertDialog(
            onDismissRequest = { hakkinda = false },
            title = { Text("LimeOBS $surum") },
            text = {
                Text(
                    "Akbim OBS kullanan okullar için bağımsız ve açık kaynaklı istemci. " +
                        "Akbim, okul yönetimleri veya ilgili kurumlarla resmî bir bağı yoktur. " +
                        "Verilerin yalnızca okulunun OBS sunucusuyla paylaşılır.\n\ngithub.com/kefy266/LimeOBS"
                )
            },
            confirmButton = { TextButton(onClick = { hakkinda = false }) { Text("Tamam") } },
        )
    }
}

@Composable
private fun Grup(icerik: @Composable () -> Unit) {
    Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surfaceContainer, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(vertical = 6.dp)) { icerik() }
    }
}

@Composable
private fun Satir(ikon: androidx.compose.ui.graphics.vector.ImageVector, baslik: String, alt: String?, tikla: () -> Unit) {
    Surface(onClick = tikla, color = Color.Transparent) {
        ListItem(
            headlineContent = { Text(baslik) },
            supportingContent = if (alt != null) { { Text(alt) } } else null,
            leadingContent = { Icon(ikon, null) },
            trailingContent = { Icon(Icons.Outlined.ChevronRight, null) },
            colors = ListItemDefaults.colors(containerColor = Color.Transparent),
        )
    }
}
