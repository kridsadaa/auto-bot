import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import yaml
import os
import copy

CONFIG_PATH = "config/bot_config.yaml"

ACTION_TYPES = [
    "click_image", "type", "key", "hotkey", "wait", "screenshot", "scroll", "drag",
    "wait_image", "wait_text", "repeat_key_until", "stop_if_image",
    "skip_row_if_image", "skip_row", "if_image", "switch_image",
    "write_row",
    "click_element", "set_element_text", "wait_element",
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
    if action == "skip_row_if_image":
        return f"skip_row_if_image  →   {os.path.basename(step.get('target', ''))}"
    if action == "skip_row":
        return "skip_row       →   ข้ามไปแถว CSV ถัดไป"
    if action == "if_image":
        return (f"if_image       →   {os.path.basename(step.get('target', ''))}  "
                f"(then {len(step.get('then', []))} / else {len(step.get('else', []))})")
    if action == "switch_image":
        return (f"switch_image   →   {len(step.get('cases', []))} cases "
                f"(+default {len(step.get('default', []))})")
    if action == "write_row":
        cols = step.get("columns", [])
        n = len(cols) if isinstance(cols, list) else len(str(cols).split(","))
        return f"write_row      →   {os.path.basename(str(step.get('path', '?')))}  ({n} cols)"
    if action in ("click_element", "set_element_text", "wait_element"):
        who = step.get("name") or step.get("auto_id") or step.get("control_type") or "?"
        if action == "set_element_text":
            return f"set_element_text → {who} = {step.get('text', '')}"
        return f"{action}  →   {who}"
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

    def __init__(self, parent, step: dict = None, csv_columns: list = None):
        super().__init__(parent)
        self.title("แก้ไข Step" if step else "เพิ่ม Step")
        self.resizable(False, False)
        self.grab_set()
        self._result: dict = None
        self._step = step or {}
        self._csv_columns = csv_columns or []  # คอลัมน์ CSV ของ loop (สำหรับ dropdown ในช่อง type)
        self._fields: dict[str, tk.Variable] = {}
        self._offset_label = None
        ox, oy = self._step.get("offset_x"), self._step.get("offset_y")
        self._offset = (ox, oy) if ox is not None and oy is not None else None
        # โครงสร้างสาขา (แก้บนสำเนา → ถ้า cancel ของเดิมไม่โดนแตะ; เขียนกลับตอน _save)
        self._then = copy.deepcopy(self._step.get("then", []))
        self._else = copy.deepcopy(self._step.get("else", []))
        self._cases = copy.deepcopy(self._step.get("cases", []))
        self._default = copy.deepcopy(self._step.get("default", []))
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
        # action ที่มีสาขาซ้อน ต้องใช้พื้นที่มาก → ให้ปรับขนาดได้
        self.resizable(action in ("if_image", "switch_image"),
                       action in ("if_image", "switch_image"))

        if action == "click_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 10)))
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            self._add_position_row()

        elif action == "type":
            self._add_field("text", "Text / Variable:", default=self._step.get("text", ""))
            tk.Label(self._fields_frame, text="  ตัวอย่าง: {USERNAME}  {TODAY}  {csv.COL}",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_csv_column_picker()
            self._add_dropdown("method", "วิธีพิมพ์:", ["paste", "type"],
                               default=self._step.get("method", "paste"))
            tk.Label(self._fields_frame,
                     text="  paste = วางผ่าน clipboard (เร็ว, เหมาะ SAP) / type = จำลองกดคีย์ทีละตัว (แอปที่บล็อก paste)",
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

        elif action == "skip_row_if_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            self._add_field("message", "หมายเหตุ (log):", default=self._step.get("message", ""))
            tk.Label(self._fields_frame,
                     text="  เจอรูปนี้ → ข้ามแถว CSV ปัจจุบัน ไปแถวถัดไป (ใช้กับ loop ที่มี CSV)",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "skip_row":
            self._add_field("message", "หมายเหตุ (log):", default=self._step.get("message", ""))
            tk.Label(self._fields_frame,
                     text="  ข้ามแถว CSV ปัจจุบันทันที (step ที่เหลือในแถวนี้จะไม่ถูกทำ)",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "if_image":
            self._add_field("target", "Image file:", browse=True)
            self._add_field("confidence", "Confidence:", default=str(self._step.get("confidence", 0.85)))
            NestedStepsEditor(self._fields_frame, self._then, "THEN — ทำเมื่อ 'เจอ' รูป:",
                              height=4, csv_columns=self._csv_columns).pack(fill="both", expand=True, pady=(8, 2))
            NestedStepsEditor(self._fields_frame, self._else, "ELSE — ทำเมื่อ 'ไม่เจอ' รูป:",
                              height=4, csv_columns=self._csv_columns).pack(fill="both", expand=True, pady=2)

        elif action == "switch_image":
            self._add_field("confidence", "Confidence (default):", default=str(self._step.get("confidence", 0.85)))
            tk.Label(self._fields_frame,
                     text="  ไล่เช็ก case จากบนลงล่าง — เจอรูปแรกที่ตรง รัน case นั้น; ไม่เข้าเลย → default",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._build_cases_editor()
            NestedStepsEditor(self._fields_frame, self._default, "DEFAULT — ทำเมื่อไม่เข้า case ใด:",
                              height=3, csv_columns=self._csv_columns).pack(fill="both", expand=True, pady=(8, 2))

        elif action == "write_row":
            row = tk.Frame(self._fields_frame)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="ไฟล์ปลายทาง:", width=18, anchor="w").pack(side="left")
            pvar = tk.StringVar(value=self._step.get("path", ""))
            tk.Entry(row, textvariable=pvar, width=28).pack(side="left", padx=4)
            tk.Button(row, text="Browse", command=lambda: self._browse_save(pvar)).pack(side="left", padx=2)
            self._fields["path"] = pvar
            self._add_field("columns", "คอลัมน์ (คั่น ,):", default=self._list_default("columns"))
            tk.Label(self._fields_frame,
                     text="  ค่าที่จะเขียนต่อท้ายไฟล์ เช่น {csv.MATERIAL_CODE},{csv.QTY},{TODAY}",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("header", "หัวคอลัมน์ (ออปชัน):", default=self._list_default("header"))
            tk.Label(self._fields_frame,
                     text="  เขียนเป็นแถวแรกถ้าไฟล์ยังว่าง เช่น MATERIAL_CODE,QTY,DATE",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action in ("click_element", "set_element_text", "wait_element"):
            if action == "set_element_text":
                self._add_field("text", "Text / Variable:", default=self._step.get("text", ""))
            self._add_element_fields()

    def _add_element_fields(self):
        tk.Label(self._fields_frame,
                 text="  เล็ง element ด้วย UI Automation — กรอกเท่าที่จำเป็น (ว่าง = ไม่ใช้เกณฑ์นั้น)",
                 fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
        self._add_field("window", "Window (regex):", default=self._step.get("window", ""))
        self._add_field("auto_id", "AutomationId:", default=self._step.get("auto_id", ""))
        self._add_field("name", "Name:", default=self._step.get("name", ""))
        self._add_field("control_type", "Control type:", default=self._step.get("control_type", ""))
        self._add_field("class_name", "Class name:", default=self._step.get("class_name", ""))
        self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 10)))
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=4)
        tk.Button(row, text="🔍 จิ้ม element", bg="#dcdcaa",
                  command=self._inspect_element).pack(side="left", padx=4)
        tk.Label(row, text="กดแล้วเอาเมาส์ชี้ element เป้าหมาย (มีนับถอยหลัง)",
                 fg="gray", font=("Segoe UI", 8)).pack(side="left", padx=4)

    def _inspect_element(self):
        self.withdraw()

        def do():
            try:
                import win32api
                from engine import ui_element
                x, y = win32api.GetCursorPos()
                props = ui_element.element_from_point(x, y)
            except Exception as e:
                self._deiconify_focus()
                messagebox.showwarning("Inspect", f"อ่าน element ไม่ได้: {e}", parent=self)
                return
            for key in ("window", "auto_id", "name", "control_type", "class_name"):
                if key in self._fields and props.get(key):
                    self._fields[key].set(str(props[key]))
            self._deiconify_focus()

        self._countdown_then(3, do)

    def _countdown_then(self, secs: int, fn):
        tip = tk.Toplevel(self.master)
        tip.attributes("-topmost", True)
        tip.overrideredirect(True)
        lbl = tk.Label(tip, text="", bg="#222", fg="white",
                       font=("Segoe UI", 14, "bold"), padx=20, pady=10)
        lbl.pack()
        sw = tip.winfo_screenwidth()
        tip.geometry(f"+{sw // 2 - 120}+40")

        def tick(n):
            if n <= 0:
                tip.destroy()
                fn()
                return
            lbl.configure(text=f"เอาเมาส์ชี้ element… {n}")
            tip.after(1000, lambda: tick(n - 1))

        tick(secs)

    def _deiconify_focus(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _list_default(self, key: str) -> str:
        v = self._step.get(key, [])
        return ",".join(v) if isinstance(v, list) else str(v)

    def _browse_save(self, var: tk.StringVar):
        path = filedialog.asksaveasfilename(
            title="ไฟล์ปลายทาง", initialdir="data", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"), ("All", "*.*")],
        )
        if path:
            var.set(os.path.relpath(path))

    def _build_cases_editor(self):
        """ตัวจัดการ list ของ case (แต่ละ case = target + steps) สำหรับ switch_image"""
        wrap = tk.LabelFrame(self._fields_frame, text="Cases (ตามลำดับความสำคัญ)",
                             fg="#0e639c", font=("Segoe UI", 9, "bold"))
        wrap.pack(fill="both", expand=True, pady=(8, 2))

        self._cases_listbox = tk.Listbox(
            wrap, height=4, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
            relief="flat", activestyle="none",
        )
        self._cases_listbox.pack(fill="both", expand=True, padx=4, pady=2)
        self._cases_listbox.bind("<Double-Button-1>", lambda e: self._edit_case())

        ctrl = tk.Frame(wrap)
        ctrl.pack(fill="x", padx=4, pady=2)
        tk.Button(ctrl, text="+ Case", width=8, command=self._add_case).pack(side="left", padx=2)
        tk.Button(ctrl, text="Edit", width=6, command=self._edit_case).pack(side="left", padx=2)
        tk.Button(ctrl, text="↑", width=3, command=lambda: self._move_case(-1)).pack(side="left", padx=1)
        tk.Button(ctrl, text="↓", width=3, command=lambda: self._move_case(1)).pack(side="left", padx=1)
        tk.Button(ctrl, text="Del", width=5, fg="red", command=self._del_case).pack(side="left", padx=2)
        self._refresh_cases()

    def _refresh_cases(self):
        self._cases_listbox.delete(0, "end")
        for i, case in enumerate(self._cases, 1):
            target = os.path.basename(case.get("target", "?"))
            self._cases_listbox.insert("end", f" {i:2d}. {target}  ({len(case.get('steps', []))} steps)")

    def _add_case(self):
        dlg = CaseDialog(self, csv_columns=self._csv_columns)
        self.wait_window(dlg)
        if dlg.get_result():
            self._cases.append(dlg.get_result())
            self._refresh_cases()

    def _edit_case(self):
        sel = self._cases_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = CaseDialog(self, self._cases[idx], csv_columns=self._csv_columns)
        self.wait_window(dlg)
        if dlg.get_result():
            self._cases[idx] = dlg.get_result()
            self._refresh_cases()

    def _move_case(self, delta: int):
        sel = self._cases_listbox.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + delta
        if j < 0 or j >= len(self._cases):
            return
        self._cases[i], self._cases[j] = self._cases[j], self._cases[i]
        self._refresh_cases()
        self._cases_listbox.selection_set(j)

    def _del_case(self):
        sel = self._cases_listbox.curselection()
        if not sel:
            return
        self._cases.pop(sel[0])
        self._refresh_cases()

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

    def _add_csv_column_picker(self):
        """dropdown เลือกคอลัมน์ CSV → ใส่ {csv.COL} ต่อท้ายช่อง text (เฉพาะ loop ที่มี data_source)"""
        if not self._csv_columns:
            return
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="คอลัมน์ CSV:", width=18, anchor="w").pack(side="left")
        col_var = tk.StringVar(value=self._csv_columns[0])
        ttk.Combobox(row, textvariable=col_var, values=self._csv_columns,
                     state="readonly", width=20).pack(side="left", padx=4)
        tk.Button(row, text="+ ใส่ {csv.X}",
                  command=lambda: self._insert_csv_var(col_var.get())).pack(side="left", padx=4)

    def _insert_csv_var(self, col: str):
        var = self._fields.get("text")
        if col and var is not None:
            var.set(var.get() + f"{{csv.{col}}}")

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
            elif key in ("columns", "header"):
                step[key] = [p.strip() for p in val.split(",") if p.strip()]
            else:
                step[key] = val

        if action == "click_image" and self._offset is not None:
            step["offset_x"] = int(self._offset[0])
            step["offset_y"] = int(self._offset[1])

        if action == "if_image":
            step["then"] = self._then
            step["else"] = self._else
        elif action == "switch_image":
            step["cases"] = self._cases
            step["default"] = self._default

        self._result = step
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


# ─── Nested Steps Editor (component ใช้ซ้ำ) ──────────────────────────────────

class NestedStepsEditor(tk.Frame):
    """แก้ไข list ของ step ย่อย — ใช้ใน then/else ของ if_image และ cases/default ของ switch_image
    เปิด StepDialog ซ้ำแบบ recursive (StepDialog เป็น modal grab_set ซ้อนกันได้)"""

    def __init__(self, parent, steps: list, title: str, height: int = 5, csv_columns: list = None):
        super().__init__(parent)
        self._steps = steps  # อ้างถึง list เดิม → แก้ใน place
        self._csv_columns = csv_columns or []

        tk.Label(self, text=title, anchor="w", fg="#0e639c",
                 font=("Segoe UI", 9, "bold")).pack(fill="x")

        body = tk.Frame(self)
        body.pack(fill="both", expand=True)
        self._listbox = tk.Listbox(
            body, height=height, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
            relief="flat", activestyle="none",
        )
        sb = tk.Scrollbar(body, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)
        self._listbox.bind("<Double-Button-1>", lambda e: self._edit())

        ctrl = tk.Frame(self)
        ctrl.pack(fill="x", pady=2)
        tk.Button(ctrl, text="+ Add", width=7, command=self._add).pack(side="left", padx=2)
        tk.Button(ctrl, text="Edit", width=6, command=self._edit).pack(side="left", padx=2)
        tk.Button(ctrl, text="↑", width=3, command=self._up).pack(side="left", padx=1)
        tk.Button(ctrl, text="↓", width=3, command=self._down).pack(side="left", padx=1)
        tk.Button(ctrl, text="Del", width=5, fg="red", command=self._del).pack(side="left", padx=2)

        self._refresh()

    def _refresh(self):
        self._listbox.delete(0, "end")
        for i, step in enumerate(self._steps, 1):
            self._listbox.insert("end", f" {i:2d}. {_step_label(step)}")

    def _open_dialog(self, step: dict = None) -> dict | None:
        dlg = StepDialog(self.winfo_toplevel(), step, csv_columns=self._csv_columns)
        self.wait_window(dlg)
        return dlg.get_result()

    def _add(self):
        result = self._open_dialog()
        if result:
            sel = self._listbox.curselection()
            idx = sel[0] + 1 if sel else len(self._steps)
            self._steps.insert(idx, result)
            self._refresh()
            self._listbox.selection_set(idx)

    def _edit(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        result = self._open_dialog(self._steps[idx])
        if result:
            self._steps[idx] = result
            self._refresh()
            self._listbox.selection_set(idx)

    def _up(self):
        sel = self._listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        self._steps[i - 1], self._steps[i] = self._steps[i], self._steps[i - 1]
        self._refresh()
        self._listbox.selection_set(i - 1)

    def _down(self):
        sel = self._listbox.curselection()
        if not sel or sel[0] >= len(self._steps) - 1:
            return
        i = sel[0]
        self._steps[i], self._steps[i + 1] = self._steps[i + 1], self._steps[i]
        self._refresh()
        self._listbox.selection_set(i + 1)

    def _del(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        self._steps.pop(sel[0])
        self._refresh()


# ─── Case Dialog (สำหรับ switch_image) ───────────────────────────────────────

class CaseDialog(tk.Toplevel):
    """แก้ไข 1 case ของ switch_image: target + confidence + steps"""

    def __init__(self, parent, case: dict = None, csv_columns: list = None):
        super().__init__(parent)
        self.title("แก้ไข Case" if case else "เพิ่ม Case")
        self.grab_set()
        self._result = None
        self._case = case or {}
        self._csv_columns = csv_columns or []
        self._steps = copy.deepcopy(self._case.get("steps", []))
        self._build()
        self._center()

    def _build(self):
        pad = dict(padx=10, pady=4)
        row = tk.Frame(self)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Image file:", width=12, anchor="w").pack(side="left")
        self._target_var = tk.StringVar(value=self._case.get("target", ""))
        tk.Entry(row, textvariable=self._target_var, width=28).pack(side="left", padx=4)
        tk.Button(row, text="Browse", command=self._browse).pack(side="left", padx=2)
        tk.Button(row, text="📷 Capture", bg="#569cd6", fg="white",
                  command=self._capture).pack(side="left", padx=2)

        row2 = tk.Frame(self)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="Confidence:", width=12, anchor="w").pack(side="left")
        self._conf_var = tk.StringVar(value=str(self._case.get("confidence", "")))
        tk.Entry(row2, textvariable=self._conf_var, width=10).pack(side="left", padx=4)
        tk.Label(row2, text="(เว้นว่าง = ใช้ค่า default ของ switch)", fg="gray",
                 font=("Segoe UI", 8)).pack(side="left", padx=4)

        NestedStepsEditor(self, self._steps, "Steps ของ case นี้:", height=5,
                          csv_columns=self._csv_columns).pack(
            fill="both", expand=True, padx=10, pady=4)

        btn = tk.Frame(self)
        btn.pack(pady=8)
        tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=self._save).pack(side="left", padx=6)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=6)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="เลือก image", initialdir="elements",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
        )
        if path:
            self._target_var.set(os.path.relpath(path))

    def _capture(self):
        self.withdraw()

        def on_done(path):
            self._target_var.set(os.path.relpath(path))
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_cancel():
            self.deiconify()
            self.lift()

        from gui.capture_tool import CaptureTool
        tool = CaptureTool(root=self, save_dir="elements", on_done=on_done, on_cancel=on_cancel)
        self.after(200, tool.start)

    def _save(self):
        target = self._target_var.get().strip()
        if not target:
            messagebox.showwarning("", "ต้องระบุ Image file ของ case", parent=self)
            return
        case = {"target": target}
        conf = self._conf_var.get().strip()
        if conf:
            try:
                case["confidence"] = float(conf)
            except ValueError:
                pass
        case["steps"] = self._steps
        self._result = case
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

        row2 = tk.Frame(self)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="ถ้าแถวพลาด:", width=18, anchor="w").pack(side="left")
        self._row_err_var = tk.StringVar(value=self._cfg.get("on_row_error", "stop"))
        ttk.Combobox(row2, textvariable=self._row_err_var, values=["stop", "skip"],
                     state="readonly", width=12).pack(side="left", padx=4)
        tk.Label(self, text="  stop = หยุดทั้งงาน / skip = ข้ามแถวที่ error ไปทำแถวถัดไป",
                 fg="gray", font=("Segoe UI", 8)).pack(anchor="w", padx=12)

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
        # เขียน on_row_error เฉพาะเมื่อเลือก skip (stop เป็น default — ไม่ต้องรก config)
        if self._row_err_var.get() == "skip":
            self._result["on_row_error"] = "skip"
        else:
            self._result.pop("on_row_error", None)
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


# ─── Variables Dialog ────────────────────────────────────────────────────────

class VariablesDialog(tk.Toplevel):
    """แก้ไข config['variables'] — key/value; value ว่าง = bot ถามตอน Start"""

    def __init__(self, parent, variables: dict):
        super().__init__(parent)
        self.title("ตัวแปร (Variables)")
        self.grab_set()
        self._result = None
        self._rows = []  # (key_var, val_var, row_frame)
        self._build()
        for k, v in (variables or {}).items():
            self._add_row(k, "" if v is None else str(v))
        if not self._rows:
            self._add_row()
        self._center()

    def _build(self):
        tk.Label(self, text="ใช้ใน step ผ่าน {ชื่อตัวแปร}  •  value ว่าง = bot ถามตอน Start",
                 fg="#0e639c", font=("Segoe UI", 9)).pack(padx=10, pady=(10, 4), anchor="w")
        hdr = tk.Frame(self)
        hdr.pack(fill="x", padx=10)
        tk.Label(hdr, text="ชื่อตัวแปร", width=22, anchor="w").pack(side="left")
        tk.Label(hdr, text="ค่า", width=26, anchor="w").pack(side="left", padx=2)

        self._rows_frame = tk.Frame(self)
        self._rows_frame.pack(fill="both", expand=True, padx=10, pady=4)

        tk.Button(self, text="+ เพิ่มตัวแปร", command=lambda: self._add_row()).pack(anchor="w", padx=10)

        btn = tk.Frame(self)
        btn.pack(pady=10)
        tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=self._save).pack(side="left", padx=6)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=6)

    def _add_row(self, key: str = "", val: str = ""):
        row = tk.Frame(self._rows_frame)
        row.pack(fill="x", pady=2)
        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=val)
        tk.Entry(row, textvariable=kv, width=22).pack(side="left", padx=2)
        tk.Entry(row, textvariable=vv, width=26).pack(side="left", padx=2)
        entry = (kv, vv, row)
        tk.Button(row, text="ลบ", fg="red", command=lambda: self._del_row(entry)).pack(side="left", padx=4)
        self._rows.append(entry)

    def _del_row(self, entry):
        entry[2].destroy()
        self._rows.remove(entry)

    def _save(self):
        result = {}
        for kv, vv, _ in self._rows:
            key = kv.get().strip()
            if not key:
                continue
            result[key] = vv.get()  # เก็บค่าว่างได้ (= runtime prompt)
        self._result = result
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


# ─── States Editor ───────────────────────────────────────────────────────────

class StateDialog(tk.Toplevel):
    """แก้ไข 1 state: name + trigger(image/confidence/timeout) + loop ที่จะรัน"""

    def __init__(self, parent, loop_names: list, state: dict = None):
        super().__init__(parent)
        self.title("แก้ไข State" if state else "เพิ่ม State")
        self.grab_set()
        self._result = None
        self._state = state or {}
        self._loop_names = loop_names
        self._build()
        self._center()

    def _build(self):
        pad = dict(padx=10, pady=4)
        trig = self._state.get("trigger", {})

        r = tk.Frame(self)
        r.pack(fill="x", **pad)
        tk.Label(r, text="ชื่อ State:", width=14, anchor="w").pack(side="left")
        self._name_var = tk.StringVar(value=self._state.get("name", ""))
        tk.Entry(r, textvariable=self._name_var, width=30).pack(side="left", padx=4)

        r2 = tk.Frame(self)
        r2.pack(fill="x", **pad)
        tk.Label(r2, text="Trigger image:", width=14, anchor="w").pack(side="left")
        self._file_var = tk.StringVar(value=trig.get("file", ""))
        tk.Entry(r2, textvariable=self._file_var, width=26).pack(side="left", padx=4)
        tk.Button(r2, text="Browse", command=self._browse).pack(side="left", padx=2)
        tk.Button(r2, text="📷 Capture", bg="#569cd6", fg="white",
                  command=self._capture).pack(side="left", padx=2)

        r3 = tk.Frame(self)
        r3.pack(fill="x", **pad)
        tk.Label(r3, text="Confidence:", width=14, anchor="w").pack(side="left")
        self._conf_var = tk.StringVar(value=str(trig.get("confidence", 0.85)))
        tk.Entry(r3, textvariable=self._conf_var, width=8).pack(side="left", padx=4)
        tk.Label(r3, text="Timeout (s):").pack(side="left", padx=(10, 2))
        self._timeout_var = tk.StringVar(value=str(trig.get("timeout", 15)))
        tk.Entry(r3, textvariable=self._timeout_var, width=8).pack(side="left", padx=4)

        r4 = tk.Frame(self)
        r4.pack(fill="x", **pad)
        tk.Label(r4, text="รัน Loop:", width=14, anchor="w").pack(side="left")
        self._loop_var = tk.StringVar(value=self._state.get("loop", ""))
        ttk.Combobox(r4, textvariable=self._loop_var, values=self._loop_names,
                     state="readonly", width=28).pack(side="left", padx=4)

        btn = tk.Frame(self)
        btn.pack(pady=10)
        tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=self._save).pack(side="left", padx=6)
        tk.Button(btn, text="ยกเลิก", width=10, command=self.destroy).pack(side="left", padx=6)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="เลือก trigger image", initialdir="triggers",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
        )
        if path:
            self._file_var.set(os.path.relpath(path))

    def _capture(self):
        self.withdraw()

        def on_done(path):
            self._file_var.set(os.path.relpath(path))
            self.deiconify()
            self.lift()
            self.focus_force()

        def on_cancel():
            self.deiconify()
            self.lift()

        from gui.capture_tool import CaptureTool
        tool = CaptureTool(root=self, save_dir="triggers", on_done=on_done, on_cancel=on_cancel)
        self.after(200, tool.start)

    def _save(self):
        name = self._name_var.get().strip()
        file = self._file_var.get().strip()
        loop = self._loop_var.get().strip()
        if not name or not file or not loop:
            messagebox.showwarning("", "ต้องกรอก ชื่อ / trigger image / loop ให้ครบ", parent=self)
            return
        try:
            conf = float(self._conf_var.get().strip())
        except ValueError:
            conf = 0.85
        try:
            t = float(self._timeout_var.get().strip())
            timeout = int(t) if t == int(t) else t
        except ValueError:
            timeout = 15
        self._result = {
            "name": name,
            "trigger": {"type": "image", "file": file, "confidence": conf, "timeout": timeout},
            "loop": loop,
        }
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def get_result(self) -> dict | None:
        return self._result


class StatesDialog(tk.Toplevel):
    """จัดการรายการ states — เพิ่ม/แก้/ลบ (แก้ config['states'] ใน place)"""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("States")
        self.grab_set()
        self._config = config
        self._states = config.setdefault("states", [])
        self._build()
        self._refresh()
        self._center()

    def _build(self):
        tk.Label(self, text="State = เจอ trigger image บนจอ → รัน loop ที่ผูกไว้ (Agent/Copilot mode)",
                 fg="#0e639c", font=("Segoe UI", 9)).pack(padx=10, pady=(10, 4), anchor="w")
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10)
        self._listbox = tk.Listbox(
            body, height=8, width=64, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
            relief="flat", activestyle="none",
        )
        sb = tk.Scrollbar(body, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)
        self._listbox.bind("<Double-Button-1>", lambda e: self._edit())

        ctrl = tk.Frame(self)
        ctrl.pack(fill="x", padx=10, pady=6)
        tk.Button(ctrl, text="+ Add", width=8, command=self._add).pack(side="left", padx=2)
        tk.Button(ctrl, text="Edit", width=6, command=self._edit).pack(side="left", padx=2)
        tk.Button(ctrl, text="Del", width=6, fg="red", command=self._del).pack(side="left", padx=2)
        tk.Button(ctrl, text="ปิด", width=8, command=self.destroy).pack(side="right", padx=2)

    def _loop_names(self) -> list:
        return list(self._config.get("loops", {}).keys())

    def _refresh(self):
        self._listbox.delete(0, "end")
        for s in self._states:
            trig = s.get("trigger", {})
            self._listbox.insert(
                "end",
                f" {s.get('name', '?')}  →  loop: {s.get('loop', '?')}  | {os.path.basename(trig.get('file', '?'))}",
            )

    def _add(self):
        dlg = StateDialog(self, self._loop_names())
        self.wait_window(dlg)
        if dlg.get_result():
            self._states.append(dlg.get_result())
            self._refresh()

    def _edit(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        dlg = StateDialog(self, self._loop_names(), self._states[idx])
        self.wait_window(dlg)
        if dlg.get_result():
            self._states[idx] = dlg.get_result()
            self._refresh()

    def _del(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        if messagebox.askyesno("ลบ", "ลบ state นี้?", parent=self):
            self._states.pop(sel[0])
            self._refresh()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")


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

        tk.Frame(btn_left, height=1, bg="#3a3a3a").pack(fill="x", pady=6)
        tk.Button(btn_left, text="🔧 ตัวแปร", command=self._edit_variables).pack(fill="x", pady=2)
        tk.Button(btn_left, text="🖥 States", command=self._edit_states).pack(fill="x", pady=2)

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
        tk.Button(ctrl, text="⏺ Record", width=10, bg="#a00000", fg="white",
                  command=self._record_steps).pack(side="right", padx=4)

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

    # ─── Variables / States ─────────────────────────────────────────────────

    def _edit_variables(self):
        dlg = VariablesDialog(self, self._config.get("variables", {}))
        self.wait_window(dlg)
        if dlg.get_result() is not None:
            self._config["variables"] = dlg.get_result()

    def _edit_states(self):
        # StatesDialog แก้ config['states'] ใน place (ใช้รายชื่อ loop ปัจจุบัน)
        dlg = StatesDialog(self, self._config)
        self.wait_window(dlg)

    def _record_steps(self):
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ก่อน")
            return
        if not messagebox.askyesno(
            "Record",
            "เริ่มอัด? หลังกดตกลง รออีก 2 วิ แล้วคลิก/พิมพ์ตามต้องการ\nกด F10 เพื่อหยุดอัด",
            parent=self,
        ):
            return
        from gui.recorder import Recorder
        self._recorder = Recorder(
            self, on_done=lambda steps: self._apply_recorded(steps)
        )
        # หน่วงก่อนเริ่ม เพื่อไม่อัดคลิกปุ่มตกลง
        self.after(2000, self._recorder.start)

    def _apply_recorded(self, steps: list):
        if not self._selected_loop:
            return
        self._steps().extend(steps)
        self._refresh_steps()
        messagebox.showinfo("Record", f"เพิ่ม {len(steps)} step จากการอัด", parent=self)

    # ─── Step management ────────────────────────────────────────────────────

    def _steps(self) -> list:
        if not self._selected_loop:
            return []
        return self._config["loops"][self._selected_loop].setdefault("steps", [])

    def _refresh_steps(self):
        self._step_listbox.delete(0, "end")
        for i, step in enumerate(self._steps(), 1):
            self._step_listbox.insert("end", f"  {i:2d}.  {_step_label(step)}")

    def _loop_csv_columns(self) -> list:
        """อ่านชื่อคอลัมน์จาก data_source ของ loop ที่เลือก (ถ้ามี) — สำหรับ dropdown ในช่อง type"""
        if not self._selected_loop:
            return []
        path = self._config["loops"][self._selected_loop].get("data_source")
        if not path:
            return []
        from engine.data_source import DataSource
        return DataSource.read_headers(path)

    def _add_step(self):
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ก่อน")
            return
        dlg = StepDialog(self, csv_columns=self._loop_csv_columns())
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
        dlg = StepDialog(self, self._steps()[idx], csv_columns=self._loop_csv_columns())
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
