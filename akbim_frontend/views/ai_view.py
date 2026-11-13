import re
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Pango

import ai_assistant as ai


def markdown_to_pango(text):
    """Modelin yazdığı sade Markdown'u (kalın, başlık, madde) Pango biçimine çevirir."""
    out = []
    for line in GLib.markup_escape_text(text).split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            line = "<b>" + stripped.lstrip("#").strip() + "</b>"
        elif stripped[:2] in ("- ", "* "):
            line = "  • " + stripped[2:]
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)


class AIAssistantView(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.conversation = ai.Conversation()
        self.busy = False

        # --- Başlık
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_margin_top(24)
        header.set_margin_start(20)
        header.set_margin_end(20)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='x-large' weight='bold'>✨ Asistan</span>")
        title_lbl.set_halign(Gtk.Align.START)
        title_box.append(title_lbl)
        sub_lbl = Gtk.Label()
        sub_lbl.set_markup("<span size='small' foreground='#b8b8b8'>OBS verilerine bakarak ödev, sınav ve "
                           "program sorularını cevaplar</span>")
        sub_lbl.set_halign(Gtk.Align.START)
        title_box.append(sub_lbl)
        header.append(title_box)

        clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic")
        clear_btn.set_tooltip_text("Sohbeti Temizle")
        clear_btn.add_css_class("flat")
        clear_btn.connect("clicked", lambda _: self.reset_state())
        header.append(clear_btn)

        self.append(header)

        # --- Anahtar yoksa kurulum kartı
        self.setup_banner = Adw.Banner()
        self.setup_banner.set_title("Asistan servisi henüz kurulmadı")
        self.setup_banner.set_margin_top(12)
        self.append(self.setup_banner)

        # --- Sohbet alanı
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_vexpand(True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(820)
        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.chat_box.set_margin_top(18)
        self.chat_box.set_margin_bottom(18)
        self.chat_box.set_margin_start(20)
        self.chat_box.set_margin_end(20)
        clamp.set_child(self.chat_box)
        self.scroller.set_child(clamp)
        self.append(self.scroller)

        # --- Hızlı sorular + giriş
        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        bottom.set_margin_start(20)
        bottom.set_margin_end(20)
        bottom.set_margin_bottom(18)

        self.quick_box = Gtk.FlowBox()
        self.quick_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.quick_box.set_max_children_per_line(4)
        self.quick_box.set_column_spacing(8)
        self.quick_box.set_row_spacing(8)
        for label, question in ai.QUICK_ACTIONS:
            btn = Gtk.Button(label=label)
            btn.add_css_class("pill")
            btn.connect("clicked", lambda _, q=question: self.ask(q))
            self.quick_box.append(btn)
        bottom.append(self.quick_box)

        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        self.entry.set_placeholder_text("Bir şey sor… (ör. Fen ödevime nasıl başlamalıyım?)")
        self.entry.connect("activate", lambda _: self.on_send())
        input_row.append(self.entry)
        self.spinner = Gtk.Spinner()
        input_row.append(self.spinner)
        self.send_btn = Gtk.Button(icon_name="mail-send-symbolic")
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.add_css_class("circular")
        self.send_btn.set_tooltip_text("Gönder")
        self.send_btn.connect("clicked", lambda _: self.on_send())
        input_row.append(self.send_btn)
        bottom.append(input_row)
        self.append(bottom)

        self.show_welcome()
        self.refresh_setup_state()

    # ------------------------------------------------------------------ durum

    def refresh_setup_state(self):
        self.setup_banner.set_revealed(not ai.service_configured())

    def load_data(self):
        """Sekmeye geçildiğinde çağrılır; ağ isteği yapmaz."""
        self.refresh_setup_state()

    def reset_state(self):
        self.conversation.reset()
        while child := self.chat_box.get_first_child():
            self.chat_box.remove(child)
        self.show_welcome()

    def show_welcome(self):
        lbl = Gtk.Label()
        lbl.set_markup("<span foreground='#b8b8b8'>Aşağıdaki hızlı sorulardan birini seç ya da kendi sorunu yaz. "
                       "Asistan dersler, ödevler, sınav sonuçları ve yemek listesi hakkında bilgi sahibi.</span>")
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_margin_top(40)
        self.chat_box.append(lbl)

    # ------------------------------------------------------------------ sohbet

    def _bubble(self, text, user):
        lbl = Gtk.Label()
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_xalign(0)
        lbl.set_selectable(True)
        if user:
            lbl.set_text(text)
        frame = Gtk.Box()
        frame.add_css_class("card")
        lbl.set_margin_top(10)
        lbl.set_margin_bottom(10)
        lbl.set_margin_start(14)
        lbl.set_margin_end(14)
        frame.append(lbl)
        frame.set_halign(Gtk.Align.END if user else Gtk.Align.FILL)
        if user:
            frame.add_css_class("accent")
            frame.set_margin_start(80)
        self.chat_box.append(frame)
        return lbl

    def _scroll_to_end(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def on_send(self):
        text = self.entry.get_text().strip()
        if text:
            self.entry.set_text("")
            self.ask(text)

    def set_busy(self, busy):
        self.busy = busy
        self.send_btn.set_sensitive(not busy)
        self.quick_box.set_sensitive(not busy)
        self.spinner.set_spinning(busy)

    def ask(self, question):
        if self.busy:
            return
        if not ai.service_configured():
            return
        first = self.chat_box.get_first_child()
        if first and isinstance(first, Gtk.Label):  # karşılama metnini kaldır
            self.chat_box.remove(first)

        self._bubble(question, user=True)
        answer_lbl = self._bubble("", user=False)
        answer_lbl.set_markup("<span foreground='#b8b8b8'>OBS verilerine bakılıyor…</span>")
        self.set_busy(True)
        GLib.idle_add(self._scroll_to_end)

        state = {"text": "", "pending": False}

        def render():
            state["pending"] = False
            answer_lbl.set_markup(markdown_to_pango(state["text"]))
            GLib.idle_add(self._scroll_to_end)
            return False

        def on_text(piece):
            state["text"] += piece
            if not state["pending"]:
                state["pending"] = True
                GLib.timeout_add(60, render)  # parçaları birleştirip saniyede ~15 kez çiz

        def worker():
            try:
                self.conversation.ask(question, on_text)
                GLib.idle_add(render)
            except ai.AssistantError as e:
                msg = str(e)
                GLib.idle_add(lambda: answer_lbl.set_markup(
                    f"<span foreground='#e01b24'>⚠️ {GLib.markup_escape_text(msg)}</span>") and False)
            except Exception as e:
                print(f"Asistan hatası: {e}")
                GLib.idle_add(lambda: answer_lbl.set_markup(
                    "<span foreground='#e01b24'>⚠️ Beklenmeyen bir hata oluştu. Tekrar deneyin.</span>") and False)
            finally:
                GLib.idle_add(lambda: self.set_busy(False) or False)

        threading.Thread(target=worker, daemon=True).start()
