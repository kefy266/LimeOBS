"""
LimeOBS Telegram bildirimlerini bir kez kurar.

1. Telegram'da @BotFather ile bot oluşturun (/newbot) ve verdiği anahtarı (token) kopyalayın.
2. Kendi botunuzun sohbetini açıp Başlat'a basın ve bir mesaj yazın.
3. Bu betiği çalıştırın:  venv/bin/python scripts/telegram_setup.py
   Anahtar gizli girişle sorulur (ekranda görünmez) ve sistem anahtarlığına ('LimeOBS') kaydedilir.
   Betik, mesaj yazdığınız sohbeti bulur, sohbet kimliğini de anahtarlığa kaydeder ve bir deneme mesajı yollar.

Kaldırmak için: venv/bin/python scripts/telegram_setup.py --remove
"""
import getpass
import sys

import keyring
import requests
from keyring.errors import PasswordDeleteError

SERVICE = "LimeOBS"
API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method, **params):
    res = requests.post(API.format(token=token, method=method), json=params, timeout=20)
    data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise SystemExit(f"Telegram '{method}' hatası: {data.get('description') or res.status_code}")
    return data["result"]


def main():
    if "--remove" in sys.argv:
        for name in ("telegram_bot_token", "telegram_chat_id"):
            try:
                keyring.delete_password(SERVICE, name)
            except PasswordDeleteError:
                pass
        print("Telegram ayarları anahtarlıktan silindi.")
        return

    token = keyring.get_password(SERVICE, "telegram_bot_token")
    if not token or input("Kayıtlı bir bot anahtarı var. Yenisini girmek ister misiniz? [e/H] ").strip().lower() == "e":
        token = getpass.getpass("BotFather'ın verdiği bot anahtarı (ekranda görünmez): ").strip()
        if not token:
            raise SystemExit("Anahtar girilmedi.")

    bot = call(token, "getMe")
    print(f"Bot doğrulandı: @{bot.get('username')}")

    updates = call(token, "getUpdates")
    chats = [u["message"]["chat"] for u in updates if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not chats:
        raise SystemExit(
            f"Bota henüz mesaj gelmemiş. Telegram'da @{bot.get('username')} sohbetini açıp Başlat'a basın, "
            "bir mesaj yazın ve bu betiği tekrar çalıştırın."
        )
    chat = chats[-1]
    keyring.set_password(SERVICE, "telegram_bot_token", token)
    keyring.set_password(SERVICE, "telegram_chat_id", str(chat["id"]))
    print(f"Sohbet bulundu: {chat.get('first_name', '')} — kimlik anahtarlığa kaydedildi.")

    call(token, "sendMessage", chat_id=chat["id"],
         text="✅ <b>LimeOBS bağlandı</b>\nSabah özeti ve yeni ödev/mesaj bildirimleri buraya gelecek.",
         parse_mode="HTML")
    print("Deneme mesajı gönderildi. Kurulum tamam.")


if __name__ == "__main__":
    main()
