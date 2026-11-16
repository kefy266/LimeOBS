// LimeOBS asistan aracı sunucusu (Cloudflare Worker).
// Uygulama Groq'a doğrudan değil buraya bağlanır; Groq anahtarı yalnızca bu Worker'da gizli değişken
// (GROQ_API_KEY) olarak durur. Model, cevap uzunluğu ve mesaj boyutu burada sabitlenir, böylece
// adres bulunsa bile anahtar başka işler için kullanılamaz. IP başına dakikalık sınır uygulanır.

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const MODEL = "openai/gpt-oss-120b";
const MAX_BODY_BYTES = 40_000;
const MAX_MESSAGES = 14;
const MAX_MESSAGE_CHARS = 12_000;

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

// ---------------------------------------------------------------- Telegram bildirimleri
// Uygulama rastgele bir bağlantı kodu üretir ve kullanıcıyı t.me/<bot>?start=<kod> adresine gönderir.
// Kullanıcı Başlat'a basınca Telegram bu Worker'ın /tg/webhook adresine haber verir; kod → sohbet kimliği
// KV'ye yazılır. Uygulama sonra yalnızca bu kodla /tg/send çağırır: bot anahtarı ve sohbet kimliği
// uygulamaya hiç gelmez. Kod, o sohbete mesaj göndermenin anahtarıdır; bu yüzden uzun ve rastgeledir.

const CODE_RE = /^[A-Za-z0-9_-]{32,64}$/;
const MAX_TG_TEXT = 3800;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

async function tg(env, method, params) {
  const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json().catch(() => ({ ok: false, error_code: res.status }));
}

async function readJson(request) {
  const raw = await request.text();
  if (raw.length > 8000) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// Bot adını öğrenir ve webhook'u (bir kez) bu Worker'a ayarlar.
async function botInfo(env, origin) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TG_WEBHOOK_SECRET) return null;
  const botId = env.TELEGRAM_BOT_TOKEN.split(":")[0];
  let name = await env.TG.get(`bot:${botId}`);
  if (!name) {
    const me = await tg(env, "getMe", {});
    if (!me.ok) return null;
    name = me.result.username;
    const hook = await tg(env, "setWebhook", {
      url: `${origin}/tg/webhook`,
      secret_token: env.TG_WEBHOOK_SECRET,
      allowed_updates: ["message"],
      drop_pending_updates: true,
    });
    if (!hook.ok) return null;
    await env.TG.put(`bot:${botId}`, name);
  }
  return name;
}

async function unlinkChat(env, code) {
  const chat = await env.TG.get(`c:${code}`);
  if (chat) {
    await env.TG.delete(`c:${code}`);
    await env.TG.delete(`u:${chat}`);
  }
  return chat;
}

async function handleTelegram(request, env, pathname, origin) {
  if (pathname === "/tg/webhook") {
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TG_WEBHOOK_SECRET) return error(403, "forbidden");
    const update = await readJson(request);
    const msg = update && update.message;
    if (!msg || !msg.chat || msg.chat.type !== "private" || typeof msg.text !== "string") return json({ ok: true });
    const chat = String(msg.chat.id);
    const [cmd, arg] = msg.text.trim().split(/\s+/, 2);
    let reply;
    if (cmd === "/start" && arg && CODE_RE.test(arg)) {
      const old = await env.TG.get(`u:${chat}`);
      if (old && old !== arg) await env.TG.delete(`c:${old}`);
      await env.TG.put(`c:${arg}`, chat);
      await env.TG.put(`u:${chat}`, arg);
      reply = "✅ <b>LimeOBS bağlandı!</b>\nYeni ödev, mesaj, duyuru ve sınav sonuçlarını buradan bildireceğim.\n\nBildirimleri kapatmak için /stop yaz.";
    } else if (cmd === "/stop") {
      const code = await env.TG.get(`u:${chat}`);
      if (code) await unlinkChat(env, code);
      reply = code ? "🔕 Bildirimler kapatıldı. Tekrar açmak için LimeOBS'ta \"Telegram'a bağla\"ya bas." : "Bu sohbete bağlı bir LimeOBS yok.";
    } else {
      reply = "👋 Ben LimeOBS bildirim botuyum.\nBağlanmak için LimeOBS uygulamasında <b>Profil → Telefon bildirimleri → Telegram'a bağla</b>'ya bas.";
    }
    await tg(env, "sendMessage", { chat_id: chat, text: reply, parse_mode: "HTML" });
    return json({ ok: true });
  }

  if (pathname === "/tg/info" && request.method === "GET") {
    return json({ bot: await botInfo(env, origin) });
  }
  if (request.method !== "POST") return error(405, "method_not_allowed");
  const body = await readJson(request);
  if (!body || !CODE_RE.test(body.code || "")) return error(400, "bad_code");

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const { success } = await env.LIMITER.limit({ key: `tg:${ip}` });
  if (!success) return error(429, "rate_limited");

  if (pathname === "/tg/status") return json({ linked: Boolean(await env.TG.get(`c:${body.code}`)) });

  if (pathname === "/tg/unlink") {
    const chat = await unlinkChat(env, body.code);
    if (chat) await tg(env, "sendMessage", { chat_id: chat, text: "🔕 LimeOBS bağlantısı uygulamadan kaldırıldı." });
    return json({ ok: true });
  }

  if (pathname === "/tg/send") {
    if (typeof body.text !== "string" || !body.text.trim() || body.text.length > MAX_TG_TEXT) return error(400, "bad_text");
    const chat = await env.TG.get(`c:${body.code}`);
    if (!chat) return error(404, "not_linked");
    const res = await tg(env, "sendMessage", {
      chat_id: chat, text: body.text, parse_mode: "HTML", link_preview_options: { is_disabled: true },
    });
    if (!res.ok && res.error_code === 403) {  // kullanıcı botu engellemiş
      await unlinkChat(env, body.code);
      return error(410, "blocked");
    }
    return res.ok ? json({ ok: true }) : error(502, "telegram_error");
  }
  return error(404, "not_found");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    if (pathname === "/health") return new Response("ok");
    if (pathname.startsWith("/tg/")) {
      if (!env.TG) return error(503, "telegram_disabled");
      return handleTelegram(request, env, pathname, url.origin);
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
