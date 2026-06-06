import tkinter as tk

import pytest

from gui.sequence_editor import _step_label, StepDialog
from engine import prefs


@pytest.fixture(scope="module")
def tk_root():
    """root เดียวต่อโมดูล — สร้าง tk.Tk() หลายครั้งในโปรเซสเดียวทำให้ Tcl พัง"""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_step_label():
    assert "click_image" in _step_label({"action": "click_image", "target": "elements/test.png"})
    assert "wait_image" in _step_label({"action": "wait_image", "target": "elements/test.png", "mode": "appear"})
    assert "wait_text" in _step_label({"action": "wait_text", "region": [10, 20, 30, 40], "mode": "filled"})
    assert "repeat" in _step_label({"action": "repeat_key_until", "key": "enter", "until": "image_appears"})
    assert "stop_if_image" in _step_label({"action": "stop_if_image", "target": "elements/error.png"})
    assert "if_image" in _step_label({"action": "if_image", "target": "elements/chk.png", "then": [1], "else": []})


def test_step_dialog_preserves_nested_fields(tk_root):
    original_step = {
        "action": "if_image",
        "target": "elements/chk.png",
        "confidence": 0.9,
        "then": [{"action": "key", "key": "enter"}],
        "else": []
    }

    dialog = StepDialog(tk_root, original_step)
    # Simulate editing the confidence field in GUI
    dialog._fields["confidence"].set("0.95")
    # Simulate saving
    dialog._save()

    result = dialog.get_result()
    assert result["action"] == "if_image"
    assert result["confidence"] == 0.95
    # verify nested keys are preserved
    assert result["then"] == [{"action": "key", "key": "enter"}]
    assert result["else"] == []


def test_edit_type_step_preserves_clear_first(tk_root, tmp_path, monkeypatch):
    # bug เดิม: เปิดแก้ type step ที่ clear_first=True แล้วเซฟ → ค่าหายกลับเป็น default
    monkeypatch.setattr(prefs, "PREFS_PATH", str(tmp_path / "editor_prefs.json"))

    step = {"action": "type", "text": "{X}", "method": "type", "clear_first": True}
    dlg = StepDialog(tk_root, step)
    # โหลดมาต้องโชว์ค่าจริง (เคยโชว์ "1"/ว่าง เพราะอ่าน bool ทับ)
    assert dlg._fields["clear_first"].get() == "yes"
    assert dlg._fields["method"].get() == "type"

    dlg._save()  # เซฟโดยไม่แตะอะไร — ค่าต้องไม่หาย
    res = dlg.get_result()
    assert res["clear_first"] is True
    assert res["method"] == "type"


def test_new_type_step_uses_remembered_pref(tk_root, tmp_path, monkeypatch):
    # step ใหม่ควรหยิบค่าล่าสุดที่จำไว้มาเป็น default
    monkeypatch.setattr(prefs, "PREFS_PATH", str(tmp_path / "editor_prefs.json"))
    prefs.set("type_method", "type")
    prefs.set("type_clear_first", True)

    dlg = StepDialog(tk_root)          # step ใหม่ (step=None)
    dlg._action_var.set("type")
    dlg._refresh_fields()
    assert dlg._fields["method"].get() == "type"
    assert dlg._fields["clear_first"].get() == "yes"
    dlg.destroy()
