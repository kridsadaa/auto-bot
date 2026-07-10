"""Generic add/edit/move/delete/copy-paste controller for a Tk Listbox backed
by a plain Python list of dicts.

Every listbox-based CRUD panel in gui/sequence_editor.py (main step list,
nested step editor, switch_image cases, states list) repeated the same
curselection -> guard -> mutate list -> refresh -> reselect shape by hand.
This wraps that shape once; each panel only supplies how to render a row and
how to open its add/edit dialog, and gets Enter/Delete/Ctrl+C/Ctrl+V for free.
"""
import copy
import tkinter as tk
from tkinter import messagebox

from gui.keybind_utils import bind_ctrl_key


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
        self._bind_keys()

    def _bind_keys(self):
        self.listbox.bind("<Double-Button-1>", lambda e: self.edit())
        self.listbox.bind("<Return>", lambda e: self.edit())
        self.listbox.bind("<Delete>", lambda e: self.delete())
        bind_ctrl_key(self.listbox, "C", self.copy)
        bind_ctrl_key(self.listbox, "V", self.paste)

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
        items[idx] = result
        self.refresh()
        self.listbox.selection_set(idx)

    def move_up(self):
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        items = self._get_items()
        items[idx - 1], items[idx] = items[idx], items[idx - 1]
        self.refresh()
        self.listbox.selection_set(idx - 1)

    def move_down(self):
        idx = self._selected_index()
        items = self._get_items()
        if idx is None or idx >= len(items) - 1:
            return
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
        items = self._get_items()
        idx = self._selected_index()
        idx = idx + 1 if idx is not None else len(items)
        items.insert(idx, copy.deepcopy(self._clipboard))
        self.refresh()
        self.listbox.selection_set(idx)
