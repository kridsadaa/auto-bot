import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os

import pyautogui


THUMB_SIZE = (320, 200)

INJECT_ACTIONS = ["key", "click", "wait"]
KEY_OPTIONS = ["enter", "tab", "escape", "f1", "f2", "f3", "f4", "f5",
               "f12", "delete", "backspace", "up", "down", "left", "right"]


def _pil_to_tk(img: Image.Image, size: tuple) -> ImageTk.PhotoImage:
    img = img.copy()
    img.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


class DebugConsole(tk.Toplevel):
    """
    Debug Console — เด้งเมื่อ step พลาด (image-not-found หรือ action error)
    ให้ผู้ใช้กู้คืนแบบเรียลไทม์ คืน decision dict:
      {"decision": "retry" | "skip" | "restart" | "stop"}
      {"decision": "inject", "steps": [...], "then": "retry"}
    """

    def __init__(self, parent, context: dict, on_recapture=None):
        super().__init__(parent)
        self.title("Debug Console — บอทหยุดเพราะ error")
        self.resizable(False, False)
        self.grab_set()

        self._ctx = context
        self._on_recapture = on_recapture
        self._result = {"decision": "stop"}
        self._inject_steps: list = []

        self._build()
        self._center()

    # ─── layout ──────────────────────────────────────────────────────────────
    def _build(self):
        pad = dict(padx=10, pady=4)
        is_img = self._ctx.get("is_image_error")
        step = self._ctx.get("step", {})

        tk.Label(self, text="⛔ บอทหยุดทำงาน", font=("Segoe UI", 13, "bold"),
                 fg="#f44747").pack(**pad)
        tk.Label(self, text=self._ctx.get("message", ""), wraplength=660,
                 fg="#cccccc").pack(padx=10)
        tk.Label(self, text=f"Step #{self._ctx.get('index', 0) + 1}: {step.get('action', '?')}",
                 font=("Consolas", 9)).pack(pady=(2, 6))

        self._build_images(is_img)
        self._build_inject_panel()
        self._build_buttons(is_img)

    def _build_images(self, is_img: bool):
        frame = tk.Frame(self)
        frame.pack(padx=10, pady=6)

        if is_img and self._ctx.get("template_path"):
            left = tk.Frame(frame)
            left.pack(side="left", padx=6)
            tk.Label(left, text="รูปที่ใช้หา (reference)", font=("Segoe UI", 9, "bold")).pack()
            ref_label = tk.Label(left, bg="#333", width=THUMB_SIZE[0], height=THUMB_SIZE[1])
            ref_label.pack()
            try:
                self._ref_img = _pil_to_tk(Image.open(self._ctx["template_path"]), THUMB_SIZE)
                ref_label.configure(image=self._ref_img)
            except Exception:
                ref_label.configure(text="(ไม่มีรูป)")

        right = tk.Frame(frame)
        right.pack(side="left", padx=6)
        tk.Label(right, text="หน้าจอปัจจุบัน", font=("Segoe UI", 9, "bold")).pack()
        screen_label = tk.Label(right, bg="#333", width=THUMB_SIZE[0], height=THUMB_SIZE[1])
        screen_label.pack()
        shot = self._ctx.get("screenshot")
        if shot is None:
            try:
                shot = pyautogui.screenshot()
            except Exception:
                shot = None
        if shot is not None:
            self._screen_img = _pil_to_tk(shot, THUMB_SIZE)
            screen_label.configure(image=self._screen_img)

    def _build_inject_panel(self):
        wrap = tk.LabelFrame(self, text="แทรกคำสั่งกู้ภัย (Inject — รันนี้พอ)",
                             fg="#0e639c", font=("Segoe UI", 9, "bold"))
        wrap.pack(fill="x", padx=10, pady=4)

        row = tk.Frame(wrap)
        row.pack(fill="x", padx=6, pady=4)
        self._inj_action = tk.StringVar(value="key")
        ttk.Combobox(row, textvariable=self._inj_action, values=INJECT_ACTIONS,
                     state="readonly", width=8).pack(side="left", padx=2)
        self._inj_value = tk.StringVar(value="enter")
        tk.Entry(row, textvariable=self._inj_value, width=18).pack(side="left", padx=2)
        tk.Label(row, text="key: ชื่อคีย์ · click: x,y · wait: วินาที",
                 fg="gray", font=("Segoe UI", 8)).pack(side="left", padx=4)
        tk.Button(row, text="+ เพิ่ม", command=self._add_inject).pack(side="right", padx=4)

        self._inj_list = tk.Listbox(wrap, height=3, font=("Consolas", 9),
                                    bg="#1e1e1e", fg="#d4d4d4", relief="flat")
        self._inj_list.pack(fill="x", padx=6, pady=(0, 4))

    def _build_buttons(self, is_img: bool):
        bar = tk.Frame(self)
        bar.pack(pady=10)
        if is_img and self._ctx.get("template_path"):
            tk.Button(bar, text="📷 Recapture", width=12, bg="#0e639c", fg="white",
                      command=self._recapture).pack(side="left", padx=4)
        tk.Button(bar, text="↻ Retry", width=10, bg="#4ec9b0",
                  command=lambda: self._done("retry")).pack(side="left", padx=4)
        tk.Button(bar, text="⤼ Inject & Retry", width=14, bg="#dcdcaa",
                  command=self._inject_and_retry).pack(side="left", padx=4)
        tk.Button(bar, text="⏭ ข้าม Step", width=11,
                  command=lambda: self._done("skip")).pack(side="left", padx=4)
        tk.Button(bar, text="↩ Restart Row", width=12,
                  command=lambda: self._done("restart")).pack(side="left", padx=4)
        tk.Button(bar, text="⏹ Stop", width=9, bg="#f44747", fg="white",
                  command=lambda: self._done("stop")).pack(side="left", padx=4)

    # ─── inject builder ──────────────────────────────────────────────────────
    def _add_inject(self):
        action = self._inj_action.get()
        val = self._inj_value.get().strip()
        step = None
        if action == "key" and val:
            step = {"action": "key", "key": val}
        elif action == "click":
            try:
                x, y = (int(p.strip()) for p in val.split(","))
                step = {"action": "click", "x": x, "y": y}
            except Exception:
                messagebox.showwarning("", "click ต้องใส่เป็น x,y เช่น 100,200", parent=self)
                return
        elif action == "wait":
            try:
                step = {"action": "wait", "seconds": float(val)}
            except Exception:
                messagebox.showwarning("", "wait ต้องเป็นตัวเลขวินาที", parent=self)
                return
        if not step:
            return
        self._inject_steps.append(step)
        self._inj_list.insert("end", f" {len(self._inject_steps)}. {step}")

    # ─── result handlers ─────────────────────────────────────────────────────
    def _done(self, decision: str):
        self._result = {"decision": decision}
        self.destroy()

    def _inject_and_retry(self):
        if not self._inject_steps:
            messagebox.showwarning("", "ยังไม่ได้เพิ่มคำสั่ง inject", parent=self)
            return
        self._result = {"decision": "inject", "steps": list(self._inject_steps), "then": "retry"}
        self.destroy()

    def _recapture(self):
        # ปิด console → เปิด capture overlay (main_window จัดการเซฟทับรูป) แล้ว retry
        self.destroy()
        if self._on_recapture:
            self._on_recapture(self._ctx.get("template_path"))
        self._result = {"decision": "retry"}

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict:
        return self._result


def show_debug_console(parent, context: dict, on_recapture=None) -> dict:
    """เปิด Debug Console และรอผล คืน decision dict"""
    dialog = DebugConsole(parent, context, on_recapture)
    parent.wait_window(dialog)
    return dialog.get_result()
