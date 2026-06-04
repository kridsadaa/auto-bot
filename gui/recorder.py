"""
Recorder — อัดการคลิก/พิมพ์เป็น step อัตโนมัติ
mode="image": คลิก → ครอปรูปรอบจุด → สร้าง click_image (ทนทานกว่าพิกัด)
mode="coords": คลิก → พิกัด x,y (เปราะกว่า)
กด F10 เพื่อหยุดอัด
"""
import os
import time
import tkinter as tk

import pyautogui
from pynput import keyboard as _kb, mouse as _ms

STOP_KEY = _kb.Key.f10
CROP_RADIUS = 30  # ครึ่งหนึ่งของกรอบครอป → กรอบ 60×60 รอบจุดคลิก

# pynput special key → ชื่อคีย์ของระบบ (ตรงกับ pyautogui.press)
SPECIAL_KEYS = {
    _kb.Key.enter: "enter",
    _kb.Key.tab: "tab",
    _kb.Key.esc: "esc",
    _kb.Key.backspace: "backspace",
    _kb.Key.delete: "delete",
    _kb.Key.up: "up",
    _kb.Key.down: "down",
    _kb.Key.left: "left",
    _kb.Key.right: "right",
    _kb.Key.home: "home",
    _kb.Key.end: "end",
    _kb.Key.page_up: "pageup",
    _kb.Key.page_down: "pagedown",
}
# function keys f1..f12 (เว้น f10 = ปุ่มหยุด)
for _i in range(1, 13):
    _k = getattr(_kb.Key, f"f{_i}", None)
    if _k is not None and _k != STOP_KEY:
        SPECIAL_KEYS[_k] = f"f{_i}"


def events_to_steps(events: list) -> list:
    """แปลง event ที่อัดได้ → list ของ step
    event: ("click", x, y) | ("char", ch) | ("key", name)
    - ตัวอักษรติดกันรวมเป็น type เดียว (method=type)
    - คลิก/special key จะ flush buffer ของ type ก่อน
    """
    steps: list = []
    buf: list = []

    def flush():
        if buf:
            steps.append({"action": "type", "text": "".join(buf), "method": "type"})
            buf.clear()

    for ev in events:
        kind = ev[0]
        if kind == "char":
            buf.append(ev[1])
        elif kind == "key":
            flush()
            steps.append({"action": "key", "key": ev[1]})
        elif kind == "click":
            flush()
            steps.append({"action": "click", "x": ev[1], "y": ev[2]})
        elif kind == "click_image":
            flush()
            # ครอปให้จุดคลิกอยู่กลางรูป → click_image คลิกกลางรูป = จุดเดิมพอดี (ไม่ต้อง offset)
            steps.append({"action": "click_image", "target": ev[1]})
    flush()
    return steps


class Recorder:
    """อัด mouse click + keystroke ทั่วทั้งจอ จนกด F10 → คืน steps ผ่าน on_done"""

    def __init__(self, parent, on_done, mode: str = "image", capture_dir: str = "elements"):
        self._parent = parent
        self._on_done = on_done
        self._mode = mode  # "image" (click_image) | "coords" (click x,y)
        self._capture_dir = capture_dir
        self._events: list = []
        self._mouse: _ms.Listener = None
        self._kb_listener: _kb.Listener = None
        self._indicator: tk.Toplevel = None

    def start(self):
        self._show_indicator()
        self._mouse = _ms.Listener(on_click=self._on_click)
        self._kb_listener = _kb.Listener(on_press=self._on_press)
        self._mouse.start()
        self._kb_listener.start()

    def _show_indicator(self):
        tip = tk.Toplevel(self._parent)
        tip.attributes("-topmost", True)
        tip.overrideredirect(True)
        tk.Label(tip, text="● REC — กด F10 เพื่อหยุด", bg="#a00000", fg="white",
                 font=("Segoe UI", 11, "bold"), padx=16, pady=8).pack()
        sw = tip.winfo_screenwidth()
        tip.geometry(f"+{sw // 2 - 90}+10")
        self._indicator = tip

    def _stop(self):
        if self._mouse:
            self._mouse.stop()
        if self._indicator is not None:
            # ทำงานบน main thread ผ่าน after (ถูกเรียกจาก listener thread)
            self._parent.after(0, self._indicator.destroy)
        steps = events_to_steps(self._events)
        self._parent.after(0, lambda: self._on_done(steps))

    def _on_click(self, x, y, button, pressed):
        if not (pressed and button == _ms.Button.left):
            return
        x, y = int(x), int(y)
        if self._mode == "image":
            path = self._capture_click_image(x, y)
            if path:
                self._events.append(("click_image", path))
                return
        self._events.append(("click", x, y))  # coords mode หรือ fallback

    def _capture_click_image(self, x: int, y: int) -> str | None:
        """ครอปกรอบ 60×60 รอบจุดคลิก (จุดอยู่กลาง) เซฟเป็น element image → คืน relpath"""
        try:
            os.makedirs(self._capture_dir, exist_ok=True)
            shot = pyautogui.screenshot()
            w, h = shot.size
            left = max(0, x - CROP_RADIUS)
            top = max(0, y - CROP_RADIUS)
            right = min(w, x + CROP_RADIUS)
            bottom = min(h, y + CROP_RADIUS)
            if right - left < 4 or bottom - top < 4:
                return None
            crop = shot.crop((left, top, right, bottom))
            path = os.path.join(self._capture_dir, f"rec_{int(time.time() * 1000)}.png")
            crop.save(path)
            return os.path.relpath(path)
        except Exception:
            return None

    def _on_press(self, key):
        if key == STOP_KEY:
            self._stop()
            return False  # หยุด keyboard listener
        if key == _kb.Key.space:
            self._events.append(("char", " "))
            return
        name = SPECIAL_KEYS.get(key)
        if name:
            self._events.append(("key", name))
            return
        ch = getattr(key, "char", None)
        if ch:
            self._events.append(("char", ch))
