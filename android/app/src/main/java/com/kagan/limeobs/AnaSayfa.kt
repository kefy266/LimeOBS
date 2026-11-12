package com.kagan.limeobs

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Campaign
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.EventBusy
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.Restaurant
import androidx.compose.material.icons.outlined.Groups
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

private val TR = Locale("tr")
val GUN_ADLARI = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

/** Okul günü 16:30'da biter; sonrasında ve hafta sonu bir sonraki okul günü gösterilir. */
fun etkinOkulGunu(simdi: LocalDateTime = LocalDateTime.now()): LocalDate {
    val bitti = simdi.toLocalTime() >= LocalTime.of(16, 30)
    val g = simdi.toLocalDate()
    return when (simdi.dayOfWeek.value) {
        in 1..4 -> if (bitti) g.plusDays(1) else g
        5 -> if (bitti) g.plusDays(3) else g
        6 -> g.plusDays(2)
        else -> g.plusDays(1)
    }
}

fun saatAraligi(metin: String): Pair<LocalTime, LocalTime>? {
    val p = Regex("(\\d{1,2}):(\\d{2})").findAll(metin).map { LocalTime.of(it.groupValues[1].toInt(), it.groupValues[2].toInt()) }.toList()
    return if (p.size >= 2) p[0] to p[1] else null
}

fun tarihCoz(t: String): LocalDate? = runCatching {
    val p = t.trim().split(' ')[0]
    when {
        p.contains('.') -> LocalDate.parse(p, DateTimeFormatter.ofPattern("dd.MM.yyyy"))
        else -> LocalDate.parse(p)
    }
}.getOrNull()

fun kalanGun(t: String): Long? = tarihCoz(t)?.let { ChronoUnit.DAYS.between(LocalDate.now(), it) }

fun kalanMetni(gun: Long): String = when {
    gun < 0 -> "${-gun} gün geçti"
    gun == 0L -> "Bugün"
    gun == 1L -> "Yarın"
    else -> "$gun gün"
}

private data class Bugun(val ana: AnaVeri, val profil: Profil, val odevler: List<Odev>)

@Composable
fun AnaSayfa(ac: (Sayfa) -> Unit, sekmeyeGit: (Sekme) -> Unit) {
    val obs = Obs.al(LocalContext.current)
    var simdi by remember { mutableStateOf(LocalDateTime.now()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(20_000)
            simdi = LocalDateTime.now()
        }
    }
    Yukle(
        anahtar = "ana",
        yukle = { zorla ->
            coroutineScope {
                val a = async { obs.anaVeri(zorla) }
                val p = async { obs.profil(zorla) }
                val o = async { runCatching { obs.odevler(zorla) }.getOrDefault(emptyList()) }
                Bugun(a.await(), p.await(), o.await())
            }
        },
    ) { b ->
        item { Selamlama(b.profil, simdi) }
        item { SimdiKarti(b.ana.program, simdi) { sekmeyeGit(Sekme.PROGRAM) } }
        item { Kisayollar(ac) }
        val aktif = b.odevler.filter { it.aktif && it.durumKod == 0 }.sortedBy { Obs.tarihSayi(it.bitis) }
        item {
            Kart(Modifier.clickable { sekmeyeGit(Sekme.ODEV) }) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Aktif ödevler", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            if (aktif.isEmpty()) "Teslim bekleyen ödevin yok" else "${aktif.size} ödev teslim bekliyor",
                            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    Text("${aktif.size}", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Black, color = MaterialTheme.colorScheme.primary)
                }
                aktif.take(3).forEach { o ->
                    Spacer(Modifier.height(10.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(10.dp).clip(CircleShape).background(dersRengi(o.ders)))
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(o.baslik, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
                            Text(guzelAd(o.ders), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        kalanGun(o.bitis)?.let { g ->
                            Rozet(
                                kalanMetni(g),
                                renk = if (g <= 1) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
                                yazi = if (g <= 1) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
                            )
                        }
                    }
                }
            }
        }
        val yaklasan = b.ana.sinavlar.mapNotNull { s -> kalanGun(s.tarih)?.takeIf { it >= 0 }?.let { s to it } }.sortedBy { it.second }
        if (yaklasan.isNotEmpty()) {
            item {
                Kart {
                    Text("Yaklaşan sınavlar", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    yaklasan.take(4).forEach { (s, g) ->
                        Spacer(Modifier.height(10.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(s.ad, fontWeight = FontWeight.Medium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Text(s.tarih, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Rozet(kalanMetni(g), renk = MaterialTheme.colorScheme.tertiaryContainer, yazi = MaterialTheme.colorScheme.onTertiaryContainer)
                        }
                    }
                }
            }
        }
        if (b.ana.duyurular.isNotEmpty()) {
            item {
                Kart(Modifier.clickable { ac(Sayfa.DUYURULAR) }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Campaign, null, tint = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(10.dp))
                        Text("Duyurular", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Icon(Icons.Outlined.ChevronRight, null)
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(b.ana.duyurular.first(), maxLines = 3, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun Selamlama(p: Profil, simdi: LocalDateTime) {
    val saat = simdi.hour
    val selam = when (saat) {
        in 5..11 -> "Günaydın"
        in 12..17 -> "İyi günler"
        else -> "İyi akşamlar"
    }
    val ilkAd = guzelAd(p.ad).split(' ').firstOrNull().orEmpty()
    Surface(shape = RoundedCornerShape(28.dp), color = Color.Transparent, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
        Box(
            Modifier
                .background(Brush.linearGradient(listOf(Color(0xFF8BD450), Color(0xFF2E8B3E), Color(0xFF1C5E3A))))
                .padding(20.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Avatar(p.ad, p.foto, 64.dp)
                Spacer(Modifier.width(16.dp))
                Column(Modifier.weight(1f)) {
                    Text("$selam,", color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.bodyLarge)
                    Text(ilkAd, color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    val ust = listOf(p.sinif, p.okul).filter { it.isNotBlank() }.joinToString(" • ")
                    Text(
                        simdi.format(DateTimeFormatter.ofPattern("d MMMM EEEE", TR)) + if (ust.isNotBlank()) "\n$ust" else "",
                        color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun SimdiKarti(program: DersProgrami, simdi: LocalDateTime, git: () -> Unit) {
    val okulGunu = etkinOkulGunu(simdi)
    val gunNo = okulGunu.dayOfWeek.value
    val bugunMu = okulGunu == simdi.toLocalDate()
    val dersler = program.hucreler.filter { it.gun == gunNo }.sortedBy { it.saat }
    val saat = simdi.toLocalTime()

    var baslik = ""
    var ana = ""
    var alt = ""
    var ilerleme: Float? = null
    var renk = MaterialTheme.colorScheme.primary

    val araliklar = dersler.associateWith { saatAraligi(program.saatler.getOrNull(it.saat - 1).orEmpty()) }
    val suanki = if (bugunMu) dersler.firstOrNull { d -> araliklar[d]?.let { saat >= it.first && saat < it.second } == true } else null
    val sonraki = if (bugunMu) dersler.firstOrNull { d -> araliklar[d]?.let { saat < it.first } == true } else dersler.firstOrNull()

    when {
        dersler.isEmpty() -> {
            baslik = "Ders programı"; ana = "Bugün için ders bulunamadı"; alt = "Programın tamamını görmek için dokun"
        }
        suanki != null -> {
            val (b, s) = araliklar[suanki]!!
            val kalan = ChronoUnit.MINUTES.between(saat, s)
            baslik = "Şu an derstesin"; ana = guzelAd(suanki.ders); renk = Color(suanki.renk)
            alt = "Bitmesine $kalan dk" + (sonraki?.let { " • Sonra: ${guzelAd(it.ders)}" } ?: " • Günün son dersi")
            ilerleme = (ChronoUnit.SECONDS.between(b, saat).toFloat() / ChronoUnit.SECONDS.between(b, s).coerceAtLeast(1)).coerceIn(0f, 1f)
        }
        sonraki != null && bugunMu -> {
            val b = araliklar[sonraki]!!.first
            val dk = ChronoUnit.MINUTES.between(saat, b)
            baslik = if (dk <= 15) "Teneffüs" else "Sıradaki ders"
            ana = guzelAd(sonraki.ders); renk = Color(sonraki.renk)
            alt = "${if (dk >= 60) "${dk / 60} sa ${dk % 60} dk" else "$dk dk"} sonra • ${guzelAd(sonraki.ogretmen)}"
        }
        else -> {
            val gunAdi = GUN_ADLARI[gunNo - 1]
            baslik = if (ChronoUnit.DAYS.between(simdi.toLocalDate(), okulGunu) == 1L) "Yarın ($gunAdi)" else gunAdi
            ana = "${dersler.size} ders seni bekliyor"
            alt = "İlk ders " + guzelAd(dersler.first().ders) + " • " + (program.saatler.getOrNull(dersler.first().saat - 1)?.substringBefore(" -") ?: "")
        }
    }

    Kart(Modifier.clickable(onClick = git)) {
        Text(baslik, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(14.dp).clip(CircleShape).background(renk))
            Spacer(Modifier.width(10.dp))
            Text(ana, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        }
        Text(alt, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        ilerleme?.let {
            Spacer(Modifier.height(12.dp))
            LinearProgressIndicator(
                progress = { it }, modifier = Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(50)),
                color = renk, trackColor = renk.copy(alpha = 0.18f), strokeCap = StrokeCap.Round,
            )
        }
        if (dersler.isNotEmpty()) {
            Spacer(Modifier.height(14.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.fillMaxWidth()) {
                dersler.forEach { d ->
                    val gecti = bugunMu && araliklar[d]?.let { saat >= it.second } == true
                    Box(
                        Modifier.weight(1f).height(6.dp).clip(RoundedCornerShape(50))
                            .background(Color(d.renk).copy(alpha = if (gecti) 0.25f else 1f))
                    )
                }
            }
        }
    }
}

@Composable
private fun Kisayollar(ac: (Sayfa) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
        Kisayol(Icons.Outlined.Mail, "Mesajlar", Modifier.weight(1f)) { ac(Sayfa.MESAJLAR) }
        Kisayol(Icons.Outlined.Restaurant, "Yemek", Modifier.weight(1f)) { ac(Sayfa.YEMEK) }
        Kisayol(Icons.Outlined.EventBusy, "Devamsızlık", Modifier.weight(1f)) { ac(Sayfa.DEVAMSIZLIK) }
        Kisayol(Icons.Outlined.Groups, "Öğretmenler", Modifier.weight(1f)) { ac(Sayfa.OGRETMENLER) }
    }
}

@Composable
private fun Kisayol(ikon: ImageVector, ad: String, modifier: Modifier, tikla: () -> Unit) {
    Surface(modifier = modifier, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceContainer, onClick = tikla) {
        Column(Modifier.padding(vertical = 14.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(40.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
                Icon(ikon, null, tint = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            Spacer(Modifier.height(6.dp))
            Text(ad, style = MaterialTheme.typography.labelMedium, maxLines = 1)
        }
    }
}
