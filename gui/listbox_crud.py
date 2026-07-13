"""Generic add/edit/move/delete/copy-paste/undo controller for a Tk Listbox
backed by a plain Python list of dicts.

Every listbox-based CRUD panel in gui/sequence_editor.py (main step list,
nested step editor, switch_image cases, states list) repeated the same
curselection -> guard -> mutate list -> refresh -> reselect shape by hand.
This wraps that shape once; each panel only supplies how to render a row and
how to open its add/edit dialog, and gets Enter/Delete/Ctrl+C/Ctrl+V/Ctrl+Z
for free.
"""
import copy
import tkinter as tk
from tkinter import messagebox

from gui.keybind_utils import bind_ctrl_key

# กันไม่ให้ session แก้ไขนานๆ สะสม snapshot จนกินแรมมากเกินไป — undo ย้อนได้ 50
# ครั้งก็เกินพอสำหรับ "วางผิด/ลบผิด แล้วย้อนกลับ" ที่เป็น use case จริง
_MAX_UNDO = 50


class ListboxCrud:
    def __init__(self, listbox: tk.Listbox, get_items, make_label, open_dialog,
                 confirm_delete=None):
        """
        listbox: the tk.Listbox this controller drives
        get_items: () -> list — live reference to the backing list
        make_label: (position: int, item) -> str — text for one row (position is 1-based)
        open_dialog: (existing_item_or_None) -> new_item_or_None
                     None existing = "add" mode; None return = dialog was cancelled
        confirm_delete: optional (item, index) -> bool; skip to delete without asking
        """
        self.listbox = listbox
        self._get_items = get_items
        self._make_label = make_label
        self._open_dialog = open_dialog
        self._confirm_delete = confirm_delete
        self._clipboard = None
        self._undo_stack: list[list] = []
        self._bind_keys()

    def _bind_keys(self):
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit())
        self.listbox.bind("<Return>", lambda e: self.edit())
        self.listbox.bind("<Delete>", lambda e: self.delete())
        bind_ctrl_key(self.listbox, "C", self.copy)
        bind_ctrl_key(self.listbox, "V", self.paste)
        bind_ctrl_key(self.listbox, "Z", self.undo)
        self.listbox.bind("<Button-3>", self._show_context_menu)

    def _snapshot(self):
        """เก็บสถานะ list ปัจจุบันไว้ก่อนแก้ไข — เรียกก่อนทุก mutation จริง (หลังผ่าน
        guard ทั้งหมดแล้ว ไม่เก็บ snapshot เปล่าตอน action ไม่ได้ทำอะไรจริง)"""
        self._undo_stack.append(copy.deepcopy(self._get_items()))
        del self._undo_stack[:-_MAX_UNDO]

    def undo(self):
        """คืน list กลับไปสถานะก่อนแก้ไขครั้งล่าสุด (วาง/ลบ/แก้/ย้าย ผิด) — no-op ถ้า
        ไม่มีอะไรให้ย้อน แก้ผ่าน slice-assign (items[:] = ...) ไม่ reassign ตัวแปร
        เพราะ get_items() คืน reference ของ list จริงที่โค้ดอื่นถืออยู่ด้วย (เช่น
        self._steps ของ StepDialog) — ต้อง mutate ตัวเดิม ไม่ใช่สร้าง list ใหม่แทน"""
        if not self._undo_stack:
            return
        items = self._get_items()
        items[:] = self._undo_stack.pop()
        self.refresh()

    def _select_row_at(self, y: int):
        """เลือกแถวที่พิกัด y นี้ชี้ (ใน listbox) — no-op ถ้า list ว่าง แยกออกมาจาก
        _show_context_menu เพื่อให้ทดสอบ "คลิกขวา = เลือกแถวใต้เมาส์ก่อนเหมือน
        Explorer" ได้โดยไม่ต้องยุ่งกับ tk.Menu/tk_popup จริง"""
        items = self._get_items()
        if not items:
            return
        idx = max(0, min(self.listbox.nearest(y), len(items) - 1))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)

    def _show_context_menu(self, event):
        """คลิกขวา = เลือกแถวใต้เมาส์ก่อน (เหมือน Explorer) แล้วโชว์เมนูรวมทุก action
        ที่มีอยู่แล้ว (ปุ่มด้านล่าง + Enter/Delete/Ctrl+C/Ctrl+V) ให้เข้าถึงจากคลิกขวา
        ได้ด้วย ไม่ต้องเล็งปุ่มเล็กๆ — เมนูใช้ label เดียวกับปุ่ม/tooltip เดิมทุกจุด"""
        self._select_row_at(event.y)
        idx = self._selected_index()
        items = self._get_items()
        has_sel = idx is not None

        def state(cond):
            return "normal" if cond else "disabled"

        menu = tk.Menu(self.listbox, tearoff=False)
        menu.add_command(label="เลิกทำ (Ctrl+Z)", command=self.undo,
                          state=state(bool(self._undo_stack)))
        menu.add_separator()
        menu.add_command(label="แก้ไข (Enter)", command=self.edit, state=state(has_sel))
        menu.add_command(label="เพิ่ม/แทรกแถว", command=self.add)
        menu.add_separator()
        menu.add_command(label="คัดลอก (Ctrl+C)", command=self.copy, state=state(has_sel))
        menu.add_command(label="วาง (Ctrl+V)", command=self.paste,
                          state=state(self._clipboard is not None))
        menu.add_separator()
        menu.add_command(label="เลื่อนขึ้น", command=self.move_up,
                          state=state(has_sel and idx > 0))
        menu.add_command(label="เลื่อนลง", command=self.move_down,
                          state=state(has_sel and idx < len(items) - 1))
        menu.add_separator()
        menu.add_command(label="ลบ (Delete)", command=self.delete, state=state(has_sel))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _selected_index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def refresh(self):
        self.listbox.delete(0, "end")
        for i, item in enumerate(self._get_items(), 1):
            self.listbox.insert("end", self._make_label(i, item))

    def add(self):
        result = self._open_dialog(None)
        if result is None:
            return
        self._snapshot()
        items = self._get_items()
        idx = self._selected_index()
        idx = idx + 1 if idx is not None else len(items)
        items.insert(idx, result)
        self.refresh()
        self.listbox.selection_set(idx)

    def edit(self):
        idx = self._selected_index()
        if idx is None:
            return
        items = self._get_items()
        result = self._open_dialog(items[idx])
        if result is None:
            return
        self._snapshot()
        items[idx] = result
        self.refresh()
        self.listbox.selection_set(idx)

    def move_up(self):
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        self._snapshot()
        items = self._get_items()
        items[idx - 1], items[idx] = items[idx], items[idx - 1]
        self.refresh()
        self.listbox.selection_set(idx - 1)

    def move_down(self):
        idx = self._selected_index()
        items = self._get_items()
        if idx is None or idx >= len(items) - 1:
            return
        self._snapshot()
        items[idx], items[idx + 1] = items[idx + 1], items[idx]
        self.refresh()
        self.listbox.selection_set(idx + 1)

    def delete(self):
        idx = self._selected_index()
        if idx is None:
            return
        items = self._get_items()
        if self._confirm_delete and not self._confirm_delete(items[idx], idx):
            return
        self._snapshot()
        items.pop(idx)
        self.refresh()

    def copy(self):
        idx = self._selected_index()
        if idx is None:
            return
        self._clipboard = copy.deepcopy(self._get_items()[idx])

    def paste(self):
        if self._clipboard is None:
            return
        self._snapshot()
        items = self._get_items()
        idx = self._selected_index()
        idx = idx + 1 if idx is not None else len(items)
        items.insert(idx, copy.deepcopy(self._clipboard))
        self.refresh()
        self.listbox.selection_set(idx)
