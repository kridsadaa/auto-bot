import tkinter as tk
from datetime import datetime


class LogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build()

    def _build(self):
        self._text = tk.Text(
            self,
            state="disabled",
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
        )
        scrollbar = tk.Scrollbar(self, command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)

        self._text.tag_config("info", foreground="#9cdcfe")
        self._text.tag_config("ok", foreground="#4ec9b0")
        self._text.tag_config("warn", foreground="#ce9178")
        self._text.tag_config("error", foreground="#f44747")
        self._text.tag_config("time", foreground="#569cd6")

        scrollbar.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True)

    def log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.configure(state="normal")
        self._text.insert("end", f"[{ts}] ", "time")
        self._text.insert("end", f"{message}\n", level)
        self._text.configure(state="disabled")
        self._text.see("end")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
