import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import yaml
import os

CONFIG_PATH = "config/bot_config.yaml"

ACTION_TYPES = [
    "click_image", "type", "key", "hotkey", "wait", "screenshot", "scroll", "drag",
    "wait_image", "wait_text", "repeat_key_until", "stop_if_image", "if_image",
]

KEY_OPTIONS = ["enter", "tab", "escape", "f1", "f2", "f3", "f4", "f5", "f6",
               "f7", "f8", "f12", "delete", "backspace", "up", "down", "left", "right"]

UNTIL_OPTIONS = ["image_appears", "image_disappears", "text_filled", "text_empty"]
WAIT_MODE_OPTIONS = ["appear", "disappear"]
TEXT_MODE_OPTIONS = ["filled", "empty"]


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _step_label(step: dict) -> str:
    action = step.get("action", "?")
    if action == "click_image":
        label = f"click_image   →   {os.path.basename(step.get('target', ''))}"
        if step.get("offset_x") is not None and step.get("offset_y") is not None:
            label += f"  @({step['offset_x']},{step['offset_y']})"
        return label
    if action == "type":
        return f"type          →   {step.get('text', '')}"
    if action == "key":
        return f"key           →   {step.get('key', '')}"
    if action == "hotkey":
        return f"hotkey        →   {'+'.join(step.get('keys', []))}"
    if action == "wait":
        return f"wait          →   {step.get('seconds', 1)}s"
    if action == "screenshot":
        return f"screenshot    →   {step.get('path', 'auto')}"
    if action == "scroll":
        return f"scroll        →   {step.get('clicks', 3)} clicks"
    if action == "drag":
        return f"drag          →   ({step.get('src_x')},{step.get('src_y')}) → ({step.get('dst_x')},{step.get('dst_y')})"
    if action == "wait_image":
        return f"wait_image     →   {os.path.basename(step.get('target', ''))}  [{step.get('mode', 'appear')}]"
    if action == "wait_text":
        return f"wait_text      →   region {step.get('region', '?')}  [{step.get('mode', 'filled')}]"
    if action == "repeat_key_until":
        return f"repeat '{step.get('key', 'enter')}'  until  {step.get('until', '?')}"
    if action == "stop_if_image":
        return f"stop_if_image  →   {os.path.basename(step.get('target', ''))}"
    if action == "if_image":
        return (f"if_image       →   {os.path.basename(step.get('target', ''))}  "
                f"(then {len(step.get('then', []))} / else {len(step.get('else', []))})")
    return action


# ─── Position Picker ─────────────────────────────────────────────────────────

class PositionPicker(tk.Toplevel):
    """
    เปิดรูป element ให้ user คลิกเลือก 'จุดที่จะกด' (offset จากมุมซ้ายบนของรูป)
    แสดงจุดสีแดงตรงตำแหน่งที่เลือก
    """

    MAX_W, MAX_H = 720, 520

    def __init__(self, parent, image_path: str, init_offset: tuple = None):
        super().__init__(parent)
        self.title("เลือกจุดกดในรูป")
        self.resizable(False, False)
        self.grab_set()
        self._committed = False
        self._offset = init_offset  # (x, y) เป็น pixel ของรูปต้นฉบับ หรือ None = กลางรูป
        self._dot = None

        img = Image.open(image_path)
        self._ow, self._oh = img.size
        self._scale = min(self.MAX_W / self._ow, self.MAX_H / self._oh, 1.0)
        dw, dh = int(self._ow * self._scale), int(self._oh * self._scale)
        disp = img.resize((dw, dh)) if self._scale != 1.0 else img
        self._photo = ImageTk.PhotoImage(disp)

        self._build(dw, dh)
        start = init_offset if init_offset is not None else (self._ow // 2, self._oh // 2)
        self._set_dot(start[0], start[1], save=False)
        self._center()

    def _build(self, dw, dh):
        tk.Label(
            self, text="คลิกบนรูปเพื่อเลือกจุดที่จะกด  •  จุดสีแดง = ตำแหน่งที่จะคลิก",
            fg="#333",
        ).pack(padx=10, pady=(10, 4))

        self._canvas = tk.Canvas(
            self, width=dw, height=dh, cursor="cross",
            highlightthickness=1, highlightbackground="#888",
        )
        self._canvas.pack(padx=10)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.bind("<Button-1>", self._on_click)

        self._coord_var = tk.StringVar()
        tk.Label(self, textvariable=self._coord_var, fg="#0e639c",
                 font=("Consolas", 9)).pack(pady=4)

        btn = tk.Frame(self)
        btn.pack(pady=8)
        tk.Button(btn, text="บันทึกจุดนี้", width=12, bg="#4ec9b0",
                  command=self._save).pack(side="left", padx=5)
        tk.Button(btn, text="ใช้กลางรูป", width=12,
                  command=self._use_center).pack(side="left", padx=5)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=5)

    def _on_click(self, event):
        ox = max(0, min(int(event.x / self._scale), self._ow - 1))
        oy = max(0, min(int(event.y / self._scale), self._oh - 1))
        self._set_dot(ox, oy, save=True)

    def _set_dot(self, ox: int, oy: int, save: bool):
        dx, dy = ox * self._scale, oy * self._scale
        if self._dot:
            self._canvas.delete(self._dot)
        r = 5
        self._dot = self._canvas.create_oval(
            dx - r, dy - r, dx + r, dy + r,
            fill="#ff3030", outline="white", width=2,
        )
        self._coord_var.set(f"จุดกด (offset): ({ox}, {oy})   จากขนาดรูป {self._ow}x{self._oh}")
        if save:
            self._offset = (ox, oy)

    def _save(self):
        self._committed = True
        self.destroy()

    def _use_center(self):
        self._committed = True
        self._offset = None
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> tuple[bool, tuple | None]:
        """คืน (committed, offset) — committed=False ถ้ายกเลิก"""
        return (self._committed, self._offset)


# ─── Region Picker ───────────────────────────────────────────────────────────

class RegionPicker(tk.Toplevel):
    """ลากกรอบบนหน้าจอเพื่อเลือก region (x, y, w, h) — ใช้กับ OCR"""

    def __init__(self, parent, on_done=None, on_cancel=None):
        super().__init__(parent)
        self._on_done = on_done
        self._on_cancel = on_cancel
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3)
        self.attributes("-topmost", True)
        self.configure(bg="black")

        self._canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        sw = self.winfo_screenwidth()
        self._canvas.create_text(
            sw // 2, 30,
            text="ลากกรอบเลือกพื้นที่อ่านข้อความ (OCR)  |  ESC = ยกเลิก",
            fill="white", font=("Segoe UI", 13, "bold"),
        )

        self._sx = self._sy = 0
        self._rect = None
        self._canvas.bind("<ButtonPress-1>", self._press)
        self._canvas.bind("<B1-Motion>", self._drag)
        self._canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self._cancel())
        self._canvas.focus_set()

    def _press(self, e):
        self._sx, self._sy = e.x, e.y
        if self._rect:
            self._canvas.delete(self._rect)
        self._rect = self._canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline="#00ff00", width=2,
        )

    def _drag(self, e):
        self._canvas.coords(self._rect, self._sx, self._sy, e.x, e.y)

    def _release(self, e):
        x1, y1 = min(self._sx, e.x), min(self._sy, e.y)
        x2, y2 = max(self._sx, e.x), max(self._sy, e.y)
        self.destroy()
        if x2 - x1 >= 3 and y2 - y1 >= 3:
            if self._on_done:
                self._on_done((x1, y1, x2 - x1, y2 - y1))
        elif self._on_cancel:
            self._on_cancel()

    def _cancel(self):
        self.destroy()
        if self._on_cancel:
            self._on_cancel()


# ─── Step Dialog ────────────────────────────────────────────────────────────

class StepDialog(tk.Toplevel):
    """Dialog สำหรับเพิ่มหรือแก้ไข step"""

    def __init__(self, parent, step: dict = None):
        super().__init__(parent)
        self.title("แก้ไข Step" if step else "เพิ่ม Step")
        self.resizable(False, False)
        self.grab_set()
        self._result: dict = None
        self._step = step or {}
        self._fields: dict[str, tk.Variable] = {}
        self._offset_label = None
        ox, oy = self._step.get("offset_x"), self._step.get("offset_y")
        self._offset = (ox, oy) if ox is not None and oy is not None else None
        self._action_var = tk.StringVar(value=self._step.get("action", "click_image"))
        self._build()
        self._center()

    def _build(self):
        pad = dict(padx=10, pady=4)

        # Action type selector
        top = tk.Frame(self)
        top.pack(fill="x", **pad)
        tk.Label(top, text="Action:", width=12, anchor="w").pack(side="left")
        action_menu = ttk.Combobox(
            top, textvariable=self._action_var,
            values=ACTION_TYPES, state="readonly", width=20,
        )
        action_menu.pack(side="left")
        action_menu.bind("<<ComboboxSelected>>", lambda e: self._refresh_fields())

        # Dynamic fields area
        self._fields_frame = tk.Frame(self)
        self._fields_frame.pack(fill="x", padx=10)
        self._refresh_fields()

        # Buttons
        btn = tk.Frame(self)
        btn.pack(pady=10)
        tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=self._save).pack(side="left", padx=6)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=6)

    def _refresh_fields(self):
        for w in self._fields_frame.winfo_children():
            w.destroy()
        self._fields.clear()
        action = self._action_var.get()

        if action == "click_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 10)))
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            self._add_position_row()

        elif action == "type":
            self._add_field("text", "Text / Variable:", default=self._step.get("text", ""))
            tk.Label(self._fields_frame, text="  ตัวอย่าง: {USERNAME}  {TODAY}  {csv.COL}",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "key":
            self._add_dropdown("key", "Key:", KEY_OPTIONS, default=self._step.get("key", "enter"))

        elif action == "hotkey":
            self._add_field("keys", "Keys (คั่นด้วย +):", default="+".join(self._step.get("keys", ["ctrl", "v"])))

        elif action == "wait":
            self._add_field("seconds", "วินาที:", default=str(self._step.get("seconds", 1)))

        elif action == "screenshot":
            self._add_field("path", "บันทึกที่ (ไม่บังคับ):", default=self._step.get("path", ""))

        elif action == "scroll":
            self._add_field("x", "X:", default=str(self._step.get("x", 0)))
            self._add_field("y", "Y:", default=str(self._step.get("y", 0)))
            self._add_field("clicks", "Clicks (+ขึ้น/-ลง):", default=str(self._step.get("clicks", 3)))

        elif action == "drag":
            self._add_field("src_x", "จาก X:", default=str(self._step.get("src_x", 0)))
            self._add_field("src_y", "จาก Y:", default=str(self._step.get("src_y", 0)))
            self._add_field("dst_x", "ถึง X:", default=str(self._step.get("dst_x", 0)))
            self._add_field("dst_y", "ถึง Y:", default=str(self._step.get("dst_y", 0)))

        elif action == "wait_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_dropdown("mode", "รอจน:", WAIT_MODE_OPTIONS,
                               default=self._step.get("mode", "appear"))
            tk.Label(self._fields_frame, text="  appear = รอจนรูปโผล่ / disappear = รอจนรูปหาย",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 15)))
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))

        elif action == "wait_text":
            self._add_region_field("region", "Region (OCR):")
            self._add_dropdown("mode", "รอจนช่อง:", TEXT_MODE_OPTIONS,
                               default=self._step.get("mode", "filled"))
            tk.Label(self._fields_frame, text="  filled = รอจนมีข้อความ / empty = รอจนว่าง",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 15)))
            self._add_field("min_chars", "ขั้นต่ำ (ตัวอักษร):", default=str(self._step.get("min_chars", 1)))

        elif action == "repeat_key_until":
            self._add_dropdown("key", "กดปุ่ม:", KEY_OPTIONS, default=self._step.get("key", "enter"))
            self._add_dropdown("until", "ซ้ำจนกว่า:", UNTIL_OPTIONS,
                               default=self._step.get("until", "image_appears"))
            self._add_field("target", "Image (image_*):", browse=True)
            self._add_region_field("region", "Region (text_*):")
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            self._add_field("max_attempts", "กดสูงสุด (ครั้ง):", default=str(self._step.get("max_attempts", 20)))
            self._add_field("delay", "หน่วงต่อครั้ง (s):", default=str(self._step.get("delay", 0.5)))

        elif action == "stop_if_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            self._add_field("message", "ข้อความเตือน:", default=self._step.get("message", ""))

        elif action == "if_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))

    def _add_field(self, key: str, label: str, default: str = "", browse: bool = False):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=self._step.get(key, default))
        entry = tk.Entry(row, textvariable=var, width=28)
        entry.pack(side="left", padx=4)
        if browse:
            tk.Button(
                row, text="Browse",
                command=lambda: self._browse(var),
            ).pack(side="left", padx=2)
            tk.Button(
                row, text="📷 Capture",
                bg="#569cd6", fg="white",
                command=lambda: self._capture(var),
            ).pack(side="left", padx=2)
        self._fields[key] = var

    def _add_dropdown(self, key: str, label: str, options: list, default: str = ""):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=self._step.get(key, default))
        ttk.Combobox(row, textvariable=var, values=options, width=20).pack(side="left", padx=4)
        self._fields[key] = var

    def _add_region_field(self, key: str, label: str):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        existing = self._step.get(key)
        default = ",".join(str(n) for n in existing) if existing else ""
        var = tk.StringVar(value=default)
        tk.Entry(row, textvariable=var, width=20).pack(side="left", padx=4)
        tk.Button(row, text="เลือก Region", bg="#569cd6", fg="white",
                  command=lambda: self._pick_region(var)).pack(side="left", padx=2)
        tk.Label(self._fields_frame, text="  รูปแบบ: x,y,w,h (เว้นว่างถ้าไม่ใช้)",
                 fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
        self._fields[key] = var

    def _pick_region(self, var: tk.StringVar):
        self.withdraw()

        def on_done(region):
            var.set(",".join(str(n) for n in region))
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_cancel():
            self.deiconify()
            self.lift()

        self.after(200, lambda: RegionPicker(self, on_done=on_done, on_cancel=on_cancel))

    def _add_position_row(self):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="จุดที่จะกด:", width=18, anchor="w").pack(side="left")
        tk.Button(row, text="🎯 เลือกจุดกด", bg="#dcdcaa",
                  command=self._pick_position).pack(side="left", padx=4)
        self._offset_label = tk.Label(row, text="", fg="#0e639c")
        self._offset_label.pack(side="left", padx=6)
        self._update_offset_label()

    def _update_offset_label(self):
        if self._offset_label is None:
            return
        if self._offset is None:
            self._offset_label.configure(text="กลางรูป (default)")
        else:
            self._offset_label.configure(text=f"({self._offset[0]}, {self._offset[1]})")

    def _pick_position(self):
        target = self._fields.get("target")
        path = target.get().strip() if target else ""
        if not path or not os.path.exists(path):
            messagebox.showwarning(
                "", "ต้องเลือก/แคป Image file ก่อน ถึงจะเลือกจุดกดได้", parent=self,
            )
            return
        picker = PositionPicker(self, path, init_offset=self._offset)
        self.wait_window(picker)
        committed, offset = picker.get_result()
        if committed:
            self._offset = offset
            self._update_offset_label()

    def _browse(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="เลือก image", initialdir="elements",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
        )
        if path:
            var.set(os.path.relpath(path))

    def _capture(self, var: tk.StringVar):
        """ซ่อน dialog ชั่วคราว → เปิด capture overlay → คืน path ลงช่อง target"""
        self.withdraw()

        def on_done(path: str):
            var.set(os.path.relpath(path))
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_cancel():
            self.deiconify()
            self.lift()

        from gui.capture_tool import CaptureTool
        tool = CaptureTool(
            root=self,
            save_dir="elements",
            on_done=on_done,
            on_cancel=on_cancel,
        )
        self.after(200, tool.start)

    def _save(self):
        action = self._action_var.get()
        if self._step.get("action") == action:
            step = dict(self._step)
        else:
            step = {"action": action}

        for key, var in self._fields.items():
            val = var.get().strip()
            if not val:
                step.pop(key, None)
                continue
            if key in ("timeout", "seconds", "x", "y", "clicks", "src_x", "src_y",
                       "dst_x", "dst_y", "max_attempts", "min_chars", "delay"):
                try:
                    step[key] = float(val) if "." in val else int(val)
                except ValueError:
                    step[key] = val
            elif key == "confidence":
                try:
                    step[key] = float(val)
                except ValueError:
                    step[key] = 0.85
            elif key == "region":
                parts = [p.strip() for p in val.split(",") if p.strip()]
                try:
                    nums = [int(float(p)) for p in parts]
                    step[key] = nums if len(nums) == 4 else val
                except ValueError:
                    step[key] = val
            elif key == "keys":
                step[key] = [k.strip() for k in val.split("+")]
            else:
                step[key] = val

        if action == "click_image" and self._offset is not None:
            step["offset_x"] = int(self._offset[0])
            step["offset_y"] = int(self._offset[1])

        if action == "if_image":
            step.setdefault("then", [])
            step.setdefault("else", [])

        self._result = step
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


# ─── Loop Settings Dialog ────────────────────────────────────────────────────

class LoopSettingsDialog(tk.Toplevel):
    def __init__(self, parent, loop_name: str, loop_config: dict):
        super().__init__(parent)
        self.title(f"ตั้งค่า Loop: {loop_name}")
        self.resizable(False, False)
        self.grab_set()
        self._result = None
        self._cfg = dict(loop_config)
        self._build()
        self._center()

    def _build(self):
        pad = dict(padx=12, pady=6)

        row1 = tk.Frame(self)
        row1.pack(fill="x", **pad)
        tk.Label(row1, text="CSV Data Source:", width=18, anchor="w").pack(side="left")
        self._csv_var = tk.StringVar(value=self._cfg.get("data_source", ""))
        tk.Entry(row1, textvariable=self._csv_var, width=30).pack(side="left", padx=4)
        tk.Button(row1, text="Browse", command=self._browse_csv).pack(side="left")
        tk.Label(self, text="  เว้นว่างถ้าไม่ต้อง loop CSV", fg="gray", font=("Segoe UI", 8)).pack(anchor="w", padx=12)

        btn = tk.Frame(self)
        btn.pack(pady=10)
        tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=self._save).pack(side="left", padx=6)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=6)

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="เลือก CSV", initialdir="data",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if path:
            self._csv_var.set(os.path.relpath(path))

    def _save(self):
        self._result = dict(self._cfg)
        csv_val = self._csv_var.get().strip()
        if csv_val:
            self._result["data_source"] = csv_val
        else:
            self._result.pop("data_source", None)
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


# ─── Sequence Editor Window ──────────────────────────────────────────────────

class SequenceEditor(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sequence Editor")
        self.geometry("820x560")
        self.resizable(True, True)

        self._config = _load_config()
        self._selected_loop: str = None
        self._build()
        self._refresh_loop_list()

    def _build(self):
        # ─ Left panel: loop list ─
        left = tk.Frame(self, width=200, bg="#1e1e1e")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Loops", bg="#1e1e1e", fg="#9cdcfe",
                 font=("Segoe UI", 10, "bold")).pack(pady=(10, 4))

        self._loop_listbox = tk.Listbox(
            left, bg="#252526", fg="#d4d4d4", selectbackground="#0e639c",
            font=("Consolas", 9), relief="flat", activestyle="none",
        )
        self._loop_listbox.pack(fill="both", expand=True, padx=6)
        self._loop_listbox.bind("<<ListboxSelect>>", self._on_loop_select)

        btn_left = tk.Frame(left, bg="#1e1e1e")
        btn_left.pack(fill="x", pady=6, padx=6)
        tk.Button(btn_left, text="+ Loop ใหม่", command=self._new_loop).pack(fill="x", pady=2)
        tk.Button(btn_left, text="ตั้งค่า Loop", command=self._loop_settings).pack(fill="x", pady=2)
        tk.Button(btn_left, text="ลบ Loop", fg="red", command=self._delete_loop).pack(fill="x", pady=2)

        # ─ Right panel: steps ─
        right = tk.Frame(self, bg="#2d2d2d")
        right.pack(side="left", fill="both", expand=True)

        # Header
        hdr = tk.Frame(right, bg="#1e1e1e", pady=6)
        hdr.pack(fill="x")
        self._loop_label = tk.Label(
            hdr, text="เลือก Loop ทางซ้าย",
            bg="#1e1e1e", fg="white", font=("Segoe UI", 11, "bold"),
        )
        self._loop_label.pack(side="left", padx=12)

        self._csv_label = tk.Label(hdr, text="", bg="#1e1e1e", fg="#ce9178", font=("Segoe UI", 8))
        self._csv_label.pack(side="left", padx=6)

        # Steps listbox
        list_frame = tk.Frame(right, bg="#2d2d2d")
        list_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self._step_listbox = tk.Listbox(
            list_frame, bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
            font=("Consolas", 10), relief="flat", activestyle="none",
        )
        sb = tk.Scrollbar(list_frame, command=self._step_listbox.yview)
        self._step_listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._step_listbox.pack(fill="both", expand=True)
        self._step_listbox.bind("<Double-Button-1>", lambda e: self._edit_step())

        # Step controls
        ctrl = tk.Frame(right, bg="#2d2d2d", pady=6)
        ctrl.pack(fill="x", padx=10)

        tk.Button(ctrl, text="+ Add Step", width=12, bg="#4ec9b0", fg="black",
                  command=self._add_step).pack(side="left", padx=4)
        tk.Button(ctrl, text="Edit", width=8, command=self._edit_step).pack(side="left", padx=4)
        tk.Button(ctrl, text="↑", width=4, command=self._move_up).pack(side="left", padx=2)
        tk.Button(ctrl, text="↓", width=4, command=self._move_down).pack(side="left", padx=2)
        tk.Button(ctrl, text="Del", width=6, fg="red", command=self._delete_step).pack(side="left", padx=4)

        # Save
        save_bar = tk.Frame(right, bg="#007acc", pady=4)
        save_bar.pack(fill="x", side="bottom")
        tk.Button(
            save_bar, text="Save Config", width=14,
            bg="#0e639c", fg="white", font=("Segoe UI", 10, "bold"),
            command=self._save_config,
        ).pack(side="right", padx=10)
        self._save_status = tk.Label(save_bar, text="", bg="#007acc", fg="white")
        self._save_status.pack(side="left", padx=10)

    # ─── Loop management ────────────────────────────────────────────────────

    def _refresh_loop_list(self):
        self._loop_listbox.delete(0, "end")
        for name in self._config.get("loops", {}):
            self._loop_listbox.insert("end", f"  {name}")

    def _on_loop_select(self, event=None):
        sel = self._loop_listbox.curselection()
        if not sel:
            return
        name = self._loop_listbox.get(sel[0]).strip()
        self._selected_loop = name
        self._loop_label.configure(text=f"Loop: {name}")

        ds = self._config["loops"][name].get("data_source", "")
        self._csv_label.configure(text=f"CSV: {ds}" if ds else "")

        self._refresh_steps()

    def _new_loop(self):
        name = tk.simpledialog.askstring("Loop ใหม่", "ชื่อ loop:", parent=self)
        if not name:
            return
        name = name.strip()
        if name in self._config.setdefault("loops", {}):
            messagebox.showwarning("ซ้ำ", f'มี loop "{name}" อยู่แล้ว')
            return
        self._config["loops"][name] = {"steps": []}
        self._refresh_loop_list()
        # เลือก loop ใหม่
        names = list(self._config["loops"].keys())
        idx = names.index(name)
        self._loop_listbox.selection_clear(0, "end")
        self._loop_listbox.selection_set(idx)
        self._on_loop_select()

    def _loop_settings(self):
        if not self._selected_loop:
            return
        loop_cfg = self._config["loops"][self._selected_loop]
        dlg = LoopSettingsDialog(self, self._selected_loop, loop_cfg)
        self.wait_window(dlg)
        if dlg.get_result() is not None:
            self._config["loops"][self._selected_loop] = dlg.get_result()
            self._config["loops"][self._selected_loop].setdefault("steps", [])
            self._on_loop_select()

    def _delete_loop(self):
        if not self._selected_loop:
            return
        if messagebox.askyesno("ลบ", f'ลบ loop "{self._selected_loop}"?', parent=self):
            del self._config["loops"][self._selected_loop]
            self._selected_loop = None
            self._loop_label.configure(text="เลือก Loop ทางซ้าย")
            self._step_listbox.delete(0, "end")
            self._refresh_loop_list()

    # ─── Step management ────────────────────────────────────────────────────

    def _steps(self) -> list:
        if not self._selected_loop:
            return []
        return self._config["loops"][self._selected_loop].setdefault("steps", [])

    def _refresh_steps(self):
        self._step_listbox.delete(0, "end")
        for i, step in enumerate(self._steps(), 1):
            self._step_listbox.insert("end", f"  {i:2d}.  {_step_label(step)}")

    def _add_step(self):
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ก่อน")
            return
        dlg = StepDialog(self)
        self.wait_window(dlg)
        if dlg.get_result():
            sel = self._step_listbox.curselection()
            idx = sel[0] + 1 if sel else len(self._steps())
            self._steps().insert(idx, dlg.get_result())
            self._refresh_steps()
            self._step_listbox.selection_set(idx)

    def _edit_step(self):
        sel = self._step_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = StepDialog(self, self._steps()[idx])
        self.wait_window(dlg)
        if dlg.get_result():
            self._steps()[idx] = dlg.get_result()
            self._refresh_steps()
            self._step_listbox.selection_set(idx)

    def _move_up(self):
        sel = self._step_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        steps = self._steps()
        steps[idx - 1], steps[idx] = steps[idx], steps[idx - 1]
        self._refresh_steps()
        self._step_listbox.selection_set(idx - 1)

    def _move_down(self):
        sel = self._step_listbox.curselection()
        steps = self._steps()
        if not sel or sel[0] >= len(steps) - 1:
            return
        idx = sel[0]
        steps[idx], steps[idx + 1] = steps[idx + 1], steps[idx]
        self._refresh_steps()
        self._step_listbox.selection_set(idx + 1)

    def _delete_step(self):
        sel = self._step_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if messagebox.askyesno("ลบ", f"ลบ step {idx+1}?", parent=self):
            self._steps().pop(idx)
            self._refresh_steps()

    # ─── Save ────────────────────────────────────────────────────────────────

    def _save_config(self):
        try:
            _save_config(self._config)
            self._save_status.configure(text="บันทึกแล้ว")
            self.after(2000, lambda: self._save_status.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


import tkinter.simpledialog
