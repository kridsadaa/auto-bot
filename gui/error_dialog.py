import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os

from engine.image_matcher import ImageNotFoundError


THUMB_SIZE = (320, 200)


def _pil_to_tk(img: Image.Image, size: tuple) -> ImageTk.PhotoImage:
    img = img.copy()
    img.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class ErrorDialog(tk.Toplevel):
    """
    Dialog แสดงเมื่อ bot หา image ไม่เจอ
    ผู้ใช้สามารถ: Capture ใหม่ | ข้าม step | Stop bot
    คืนค่า: "retry" | "skip" | "stop"
    """

    def __init__(self, parent, error: ImageNotFoundError, on_capture_new=None):
        super().__init__(parent)
        self.title("หารูปไม่เจอ")
        self.resizable(False, False)
        self.grab_set()

        self._error = error
        self._on_capture_new = on_capture_new
        self._result = "stop"

        self._build()
        self._center()

    def _build(self):
        pad = dict(padx=10, pady=6)

        header = tk.Label(
            self,
            text=f"หารูปไม่เจอบนหน้าจอ",
            font=("Segoe UI", 12, "bold"),
            fg="#f44747",
        )
        header.pack(**pad)

        filename = os.path.basename(self._error.template_path)
        tk.Label(self, text=f"ไฟล์: {filename}", font=("Consolas", 9)).pack()

        img_frame = tk.Frame(self)
        img_frame.pack(padx=10, pady=6)

        # รูป reference (ที่ใช้หา)
        left = tk.Frame(img_frame)
        left.pack(side="left", padx=6)
        tk.Label(left, text="รูปที่ใช้หา (reference)", font=("Segoe UI", 9, "bold")).pack()
        self._ref_label = tk.Label(left, bg="#333", width=THUMB_SIZE[0], height=THUMB_SIZE[1])
        self._ref_label.pack()
        self._load_reference()

        # รูปหน้าจอปัจจุบัน
        right = tk.Frame(img_frame)
        right.pack(side="left", padx=6)
        tk.Label(right, text="หน้าจอปัจจุบัน", font=("Segoe UI", 9, "bold")).pack()
        self._screen_label = tk.Label(right, bg="#333", width=THUMB_SIZE[0], height=THUMB_SIZE[1])
        self._screen_label.pack()
        self._load_current_screen()

        # ปุ่ม
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="Capture ใหม่", width=16,
            bg="#0e639c", fg="white", font=("Segoe UI", 10, "bold"),
            command=self._capture_new,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_frame, text="ข้าม Step นี้", width=14,
            command=self._skip,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_frame, text="Stop Bot", width=12,
            bg="#f44747", fg="white",
            command=self._stop,
        ).pack(side="left", padx=6)

    def _load_reference(self):
        try:
            img = Image.open(self._error.template_path)
            self._ref_img = _pil_to_tk(img, THUMB_SIZE)
            self._ref_label.configure(image=self._ref_img)
        except Exception:
            self._ref_label.configure(text="(ไม่มีรูป)")

    def _load_current_screen(self):
        if self._error.current_screenshot:
            self._screen_img = _pil_to_tk(self._error.current_screenshot, THUMB_SIZE)
            self._screen_label.configure(image=self._screen_img)

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _capture_new(self):
        self.destroy()
        if self._on_capture_new:
            self._on_capture_new(self._error.template_path)
        self._result = "retry"

    def _skip(self):
        self._result = "skip"
        self.destroy()

    def _stop(self):
        self._result = "stop"
        self.destroy()

    def get_result(self) -> str:
        return self._result


def show_error_dialog(parent, error: ImageNotFoundError, on_capture_new=None) -> str:
    """เปิด dialog และรอผล คืน 'retry' | 'skip' | 'stop'"""
    dialog = ErrorDialog(parent, error, on_capture_new)
    parent.wait_window(dialog)
    return dialog.get_result()
