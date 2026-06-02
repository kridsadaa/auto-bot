import tkinter as tk
from unittest.mock import MagicMock
from gui.sequence_editor import _step_label, StepDialog

def test_step_label():
    assert "click_image" in _step_label({"action": "click_image", "target": "elements/test.png"})
    assert "wait_image" in _step_label({"action": "wait_image", "target": "elements/test.png", "mode": "appear"})
    assert "wait_text" in _step_label({"action": "wait_text", "region": [10, 20, 30, 40], "mode": "filled"})
    assert "repeat" in _step_label({"action": "repeat_key_until", "key": "enter", "until": "image_appears"})
    assert "stop_if_image" in _step_label({"action": "stop_if_image", "target": "elements/error.png"})
    assert "if_image" in _step_label({"action": "if_image", "target": "elements/chk.png", "then": [1], "else": []})

def test_step_dialog_preserves_nested_fields():
    # We must run this inside a Tk context since StepDialog is a tk.Toplevel
    root = tk.Tk()
    root.withdraw()

    original_step = {
        "action": "if_image",
        "target": "elements/chk.png",
        "confidence": 0.9,
        "then": [{"action": "key", "key": "enter"}],
        "else": []
    }

    dialog = StepDialog(root, original_step)
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

    root.destroy()
