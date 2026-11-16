package com.kagan.limeobs

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.concurrent.TimeUnit

/**
 * Yapay zekâ asistanı. Uygulama Groq'a doğrudan bağlanmaz; istekler LimeOBS aracı sunucusuna gider
 * (proxy/ klasöründeki Cloudflare Worker), Groq anahtarı yalnızca orada durur. Puan farkları, teslim günleri
 * ve tatiller önce burada hesaplanır; model yalnızca bu "doğrulanmış bilgileri" yorumlar (uydurmasın diye).
 */
object AsistanServisi {
    private const val ADRES = "https://lime.kaganefe.com/v1/chat"
    private val http = OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).build()

    private val GUNLER = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
    private fun yaz(g: LocalDate) = "${g.dayOfMonth}.${g.monthValue}.${g.year} ${GUNLER[g.dayOfWeek.value - 1]}"

    const val TALIMAT = """Sen LimeOBS'un öğrenci asistanısın; bir ortaokul öğrencisiyle Türkçe konuşuyorsun.
Sana her soruda okulun OBS sisteminden alınmış "DOĞRULANMIŞ BİLGİLER" veriliyor. Puan farkları, en yüksek puan, kalan gün sayısı gibi hesaplar zaten yapılmış durumda; kendin yeniden hesaplama, verilen sayıları kullan.
- Yalnızca bu bilgilere dayan. Bilgilerde olmayan bir ödev, sınav, ders ya da sayı uydurma; bilmiyorsan "OBS'de bu bilgi yok" de.
- Kısa ve net yaz: birkaç cümle ya da en fazla 6 maddelik liste. Gerektiğinde **kalın** kullanabilirsin.
- Samimi ve cesaretlendirici ol ama abartma. Çalışma önerilerin somut olsun (hangi ders, ne kadar süre).
- Ödevin çözümünü yazma; nasıl yaklaşacağını ve neye dikkat edeceğini anlat."""

    private fun tarih(t: String): LocalDate? = runCatching {
        val p = t.trim().split(' ')[0]
        if (p.contains('.')) LocalDate.parse(p, DateTimeFormatter.ofPattern("dd.MM.yyyy")) else LocalDate.parse(p)
    }.getOrNull()

    /** OBS verisinden kodla hesaplanmış bilgi metni. */
    suspend fun dogrulanmisBilgiler(ctx: Context): String {
        val obs = Obs.al(ctx)
        Takvim.hazirla(ctx)
        val bugun = LocalDate.now()
        val sonraki = Takvim.sonrakiOkulGunu(bugun)
        val ana = obs.anaVeri()
        val satirlar = mutableListOf("Bugün: ${yaz(bugun)}. Bir sonraki okul günü: ${yaz(sonraki)}.")

        Takvim.okulYokNedeni(bugun)?.takeIf { bugun.dayOfWeek.value <= 5 }?.let { neden ->
            val t = Takvim.okulTatili(bugun)
            satirlar += "Bugün okul yok: $neden" + (t?.let { " (${yaz(it.baslangic)} – ${yaz(it.bitis)})" } ?: "") +
                ". Okul ${yaz(sonraki)} günü başlıyor."
        }
        Takvim.yaklasan(bugun, 120).filter { it.baslangic.isAfter(bugun) }.take(6).takeIf { it.isNotEmpty() }?.let { l ->
            satirlar += "Yaklaşan tatiller: " + l.joinToString("; ") {
                it.ad + " " + yaz(it.baslangic) + (if (it.bitis != it.baslangic) " – " + yaz(it.bitis) else "")
            } + "."
        }

        fun dersler(g: LocalDate): String {
            val sayim = LinkedHashMap<String, Int>()
            ana.program.hucreler.filter { it.gun == g.dayOfWeek.value }.sortedBy { it.saat }
                .forEach { sayim[guzelAd(it.ders)] = (sayim[guzelAd(it.ders)] ?: 0) + 1 }
            return sayim.entries.joinToString(", ") { (d, n) -> if (n > 1) "$d ($n saat)" else d }.ifBlank { "yok" }
        }
        if (Takvim.okulGunuMu(bugun)) satirlar += "Bugünün dersleri: ${dersler(bugun)}."
        satirlar += "${yaz(sonraki)} dersleri: ${dersler(sonraki)}."

        val bekleyen = runCatching { obs.odevler() }.getOrDefault(emptyList())
            .mapNotNull { o -> tarih(o.bitis)?.let { it to o } }
            .filter { (b, o) -> o.durumKod != 1 && !b.isBefore(bugun) }
            .sortedBy { it.first }
        satirlar += "Teslim edilmemiş ve süresi geçmemiş ödevler (${bekleyen.size} adet):"
        bekleyen.take(25).forEach { (b, o) ->
            val kalan = java.time.temporal.ChronoUnit.DAYS.between(bugun, b)
            val ne = when (kalan) { 0L -> "bugün"; 1L -> "yarın"; else -> "$kalan gün sonra" }
            satirlar += "  - ${o.baslik} — ${guzelAd(o.ders)}, teslim ${yaz(b)} ($ne), durum: ${o.durum}"
        }

        val sinavlar = ana.sinavlar.mapNotNull { s -> tarih(s.tarih)?.let { it to s } }
            .filter { (g, _) -> !g.isBefore(bugun) && !g.isAfter(bugun.plusDays(21)) }
        satirlar += if (sinavlar.isEmpty()) "Önümüzdeki 3 haftada planlanmış sınav yok." else "Önümüzdeki 3 haftadaki sınavlar:"
        sinavlar.forEach { (g, s) -> satirlar += "  - ${s.ad} — ${yaz(g)}" }

        runCatching { obs.sinavlar() }.getOrNull()?.let { oz ->
            val denemeler = oz.sinavlar.mapNotNull { s -> tarih(s.tarih)?.let { it to s } }
                .filter { (_, s) -> s.ad.uppercase(java.util.Locale("tr")).contains("DENEME") }.sortedBy { it.first }
            if (denemeler.isNotEmpty()) {
                satirlar += "Deneme sınavları (eskiden yeniye):"
                denemeler.forEach { (g, s) -> satirlar += "  - ${g.dayOfMonth}.${g.monthValue} ${s.ad}: puan ${"%.1f".format(s.puan)}, net ${"%.2f".format(s.net)} (D ${s.dogru} / Y ${s.yanlis} / B ${s.bos})" }
                if (denemeler.size >= 2) {
                    val son = denemeler.last().second
                    val onceki = denemeler[denemeler.size - 2].second
                    val ilk = denemeler.first().second
                    val enIyi = denemeler.maxBy { it.second.puan }.second
                    satirlar += "  * Son sınav bir öncekine göre puan ${"%+.1f".format(son.puan - onceki.puan)}, net ${"%+.2f".format(son.net - onceki.net)}."
                    satirlar += "  * İlk sınavdan son sınava puan ${"%+.1f".format(son.puan - ilk.puan)}, net ${"%+.2f".format(son.net - ilk.net)}."
                    satirlar += "  * En yüksek puan: ${"%.1f".format(enIyi.puan)} (${enIyi.ad})" + if (enIyi === son) " — bu son sınav." else "."
                }
            }
            oz.enIyiDers?.let { satirlar += "En başarılı ders: ${guzelAd(it.ders)} (%${"%.0f".format(it.oran)})." }
            oz.enZayifDers?.let { satirlar += "En zayıf ders: ${guzelAd(it.ders)} (%${"%.0f".format(it.oran)})." }
        }
        return satirlar.joinToString("\n")
    }

    /** Sunucuya sorar, cevabı parça parça [parca]'ya iletir; hata olursa Türkçe mesajla istisna fırlatır. */
    suspend fun sor(mesajlar: List<Pair<String, String>>, parca: suspend (String) -> Unit): String = withContext(Dispatchers.IO) {
        val dizi = JSONArray()
        mesajlar.forEach { (rol, icerik) -> dizi.put(JSONObject().put("role", rol).put("content", icerik)) }
        val istek = Request.Builder().url(ADRES)
            .post(JSONObject().put("messages", dizi).toString().toRequestBody("application/json".toMediaType()))
            .build()
        val cevap = try {
            http.newCall(istek).execute()
        } catch (e: Exception) {
            throw IllegalStateException("Asistan servisine bağlanılamadı. İnternet bağlantını kontrol et.")
        }
        cevap.use { r ->
            when {
                r.code == 429 -> throw IllegalStateException("Kısa sürede çok fazla soru sordun. Biraz bekleyip tekrar dene.")
                r.code == 413 -> throw IllegalStateException("Soru çok uzun. Daha kısa yazmayı dene.")
                !r.isSuccessful -> throw IllegalStateException("Asistan şu an cevap veremiyor (HTTP ${r.code}).")
            }
            val kaynak = r.body!!.source()
            val tum = StringBuilder()
            while (!kaynak.exhausted()) {
                val satir = kaynak.readUtf8Line() ?: break
                if (!satir.startsWith("data:")) continue
                val veri = satir.substring(5).trim()
                if (veri == "[DONE]") break
                val p = runCatching {
                    JSONObject(veri).getJSONArray("choices").getJSONObject(0).optJSONObject("delta")?.optString("content").orEmpty()
                }.getOrDefault("")
                if (p.isNotEmpty()) {
                    tum.append(p)
                    withContext(Dispatchers.Main) { parca(p) }
                }
            }
            tum.toString()
        }
    }
}

/** **kalın** ve "- " maddelerini gösterir (modelin yazdığı sade Markdown). */
fun mdMetin(metin: String): AnnotatedString = buildAnnotatedString {
    metin.lines().forEachIndexed { i, ham ->
        if (i > 0) append("\n")
        var satir = ham
        val bosluk = satir.takeWhile { it == ' ' }
        satir = satir.trimStart()
        when {
            satir.startsWith("#") -> { pushStyle(SpanStyle(fontWeight = FontWeight.Bold)); append(satir.trimStart('#').trim()); pop(); return@forEachIndexed }
            satir.startsWith("- ") || satir.startsWith("* ") -> { append(bosluk); append("• "); satir = satir.substring(2) }
            else -> append(bosluk)
        }
        val parcalar = satir.split("**")
        parcalar.forEachIndexed { j, p ->
            if (j % 2 == 1 && j < parcalar.lastIndex) { pushStyle(SpanStyle(fontWeight = FontWeight.Bold)); append(p); pop() } else append(p)
        }
    }
}

private data class SohbetMesaji(val rol: String, val metin: String, val hata: Boolean = false)

@Composable
fun AsistanEkrani() {
    val ctx = LocalContext.current
    val kapsam = rememberCoroutineScope()
    val mesajlar = remember { mutableStateListOf<SohbetMesaji>() }
    val gecmis = remember { mutableListOf<Pair<String, String>>() }
    var girdi by remember { mutableStateOf("") }
    var mesgul by remember { mutableStateOf(false) }
    val liste = rememberLazyListState()
    val oneriler = listOf(
        "Haftamı analiz et" to "Bu haftaki ödev ve ders yükümü analiz et, nelere öncelik vermeliyim?",
        "Sınav gidişatım" to "Deneme sınavlarındaki gidişatımı yorumla: nerede iyiyim, nereye çalışmalıyım?",
        "Okul ne zaman?" to "Okul ne zaman açılıyor? İlk gün için neye hazırlanmalıyım?",
    )

    LaunchedEffect(mesajlar.size, mesajlar.lastOrNull()?.metin?.length) {
        if (mesajlar.isNotEmpty()) liste.animateScrollToItem(mesajlar.lastIndex)
    }

    fun sor(soru: String) {
        if (mesgul || soru.isBlank()) return
        mesgul = true
        mesajlar += SohbetMesaji("user", soru)
        mesajlar += SohbetMesaji("assistant", "")
        val i = mesajlar.lastIndex
        kapsam.launch {
            try {
                val bilgiler = AsistanServisi.dogrulanmisBilgiler(ctx)
                val icerik = "${AsistanServisi.TALIMAT}\n\nDOĞRULANMIŞ BİLGİLER:\n$bilgiler\n\nSORU: $soru"
                val cevap = AsistanServisi.sor(gecmis + ("user" to icerik)) { p ->
                    mesajlar[i] = mesajlar[i].copy(metin = mesajlar[i].metin + p)
                }
                gecmis += "user" to soru
                gecmis += "assistant" to cevap
                while (gecmis.size > 12) gecmis.removeAt(0)
            } catch (e: OturumHatasi) {
                mesajlar[i] = SohbetMesaji("assistant", e.message ?: "Oturumun sona erdi.", hata = true)
            } catch (e: Exception) {
                mesajlar[i] = SohbetMesaji("assistant", e.message ?: "Beklenmeyen bir hata oluştu.", hata = true)
            } finally {
                mesgul = false
            }
        }
    }

    Column(Modifier.fillMaxSize().imePadding()) {
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (mesajlar.isEmpty()) {
                Column(
                    Modifier.fillMaxSize().padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(Icons.Outlined.AutoAwesome, null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.height(12.dp))
                    Text("Nasıl yardımcı olabilirim?", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Dersler, ödevler, sınav sonuçları ve tatiller hakkında soru sorabilirsin.",
                        textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(16.dp))
                    oneriler.forEach { (etiket, soru) ->
                        SuggestionChip(onClick = { sor(soru) }, label = { Text(etiket) })
                    }
                }
            } else {
                LazyColumn(state = liste, contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    itemsIndexed(mesajlar) { _, m ->
                        if (m.rol == "user") {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                                Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.secondaryContainer,
                                    modifier = Modifier.widthIn(max = 300.dp)) {
                                    Text(m.metin, Modifier.padding(horizontal = 14.dp, vertical = 10.dp))
                                }
                            }
                        } else if (m.metin.isEmpty()) {
                            CircularProgressIndicator(Modifier.padding(4.dp), strokeWidth = 2.dp)
                        } else {
                            Text(
                                mdMetin(m.metin),
                                color = if (m.hata) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onBackground,
                                style = MaterialTheme.typography.bodyLarge,
                            )
                        }
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = girdi, onValueChange = { girdi = it },
                modifier = Modifier.weight(1f), placeholder = { Text("Asistana bir şey sor…") },
                shape = RoundedCornerShape(24.dp), maxLines = 4,
            )
            Spacer(Modifier.padding(4.dp))
            FilledIconButton(onClick = { val s = girdi.trim(); girdi = ""; sor(s) }, enabled = !mesgul && girdi.isNotBlank()) {
                Icon(Icons.AutoMirrored.Outlined.Send, "Gönder")
            }
        }
        Text(
            "Asistan hata yapabilir. Önemli bilgileri OBS'den kontrol et.",
            Modifier.fillMaxWidth().padding(bottom = 8.dp), textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
