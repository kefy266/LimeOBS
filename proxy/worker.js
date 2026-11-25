// LimeOBS asistan aracı sunucusu (Cloudflare Worker).
// Uygulama Groq'a doğrudan değil buraya bağlanır; Groq anahtarı yalnızca bu Worker'da gizli değişken
// (GROQ_API_KEY) olarak durur. Model, cevap uzunluğu ve mesaj boyutu burada sabitlenir, böylece
// adres bulunsa bile anahtar başka işler için kullanılamaz. IP başına dakikalık sınır uygulanır.

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const MODEL = "openai/gpt-oss-120b";
const MAX_BODY_BYTES = 40_000;
const MAX_MESSAGES = 14;
const MAX_MESSAGE_CHARS = 12_000;

// Asistan OBS dışındaki sorular için internette arayabilir (Groq'un gpt-oss'a sunduğu yerleşik browser_search aracı).
// Eski uygulama sürümlerinin talimatı "yalnızca OBS bilgilerine dayan" dediği için bu not her isteğe eklenir.
const SEARCH_NOTE =
  "Ek kural: Soru öğrencinin OBS bilgileriyle (notlar, ödevler, sınavlar, program, devamsızlık) ilgiliyse yalnızca " +
  "DOĞRULANMIŞ BİLGİLER'e dayan. OBS dışındaki sorularda (ders konuları, genel kültür, güncel haberler, LGS/sınav " +
  "tarihleri, okul dışı her şey) gerekirse browser_search aracıyla internette ara, bulduklarına dayan ve sonda " +
  "kaynağın site adını kısaca belirt. Cevabı sorunun ihtiyacı kadar ayrıntılı ver; konu anlatımı istenirse örnekle açıkla.";

// Soru çözücü (mobil): fotoğraf ya da metin olarak gelen tek bir soruyu adım adım çözer.
// İki aşama: görsel model fotoğraftaki soruyu yalnızca yazıya döker (OCR, şekildeki ölçüler dahil);
// çözümü matematikte daha güçlü akıl yürütme modeli yapar. Görsel model tek başına çözünce döngüye girebiliyordu.
const VISION_MODEL = "qwen/qwen3.8-27b";
const SOLVE_MODEL = MODEL;
const MAX_SOLVE_BYTES = 4_500_000; // ~3 MB'lık JPEG'in base64 hâli
const OCR_PROMPT =
  "Görseldeki sınav/ödev sorusunu ÇÖZMEDEN, eksiksiz ve aynen yazıya dök. Soru metnini, şıkları ve şekil, " +
  "tablo ya da grafik üzerindeki TÜM sayıları ve etiketleri (hangi kenarda hangi ölçü yazdığı dahil) yaz. " +
  "Şekli kısa ve açık bir dille betimle (ör. 'dikdörtgen masa; uzun kenarında 6/5 m yazıyor'). Kesirleri a/b " +
  "biçiminde yaz. Birden fazla soru varsa hepsini numarasıyla yaz. Okunamayan kısım için [okunamadı] yaz. Yorum ekleme.";
const SOLVE_PROMPT =
  "Sen LGS'ye hazırlanan ortaokul öğrencilerine yardım eden, matematikte ve fende çok dikkatli bir öğretmensin. " +
  "Türkçe yanıt ver. Önce soruyu bir iki cümleyle özetle, sonra çözümü numaralı kısa adımlarla, her adımda nedenini " +
  "açıklayarak yap. Matematiği düz metinle yaz (3/4, x^2, √16); LaTeX ve $ işareti kullanma. Hesapları kontrol et; " +
  "sonuç şıklardan birine uymuyorsa okumayı yeniden yorumla ve uyan çözümü bul. Soruda gerçekten bir eksik ya da " +
  "çelişki varsa bunu YALNIZCA BİR KEZ kısaca söyle ve en makul yorumla devam et; aynı cümleleri asla tekrarlama. " +
  "Test sorusuysa en sonda **Cevap: X** yaz. Tablo kullanma. Yanıtın 350 kelimeyi geçmesin.";

function error(status, code) {
  return new Response(JSON.stringify({ error: code }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function validMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0 || messages.length > MAX_MESSAGES) return false;
  if (messages[messages.length - 1].role !== "user") return false;
  return messages.every(
    (m) =>
      m && (m.role === "user" || m.role === "assistant") &&
      typeof m.content === "string" && m.content.length <= MAX_MESSAGE_CHARS,
  );
}

// Arama aracının cevaba koyduğu 【1†L7-L9】 biçimli kaynak işaretlerini akıştan siler (parçalara bölünse bile).
function stripCitations(body) {
  const dec = new TextDecoder();
  const enc = new TextEncoder();
  let lineBuf = "";
  let pending = ""; // kapanmamış 【 ile başlayan metin
  const clean = (text) => {
    let t = pending + text;
    pending = "";
    t = t.replace(/【[^】]*】/g, "");
    const open = t.lastIndexOf("【");
    if (open !== -1 && t.length - open < 40) {
      pending = t.slice(open);
      t = t.slice(0, open);
    }
    return t;
  };
  const handle = (line) => {
    if (!line.startsWith("data:")) return line;
    const data = line.slice(5).trim();
    if (data === "[DONE]") return line;
    try {
      const obj = JSON.parse(data);
      const delta = obj.choices?.[0]?.delta;
      if (delta && typeof delta.content === "string") delta.content = clean(delta.content);
      return "data: " + JSON.stringify(obj);
    } catch {
      return line;
    }
  };
  return body.pipeThrough(
    new TransformStream({
      transform(chunk, ctrl) {
        lineBuf += dec.decode(chunk, { stream: true });
        const lines = lineBuf.split("\n");
        lineBuf = lines.pop();
        ctrl.enqueue(enc.encode(lines.map(handle).join("\n") + "\n"));
      },
      flush(ctrl) {
        if (lineBuf) ctrl.enqueue(enc.encode(handle(lineBuf)));
      },
    }),
  );
}

function sse(stream) {
  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache" },
  });
}

async function solve(request, env) {
  const raw = await request.text();
  if (raw.length > MAX_SOLVE_BYTES) return error(413, "too_large");
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return error(400, "bad_json");
  }
  const text = typeof body.text === "string" ? body.text.slice(0, 4000) : "";
  const image = typeof body.image === "string" && /^data:image\/(jpeg|png|webp);base64,/.test(body.image) ? body.image : "";
  if (!text && !image) return error(400, "empty");

  // 1. Fotoğraf varsa soruyu yazıya dök
  let question = text;
  if (image) {
    const ocr = await fetch(GROQ_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: VISION_MODEL,
        messages: [
          { role: "system", content: OCR_PROMPT },
          { role: "user", content: [{ type: "text", text: "Bu görseldeki soruyu yazıya dök." }, { type: "image_url", image_url: { url: image } }] },
        ],
        temperature: 0,
        max_completion_tokens: 1500,
        reasoning_format: "hidden",
      }),
    });
    if (!ocr.ok) {
      console.log("groq ocr error", ocr.status, (await ocr.text()).slice(0, 300));
      return error(ocr.status === 429 ? 429 : 502, "upstream_error");
    }
    const transcript = ((await ocr.json()).choices?.[0]?.message?.content || "").trim();
    if (!transcript) return error(422, "unreadable");
    question = `FOTOĞRAFTAKİ SORU (yazıya dökülmüş):\n${transcript}` + (text ? `\n\nÖĞRENCİNİN NOTU: ${text}` : "");
  }

  // 2. Akıl yürütme modeliyle çöz (akış hâlinde)
  const upstream = await fetch(GROQ_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: SOLVE_MODEL,
      messages: [
        { role: "system", content: SOLVE_PROMPT },
        { role: "user", content: question },
      ],
      stream: true,
      temperature: 0.2,
      max_completion_tokens: 6000,
      reasoning_effort: "high",
      include_reasoning: false,
    }),
  });
  if (!upstream.ok) {
    console.log("groq solve error", upstream.status, (await upstream.text()).slice(0, 300));
    return error(upstream.status === 429 ? 429 : 502, "upstream_error");
  }
  return sse(upstream.body);
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/health") return new Response("ok");
    if (pathname === "/v1/solve") {
      if (request.method !== "POST") return error(405, "method_not_allowed");
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      const { success } = await env.LIMITER.limit({ key: ip });
      if (!success) return error(429, "rate_limited");
      return solve(request, env);
    }
    if (pathname !== "/v1/chat") return error(404, "not_found");
    if (request.method !== "POST") return error(405, "method_not_allowed");

    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const { success } = await env.LIMITER.limit({ key: ip });
    if (!success) return error(429, "rate_limited");

    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) return error(413, "too_large");
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return error(400, "bad_json");
    }
    if (!validMessages(body.messages)) return error(400, "bad_messages");

    const messages = body.messages.map(({ role, content }) => ({ role, content }));
    const ask = (search) =>
      fetch(GROQ_URL, {
        method: "POST",
        headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: MODEL,
          messages: search ? [{ role: "system", content: SEARCH_NOTE }, ...messages] : messages,
          ...(search ? { tools: [{ type: "browser_search" }], tool_choice: "auto" } : {}),
          stream: true,
          temperature: 0.5,
          max_completion_tokens: 4096,
          reasoning_effort: "medium",
          include_reasoning: false,
        }),
      });
    let upstream = await ask(true);
    // Arama çok kelime harcar; dakikalık kota dolarsa aramasız bir kez daha dene ki öğrenci cevapsız kalmasın
    if (upstream.status === 429 || upstream.status >= 500) {
      console.log("groq error (search)", upstream.status);
      upstream = await ask(false);
    }
    if (!upstream.ok) {
      console.log("groq error", upstream.status);
      return error(upstream.status === 429 ? 429 : 502, "upstream_error");
    }
    return new Response(stripCitations(upstream.body), {
      headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache" },
    });
  },
};
