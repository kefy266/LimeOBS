// LimeOBS asistan aracı sunucusu (Cloudflare Worker).
// Uygulama Groq'a doğrudan değil buraya bağlanır; Groq anahtarı yalnızca bu Worker'da gizli değişken
// (GROQ_API_KEY) olarak durur. Model, cevap uzunluğu ve mesaj boyutu burada sabitlenir, böylece
// adres bulunsa bile anahtar başka işler için kullanılamaz. IP başına dakikalık sınır uygulanır.

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const MODEL = "openai/gpt-oss-120b";
const MAX_BODY_BYTES = 40_000;
const MAX_MESSAGES = 14;
const MAX_MESSAGE_CHARS = 12_000;

// Soru çözücü (mobil): fotoğraf ya da metin olarak gelen tek bir ödev/test sorusunu adım adım çözer.
const VISION_MODEL = "qwen/qwen3.8-27b";
const MAX_SOLVE_BYTES = 4_500_000; // ~3 MB'lık JPEG'in base64 hâli
const SOLVE_PROMPT =
  "Sen ortaokul öğrencilerine (LGS'ye hazırlanan) yardım eden sabırlı bir öğretmensin. Sana bir soru " +
  "fotoğrafı ya da metni gelecek. Türkçe yanıt ver. Önce soruyu kısaca kendi cümlenle yaz, sonra çözümü " +
  "numaralı adımlarla, her adımda neden öyle yaptığını açıklayarak anlat. Matematik ifadelerini düz metinle " +
  "yaz (ör. 3/4, x^2, √16). Test sorusuysa en sonda **Cevap: X** biçiminde doğru şıkkı belirt. Fotoğraf " +
  "okunamıyorsa ya da soru yoksa bunu kibarca söyle ve daha net bir fotoğraf iste. Tablo kullanma.";

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
  const content = [{ type: "text", text: text || "Fotoğraftaki soruyu çöz." }];
  if (image) content.push({ type: "image_url", image_url: { url: image } });

  const upstream = await fetch(GROQ_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GROQ_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: VISION_MODEL,
      messages: [
        { role: "system", content: SOLVE_PROMPT },
        { role: "user", content },
      ],
      stream: true,
      temperature: 0.3,
      max_completion_tokens: 3072,
      reasoning_format: "hidden",
    }),
  });
  if (!upstream.ok) {
    console.log("groq solve error", upstream.status, (await upstream.text()).slice(0, 300));
    return error(upstream.status === 429 ? 429 : 502, "upstream_error");
  }
  return new Response(upstream.body, {
    headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache" },
  });
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

    const upstream = await fetch(GROQ_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GROQ_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        messages: body.messages.map(({ role, content }) => ({ role, content })),
        stream: true,
        temperature: 0.5,
        max_completion_tokens: 2048,
        reasoning_effort: "low",
        include_reasoning: false,
      }),
    });
    if (!upstream.ok) {
      console.log("groq error", upstream.status);
      return error(upstream.status === 429 ? 429 : 502, "upstream_error");
    }
    return new Response(upstream.body, {
      headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache" },
    });
  },
};
