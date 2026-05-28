import tkinter as tk
from tkinter import simpledialog, messagebox
import pyautogui
from PIL import ImageTk, Image
import os


class CaptureTool:
    """
    Overlay โปร่งใสทับหน้าจอ ให้ user ลาก box เลือก region
    บันทึก PNG ไปยัง save_dir
    """

    def __init__(self, root: tk.Tk, save_dir: str, on_done=None, on_cancel=None):
        self._root = root
        self._save_dir = save_dir
        self._on_done = on_done
        self._on_cancel = on_cancel
        os.makedirs(save_dir, exist_ok=True)

    def start(self):
        screenshot = pyautogui.screenshot()
        self._screenshot = screenshot

        self._overlay = tk.Toplevel(self._root)
        self._overlay.attributes("-fullscreen", True)
        self._overlay.attributes("-alpha", 0.3)
        self._overlay.attributes("-topmost", True)
        self._overlay.configure(bg="black")
        self._overlay.title("ลาก Box เพื่อ Capture")

        self._canvas = tk.Canvas(
            self._overlay,
            cursor="cross",
            bg="black",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        self._bg_img = ImageTk.PhotoImage(screenshot)
        self._canvas.create_image(0, 0, anchor="nw", image=self._bg_img)

        # ข้อความแนะนำ
        sw = self._overlay.winfo_screenwidth()
        self._canvas.create_text(
            sw // 2, 30,
            text="ลาก Box เพื่อเลือก Region  |  กด ESC เพื่อยกเลิก",
            fill="white", font=("Segoe UI", 13, "bold"),
        )

        self._start_x = self._start_y = 0
        self._rect = None

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        # bind ESC ทั้ง overlay และ canvas เพื่อให้แน่ใจว่า focus ไม่สำคัญ
        self._overlay.bind("<Escape>", lambda e: self._cancel())
        self._canvas.bind("<Escape>", lambda e: self._cancel())
        self._canvas.focus_set()

    def _on_press(self, event):
        self._start_x = event.x
        self._start_y = event.y
        if self._rect:
            self._canvas.delete(self._rect)
        self._rect = self._canvas.create_rectangle(
            self._start_x, self._start_y,
            self._start_x, self._start_y,
            outline="#00ff00", width=2,
        )

    def _on_drag(self, event):
        self._canvas.coords(
            self._rect,
            self._start_x, self._start_y,
            event.x, event.y,
        )

    def _on_release(self, event):
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)

        if x2 - x1 < 5 or y2 - y1 < 5:
            return

        self._overlay.destroy()
        self._save_region(x1, y1, x2, y2)

    def _cancel(self):
        self._overlay.destroy()
        if self._on_cancel:
            self._on_cancel()

    def _save_region(self, x1, y1, x2, y2):
        try:
            cropped = self._screenshot.crop((x1, y1, x2, y2))
        except Exception as e:
            messagebox.showerror("Capture Error", f"ครอปรูปไม่สำเร็จ: {e}", parent=self._root)
            if self._on_cancel:
                self._on_cancel()
            return

        name = simpledialog.askstring(
            "ตั้งชื่อรูป",
            "ชื่อไฟล์ (ไม่ต้องมี .png):",
            parent=self._root,
        )
        if not name:
            if self._on_cancel:
                self._on_cancel()
            return

        filename = f"{name}.png"
        path = os.path.join(self._save_dir, filename)
        try:
            cropped.save(path)
        except Exception as e:
            messagebox.showerror("Save Error", f"บันทึกรูปไม่สำเร็จ: {e}", parent=self._root)
            if self._on_cancel:
                self._on_cancel()
            return

        if self._on_done:
            self._on_done(path)
