import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import yaml
import os
import copy

from engine.runtime import apply_window_icon
from engine import prefs
from gui.tooltip import add_tooltip
from gui.tooltip_texts import SEQ_EDITOR as TT_SEQ, STEP_DIALOG as TT_STEP, LOOP_SETTINGS as TT_LOOP
from gui.gui_utils import center_window, add_save_cancel_row, make_dark_listbox
from gui.listbox_crud import ListboxCrud

CONFIG_PATH = "config/bot_config.yaml"

ACTION_TYPES = [
    "click_image", "type", "key", "hotkey", "wait", "screenshot", "scroll", "drag",
    "wait_image", "wait_text", "repeat_key_until", "stop_if_image",
    "skip_row_if_image", "skip_row", "if_image", "switch_image",
    "write_row", "call_loop",
    "click_element", "set_element_text", "wait_element", "wait_window",
    "focus_window", "minimize_window",
    "sap_set_field", "sap_get_field", "sap_press",
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


def _show_image_preview(parent, path: str):
    """เปิดหน้าต่างเล็กๆ แสดงรูปเต็มที่ path นี้ชี้ไป — ช่วยดูว่ารูปที่อ้างถึงในช่องคือรูปอะไร"""
    path = (path or "").strip()
    if not path:
        messagebox.showwarning("Preview", "ยังไม่ได้เลือกรูป", parent=parent)
        return
    if not os.path.exists(path):
        messagebox.showwarning("Preview", f"ไม่พบไฟล์:\n{path}", parent=parent)
        return
    try:
        img = Image.open(path)
    except Exception as e:
        messagebox.showerror("Preview", f"เปิดรูปไม่ได้:\n{e}", parent=parent)
        return

    popup = tk.Toplevel(parent)
    popup.title(os.path.basename(path))
    popup.resizable(False, False)
    popup.configure(bg="#1e1e1e")

    orig_w, orig_h = img.size
    disp = img.copy()
    disp.thumbnail((640, 640), Image.LANCZOS)
    photo = ImageTk.PhotoImage(disp)
    popup.image = photo  # กัน garbage collect ตอน widget ถูกวาด

    tk.Label(popup, image=photo, bg="#1e1e1e").pack(padx=10, pady=(10, 4))
    tk.Label(
        popup, text=f"{path}   ({orig_w}×{orig_h}px)",
        bg="#1e1e1e", fg="#9cdcfe", font=("Segoe UI", 8),
    ).pack(padx=10, pady=(0, 8))
    tk.Button(popup, text="ปิด", width=10, command=popup.destroy).pack(pady=(0, 10))
    popup.bind("<Escape>", lambda e: popup.destroy())

    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    popup.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    popup.focus_set()


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
    if action == "call_loop":
        return f"call_loop      →   {step.get('loop', '?')}"
    if action == "write_row":
        cols = step.get("columns", [])
        n = len(cols) if isinstance(cols, list) else len(str(cols).split(","))
        return f"write_row      →   {os.path.basename(str(step.get('path', '?')))}  ({n} cols)"
    if action in ("click_element", "set_element_text", "wait_element"):
        who = step.get("name") or step.get("auto_id") or step.get("control_type") or "?"
        if action == "set_element_text":
            return f"set_element_text → {who} = {step.get('text', '')}"
        return f"{action}  →   {who}"
    if action == "wait_window":
        return f"wait_window    →   {step.get('title', '?')}  [{step.get('mode', 'appear')}]"
    if action == "focus_window":
        return f"focus_window   →   {step.get('title', '?')}"
    if action == "minimize_window":
        return f"minimize_window →  {step.get('title', '?')}"
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
        center_window(self)

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
        btn_save_point = tk.Button(btn, text="บันทึกจุดนี้", width=12, bg="#4ec9b0",
                  command=self._save)
        btn_save_point.pack(side="left", padx=5)
        add_tooltip(btn_save_point, "บันทึกจุดที่คลิกไว้ล่าสุดเป็นจุดกด")
        btn_use_center = tk.Button(btn, text="ใช้กลางรูป", width=12,
                  command=self._use_center)
        btn_use_center.pack(side="left", padx=5)
        add_tooltip(btn_use_center, "ใช้จุดกึ่งกลางรูปเป็นจุดกด (ค่า default ถ้าไม่เลือกอะไร)")
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

    def __init__(self, parent, step: dict = None, csv_columns: list = None,
                 variables: list = None, capture_dir: str = "elements",
                 loop_names: list = None):
        super().__init__(parent)
        self.title("แก้ไข Step" if step else "เพิ่ม Step")
        self.resizable(False, False)
        self.grab_set()
        self._result: dict = None
        self._step = step or {}
        self._csv_columns = csv_columns or []  # คอลัมน์ CSV ของ loop (สำหรับ dropdown ในช่อง type)
        self._variables = variables or []  # ตัวแปรที่ใช้ได้ (built-in + global) สำหรับ dropdown ในช่อง type
        self._capture_dir = capture_dir or "elements"  # โฟลเดอร์เซฟรูปของ loop นี้ (กันชื่อชนข้าม loop)
        self._loop_names = loop_names or []  # ชื่อ loop ทั้งหมด (สำหรับ dropdown ของ call_loop)
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
        center_window(self)

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
        add_tooltip(action_menu, TT_STEP["action_type"])

        # Dynamic fields area
        self._fields_frame = tk.Frame(self)
        self._fields_frame.pack(fill="x", padx=10)
        self._refresh_fields()

        # Buttons
        add_save_cancel_row(self, self._save, self.destroy,
                            save_tooltip=TT_STEP["save"], cancel_tooltip=TT_STEP["cancel"])

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
            self._add_variable_picker()
            self._add_csv_column_picker()
            # step ใหม่ → ใช้ค่าล่าสุดที่จำไว้ (prefs); step เดิม → ใช้ค่าจริงของมัน
            is_new = not self._step
            method_default = (prefs.get("type_method", "paste") if is_new
                              else self._step.get("method", "paste"))
            self._add_dropdown("method", "วิธีพิมพ์:", ["paste", "type"],
                               default=method_default, readonly=True)
            tk.Label(self._fields_frame,
                     text="  paste = วางผ่าน clipboard (เร็ว, เหมาะ SAP) / type = จำลองกดคีย์ทีละตัว (แอปที่บล็อก paste)",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            clear_on = (prefs.get("type_clear_first", False) if is_new
                        else bool(self._step.get("clear_first")))
            self._add_dropdown("clear_first", "เคลียร์ก่อนพิมพ์:", ["no", "yes"],
                               default=("yes" if clear_on else "no"), readonly=True)
            tk.Label(self._fields_frame,
                     text="  yes = กด Ctrl+A → Delete ลบค่าเดิมก่อน (กันช่อง SAP ที่จำค่าเก่า/ต่อกัน)",
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
            self._add_field("wait", "รอรูปก่อนตัดสิน (s):", default=str(self._step.get("wait", 0)),
                            tooltip=TT_STEP["wait_before_decide"])
            tk.Label(self._fields_frame,
                     text="  0 = เช็คทันทีครั้งเดียว (default) / >0 = รอจนกว่าจะเจอหรือหมดเวลา ค่อยไป ELSE — กันหน้าต่างเด้งช้าแล้วหลุดไป else ผิด",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            NestedStepsEditor(self._fields_frame, self._then, "THEN — ทำเมื่อ 'เจอ' รูป:", height=4,
                              csv_columns=self._csv_columns, variables=self._variables, capture_dir=self._capture_dir,
                              loop_names=self._loop_names).pack(fill="both", expand=True, pady=(8, 2))
            NestedStepsEditor(self._fields_frame, self._else, "ELSE — ทำเมื่อ 'ไม่เจอ' รูป:", height=4,
                              csv_columns=self._csv_columns, variables=self._variables, capture_dir=self._capture_dir,
                              loop_names=self._loop_names).pack(fill="both", expand=True, pady=2)

        elif action == "switch_image":
            self._add_field("confidence", "Confidence (default):", default=str(self._step.get("confidence", 0.85)))
            self._add_field("wait", "รอรูปก่อนตัดสิน (s):", default=str(self._step.get("wait", 0)),
                            tooltip=TT_STEP["wait_before_decide"])
            tk.Label(self._fields_frame,
                     text="  ไล่เช็ก case จากบนลงล่าง — เจอรูปแรกที่ตรง รัน case นั้น; ไม่เข้าเลย → default\n"
                          "  wait: 0 = เช็คทันทีครั้งเดียว (default) / >0 = รอจนกว่าจะมี case ไหนตรงหรือหมดเวลา",
                     fg="gray", font=("Segoe UI", 8), justify="left").pack(anchor="w")
            self._build_cases_editor()
            NestedStepsEditor(self._fields_frame, self._default, "DEFAULT — ทำเมื่อไม่เข้า case ใด:", height=3,
                              csv_columns=self._csv_columns, variables=self._variables, capture_dir=self._capture_dir,
                              loop_names=self._loop_names).pack(fill="both", expand=True, pady=(8, 2))

        elif action == "call_loop":
            self._add_dropdown("loop", "เรียก Loop:", self._loop_names,
                               default=self._step.get("loop", ""), readonly=True,
                               tooltip=TT_STEP["call_loop_target"])
            tk.Label(self._fields_frame,
                     text="  รัน step ทั้งหมดของ loop นี้เหมือนเป็น subroutine แล้วกลับมาทำ step ถัดไป\n"
                          "  หมายเหตุ: ใช้แถว CSV ปัจจุบันร่วมกัน + ตัวแปรเฉพาะของ loop ที่ถูกเรียกถูกใช้ระหว่างรัน\n"
                          "  แต่ไม่สน data_source/on_row_error/setup_steps ของ loop ที่ถูกเรียก",
                     fg="gray", font=("Segoe UI", 8), justify="left").pack(anchor="w")
            if not self._loop_names:
                tk.Label(self._fields_frame, text="  ⚠️ ยังไม่มี loop อื่นให้เรียก — สร้าง loop เพิ่มก่อน",
                         fg="#ce9178", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "write_row":
            row = tk.Frame(self._fields_frame)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="ไฟล์ปลายทาง:", width=18, anchor="w").pack(side="left")
            pvar = tk.StringVar(value=self._step.get("path", ""))
            tk.Entry(row, textvariable=pvar, width=28).pack(side="left", padx=4)
            btn_browse_save = tk.Button(row, text="Browse", command=lambda: self._browse_save(pvar))
            btn_browse_save.pack(side="left", padx=2)
            add_tooltip(btn_browse_save, TT_STEP["browse_save_path"])
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

        elif action == "wait_window":
            self._add_window_title_row("title", "ชื่อหน้าต่าง (regex):")
            tk.Label(self._fields_frame,
                     text="  เทียบกับ title ของหน้าต่างด้วย regex เช่น .*Notepad.*  หรือกด '🔍 จิ้ม window'",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_dropdown("mode", "รอจน:", WAIT_MODE_OPTIONS,
                               default=self._step.get("mode", "appear"))
            tk.Label(self._fields_frame, text="  appear = รอจนหน้าต่างโผล่ / disappear = รอจนหน้าต่างหาย (ปิด)",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 15)))

        elif action == "focus_window":
            self._add_window_title_row("title", "ชื่อหน้าต่าง (regex):")
            tk.Label(self._fields_frame,
                     text="  ดึงหน้าต่างขึ้น foreground + ตั้ง keyboard focus ก่อน step ที่พึ่งคีย์บอร์ดจริง"
                          " (key/type/hotkey) — กัน input หลงไปหน้าต่างอื่น",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 10)))

        elif action == "minimize_window":
            self._add_window_title_row("title", "ชื่อหน้าต่าง (regex):")
            tk.Label(self._fields_frame,
                     text="  ย่อหน้าต่างที่ตรง (ทุกอันที่เจอ) ลง taskbar — ใช้พับ SAP Logon pad หลัง"
                          " login สำเร็จ กันมันแย่ง focus/แย่งเป็นเป้าของ focus_window ตัวอื่นต่อ",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("timeout", "Timeout (s):", default=str(self._step.get("timeout", 10)))

        # ─── SAP Scripting actions ───────────────────────────────────────────
        elif action == "sap_set_field":
            self._add_field("text", "Text / Variable:", default=self._step.get("text", ""))
            self._add_variable_picker()
            self._add_csv_column_picker()
            self._add_sap_field_row("field_id", "SAP Field ID:")
            tk.Label(self._fields_frame,
                     text="  เช่น wnd[0]/usr/ctxtMATNR  หรือกด '🔍 จิ้ม SAP field'",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "sap_get_field":
            self._add_sap_field_row("field_id", "SAP Field ID:")
            tk.Label(self._fields_frame,
                     text="  เช่น wnd[0]/sbar  (status bar ที่มีเลข order)",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_field("variable", "เก็บค่าลงตัวแปร:",
                            default=self._step.get("variable", "SAP_VALUE"))
            tk.Label(self._fields_frame,
                     text="  ใช้ค่าที่อ่านได้ใน step ถัดไปด้วย {SAP_VALUE}",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

        elif action == "sap_press":
            self._add_sap_field_row("field_id", "SAP Field ID (ออปชัน):")
            tk.Label(self._fields_frame,
                     text="  เช่น wnd[0]/tbar[0]/btn[0] — หรือใช้ Virtual Key แทน",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")
            self._add_dropdown("vkey", "Virtual Key:", ["", "enter", "f3", "f4", "f8",
                                                         "f12", "save", "back"],
                               default=str(self._step.get("vkey", "")), readonly=True)
            tk.Label(self._fields_frame,
                     text="  enter=ยืนยัน, f3=Back, f8=Execute, f12=Cancel, save=บันทึก",
                     fg="gray", font=("Segoe UI", 8)).pack(anchor="w")

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
        btn_inspect = tk.Button(row, text="🔍 จิ้ม element", bg="#dcdcaa",
                  command=self._inspect_element)
        btn_inspect.pack(side="left", padx=4)
        add_tooltip(btn_inspect, TT_STEP["inspect_element"])
        tk.Label(row, text="กดแล้วเอาเมาส์ชี้ element เป้าหมาย (มีนับถอยหลัง)",
                 fg="gray", font=("Segoe UI", 8)).pack(side="left", padx=4)

    def _add_sap_field_row(self, key: str, label: str):
        """ช่องกรอก SAP element ID + ปุ่ม 'จิ้ม SAP field' (ใช้ pick_field_id)"""
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=self._step.get(key, ""))
        tk.Entry(row, textvariable=var, width=32).pack(side="left", padx=4)
        btn_pick_sap = tk.Button(row, text="🔍 จิ้ม SAP field", bg="#dcdcaa",
                  command=lambda: self._pick_sap_field(var))
        btn_pick_sap.pack(side="left", padx=2)
        add_tooltip(btn_pick_sap, TT_STEP["sap_pick_field"])
        self._fields[key] = var

    def _pick_sap_field(self, var: tk.StringVar):
        """นับถอยหลัง 3 วิ → รอผู้ใช้คลิก field ใน SAP → ใส่ ID ลงช่อง"""
        self.withdraw()

        def do():
            from engine.sap_actions import pick_field_id, SapNotAvailableError
            try:
                field_id = pick_field_id(timeout=20)
                if field_id:
                    var.set(field_id)
                else:
                    messagebox.showwarning("SAP Picker", "ไม่ได้รับ field ID — คลิก field ใน SAP ระหว่างนับถอยหลัง", parent=self)
            except SapNotAvailableError as e:
                messagebox.showerror("SAP Picker", f"ไม่พร้อม: {e}", parent=self)
            except Exception as e:
                messagebox.showwarning("SAP Picker", f"เกิดข้อผิดพลาด: {e}", parent=self)
            self._deiconify_focus()

        self._countdown_then(3, do)

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

    def _add_window_title_row(self, key: str, label: str):
        """ช่องกรอกชื่อหน้าต่าง + ปุ่ม 'จิ้ม window' (ใช้ element_from_point เอาแค่ title
        ของหน้าต่างบนสุด — ไม่ต้องคลิก แค่เอาเมาส์ไปชี้เหมือน '🔍 จิ้ม element')"""
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=self._step.get(key, ""))
        tk.Entry(row, textvariable=var, width=28).pack(side="left", padx=4)
        btn_pick_window = tk.Button(row, text="🔍 จิ้ม window", bg="#dcdcaa",
                  command=lambda: self._pick_window_title(var))
        btn_pick_window.pack(side="left", padx=2)
        add_tooltip(btn_pick_window, TT_STEP["pick_window"])
        self._fields[key] = var

    def _pick_window_title(self, var: tk.StringVar):
        """นับถอยหลัง 3 วิ → เอาเมาส์ไปชี้หน้าต่างเป้าหมาย (ไม่ต้องคลิก) → ใส่ title ลงช่อง"""
        self.withdraw()

        def do():
            try:
                import win32api
                from engine import ui_element
                x, y = win32api.GetCursorPos()
                props = ui_element.element_from_point(x, y)
            except Exception as e:
                self._deiconify_focus()
                messagebox.showwarning("Window Picker", f"อ่านหน้าต่างไม่ได้: {e}", parent=self)
                return
            title = props.get("window")
            if title:
                var.set(str(title))
            else:
                messagebox.showwarning("Window Picker", "ไม่พบชื่อหน้าต่างใต้เมาส์", parent=self)
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

        self._cases_listbox = make_dark_listbox(wrap, height=4, font=("Consolas", 9))
        self._cases_crud = ListboxCrud(
            self._cases_listbox, get_items=lambda: self._cases, make_label=self._case_row_label,
            open_dialog=self._open_case_dialog,
        )

        ctrl = tk.Frame(wrap)
        ctrl.pack(fill="x", padx=4, pady=2)
        btn_add_case = tk.Button(ctrl, text="+ Case", width=8, command=self._cases_crud.add)
        btn_add_case.pack(side="left", padx=2)
        add_tooltip(btn_add_case, TT_STEP["add_case"])
        btn_edit_case = tk.Button(ctrl, text="Edit", width=6, command=self._cases_crud.edit)
        btn_edit_case.pack(side="left", padx=2)
        add_tooltip(btn_edit_case, TT_STEP["edit_case"])
        btn_case_up = tk.Button(ctrl, text="↑", width=3, command=self._cases_crud.move_up)
        btn_case_up.pack(side="left", padx=1)
        add_tooltip(btn_case_up, TT_STEP["move_case_up"])
        btn_case_down = tk.Button(ctrl, text="↓", width=3, command=self._cases_crud.move_down)
        btn_case_down.pack(side="left", padx=1)
        add_tooltip(btn_case_down, TT_STEP["move_case_down"])
        btn_del_case = tk.Button(ctrl, text="Del", width=5, fg="red", command=self._cases_crud.delete)
        btn_del_case.pack(side="left", padx=2)
        add_tooltip(btn_del_case, TT_STEP["delete_case"])
        self._cases_crud.refresh()

    def _case_row_label(self, i: int, case: dict) -> str:
        target = os.path.basename(case.get("target", "?"))
        return f" {i:2d}. {target}  ({len(case.get('steps', []))} steps)"

    def _open_case_dialog(self, existing: dict = None) -> dict | None:
        dlg = CaseDialog(self, existing, csv_columns=self._csv_columns, variables=self._variables,
                         capture_dir=self._capture_dir, loop_names=self._loop_names)
        self.wait_window(dlg)
        return dlg.get_result()

    def _add_field(self, key: str, label: str, default: str = "", browse: bool = False,
                   tooltip: str = None):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=self._step.get(key, default))
        entry = tk.Entry(row, textvariable=var, width=28)
        entry.pack(side="left", padx=4)
        if tooltip:
            add_tooltip(entry, tooltip)
        if browse:
            btn_browse = tk.Button(
                row, text="Browse",
                command=lambda: self._browse(var),
            )
            btn_browse.pack(side="left", padx=2)
            add_tooltip(btn_browse, TT_STEP["browse"])
            btn_capture = tk.Button(
                row, text="📷 Capture",
                bg="#569cd6", fg="white",
                command=lambda: self._capture(var),
            )
            btn_capture.pack(side="left", padx=2)
            add_tooltip(btn_capture, TT_STEP["capture_image"])
            btn_preview = tk.Button(
                row, text="👁 Preview",
                command=lambda: _show_image_preview(self, var.get()),
            )
            btn_preview.pack(side="left", padx=2)
            add_tooltip(btn_preview, TT_STEP["preview_image"])
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
        btn_insert_csv = tk.Button(row, text="+ ใส่ {csv.X}",
                  command=lambda: self._insert_csv_var(col_var.get()))
        btn_insert_csv.pack(side="left", padx=4)
        add_tooltip(btn_insert_csv, TT_STEP["csv_column_insert"])

    def _insert_csv_var(self, col: str):
        var = self._fields.get("text")
        if col and var is not None:
            var.set(var.get() + f"{{csv.{col}}}")

    def _add_variable_picker(self):
        """dropdown เลือกตัวแปร (global/built-in) → ใส่ {VAR} ต่อท้ายช่อง text"""
        if not self._variables:
            return
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="ตัวแปร:", width=18, anchor="w").pack(side="left")
        var_sel = tk.StringVar(value=self._variables[0])
        ttk.Combobox(row, textvariable=var_sel, values=self._variables,
                     state="readonly", width=22).pack(side="left", padx=4)
        btn_insert_var = tk.Button(row, text="+ ใส่ {VAR}",
                  command=lambda: self._insert_var(var_sel.get()))
        btn_insert_var.pack(side="left", padx=4)
        add_tooltip(btn_insert_var, TT_STEP["variable_insert"])

    def _insert_var(self, display: str):
        # display อาจมีสัญลักษณ์ scope นำหน้า (🌐/📍) — เอาเฉพาะชื่อตัวแปรตัวสุดท้าย
        var = self._fields.get("text")
        name = display.split()[-1] if display else ""
        if name and var is not None:
            var.set(var.get() + f"{{{name}}}")

    def _add_dropdown(self, key: str, label: str, options: list, default: str = "",
                      readonly: bool = False, tooltip: str = None):
        # ใช้ค่า default ที่ผู้เรียกคำนวณมาตรงๆ — อย่าไปอ่าน self._step ทับ
        # (สำคัญกับ clear_first ที่เก็บเป็น bool แต่ dropdown ใช้ "yes"/"no")
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        state = "readonly" if readonly else "normal"
        combo = ttk.Combobox(row, textvariable=var, values=options, width=20,
                     state=state)
        combo.pack(side="left", padx=4)
        if tooltip:
            add_tooltip(combo, tooltip)
        self._fields[key] = var

    def _add_region_field(self, key: str, label: str):
        row = tk.Frame(self._fields_frame)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=18, anchor="w").pack(side="left")
        existing = self._step.get(key)
        default = ",".join(str(n) for n in existing) if existing else ""
        var = tk.StringVar(value=default)
        tk.Entry(row, textvariable=var, width=20).pack(side="left", padx=4)
        btn_pick_region = tk.Button(row, text="เลือก Region", bg="#569cd6", fg="white",
                  command=lambda: self._pick_region(var))
        btn_pick_region.pack(side="left", padx=2)
        add_tooltip(btn_pick_region, TT_STEP["region_pick"])
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
        btn_pick_pos = tk.Button(row, text="🎯 เลือกจุดกด", bg="#dcdcaa",
                  command=self._pick_position)
        btn_pick_pos.pack(side="left", padx=4)
        add_tooltip(btn_pick_pos, TT_STEP["pick_position"])
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
        initial = self._capture_dir if os.path.isdir(self._capture_dir) else "elements"
        path = filedialog.askopenfilename(
            title="เลือก image", initialdir=initial,
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
        )
        if path:
            var.set(os.path.relpath(path))

    def _capture(self, var: tk.StringVar):
        """ซ่อน dialog ชั่วคราว → เปิด capture overlay → คืน path ลงช่อง target
        เซฟลงโฟลเดอร์ของ loop นี้ (self._capture_dir) เพื่อกันชื่อชนข้าม loop"""
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
            save_dir=self._capture_dir,
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
                       "dst_x", "dst_y", "max_attempts", "min_chars", "delay", "wait"):
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
            elif key == "clear_first":
                if val == "yes":
                    step[key] = True
                else:
                    step.pop(key, None)
            elif key == "vkey":
                # vkey ว่าง = ไม่ใช้; ถ้าเป็น string ชื่อ (enter, f3 ฯลฯ) เก็บเป็น string
                step[key] = val
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

        # จำค่าล่าสุดของ type ไว้เป็น default ของ step ใหม่ครั้งหน้า
        if action == "type":
            prefs.set("type_method", step.get("method", "paste"))
            prefs.set("type_clear_first", bool(step.get("clear_first")))

        self._result = step
        self.destroy()


    def get_result(self) -> dict | None:
        return self._result


# ─── Nested Steps Editor (component ใช้ซ้ำ) ──────────────────────────────────

class NestedStepsEditor(tk.Frame):
    """แก้ไข list ของ step ย่อย — ใช้ใน then/else ของ if_image และ cases/default ของ switch_image
    เปิด StepDialog ซ้ำแบบ recursive (StepDialog เป็น modal grab_set ซ้อนกันได้)"""

    def __init__(self, parent, steps: list, title: str, height: int = 5,
                 csv_columns: list = None, variables: list = None, capture_dir: str = "elements",
                 loop_names: list = None):
        super().__init__(parent)
        self._steps = steps  # อ้างถึง list เดิม → แก้ใน place
        self._csv_columns = csv_columns or []
        self._variables = variables or []
        self._capture_dir = capture_dir or "elements"
        self._loop_names = loop_names or []

        tk.Label(self, text=title, anchor="w", fg="#0e639c",
                 font=("Segoe UI", 9, "bold")).pack(fill="x")

        body = tk.Frame(self)
        body.pack(fill="both", expand=True)
        self._listbox = make_dark_listbox(body, height=height, font=("Consolas", 9))
        self._crud = ListboxCrud(
            self._listbox, get_items=lambda: self._steps, make_label=self._row_label,
            open_dialog=self._open_dialog,
        )

        ctrl = tk.Frame(self)
        ctrl.pack(fill="x", pady=2)
        btn_add = tk.Button(ctrl, text="+ Add", width=7, command=self._crud.add)
        btn_add.pack(side="left", padx=2)
        add_tooltip(btn_add, "เพิ่ม step ย่อยเข้าในลิสต์นี้")
        btn_edit = tk.Button(ctrl, text="Edit", width=6, command=self._crud.edit)
        btn_edit.pack(side="left", padx=2)
        add_tooltip(btn_edit, "แก้ไข step ที่เลือก (หรือดับเบิลคลิก)")
        btn_up = tk.Button(ctrl, text="↑", width=3, command=self._crud.move_up)
        btn_up.pack(side="left", padx=1)
        add_tooltip(btn_up, "ย้าย step ขึ้น")
        btn_down = tk.Button(ctrl, text="↓", width=3, command=self._crud.move_down)
        btn_down.pack(side="left", padx=1)
        add_tooltip(btn_down, "ย้าย step ลง")
        btn_del = tk.Button(ctrl, text="Del", width=5, fg="red", command=self._crud.delete)
        btn_del.pack(side="left", padx=2)
        add_tooltip(btn_del, "ลบ step ที่เลือกทิ้ง")

        self._crud.refresh()

    def _row_label(self, i: int, step: dict) -> str:
        return f" {i:2d}. {_step_label(step)}"

    def _open_dialog(self, step: dict = None) -> dict | None:
        dlg = StepDialog(self.winfo_toplevel(), step,
                         csv_columns=self._csv_columns, variables=self._variables, capture_dir=self._capture_dir,
                         loop_names=self._loop_names)
        self.wait_window(dlg)
        return dlg.get_result()


# ─── Case Dialog (สำหรับ switch_image) ───────────────────────────────────────

class CaseDialog(tk.Toplevel):
    """แก้ไข 1 case ของ switch_image: target + confidence + steps"""

    def __init__(self, parent, case: dict = None, csv_columns: list = None,
                 variables: list = None, capture_dir: str = "elements", loop_names: list = None):
        super().__init__(parent)
        self.title("แก้ไข Case" if case else "เพิ่ม Case")
        self.grab_set()
        self._result = None
        self._case = case or {}
        self._csv_columns = csv_columns or []
        self._variables = variables or []
        self._capture_dir = capture_dir or "elements"
        self._loop_names = loop_names or []
        self._steps = copy.deepcopy(self._case.get("steps", []))
        self._build()
        center_window(self)

    def _build(self):
        pad = dict(padx=10, pady=4)
        row = tk.Frame(self)
        row.pack(fill="x", **pad)
        tk.Label(row, text="Image file:", width=12, anchor="w").pack(side="left")
        self._target_var = tk.StringVar(value=self._case.get("target", ""))
        tk.Entry(row, textvariable=self._target_var, width=28).pack(side="left", padx=4)
        btn_case_browse = tk.Button(row, text="Browse", command=self._browse)
        btn_case_browse.pack(side="left", padx=2)
        add_tooltip(btn_case_browse, TT_STEP["browse"])
        btn_case_capture = tk.Button(row, text="📷 Capture", bg="#569cd6", fg="white",
                  command=self._capture)
        btn_case_capture.pack(side="left", padx=2)
        add_tooltip(btn_case_capture, TT_STEP["capture_image"])
        btn_case_preview = tk.Button(row, text="👁 Preview",
                  command=lambda: _show_image_preview(self, self._target_var.get()))
        btn_case_preview.pack(side="left", padx=2)
        add_tooltip(btn_case_preview, TT_STEP["preview_image"])

        row2 = tk.Frame(self)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="Confidence:", width=12, anchor="w").pack(side="left")
        self._conf_var = tk.StringVar(value=str(self._case.get("confidence", "")))
        tk.Entry(row2, textvariable=self._conf_var, width=10).pack(side="left", padx=4)
        tk.Label(row2, text="(เว้นว่าง = ใช้ค่า default ของ switch)", fg="gray",
                 font=("Segoe UI", 8)).pack(side="left", padx=4)

        NestedStepsEditor(self, self._steps, "Steps ของ case นี้:", height=5,
                          csv_columns=self._csv_columns, variables=self._variables, capture_dir=self._capture_dir,
                          loop_names=self._loop_names).pack(
            fill="both", expand=True, padx=10, pady=4)

        add_save_cancel_row(self, self._save, self.destroy,
                            save_tooltip=TT_STEP["save"], cancel_tooltip=TT_STEP["cancel"])

    def _browse(self):
        initial = self._capture_dir if os.path.isdir(self._capture_dir) else "elements"
        path = filedialog.askopenfilename(
            title="เลือก image", initialdir=initial,
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
        tool = CaptureTool(root=self, save_dir=self._capture_dir, on_done=on_done, on_cancel=on_cancel)
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


    def get_result(self) -> dict | None:
        return self._result


# ─── Loop Settings Dialog ────────────────────────────────────────────────────

class LoopSettingsDialog(tk.Toplevel):
    def __init__(self, parent, loop_name: str, loop_config: dict,
                 csv_columns: list = None, variables: list = None, capture_dir: str = "elements",
                 loop_names: list = None):
        super().__init__(parent)
        self.title(f"ตั้งค่า Loop: {loop_name}")
        self.resizable(True, True)
        self.grab_set()
        self._result = None
        self._cfg = dict(loop_config)
        self._csv_columns = csv_columns or []
        self._variables = variables or []
        self._capture_dir = capture_dir or "elements"
        self._loop_names = loop_names or []
        self._recovery_steps = copy.deepcopy(loop_config.get("recovery_steps", []) or [])
        self._setup_steps = copy.deepcopy(loop_config.get("setup_steps", []) or [])
        self._build()
        center_window(self)

    def _build(self):
        pad = dict(padx=12, pady=6)

        row1 = tk.Frame(self)
        row1.pack(fill="x", **pad)
        tk.Label(row1, text="CSV Data Source:", width=18, anchor="w").pack(side="left")
        self._csv_var = tk.StringVar(value=self._cfg.get("data_source", ""))
        csv_entry = tk.Entry(row1, textvariable=self._csv_var, width=30)
        csv_entry.pack(side="left", padx=4)
        add_tooltip(csv_entry, TT_LOOP["csv_data_source"])
        btn_browse_csv = tk.Button(row1, text="Browse", command=self._browse_csv)
        btn_browse_csv.pack(side="left")
        add_tooltip(btn_browse_csv, TT_LOOP["browse_csv"])
        tk.Label(self, text="  เว้นว่างถ้าไม่ต้อง loop CSV", fg="gray", font=("Segoe UI", 8)).pack(anchor="w", padx=12)

        # ─── Setup Steps — รันครั้งเดียวก่อนแถวแรก ─────────────────────────────
        setup_frame = tk.LabelFrame(
            self, text="Setup Steps — รันครั้งเดียวก่อนเริ่ม (เช่น login)",
            fg="#0e639c", font=("Segoe UI", 9, "bold"),
        )
        setup_frame.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        add_tooltip(setup_frame, TT_LOOP["setup_steps"])
        tk.Label(
            setup_frame,
            text="  รันก่อนแถว CSV แถวแรกเท่านั้น (ยังใช้ {csv.X} ไม่ได้ตอนนี้) — ถ้า step พลาด จะหยุดทั้งงานทันที",
            fg="gray", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=8)
        NestedStepsEditor(
            setup_frame, self._setup_steps, "Setup Steps:",
            height=4,
            csv_columns=self._csv_columns,
            variables=self._variables,
            capture_dir=self._capture_dir,
            loop_names=self._loop_names,
        ).pack(fill="both", expand=True, padx=8, pady=(4, 8))
        # ──────────────────────────────────────────────────────────────────────

        row2 = tk.Frame(self)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="ถ้าแถวพลาด:", width=18, anchor="w").pack(side="left")
        self._row_err_var = tk.StringVar(value=self._cfg.get("on_row_error", "stop"))
        self._err_combo = ttk.Combobox(
            row2, textvariable=self._row_err_var,
            values=["stop", "skip", "recover"], state="readonly", width=12,
        )
        self._err_combo.pack(side="left", padx=4)
        self._err_combo.bind("<<ComboboxSelected>>", lambda e: self._on_policy_change())
        add_tooltip(self._err_combo, TT_LOOP["on_row_error"])
        tk.Label(self, text="  stop = หยุดทั้งงาน / skip = ข้ามแถว / recover = กู้คืนอัตโนมัติ",
                 fg="gray", font=("Segoe UI", 8)).pack(anchor="w", padx=12)

        # ─── Recover section (show/hide ตาม dropdown) ─────────────────────────
        self._recover_frame = tk.LabelFrame(
            self, text="การกู้คืนอัตโนมัติ (recover mode)",
            fg="#0e639c", font=("Segoe UI", 9, "bold"),
        )
        add_tooltip(self._recover_frame, TT_LOOP["recovery_steps"])

        el_row = tk.Frame(self._recover_frame)
        el_row.pack(fill="x", padx=8, pady=4)
        tk.Label(el_row, text="บันทึก error ที่:", width=18, anchor="w").pack(side="left")
        self._error_log_var = tk.StringVar(value=self._cfg.get("error_log_path", "data/errors.csv"))
        error_log_entry = tk.Entry(el_row, textvariable=self._error_log_var, width=28)
        error_log_entry.pack(side="left", padx=4)
        add_tooltip(error_log_entry, TT_LOOP["error_log_path"])
        btn_browse_error_log = tk.Button(el_row, text="Browse", command=self._browse_error_log)
        btn_browse_error_log.pack(side="left")
        add_tooltip(btn_browse_error_log, TT_LOOP["browse_error_log"])
        tk.Label(
            self._recover_frame,
            text="  ไฟล์บันทึกแถวที่พลาด (row_num, timestamp, error) — สร้างอัตโนมัติ",
            fg="gray", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=8)

        NestedStepsEditor(
            self._recover_frame, self._recovery_steps,
            "Recovery Steps — รันเมื่อแถวพลาด (เช่น กด ESC, คลิกกลับหน้าแรก SAP):",
            height=5,
            csv_columns=self._csv_columns,
            variables=self._variables,
            capture_dir=self._capture_dir,
            loop_names=self._loop_names,
        ).pack(fill="both", expand=True, padx=8, pady=(4, 8))
        # ──────────────────────────────────────────────────────────────────────

        add_save_cancel_row(self, self._save, self.destroy,
                            save_tooltip=TT_STEP["save"], cancel_tooltip=TT_STEP["cancel"])

        self._on_policy_change()

    def _on_policy_change(self):
        if self._row_err_var.get() == "recover":
            # วาง recover_frame ก่อน btn frame (ปุ่ม Save อยู่ท้าย)
            btn_frame = self.winfo_children()[-1]
            self._recover_frame.pack(fill="both", expand=True, padx=12, pady=4,
                                     before=btn_frame)
            self.minsize(540, 480)
        else:
            self._recover_frame.pack_forget()
            self.minsize(0, 0)

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="เลือก CSV", initialdir="data",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if path:
            self._csv_var.set(os.path.relpath(path))

    def _browse_error_log(self):
        path = filedialog.asksaveasfilename(
            title="ไฟล์บันทึก error", initialdir="data",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
        )
        if path:
            self._error_log_var.set(os.path.relpath(path))

    def _save(self):
        self._result = dict(self._cfg)
        csv_val = self._csv_var.get().strip()
        if csv_val:
            self._result["data_source"] = csv_val
        else:
            self._result.pop("data_source", None)

        err_policy = self._row_err_var.get()
        if err_policy in ("skip", "recover"):
            self._result["on_row_error"] = err_policy
        else:
            self._result.pop("on_row_error", None)

        el = self._error_log_var.get().strip()
        if el:
            self._result["error_log_path"] = el
        else:
            self._result.pop("error_log_path", None)

        if self._recovery_steps:
            self._result["recovery_steps"] = self._recovery_steps
        else:
            self._result.pop("recovery_steps", None)

        if self._setup_steps:
            self._result["setup_steps"] = self._setup_steps
        else:
            self._result.pop("setup_steps", None)

        self.destroy()


    def get_result(self) -> dict | None:
        return self._result


# ─── Variables Dialog ────────────────────────────────────────────────────────

class VariablesDialog(tk.Toplevel):
    """แก้ไข config['variables'] — key/value; value ว่าง = bot ถามตอน Start"""

    def __init__(self, parent, variables: dict, title: str = "ตัวแปร (Variables)",
                 hint: str = "ใช้ใน step ผ่าน {ชื่อตัวแปร}  •  value ว่าง = bot ถามตอน Start"):
        super().__init__(parent)
        self.title(title)
        self.grab_set()
        self._result = None
        self._hint = hint
        self._rows = []  # (key_var, val_var, row_frame)
        self._build()
        for k, v in (variables or {}).items():
            self._add_row(k, "" if v is None else str(v))
        if not self._rows:
            self._add_row()
        center_window(self)

    def _build(self):
        tk.Label(self, text=self._hint,
                 fg="#0e639c", font=("Segoe UI", 9)).pack(padx=10, pady=(10, 4), anchor="w")
        hdr = tk.Frame(self)
        hdr.pack(fill="x", padx=10)
        tk.Label(hdr, text="ชื่อตัวแปร", width=22, anchor="w").pack(side="left")
        tk.Label(hdr, text="ค่า", width=26, anchor="w").pack(side="left", padx=2)

        self._rows_frame = tk.Frame(self)
        self._rows_frame.pack(fill="both", expand=True, padx=10, pady=4)

        btn_add_var = tk.Button(self, text="+ เพิ่มตัวแปร", command=lambda: self._add_row())
        btn_add_var.pack(anchor="w", padx=10)
        add_tooltip(btn_add_var, "เพิ่มแถวตัวแปรใหม่")

        add_save_cancel_row(self, self._save, self.destroy,
                            save_tooltip=TT_STEP["save"], cancel_tooltip=TT_STEP["cancel"])

    def _add_row(self, key: str = "", val: str = ""):
        row = tk.Frame(self._rows_frame)
        row.pack(fill="x", pady=2)
        kv = tk.StringVar(value=key)
        vv = tk.StringVar(value=val)
        tk.Entry(row, textvariable=kv, width=22).pack(side="left", padx=2)
        tk.Entry(row, textvariable=vv, width=26).pack(side="left", padx=2)
        entry = (kv, vv, row)
        btn_del_var = tk.Button(row, text="ลบ", fg="red", command=lambda: self._del_row(entry))
        btn_del_var.pack(side="left", padx=4)
        add_tooltip(btn_del_var, "ลบตัวแปรแถวนี้")
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
        center_window(self)

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
        btn_state_browse = tk.Button(r2, text="Browse", command=self._browse)
        btn_state_browse.pack(side="left", padx=2)
        add_tooltip(btn_state_browse, TT_STEP["browse"])
        btn_state_capture = tk.Button(r2, text="📷 Capture", bg="#569cd6", fg="white",
                  command=self._capture)
        btn_state_capture.pack(side="left", padx=2)
        add_tooltip(btn_state_capture, TT_STEP["capture_image"])
        btn_state_preview = tk.Button(r2, text="👁 Preview",
                  command=lambda: _show_image_preview(self, self._file_var.get()))
        btn_state_preview.pack(side="left", padx=2)
        add_tooltip(btn_state_preview, TT_STEP["preview_image"])

        r3 = tk.Frame(self)
        r3.pack(fill="x", **pad)
        tk.Label(r3, text="Confidence:", width=14, anchor="w").pack(side="left")
        self._conf_var = tk.StringVar(value=str(trig.get("confidence", 0.85)))
        conf_entry = tk.Entry(r3, textvariable=self._conf_var, width=8)
        conf_entry.pack(side="left", padx=4)
        add_tooltip(conf_entry, "ความมั่นใจขั้นต่ำในการจับคู่รูป (0-1) ยิ่งสูงยิ่งเข้มงวด")
        tk.Label(r3, text="Timeout (s):").pack(side="left", padx=(10, 2))
        self._timeout_var = tk.StringVar(value=str(trig.get("timeout", 15)))
        timeout_entry = tk.Entry(r3, textvariable=self._timeout_var, width=8)
        timeout_entry.pack(side="left", padx=4)
        add_tooltip(timeout_entry, "รอเจอ trigger image นานสุดกี่วินาที ก่อนถือว่าไม่เจอ")

        r4 = tk.Frame(self)
        r4.pack(fill="x", **pad)
        tk.Label(r4, text="รัน Loop:", width=14, anchor="w").pack(side="left")
        self._loop_var = tk.StringVar(value=self._state.get("loop", ""))
        loop_combo = ttk.Combobox(r4, textvariable=self._loop_var, values=self._loop_names,
                     state="readonly", width=28)
        loop_combo.pack(side="left", padx=4)
        add_tooltip(loop_combo, "loop ที่จะรันเมื่อเจอ trigger image นี้")

        add_save_cancel_row(self, self._save, self.destroy,
                            save_tooltip=TT_STEP["save"], cancel_tooltip=TT_STEP["cancel"])

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
        self._crud.refresh()
        center_window(self)

    def _build(self):
        tk.Label(self, text="State = เจอ trigger image บนจอ → รัน loop ที่ผูกไว้ (Agent/Copilot mode)",
                 fg="#0e639c", font=("Segoe UI", 9)).pack(padx=10, pady=(10, 4), anchor="w")
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10)
        self._listbox = make_dark_listbox(body, height=8, width=64, font=("Consolas", 9))
        self._crud = ListboxCrud(
            self._listbox, get_items=lambda: self._states, make_label=self._row_label,
            open_dialog=self._open_dialog, confirm_delete=self._confirm_delete,
        )

        ctrl = tk.Frame(self)
        ctrl.pack(fill="x", padx=10, pady=6)
        btn_add_state = tk.Button(ctrl, text="+ Add", width=8, command=self._crud.add)
        btn_add_state.pack(side="left", padx=2)
        add_tooltip(btn_add_state, "เพิ่ม state ใหม่ — ผูก trigger image กับ loop ที่จะรัน")
        btn_edit_state = tk.Button(ctrl, text="Edit", width=6, command=self._crud.edit)
        btn_edit_state.pack(side="left", padx=2)
        add_tooltip(btn_edit_state, "แก้ไข state ที่เลือก (หรือดับเบิลคลิก)")
        btn_del_state = tk.Button(ctrl, text="Del", width=6, fg="red", command=self._crud.delete)
        btn_del_state.pack(side="left", padx=2)
        add_tooltip(btn_del_state, "ลบ state ที่เลือกทิ้ง")
        btn_close_states = tk.Button(ctrl, text="ปิด", width=8, command=self.destroy)
        btn_close_states.pack(side="right", padx=2)
        add_tooltip(btn_close_states, "ปิดหน้าต่างนี้")

    def _loop_names(self) -> list:
        return list(self._config.get("loops", {}).keys())

    def _row_label(self, i: int, s: dict) -> str:
        trig = s.get("trigger", {})
        return f" {s.get('name', '?')}  →  loop: {s.get('loop', '?')}  | {os.path.basename(trig.get('file', '?'))}"

    def _open_dialog(self, existing: dict = None) -> dict | None:
        dlg = StateDialog(self, self._loop_names(), existing)
        self.wait_window(dlg)
        return dlg.get_result()

    def _confirm_delete(self, state: dict, idx: int) -> bool:
        return messagebox.askyesno("ลบ", "ลบ state นี้?", parent=self)



# ─── Sequence Editor Window ──────────────────────────────────────────────────

class SequenceEditor(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sequence Editor")
        self.geometry("880x600")
        self.minsize(820, 540)  # กันปุ่มคอลัมน์ซ้ายถูกบีบเมื่อย่อหน้าต่าง (เหมือนหน้าหลัก)
        self.resizable(True, True)
        apply_window_icon(self)

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
        add_tooltip(self._loop_listbox, TT_SEQ["loop_list"])

        btn_left = tk.Frame(left, bg="#1e1e1e")
        btn_left.pack(fill="x", pady=6, padx=6)
        btn_new_loop = tk.Button(btn_left, text="+ Loop ใหม่", command=self._new_loop)
        btn_new_loop.pack(fill="x", pady=2)
        add_tooltip(btn_new_loop, TT_SEQ["new_loop"])
        btn_loop_settings = tk.Button(btn_left, text="ตั้งค่า Loop", command=self._loop_settings)
        btn_loop_settings.pack(fill="x", pady=2)
        add_tooltip(btn_loop_settings, TT_SEQ["loop_settings"])
        btn_delete_loop = tk.Button(btn_left, text="ลบ Loop", fg="red", command=self._delete_loop)
        btn_delete_loop.pack(fill="x", pady=2)
        add_tooltip(btn_delete_loop, TT_SEQ["delete_loop"])

        tk.Frame(btn_left, height=1, bg="#3a3a3a").pack(fill="x", pady=6)
        btn_global_vars = tk.Button(btn_left, text="🌐 ตัวแปร Global", command=self._edit_variables)
        btn_global_vars.pack(fill="x", pady=2)
        add_tooltip(btn_global_vars, TT_SEQ["edit_global_variables"])
        btn_loop_vars = tk.Button(btn_left, text="📍 ตัวแปร Loop นี้", command=self._edit_loop_variables)
        btn_loop_vars.pack(fill="x", pady=2)
        add_tooltip(btn_loop_vars, TT_SEQ["edit_loop_variables"])
        btn_states = tk.Button(btn_left, text="🖥 States", command=self._edit_states)
        btn_states.pack(fill="x", pady=2)
        add_tooltip(btn_states, TT_SEQ["edit_states"])

        tk.Frame(btn_left, height=1, bg="#3a3a3a").pack(fill="x", pady=6)
        btn_export = tk.Button(btn_left, text="⬆ Export loop", command=self._export_loop)
        btn_export.pack(fill="x", pady=2)
        add_tooltip(btn_export, TT_SEQ["export_loop"])
        btn_import = tk.Button(btn_left, text="⬇ Import loop", command=self._import_loop)
        btn_import.pack(fill="x", pady=2)
        add_tooltip(btn_import, TT_SEQ["import_loop"])

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

        # ปุ่มเปิดไฟล์ตาราง (csv/xlsx) ที่ loop ผูกไว้ — โผล่เฉพาะ loop ที่มี data_source
        self._open_csv_btn = tk.Button(hdr, text="📂 เปิดตาราง", font=("Segoe UI", 8),
                                       command=self._open_csv_file)
        add_tooltip(self._open_csv_btn, TT_SEQ["open_csv"])
        self._current_csv = ""  # path ของ data_source ของ loop ที่เลือกอยู่

        # Steps listbox
        list_frame = tk.Frame(right, bg="#2d2d2d")
        list_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self._step_listbox = make_dark_listbox(list_frame, font=("Consolas", 10))
        self._step_crud = ListboxCrud(
            self._step_listbox, get_items=self._steps, make_label=self._step_row_label,
            open_dialog=self._open_step_dialog, confirm_delete=self._confirm_delete_step,
        )

        # Step controls
        ctrl = tk.Frame(right, bg="#2d2d2d", pady=6)
        ctrl.pack(fill="x", padx=10)

        btn_add_step = tk.Button(ctrl, text="+ Add Step", width=12, bg="#4ec9b0", fg="black",
                  command=self._step_crud.add)
        btn_add_step.pack(side="left", padx=4)
        add_tooltip(btn_add_step, TT_SEQ["add_step"])
        btn_edit_step = tk.Button(ctrl, text="Edit", width=8, command=self._step_crud.edit)
        btn_edit_step.pack(side="left", padx=4)
        add_tooltip(btn_edit_step, TT_SEQ["edit_step"])
        btn_step_up = tk.Button(ctrl, text="↑", width=4, command=self._step_crud.move_up)
        btn_step_up.pack(side="left", padx=2)
        add_tooltip(btn_step_up, TT_SEQ["move_up"])
        btn_step_down = tk.Button(ctrl, text="↓", width=4, command=self._step_crud.move_down)
        btn_step_down.pack(side="left", padx=2)
        add_tooltip(btn_step_down, TT_SEQ["move_down"])
        btn_delete_step = tk.Button(ctrl, text="Del", width=6, fg="red", command=self._step_crud.delete)
        btn_delete_step.pack(side="left", padx=4)
        add_tooltip(btn_delete_step, TT_SEQ["delete_step"])
        btn_record = tk.Button(ctrl, text="⏺ Record", width=10, bg="#a00000", fg="white",
                  command=self._record_steps)
        btn_record.pack(side="right", padx=4)
        add_tooltip(btn_record, TT_SEQ["record"])

        # Save
        save_bar = tk.Frame(right, bg="#007acc", pady=4)
        save_bar.pack(fill="x", side="bottom")
        btn_save_config = tk.Button(
            save_bar, text="Save Config", width=14,
            bg="#0e639c", fg="white", font=("Segoe UI", 10, "bold"),
            command=self._save_config,
        )
        btn_save_config.pack(side="right", padx=10)
        add_tooltip(btn_save_config, TT_SEQ["save_config"])
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
        self._current_csv = ds
        if ds:
            self._open_csv_btn.pack(side="left", padx=4)
        else:
            self._open_csv_btn.pack_forget()

        self._step_crud.refresh()

    def _open_csv_file(self):
        """เปิดไฟล์ตาราง (csv/xlsx) ของ loop ที่เลือก ด้วยโปรแกรมเริ่มต้น (Excel)"""
        path = self._current_csv
        if not path:
            return
        abspath = path if os.path.isabs(path) else os.path.abspath(path)
        if not os.path.exists(abspath):
            messagebox.showwarning("ไม่พบไฟล์", f"ไม่พบไฟล์ข้อมูล:\n{abspath}")
            return
        try:
            os.startfile(abspath)  # Windows: เปิดด้วยโปรแกรมที่ผูกกับนามสกุล (Excel)
        except Exception as e:
            messagebox.showerror("เปิดไฟล์ไม่ได้", str(e))

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
        dlg = LoopSettingsDialog(
            self, self._selected_loop, loop_cfg,
            csv_columns=self._loop_csv_columns(),
            variables=self._loop_variables(),
            capture_dir=self._loop_capture_dir(),
            loop_names=self._all_loop_names(),
        )
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

    def _edit_loop_variables(self):
        """แก้ตัวแปรเฉพาะ loop ที่เลือก — ทับตัวแปร global ที่ชื่อชนกัน (ตอนรัน loop นี้)"""
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ก่อน")
            return
        loop_cfg = self._config["loops"][self._selected_loop]
        dlg = VariablesDialog(
            self, loop_cfg.get("variables", {}),
            title=f"ตัวแปรเฉพาะ Loop: {self._selected_loop}",
            hint="ตัวแปรเหล่านี้ใช้ได้เฉพาะ loop นี้ และทับตัวแปร Global ที่ชื่อเดียวกัน",
        )
        self.wait_window(dlg)
        if dlg.get_result() is not None:
            result = dlg.get_result()
            if result:
                loop_cfg["variables"] = result
            else:
                loop_cfg.pop("variables", None)  # ไม่มีตัวแปร → ไม่รก config

    def _edit_states(self):
        # StatesDialog แก้ config['states'] ใน place (ใช้รายชื่อ loop ปัจจุบัน)
        dlg = StatesDialog(self, self._config)
        self.wait_window(dlg)

    # ─── Export / Import loop (.botpack) ────────────────────────────────────

    def _export_loop(self):
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ที่จะ export ก่อน")
            return
        loop_cfg = self._config["loops"][self._selected_loop]
        include_data = False
        if loop_cfg.get("data_source"):
            include_data = messagebox.askyesno(
                "แนบไฟล์ข้อมูล?",
                f"loop นี้ใช้ข้อมูล: {loop_cfg['data_source']}\n\n"
                "แนบไฟล์ข้อมูลไปในแพ็กด้วยไหม?\n(ข้อมูลจะติดไปกับไฟล์ที่แชร์)",
                parent=self,
            )
        path = filedialog.asksaveasfilename(
            title="Export loop", initialfile=f"{self._selected_loop}.botpack",
            defaultextension=".botpack",
            filetypes=[("Auto Bot pack", "*.botpack"), ("Zip", "*.zip")],
        )
        if not path:
            return
        try:
            from engine.loop_package import build_package
            summary = build_package(self._config, self._selected_loop, path, include_data=include_data)
        except Exception as e:
            messagebox.showerror("Export error", str(e), parent=self)
            return
        msg = f"Export สำเร็จ: {os.path.basename(path)}\nรูป {len(summary['assets'])} ไฟล์"
        if summary["missing"]:
            miss = "\n".join(os.path.basename(m) for m in summary["missing"])
            msg += f"\n\n⚠️ รูปหาย {len(summary['missing'])} ไฟล์ (ไม่ถูกแนบ):\n{miss}"
        if summary.get("called_loops"):
            msg += f"\n\nแนบ loop ที่ถูกเรียกด้วย (call_loop): {', '.join(summary['called_loops'])}"
        if summary.get("missing_loop_refs"):
            msg += (f"\n\n⚠️ call_loop อ้างถึง loop ที่ไม่มีจริง (ไม่ถูกแนบ): "
                    f"{', '.join(summary['missing_loop_refs'])}")
        if summary["variables"]:
            msg += f"\n\nตัวแปรที่ปลายทางต้องกรอกค่า: {', '.join(summary['variables'])}"
        messagebox.showinfo("Export", msg, parent=self)

    def _import_loop(self):
        path = filedialog.askopenfilename(
            title="Import loop",
            filetypes=[("Auto Bot pack", "*.botpack"), ("Zip", "*.zip"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            from engine.loop_package import import_package
            merged, summary = import_package(self._config, path)
        except Exception as e:
            messagebox.showerror("Import error", str(e), parent=self)
            return
        self._config = merged
        self._save_config()  # เซฟลงไฟล์ทันที
        self._refresh_loop_list()
        msg = f"Import สำเร็จ → loop: {summary['loop_name']}"
        if summary["renamed"]:
            msg += "  (เปลี่ยนชื่อกันซ้ำ)"
        if summary.get("called_loops"):
            msg += f"\nLoop ลูกที่เพิ่มมาด้วย (call_loop): {', '.join(summary['called_loops'])}"
        if summary["added_variables"]:
            msg += f"\nตัวแปรที่ต้องไปกรอกค่า: {', '.join(summary['added_variables'])}"
        if summary["states"]:
            msg += f"\nState ที่เพิ่ม: {', '.join(summary['states'])}"
        messagebox.showinfo("Import", msg, parent=self)

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
        self._step_crud.refresh()
        messagebox.showinfo("Record", f"เพิ่ม {len(steps)} step จากการอัด", parent=self)

    # ─── Step management ────────────────────────────────────────────────────

    def _steps(self) -> list:
        if not self._selected_loop:
            return []
        return self._config["loops"][self._selected_loop].setdefault("steps", [])

    def _step_row_label(self, i: int, step: dict) -> str:
        return f"  {i:2d}.  {_step_label(step)}"

    def _loop_csv_columns(self) -> list:
        """อ่านชื่อคอลัมน์จาก data_source ของ loop ที่เลือก (ถ้ามี) — สำหรับ dropdown ในช่อง type"""
        if not self._selected_loop:
            return []
        path = self._config["loops"][self._selected_loop].get("data_source")
        if not path:
            return []
        from engine.data_source import DataSource
        return DataSource.read_headers(path)

    def _loop_variables(self) -> list:
        """รายชื่อตัวแปรที่ใช้ได้ในช่อง type (สำหรับ dropdown) — มีสัญลักษณ์บอก scope:
        🌐 = global/built-in, 📍 = เฉพาะ loop นี้ (picker จะ strip สัญลักษณ์ก่อนแทรก)"""
        items = [f"🌐 {v}" for v in ("TODAY", "TODAY_ISO")]
        items += [f"🌐 {v}" for v in self._config.get("variables", {})]
        if self._selected_loop:
            loop_vars = self._config["loops"][self._selected_loop].get("variables", {})
            items += [f"📍 {v}" for v in loop_vars]
        return items

    def _loop_capture_dir(self) -> str:
        """โฟลเดอร์เซฟรูปของ loop ที่เลือก = elements/<ชื่อ loop> (กันชื่อชนข้าม loop)"""
        if not self._selected_loop:
            return "elements"
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in self._selected_loop)
        return os.path.join("elements", safe)

    def _all_loop_names(self) -> list:
        """รายชื่อ loop สำหรับ dropdown ของ action call_loop — ตัด loop ที่กำลังแก้อยู่ออก
        (เรียกตัวเอง = recursion error ตอนรันเสมอ ไม่ควรมีให้เลือก)"""
        return [n for n in self._config.get("loops", {}) if n != self._selected_loop]

    def _open_step_dialog(self, existing: dict = None) -> dict | None:
        if not self._selected_loop:
            messagebox.showwarning("", "เลือก loop ก่อน")
            return None
        dlg = StepDialog(self, existing, csv_columns=self._loop_csv_columns(),
                         variables=self._loop_variables(),
                         capture_dir=self._loop_capture_dir(),
                         loop_names=self._all_loop_names())
        self.wait_window(dlg)
        return dlg.get_result()

    def _confirm_delete_step(self, step: dict, idx: int) -> bool:
        return messagebox.askyesno("ลบ", f"ลบ step {idx+1}?", parent=self)

    # ─── Save ────────────────────────────────────────────────────────────────

    def _save_config(self):
        try:
            _save_config(self._config)
            self._save_status.configure(text="บันทึกแล้ว")
            self.after(2000, lambda: self._save_status.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


import tkinter.simpledialog
