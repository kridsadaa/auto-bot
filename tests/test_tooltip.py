import tkinter as tk

import pytest

from gui.tooltip import Tooltip, add_tooltip

# tk_root มาจาก conftest.py (session-scoped) — ห้ามสร้าง tk.Tk() เองในโมดูล
# เพราะ Tcl บน Windows พังถ้ามี root ตัวที่สองหลังตัวแรกถูก destroy


@pytest.fixture
def button(tk_root):
    btn = tk.Button(tk_root, text="ทดสอบ")
    btn.pack()
    yield btn
    btn.destroy()


def test_no_popup_before_delay(button):
    tip = Tooltip(button, "คำอธิบาย", delay_ms=500)
    tip._on_enter()
    assert tip._popup is None
    tip._on_leave()


def test_popup_shows_after_show_called(button):
    tip = Tooltip(button, "คำอธิบาย", delay_ms=500)
    tip._show()
    assert tip._popup is not None
    assert tip._popup.winfo_exists()
    tip._on_leave()
    assert tip._popup is None


def test_leave_cancels_pending_show(button):
    tip = Tooltip(button, "คำอธิบาย", delay_ms=500)
    tip._on_enter()
    assert tip._after_id is not None
    tip._on_leave()
    assert tip._after_id is None
    assert tip._popup is None


def test_empty_text_does_not_show(button):
    tip = Tooltip(button, "", delay_ms=500)
    tip._show()
    assert tip._popup is None


def test_add_tooltip_returns_instance(button):
    tip = add_tooltip(button, "สวัสดี")
    assert isinstance(tip, Tooltip)
    assert tip._text == "สวัสดี"


def test_set_text_updates_text(button):
    tip = Tooltip(button, "เก่า")
    tip.set_text("ใหม่")
    assert tip._text == "ใหม่"


def test_destroyed_widget_does_not_raise(button):
    tip = Tooltip(button, "คำอธิบาย", delay_ms=500)
    tip._show()
    button.destroy()
    tip._on_leave()
