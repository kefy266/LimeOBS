package com.kagan.limeobs

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Box
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
    MESAJLAR("Mesajlar"),
    YEMEK("Yemek listesi"),
    DEVAMSIZLIK("Devamsızlık"),
    OGRETMENLER("Öğretmenlerim"),
    PROFIL("Profil"),
    DUYURULAR("Duyuru ve etkinlikler"),
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

    CompositionLocalProvider(LocalOturumDustu provides cikis) {
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
                    Box(Modifier.fillMaxSize().padding(ic)) {
                        when (sayfa) {
                            Sayfa.MESAJLAR -> MesajlarEkrani()
                            Sayfa.YEMEK -> YemekEkrani()
                            Sayfa.DEVAMSIZLIK -> DevamsizlikEkrani()
                            Sayfa.OGRETMENLER -> OgretmenlerEkrani()
                            Sayfa.PROFIL -> ProfilEkrani(cikis)
                            Sayfa.DUYURULAR -> DuyurularEkrani()
                        }
                    }
                }
            } else {
                Scaffold(
                    topBar = {
                        if (sekme != Sekme.ANA) {
                            TopAppBar(
                                title = { Text(sekme.ad, fontWeight = FontWeight.Bold) },
                                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                            )
                        }
                    },
                    bottomBar = {
                        NavigationBar {
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
                    Box(Modifier.fillMaxSize().padding(ic)) {
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
}
