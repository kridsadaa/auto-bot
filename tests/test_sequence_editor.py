import pytest

from gui.sequence_editor import _step_label, StepDialog
from engine import prefs

# tk_root มาจาก conftest.py (session-scoped) — ห้ามสร้าง tk.Tk() เองในโมดูล
# เพราะ Tcl บน Windows พังถ้ามี root ตัวที่สองหลังตัวแรกถูก destroy


def test_step_label():
    assert "click_image" in _step_label({"action": "click_image", "target": "elements/test.png"})
    assert "wait_image" in _step_label({"action": "wait_image", "target": "elements/test.png", "mode": "appear"})
    assert "wait_text" in _step_label({"action": "wait_text", "region": [10, 20, 30, 40], "mode": "filled"})
    assert "repeat" in _step_label({"action": "repeat_key_until", "key": "enter", "until": "image_appears"})
    assert "stop_if_image" in _step_label({"action": "stop_if_image", "target": "elements/error.png"})
    assert "if_image" in _step_label({"action": "if_image", "target": "elements/chk.png", "then": [1], "else": []})


def test_step_label_sap_actions():
    # sap_set_field/sap_get_field/sap_press เดิม fallback ไปคืนแค่ชื่อ action เปล่าๆ
    # (ไม่มี field_id/text/vkey ให้เห็นใน list ต่างจาก step อื่นที่โชว์ค่าไว้) —
    # ตัด field_id ให้เหลือส่วนสุดท้ายหลัง / เท่านั้น (ตัวเต็มยาวเกินไปสำหรับ list)
    label = _step_label({
        "action": "sap_set_field", "field_id": "wnd[0]/usr/ctxtMATNR", "text": "{csv.MATERIAL}",
    })
    assert "ctxtMATNR" in label
    assert "wnd[0]/usr/ctxtMATNR" not in label
    assert "{csv.MATERIAL}" in label

    label = _step_label({
        "action": "sap_get_field", "field_id": "wnd[0]/sbar", "variable": "ORDER_NO",
    })
    assert "sbar" in label
    assert "ORDER_NO" in label

    label = _step_label({"action": "sap_press", "field_id": "wnd[0]/tbar[0]/btn[0]"})
    assert "btn[0]" in label
    assert "wnd[0]/tbar[0]/btn[0]" not in label

    label = _step_label({"action": "sap_press", "vkey": "enter"})
    assert "enter" in label


def test_step_label_launch_program():
    label = _step_label({
        "action": "launch_program", "path": r"C:\Users\me\Desktop\SAP Logon.lnk",
    })
    assert "SAP Logon.lnk" in label
    assert r"C:\Users\me\Desktop" not in label  # basename เท่านั้น เต็มยาวเกินไปสำหรับ list

    label = _step_label({"action": "launch_program", "path": "app.exe", "args": "--quiet"})
    assert "app.exe" in label
    assert "--quiet" in label


def test_step_label_kill_window():
    label = _step_label({"action": "kill_window", "title": "SAP"})
    assert "kill_window" in label
    assert "SAP" in label


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
