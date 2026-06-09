"""
SAP Compare Dialog — เปรียบ step ภาพ (loop เดิม) กับ SAP script ที่ Shadow Capture จดได้
ผู้ใช้สามารถ:
  - ดู side-by-side: step ภาพ (ซ้าย) ↔ SAP step ที่จดได้ (ขวา)
  - กด 'บันทึก loop_sap' เพื่อสร้าง loop ใหม่คู่กับของเดิม (ไม่ทับ)
"""
import tkinter as tk
from tkinter import ttk, messagebox

from engine.sap_capture import CapturedEvent, to_sap_steps
from gui.sequence_editor import _step_label


class SapCompareDialog(tk.Toplevel):
    """
    image_steps: list[dict]         — steps เดิมของ loop (ภาพ)
    sap_events:  list[CapturedEvent] — events ที่ shadow capture จดได้
    loop_name:   str                 — ชื่อ loop เดิม (สร้างใหม่เป็น <loop>_sap)
    on_save:     callable(new_loop_name, new_steps) — เรียกเมื่อผู้ใช้กด Save
    """

    def __init__(self, parent, image_steps: list, sap_events: list[CapturedEvent],
                 loop_name: str, on_save=None):
        super().__init__(parent)
        self.title("เปรียบ Loop ภาพ ↔ SAP Script")
        self.geometry("900x520")
        self.minsize(720, 400)
        self.grab_set()
        self._image_steps = image_steps
        self._sap_steps = to_sap_steps(sap_events)
        self._loop_name = loop_name
        self._on_save = on_save
        self._build()
        self._center()

    def _build(self):
        # ─ header ─
        hdr = tk.Frame(self, bg="#1e1e1e", pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Loop: {self._loop_name}",
                 bg="#1e1e1e", fg="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)
        status = "✅ จดได้ครบ" if self._sap_steps else "⚠️ ไม่พบ SAP action (ตรวจว่าเปิด SAP Scripting)"
        tk.Label(hdr, text=status, bg="#1e1e1e",
                 fg="#4ec9b0" if self._sap_steps else "#f44747",
                 font=("Segoe UI", 9)).pack(side="left", padx=8)

        # ─ body: สองคอลัมน์ ─
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        def make_col(parent, col, title, color):
            tk.Label(parent, text=title, fg=color, font=("Segoe UI", 9, "bold"),
                     anchor="w").grid(row=0, column=col, sticky="ew", pady=(0, 4))
            lb = tk.Listbox(parent, bg="#1e1e1e", fg="#d4d4d4",
                            selectbackground="#0e639c", font=("Consolas", 9),
                            relief="flat", activestyle="none")
            lb.grid(row=1, column=col, sticky="nsew", padx=(0 if col else 0, 4 if col == 0 else 0))
            sb = tk.Scrollbar(parent, command=lb.yview)
            sb.grid(row=1, column=col, sticky="nse")
            lb.configure(yscrollcommand=sb.set)
            parent.rowconfigure(1, weight=1)
            return lb

        self._lb_image = make_col(body, 0, "🖼  Loop ภาพ (เดิม)", "#9cdcfe")
        self._lb_sap   = make_col(body, 1, "⚙️  SAP Script (จะสร้างใหม่)", "#4ec9b0")

        for i, s in enumerate(self._image_steps, 1):
            self._lb_image.insert("end", f"  {i:2d}.  {_step_label(s)}")
        for i, s in enumerate(self._sap_steps, 1):
            self._lb_sap.insert("end", f"  {i:2d}.  {_step_label(s)}")
        if not self._sap_steps:
            self._lb_sap.insert("end", "  (ไม่มีข้อมูล)")

        # ─ sync scroll ─
        def sync_scroll(*args):
            self._lb_image.yview(*args)
            self._lb_sap.yview(*args)
        self._lb_image.configure(yscrollcommand=lambda *a: (
            self._lb_image.yview_moveto(a[0]), self._lb_sap.yview_moveto(a[0])))

        # ─ footer ─
        foot = tk.Frame(self, pady=8)
        foot.pack(fill="x", padx=10)
        new_name = f"{self._loop_name}_sap"
        tk.Label(foot, text=f"Loop ใหม่จะชื่อ: {new_name}",
                 fg="#6e6e6e", font=("Segoe UI", 8)).pack(side="left", padx=4)
        tk.Button(foot, text="ยกเลิก", width=10,
                  command=self.destroy).pack(side="right", padx=4)
        self._btn_save = tk.Button(
            foot, text=f"💾 บันทึก {new_name}", width=20,
            bg="#4ec9b0", fg="black", font=("Segoe UI", 9, "bold"),
            state="normal" if self._sap_steps else "disabled",
            command=self._do_save,
        )
        self._btn_save.pack(side="right", padx=4)

    def _do_save(self):
        new_name = f"{self._loop_name}_sap"
        if self._on_save:
            self._on_save(new_name, list(self._sap_steps))
        messagebox.showinfo(
            "บันทึกแล้ว",
            f"สร้าง loop '{new_name}' สำเร็จ\n"
            f"ไปที่ Sequence Editor เพื่อตรวจ/แก้ไข\n"
            f"หรือสลับ state ให้ชี้ loop ใหม่ได้เลย",
            parent=self,
        )
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")
