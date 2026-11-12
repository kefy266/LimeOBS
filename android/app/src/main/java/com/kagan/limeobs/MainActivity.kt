package com.kagan.limeobs

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Badge
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        BildirimIscisi.kanalOlustur(this)
        val obs = Obs.al(this)
        setContent {
            LimeTema {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    var girisli by remember { mutableStateOf(obs.kayitliGirisVar) }
                    val izin = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
                    LaunchedEffect(girisli) {
                        if (girisli) {
                            if (Build.VERSION.SDK_INT >= 33) izin.launch(Manifest.permission.POST_NOTIFICATIONS)
                            if (obs.bildirimlerAcik) BildirimIscisi.planla(this@MainActivity)
                        }
                    }
                    AnimatedContent(girisli, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "giris") { acik ->
                        if (acik) {
                            AnaIskelet(cikis = {
                                obs.cikisYap()
                                BildirimIscisi.iptal(this@MainActivity)
                                girisli = false
                            })
                        } else {
                            GirisEkrani { girisli = true }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GirisEkrani(basarili: () -> Unit) {
    val obs = Obs.al(LocalContext.current)
    val kapsam = rememberCoroutineScope()
    var adres by remember { mutableStateOf(obs.adres.removePrefix("https://")) }
    var tc by remember { mutableStateOf("") }
    var sifre by remember { mutableStateOf("") }
    var goster by remember { mutableStateOf(false) }
    var bekliyor by remember { mutableStateOf(false) }
    var hata by remember { mutableStateOf<String?>(null) }
    var adresAcik by remember { mutableStateOf(false) }

    fun giris() {
        if (tc.isBlank() || sifre.isBlank() || bekliyor) return
        bekliyor = true
        hata = null
        kapsam.launch {
            val sonuc = obs.girisYap(tc.trim(), sifre, adres)
            bekliyor = false
            if (sonuc == null) basarili() else hata = sonuc
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f), MaterialTheme.colorScheme.background)
                )
            )
            .systemBarsPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Spacer(Modifier.height(48.dp))
        Image(painterResource(R.drawable.logo), null, Modifier.size(112.dp))
        Text("LimeOBS", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Black)
        Text(
            "Okulun cebinde. Ders programı, ödevler, sınavlar ve mesajlar tek yerde.",
            style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = tc, onValueChange = { tc = it.filter(Char::isDigit).take(11) },
            label = { Text("T.C. kimlik numarası") }, leadingIcon = { Icon(Icons.Outlined.Badge, null) },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Next),
        )
        OutlinedTextField(
            value = sifre, onValueChange = { sifre = it },
            label = { Text("Şifre") }, leadingIcon = { Icon(Icons.Outlined.Lock, null) },
            trailingIcon = {
                IconButton(onClick = { goster = !goster }) {
                    Icon(if (goster) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility, if (goster) "Gizle" else "Göster")
                }
            },
            visualTransformation = if (goster) VisualTransformation.None else PasswordVisualTransformation(),
            singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onDone = { giris() }),
        )
        if (adresAcik) {
            OutlinedTextField(
                value = adres, onValueChange = { adres = it.trim() },
                label = { Text("Okul OBS adresi") }, leadingIcon = { Icon(Icons.Outlined.School, null) },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
        }
        if (hata != null) Text(hata!!, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
        Button(
            onClick = { giris() }, enabled = !bekliyor && tc.isNotBlank() && sifre.isNotBlank(),
            modifier = Modifier.fillMaxWidth().height(54.dp),
        ) {
            if (bekliyor) CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
            else Text("Giriş yap", fontWeight = FontWeight.SemiBold)
        }
        TextButton(onClick = { adresAcik = !adresAcik }) {
            Text(if (adresAcik) "Okul adresini gizle" else "Başka okul mu? Adresi değiştir")
        }
        Text(
            "Şifren telefonun donanım kasasında şifrelenerek saklanır ve yalnızca okulunun OBS sunucusuna gönderilir. " +
                "LimeOBS bağımsız bir projedir; Akbim veya okulunla resmî bir bağı yoktur.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(24.dp))
    }
}
