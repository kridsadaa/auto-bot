import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from engine import scheduler
from gui.tooltip import add_tooltip
from gui.tooltip_texts import SCHEDULE as TT


class ScheduleDialog(tk.Toplevel):
    """ตั้ง/ลบ scheduled task (Windows Task Scheduler) ให้รัน loop แบบ headless ตามเวลา"""

    def __init__(self, parent, loop_names: list):
        super().__init__(parent)
        self.title("Schedule (Task Scheduler)")
        self.grab_set()
        self._loop_names = loop_names or []
        self._build()
        self._refresh_tasks()
        self._center()

    def _build(self):
        pad = dict(padx=10, pady=4)

        r = tk.Frame(self)
        r.pack(fill="x", **pad)
        tk.Label(r, text="Loop:", width=12, anchor="w").pack(side="left")
        self._loop_var = tk.StringVar(value=self._loop_names[0] if self._loop_names else "")
        loop_combo = ttk.Combobox(r, textvariable=self._loop_var, values=self._loop_names,
                     state="readonly", width=26)
        loop_combo.pack(side="left", padx=4)
        add_tooltip(loop_combo, TT["loop_select"])

        r2 = tk.Frame(self)
        r2.pack(fill="x", **pad)
        tk.Label(r2, text="ความถี่:", width=12, anchor="w").pack(side="left")
        self._sc_var = tk.StringVar(value="daily")
        freq_combo = ttk.Combobox(r2, textvariable=self._sc_var, values=["daily", "once"],
                     state="readonly", width=12)
        freq_combo.pack(side="left", padx=4)
        add_tooltip(freq_combo, TT["frequency"])

        r3 = tk.Frame(self)
        r3.pack(fill="x", **pad)
        tk.Label(r3, text="เวลา (HH:MM):", width=12, anchor="w").pack(side="left")
        self._st_var = tk.StringVar(value="08:00")
        time_entry = tk.Entry(r3, textvariable=self._st_var, width=10)
        time_entry.pack(side="left", padx=4)
        add_tooltip(time_entry, TT["time_field"])
        tk.Label(r3, text="วันที่ (MM/DD/YYYY · ใช้กับ once):").pack(side="left", padx=(10, 2))
        self._sd_var = tk.StringVar(value=datetime.now().strftime("%m/%d/%Y"))
        date_entry = tk.Entry(r3, textvariable=self._sd_var, width=12)
        date_entry.pack(side="left", padx=4)
        add_tooltip(date_entry, TT["date_field"])

        btn_create = tk.Button(self, text="+ สร้าง Schedule", bg="#4ec9b0",
                  command=self._create)
        btn_create.pack(pady=6)
        add_tooltip(btn_create, TT["create"])

        tk.Label(self, text="Task ที่ตั้งไว้ (AutoBot_*):",
                 fg="#0e639c", font=("Segoe UI", 9)).pack(anchor="w", padx=10)
        self._listbox = tk.Listbox(self, height=6, width=52, font=("Consolas", 9),
                                   bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
                                   relief="flat", activestyle="none")
        self._listbox.pack(fill="both", expand=True, padx=10, pady=4)
        add_tooltip(self._listbox, TT["task_list"])

        b = tk.Frame(self)
        b.pack(fill="x", padx=10, pady=6)
        btn_delete = tk.Button(b, text="ลบ task ที่เลือก", fg="red", command=self._delete)
        btn_delete.pack(side="left")
        add_tooltip(btn_delete, TT["delete_task"])
        btn_close = tk.Button(b, text="ปิด", command=self.destroy)
        btn_close.pack(side="right")
        add_tooltip(btn_close, TT["close"])

    def _create(self):
        loop = self._loop_var.get().strip()
        if not loop:
            messagebox.showwarning("", "เลือก loop ก่อน", parent=self)
            return
        sc = self._sc_var.get()
        st = self._st_var.get().strip()
        sd = self._sd_var.get().strip() if sc == "once" else None
        try:
            name = scheduler.create_task(loop, sc, st, sd)
            messagebox.showinfo("Schedule", f"สร้าง task: {name}\nรัน {sc} เวลา {st}", parent=self)
            self._refresh_tasks()
        except Exception as e:
            messagebox.showerror("Schedule error", str(e), parent=self)

    def _refresh_tasks(self):
        self._listbox.delete(0, "end")
        try:
            tasks = scheduler.list_tasks()
            if not tasks:
                self._listbox.insert("end", "(ยังไม่มี)")
            for n in tasks:
                self._listbox.insert("end", n)
        except Exception as e:
            self._listbox.insert("end", f"(อ่าน task ไม่ได้: {e})")

    def _delete(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        name = self._listbox.get(sel[0])
        if not name.startswith(scheduler.TASK_PREFIX):
            return
        if messagebox.askyesno("ลบ", f"ลบ task: {name}?", parent=self):
            try:
                scheduler.delete_task(name)
                self._refresh_tasks()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")
