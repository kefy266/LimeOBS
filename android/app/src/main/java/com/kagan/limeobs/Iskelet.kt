package com.kagan.limeobs

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.Apps
import androidx.compose.material.icons.outlined.Apps
import androidx.compose.material.icons.outlined.Assignment
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Insights
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.collectAsState
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.background
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight

enum class Sekme(val ad: String, val dolu: ImageVector, val bos: ImageVector) {
    ANA("Bugün", Icons.Filled.Home, Icons.Outlined.Home),
    PROGRAM("Program", Icons.Filled.CalendarMonth, Icons.Outlined.CalendarMonth),
    ODEV("Ödevler", Icons.Filled.Assignment, Icons.Outlined.Assignment),
    SINAV("Sınavlar", Icons.Filled.Insights, Icons.Outlined.Insights),
    DAHA("Daha", Icons.Filled.Apps, Icons.Outlined.Apps),
}

/** "Daha" menüsünden ve kısayollardan açılan alt sayfalar */
enum class Sayfa(val baslik: String) {
    ASISTAN("Asistan"),
    MESAJLAR("Mesajlar"),
    YEMEK("Yemek listesi"),
    DEVAMSIZLIK("Devamsızlık"),
    OGRETMENLER("Öğretmenlerim"),
    PROFIL("Profil"),
    DUYURULAR("Duyuru ve etkinlikler"),
}

/** Tablet ve geniş ekranlarda içeriği ortada okunabilir genişlikte tutar. */
@Composable
fun Ortali(modifier: Modifier = Modifier, maks: androidx.compose.ui.unit.Dp = 840.dp, icerik: @Composable BoxScope.() -> Unit) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Box(Modifier.widthIn(max = maks).fillMaxSize(), content = icerik)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnaIskelet(cikis: () -> Unit) {
    var sekme by rememberSaveable { mutableStateOf(Sekme.ANA) }
    val yigin = remember { mutableStateListOf<Sayfa>() }
    val ac: (Sayfa) -> Unit = { yigin.add(it) }

    BackHandler(enabled = yigin.isNotEmpty() || sekme != Sekme.ANA) {
        if (yigin.isNotEmpty()) yigin.removeAt(yigin.lastIndex) else sekme = Sekme.ANA
    }

    // 600 dp ve üstü (tablet, yatay telefon): alt çubuk yerine yan menü
    val genis = LocalConfiguration.current.screenWidthDp >= 600

    CompositionLocalProvider(LocalOturumDustu provides cikis) {
      Box(Modifier.fillMaxSize()) {
        val ustteki = yigin.lastOrNull()
        AnimatedContent(ustteki, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "sayfa") { sayfa ->
            if (sayfa != null) {
                Scaffold(
                    topBar = {
                        TopAppBar(
                            title = { Text(sayfa.baslik, fontWeight = FontWeight.Bold) },
                            navigationIcon = {
                                IconButton(onClick = { yigin.removeAt(yigin.lastIndex) }) {
                                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Geri")
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                        )
                    },
                ) { ic ->
                    Ortali(Modifier.padding(ic), if (sayfa == Sayfa.MESAJLAR) 1200.dp else 840.dp) {
                        when (sayfa) {
                            Sayfa.MESAJLAR -> MesajlarEkrani()
                            Sayfa.YEMEK -> YemekEkrani()
                            Sayfa.DEVAMSIZLIK -> DevamsizlikEkrani()
                            Sayfa.OGRETMENLER -> OgretmenlerEkrani()
                            Sayfa.PROFIL -> ProfilEkrani(cikis)
                            Sayfa.ASISTAN -> AsistanEkrani()
                            Sayfa.DUYURULAR -> DuyurularEkrani()
                        }
                    }
                }
            } else {
                // Geniş ekranda yan menü Scaffold'un dışında: başlık ve içerik aynı eksende ortalanır
                Row(Modifier.fillMaxSize()) {
                    if (genis) {
                        NavigationRail(Modifier.fillMaxHeight()) {
                            Box(Modifier.weight(1f))
                            Sekme.entries.forEach { s ->
                                NavigationRailItem(
                                    selected = sekme == s,
                                    onClick = { sekme = s },
                                    icon = { Icon(if (sekme == s) s.dolu else s.bos, null) },
                                    label = { Text(s.ad) },
                                    modifier = Modifier.padding(vertical = 4.dp),
                                )
                            }
                            Box(Modifier.weight(1f))
                        }
                    }
                    // Ana sayfa (iki sütun) ve program (haftalık tablo) tablette daha geniş kullanılır
                    val maks = if (sekme == Sekme.ANA || sekme == Sekme.PROGRAM) 1200.dp else 840.dp
                    Scaffold(
                        modifier = Modifier.weight(1f),
                        topBar = { if (sekme != Sekme.ANA) SayfaBasligi(sekme.ad, maks) },
                        bottomBar = {
                            if (!genis) NavigationBar {
                                Sekme.entries.forEach { s ->
                                    NavigationBarItem(
                                        selected = sekme == s,
                                        onClick = { sekme = s },
                                        icon = { Icon(if (sekme == s) s.dolu else s.bos, null) },
                                        label = { Text(s.ad) },
                                    )
                                }
                            }
                        },
                    ) { ic ->
                        Ortali(Modifier.padding(ic), maks) {
                            when (sekme) {
                                Sekme.ANA -> AnaSayfa(ac = ac, sekmeyeGit = { sekme = it })
                                Sekme.PROGRAM -> ProgramEkrani()
                                Sekme.ODEV -> OdevlerEkrani()
                                Sekme.SINAV -> SinavlarEkrani()
                                Sekme.DAHA -> DahaEkrani(ac = ac, cikis = cikis)
                            }
                        }
                    }
                }
            }
        }
        CevrimdisiBandi(
            Modifier.align(Alignment.BottomCenter).navigationBarsPadding()
                .padding(bottom = if (genis || ustteki != null) 16.dp else 92.dp)
        )
      }
    }
}

/** Sekme başlığı: içerikle aynı genişlikte ve hizada. */
@Composable
private fun SayfaBasligi(ad: String, maks: androidx.compose.ui.unit.Dp) {
    Box(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).statusBarsPadding(),
        contentAlignment = Alignment.TopCenter,
    ) {
        Text(
            ad, Modifier.widthIn(max = maks).fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp),
            style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
        )
    }
}

/** İnternet yokken telefonda saklanan son verilerin gösterildiğini belirtir. */
@Composable
private fun CevrimdisiBandi(modifier: Modifier) {
    val obs = Obs.al(androidx.compose.ui.platform.LocalContext.current)
    val zaman by obs.cevrimdisi.collectAsState()
    androidx.compose.animation.AnimatedVisibility(zaman != null, modifier) {
        val metin = zaman?.let {
            val t = java.time.Instant.ofEpochMilli(it).atZone(java.time.ZoneId.systemDefault())
            val bugun = t.toLocalDate() == java.time.LocalDate.now()
            "Çevrimdışı · son veriler " + t.format(java.time.format.DateTimeFormatter.ofPattern(if (bugun) "HH:mm" else "d MMM HH:mm", java.util.Locale("tr")))
        }.orEmpty()
        androidx.compose.material3.Surface(
            shape = androidx.compose.foundation.shape.RoundedCornerShape(50),
            color = MaterialTheme.colorScheme.inverseSurface,
            contentColor = MaterialTheme.colorScheme.inverseOnSurface,
            shadowElevation = 4.dp,
        ) {
            Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(androidx.compose.material.icons.Icons.Outlined.CloudOff, null, Modifier.padding(end = 8.dp))
                Text(metin, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}
