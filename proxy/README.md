# LimeOBS asistan aracı sunucusu

Uygulamadaki yapay zekâ asistanı Groq'a doğrudan bağlanmaz; istekler bu Cloudflare Worker'a gelir ve Worker
Groq'a senin anahtarınla iletir. Anahtar uygulamanın içinde olmadığı için kimse onu çıkaramaz.

Worker şunları sabitler: model (`openai/gpt-oss-120b`), en fazla 2048 token cevap, en fazla 14 mesaj ve
IP başına dakikada 6 soru. Ek güvence olarak Groq konsolundan aylık harcama sınırı koy
(console.groq.com → Settings → Billing → Spend limit).

## Kurulum (bir kez)

```bash
cd proxy
npx wrangler login                    # tarayıcıda Cloudflare hesabınla giriş
npx wrangler secret put GROQ_API_KEY  # Groq anahtarını sorar; yazdığın ekranda görünmez
npx wrangler deploy                   # https://limeobs-ai.<hesap>.workers.dev adresini verir
```

Çıkan adresi `akbim_frontend/ai_assistant.py` içindeki `AI_PROXY_URL` değişkenine yaz.

Test: `curl https://limeobs-ai.<hesap>.workers.dev/health` → `ok`
