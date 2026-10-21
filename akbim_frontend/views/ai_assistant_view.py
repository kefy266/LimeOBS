import os
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

try:
    from google import genai
    from google.genai import interactions
    HAS_GENAI = True
except Exception:
    genai = None
    interactions = None
    HAS_GENAI = False
import akbim_api


class AIAssistantView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(16)
        self.set_margin_end(16)

        self.client = None
        self.last_interaction_id = None
        self.system_prompt = ""

        # 1. Başlık & Bilgi
        info_banner = Adw.Banner()
        info_banner.set_title("🤖 Akbim OBS Asistanı (Gemini 3.8 Flash)")
        info_banner.set_revealed(True)
        self.append(info_banner)

        # 2. Sohbet Geçmişi (Scrolled Window + ListBox)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_vexpand(True)

        self.chat_list = Gtk.ListBox()
        self.chat_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chat_list.add_css_class("boxed-list")
        self.scrolled_window.set_child(self.chat_list)
        self.append(self.scrolled_window)

        # 3. Hızlı Soru Butonları (Quick Pills)
        quick_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        quick_box.set_margin_top(4)
        quick_box.set_margin_bottom(4)

        quick_prompts = [
            ("Bugünkü derslerim neler?", "Bugün hangi derslerim var ve saatleri kaçta?"),
            ("En yakın sınavım ne zaman?", "En yakın tarihteki sınavım nedir ve hangi tarihte yapılacak?"),
            ("Son duyuruyu özetle", "Okuldan gelen son duyuru nedir, kısaca özetler misin?"),
            ("Ders programı analizi", "Haftalık ders programımı gün gün kısaca özetle."),
        ]

        for label, full_prompt in quick_prompts:
            btn = Gtk.Button(label=label)
            btn.add_css_class("pill")
            btn.connect("clicked", lambda _, p=full_prompt: self.send_quick_prompt(p))
            quick_box.append(btn)

        self.append(quick_box)

        # 4. Mesaj Gönderme Kutusu (Alt Bar)
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Akbim derslerin, sınavların veya duyuruların hakkında soru sor...")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self.on_send_clicked)
        input_box.append(self.entry)

        self.send_btn = Gtk.Button(label="Gönder")
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.connect("clicked", self.on_send_clicked)
        input_box.append(self.send_btn)

        self.append(input_box)

        # Başlangıç Hoş Geldin Mesajı
        self.add_message_bubble("Asistan", "Merhaba! Ben Akbim OBS yapay zeka asistanınım. Ders programın, sınavların veya duyuruların hakkında bana her şeyi sorabilirsin. Aşağıdaki hızlı butonlara tıklayarak da hemen başlayabilirsin!", is_user=False)

        # Arka planda Gemini istemcisini hazırla
        self.init_ai_client()

    def init_ai_client(self):
        def worker():
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                akbim_context = akbim_api.get_all_student_data()
                self.system_prompt = f"""Sen Akbim OBS (Okul Bilgi Sistemi) için özel olarak geliştirilmiş Akıllı Öğrenci ve Veli Asistanısın.

GÖREV VE KAPSAM KURALLARI:
1. SADECE OKUMA VE ANALİZ: Sana sağlanan Akbim OBS verilerini okuyup analiz etmekle sorumlusun.
2. SIFIR YAZMA/DEĞİŞTİRME: Okul sistemine yeni kayıt ekleme, veri değiştirme, silme veya mesaj gönderme gibi bir yetkin ve erişimin KESİNLİKLE YOKTUR.
3. DIŞ DÜNYAYA KAPALILIK: Yalnızca Akbim OBS verilerine dayanarak cevap ver.
4. YANIT DİLİ: Türkçe, net, doğru, anlaşılır ve kibar.

=== GÜNCEL AKBİM OBS VERİLERİ ===
{akbim_context}
"""
        threading.Thread(target=worker, daemon=True).start()

    def add_message_bubble(self, sender, text, is_user=False):
        row = Adw.ActionRow()
        row.set_title(text)
        row.set_subtitle(sender)
        row.set_icon_name("avatar-default-symbolic" if is_user else "starred-symbolic")
        if is_user:
            row.add_css_class("user-bubble")
        else:
            row.add_css_class("bot-bubble")
        self.chat_list.append(row)
        return row

    def send_quick_prompt(self, prompt_text):
        if not self.entry.get_sensitive():
            return
        self.entry.set_text(prompt_text)
        self.on_send_clicked(None)

    def on_send_clicked(self, widget):
        question = self.entry.get_text().strip()
        if not question:
            return

        self.entry.set_text("")
        self.add_message_bubble("Sen", question, is_user=True)
        self.entry.set_sensitive(False)
        self.send_btn.set_sensitive(False)

        # Bot geçici balonu
        bot_row = self.add_message_bubble("Asistan", "Düşünüyor...", is_user=False)

        def worker():
            if not HAS_GENAI or not genai:
                GLib.idle_add(self.finish_response, bot_row, "[!] Google GenAI kütüphanesi ortamda yüklü değil.")
                return
            if not self.client:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    GLib.idle_add(self.finish_response, bot_row, "[!] GEMINI_API_KEY bulunamadı. Lütfen çevre değişkenini ayarlayın.")
                    return
                try:
                    self.client = genai.Client(api_key=api_key)
                except Exception as e:
                    GLib.idle_add(self.finish_response, bot_row, f"[!] GenAI başlatma hatası: {e}")
                    return

            try:
                kwargs = {
                    "model": "gemini-3.8-flash",
                    "input": question,
                    "system_instruction": self.system_prompt,
                    "generation_config": {"max_output_tokens": 1024},
                    "stream": True,
                }
                if self.last_interaction_id:
                    kwargs["previous_interaction_id"] = self.last_interaction_id

                stream = self.client.interactions.create(**kwargs)
                full_text = ""
                for event in stream:
                    if isinstance(event, interactions.InteractionCreatedEvent) and event.interaction:
                        self.last_interaction_id = event.interaction.id

                    if isinstance(event, interactions.StepDelta) and isinstance(event.delta, interactions.TextDelta):
                        if event.delta.text:
                            full_text += event.delta.text
                            GLib.idle_add(self.update_bot_bubble, bot_row, full_text)

                GLib.idle_add(self.finish_response, bot_row, full_text if full_text else "Yanıt üretilemedi.")
            except Exception as e:
                GLib.idle_add(self.finish_response, bot_row, f"Hata: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def update_bot_bubble(self, row, text):
        row.set_title(text)

    def finish_response(self, row, final_text):
        row.set_title(final_text)
        self.entry.set_sensitive(True)
        self.send_btn.set_sensitive(True)
        self.entry.grab_focus()

    def reset_state(self):
        """Hesap değiştiğinde sohbet geçmişini ve AI durumunu temizler."""
        self.last_interaction_id = None
        self.client = None
        self.system_prompt = ""
        while child := self.chat_list.get_first_child():
            self.chat_list.remove(child)
        self.add_message_bubble("Asistan", "Merhaba! Ben Akbim OBS yapay zeka asistanınım. Ders programın, sınavların veya duyuruların hakkında bana her şeyi sorabilirsin. Aşağıdaki hızlı butonlara tıklayarak da hemen başlayabilirsin!", is_user=False)
        self.init_ai_client()

    def load_data(self):
        # Arka planda yeni öğrenci verileriyle asistan sistem promptunu tazele
        self.init_ai_client()

