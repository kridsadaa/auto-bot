"""Test gui.listbox_crud.ListboxCrud — คลิกขวา = เลือกแถวใต้เมาส์ก่อนเปิดเมนู

ไม่เรียก _show_context_menu ตรงๆ (tk.Menu.tk_popup เป็น UI call จริง ไม่เหมาะ
ทดสอบแบบ headless) — ทดสอบ _select_row_at ที่แยกออกมาต่างหากแทน ใช้ tk_root
session fixture (conftest.py) เท่านั้น — ห้ามสร้าง tk.Tk() เอง
"""
import tkinter as tk

from gui.listbox_crud import ListboxCrud


def _make_crud(tk_root, items):
    listbox = tk.Listbox(tk_root)
    listbox.pack()
    crud = ListboxCrud(
        listbox, get_items=lambda: items,
        make_label=lambda pos, item: f"{pos}. {item}",
        open_dialog=lambda existing: existing,
    )
    crud.refresh()
    return crud, listbox


def _row_center_y(tk_root, listbox, index):
    """คืนพิกัด y ของกึ่งกลางแถว — bbox() คืน None ตลอดถ้าหน้าต่างยัง withdraw อยู่
    (ยังไม่ผ่าน window-manager map เลยครั้งเดียว) เลย deiconify สั้นๆแค่พอให้ Tk
    คำนวณ geometry จริงแล้ว withdraw กลับตามเดิม (ค่า bbox ที่ได้ยังใช้ได้ต่อแม้
    หลัง withdraw ไปแล้ว — geometry ไม่ได้หายไปพร้อมการซ่อนหน้าต่าง)"""
    tk_root.deiconify()
    tk_root.update()
    bbox = listbox.bbox(index)
    tk_root.withdraw()
    tk_root.update()
    return bbox[1] + bbox[3] // 2


def test_select_row_at_picks_row_under_cursor(tk_root):
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)

    y = _row_center_y(tk_root, listbox, 1)
    crud._select_row_at(y)

    assert crud._selected_index() == 1


def test_select_row_at_clears_previous_selection(tk_root):
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(0)

    y = _row_center_y(tk_root, listbox, 2)
    crud._select_row_at(y)

    assert crud._selected_index() == 2
    assert listbox.curselection() == (2,)  # เดิม 0 ต้องถูกล้าง ไม่ใช่เลือกซ้อนกัน


def test_select_row_at_is_noop_on_empty_list(tk_root):
    crud, listbox = _make_crud(tk_root, [])
    crud._select_row_at(50)  # ต้องไม่ raise แม้ nearest() ถูกเรียกกับ listbox เปล่า
    assert crud._selected_index() is None


def test_move_up_down_respect_list_boundaries(tk_root):
    # ตรงกับเงื่อนไข enable/disable ของเมนูคลิกขวา: เลื่อนขึ้นจากแถวแรก/เลื่อนลง
    # จากแถวสุดท้ายต้องไม่ทำอะไร (ปุ่มเมนูจะถูก disable ไว้ แต่ logic เบื้องหลังก็ต้อง
    # เป็น no-op เองด้วยเผื่อถูกเรียกตรงๆ)
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)

    listbox.selection_set(0)
    crud.move_up()
    assert items == ["a", "b", "c"]  # แถวแรกเลื่อนขึ้นไม่ได้ ไม่มีอะไรเปลี่ยน

    listbox.selection_clear(0, "end")
    listbox.selection_set(2)
    crud.move_down()
    assert items == ["a", "b", "c"]  # แถวสุดท้ายเลื่อนลงไม่ได้ ไม่มีอะไรเปลี่ยน


def test_paste_disabled_until_something_copied(tk_root):
    items = ["a", "b"]
    crud, listbox = _make_crud(tk_root, items)
    assert crud._clipboard is None

    crud.paste()
    assert items == ["a", "b"]  # ยังไม่มีของใน clipboard — paste ต้องไม่ทำอะไร

    listbox.selection_set(0)
    crud.copy()
    assert crud._clipboard == "a"


# ─── undo (Ctrl+Z) ────────────────────────────────────────────────────────────

def test_undo_reverts_a_wrong_paste(tk_root):
    # use case ตรงตามที่ขอ: วางผิดที่ → Ctrl+Z ย้อนกลับ
    items = ["a", "b"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(0)
    crud.copy()

    crud.paste()
    assert items == ["a", "a", "b"]

    crud.undo()
    assert items == ["a", "b"]


def test_undo_reverts_delete(tk_root):
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(1)

    crud.delete()
    assert items == ["a", "c"]

    crud.undo()
    assert items == ["a", "b", "c"]


def test_undo_reverts_move(tk_root):
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(0)

    crud.move_down()
    assert items == ["b", "a", "c"]

    crud.undo()
    assert items == ["a", "b", "c"]


def test_undo_reverts_edit(tk_root):
    items = ["a", "b"]
    crud = ListboxCrud(
        tk.Listbox(tk_root), get_items=lambda: items,
        make_label=lambda pos, item: f"{pos}. {item}",
        open_dialog=lambda existing: "EDITED",
    )
    crud.refresh()
    crud.listbox.selection_set(0)

    crud.edit()
    assert items == ["EDITED", "b"]

    crud.undo()
    assert items == ["a", "b"]


def test_undo_stacks_multiple_steps_back(tk_root):
    items = ["a", "b", "c"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(0)
    crud.copy()

    crud.paste()          # ["a", "a", "b", "c"]
    crud.delete()          # ["a", "b", "c"] (ลบ selection ที่ paste วางไว้ index 1)
    assert items == ["a", "b", "c"]

    crud.undo()             # ย้อน delete
    assert items == ["a", "a", "b", "c"]
    crud.undo()             # ย้อน paste
    assert items == ["a", "b", "c"]


def test_undo_is_noop_when_nothing_to_undo(tk_root):
    items = ["a", "b"]
    crud, listbox = _make_crud(tk_root, items)
    crud.undo()  # ไม่มี snapshot เลย — ต้องไม่ raise, list ต้องไม่เปลี่ยน
    assert items == ["a", "b"]


def test_undo_does_not_record_noop_actions(tk_root):
    # ปุ่ม/keyboard ที่ไม่ได้ทำอะไรจริง (เช่น delete โดยไม่มี selection, move_up
    # จากแถวแรก) ต้องไม่ไปเก็บ snapshot เปล่าๆ ไว้ใน undo stack
    items = ["a", "b"]
    crud, listbox = _make_crud(tk_root, items)

    crud.delete()  # ไม่มี selection — ไม่ทำอะไร
    listbox.selection_set(0)
    crud.move_up()  # อยู่แถวแรกแล้ว — ไม่ทำอะไร

    assert crud._undo_stack == []


def test_undo_does_not_mutate_list_identity(tk_root):
    # get_items() คืน reference ของ list จริงที่โค้ดอื่นถืออยู่ (เช่น self._steps)
    # undo ต้อง mutate list เดิม ไม่ใช่ผูก reference ใหม่ ไม่งั้นโค้ดที่ถือ list
    # ตัวเดิมไว้ก่อนหน้า (เช่น ปิด dialog แล้วเซฟ) จะเห็นค่าเก่าที่ไม่ได้ undo
    items = ["a", "b"]
    crud, listbox = _make_crud(tk_root, items)
    listbox.selection_set(0)

    crud.delete()
    crud.undo()

    assert items == ["a", "b"]  # ตัวแปรเดิม (ไม่ใช่ list ใหม่) ต้องเห็นผล undo ด้วย
