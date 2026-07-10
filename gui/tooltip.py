import tkinter as tk

SHOW_DELAY_MS = 500
WRAP_LENGTH = 320


class Tooltip:
    """กล่องคำอธิบายเล็กๆ ที่โผล่ขึ้นเมื่อชี้เมาส์ค้างบน widget"""

    def __init__(self, widget, text: str, delay_ms: int = SHOW_DELAY_MS):
        self._widget = widget
        self._text = text
        self._delay_ms = delay_ms
        self._after_id = None
        self._popup: tk.Toplevel = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        widget.bind("<Destroy>", self._on_leave, add="+")

    def set_text(self, text: str):
        self._text = text

    def _on_enter(self, _event=None):
        self._cancel_pending()
        self._after_id = self._widget.after(self._delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel_pending()
        self._hide()

    def _cancel_pending(self):
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        if self._popup is not None or not self._text:
            return
        try:
            x = self._widget.winfo_rootx() + 12
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 8
        except tk.TclError:
            return

        popup = tk.Toplevel(self._widget)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#3c3c3c")

        label = tk.Label(
            popup, text=self._text, justify="left", wraplength=WRAP_LENGTH,
            bg="#3c3c3c", fg="#e6e6e6", font=("Segoe UI", 9),
            relief="solid", borderwidth=1, padx=8, pady=4,
        )
        label.pack()

        popup.update_idletasks()
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        pop_w = popup.winfo_width()
        pop_h = popup.winfo_height()
        if x + pop_w > screen_w:
            x = screen_w - pop_w - 4
        if y + pop_h > screen_h:
            y = self._widget.winfo_rooty() - pop_h - 8

        popup.geometry(f"+{x}+{y}")
        self._popup = popup

    def _hide(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None


def add_tooltip(widget, text: str, delay_ms: int = SHOW_DELAY_MS) -> Tooltip:
    """ผูก tooltip เข้ากับ widget แล้วคืนอินสแตนซ์ (เผื่ออยาก set_text ทีหลัง)"""
    return Tooltip(widget, text, delay_ms=delay_ms)
