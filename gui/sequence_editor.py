import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yaml
import os

CONFIG_PATH = "config/bot_config.yaml"

ACTION_TYPES = ["click_image", "type", "key", "hotkey", "wait", "screenshot", "scroll", "drag"]

KEY_OPTIONS = ["enter", "tab", "escape", "f1", "f2", "f3", "f4", "f5", "f6",
               "f7", "f8", "f12", "delete", "backspace", "up", "down", "left", "right"]


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _step_label(step: dict) -> str:
    action = step.get("action", "?")
    if action == "click_image":
        return f"click_image   →   {os.path.basename(step.get('target', ''))}"
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
    return action


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
        step = {"action": action}

        for key, var in self._fields.items():
            val = var.get().strip()
            if not val:
                continue
            if key in ("timeout", "seconds", "x", "y", "clicks", "src_x", "src_y", "dst_x", "dst_y"):
                try:
                    step[key] = float(val) if "." in val else int(val)
                except ValueError:
                    step[key] = val
            elif key == "confidence":
                try:
                    step[key] = float(val)
                except ValueError:
                    step[key] = 0.85
            elif key == "keys":
                step[key] = [k.strip() for k in val.split("+")]
            else:
                step[key] = val

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
