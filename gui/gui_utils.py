"""Small shared Tk helpers to avoid re-typing the same widget-construction
boilerplate in every dialog in gui/sequence_editor.py."""
import tkinter as tk

from gui.tooltip import add_tooltip

DARK_LISTBOX_KW = dict(
    bg="#1e1e1e", fg="#d4d4d4", selectbackground="#0e639c",
    relief="flat", activestyle="none",
)


def center_window(win: tk.Toplevel):
    """จัดหน้าต่างให้อยู่กึ่งกลางจอ — เรียกหลังสร้าง widget ทั้งหมดแล้ว"""
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


def add_save_cancel_row(parent, on_save, on_cancel, save_tooltip=None, cancel_tooltip=None):
    """แถวปุ่ม บันทึก/ยกเลิก มาตรฐานที่ใช้ซ้ำในทุก dialog ของ sequence editor"""
    btn = tk.Frame(parent)
    btn.pack(pady=10)
    btn_save = tk.Button(btn, text="บันทึก", width=10, bg="#4ec9b0", command=on_save)
    btn_save.pack(side="left", padx=6)
    if save_tooltip:
        add_tooltip(btn_save, save_tooltip)
    btn_cancel = tk.Button(btn, text="ยกเลิก", width=10, command=on_cancel)
    btn_cancel.pack(side="left", padx=6)
    if cancel_tooltip:
        add_tooltip(btn_cancel, cancel_tooltip)
    return btn_save, btn_cancel


def make_dark_listbox(parent, font=("Consolas", 9), **kwargs) -> tk.Listbox:
    """สร้าง Listbox ธีมมืด + Scrollbar ผูกกัน แพ็คลงใน `parent` โดยตรง
    (parent ควรเป็น frame เฉพาะสำหรับ listbox ตัวนี้ ไม่ใช่ container ที่มี widget อื่นแชร์ด้วย)"""
    listbox = tk.Listbox(parent, font=font, **{**DARK_LISTBOX_KW, **kwargs})
    sb = tk.Scrollbar(parent, command=listbox.yview)
    listbox.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)
    return listbox
