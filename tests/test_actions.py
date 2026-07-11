"""Test การเคลียร์ช่องแบบตรวจผลจริง + paste แบบ layout-proof ใน engine/actions.py

กติกา: ห้ามยิงคีย์/แตะ clipboard จริง — mock pyautogui, pyperclip (ผ่าน sys.modules
เพราะ import ในฟังก์ชัน) และ _ctrl_combo ทั้งหมด
"""
import sys

import pytest

import engine.actions as actions


class _FakePyAutoGui:
    class FailSafeException(Exception):
        pass

    def __init__(self):
        self.calls = []

    def press(self, key):
        self.calls.append(("press", key))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))


class _FakeClipboard:
    def __init__(self):
        self.value = ""

    def copy(self, text):
        self.value = text

    def paste(self):
        return self.value


@pytest.fixture
def fake_gui(monkeypatch):
    gui = _FakePyAutoGui()
    monkeypatch.setattr("engine.actions.pyautogui", gui)
    monkeypatch.setattr("engine.actions.time.sleep", lambda s: None)
    return gui


@pytest.fixture
def fake_clipboard(monkeypatch):
    clip = _FakeClipboard()
    monkeypatch.setitem(sys.modules, "pyperclip", clip)
    return clip


def _script_ctrl_combo(monkeypatch, clipboard, selections):
    """จำลอง Ctrl+C: การกดแต่ละครั้ง 'copy สิ่งที่ถูกเลือกอยู่' ตามคิว selections
    (None = ไม่มีอะไรถูกเลือก → clipboard คงเดิมเหมือนพฤติกรรมจริงของ Windows)"""
    queue = list(selections)

    def fake_combo(letter):
        assert letter == "c"
        sel = queue.pop(0) if queue else None
        if sel is not None:
            clipboard.value = sel
        return True

    monkeypatch.setattr("engine.actions._ctrl_combo", fake_combo)
    return queue


def _deletes(gui):
    return [c for c in gui.calls if c == ("press", "delete")]


def test_clear_stops_after_verified_empty(fake_gui, fake_clipboard, monkeypatch):
    # ช่องว่างตั้งแต่รอบแรก (Ctrl+C ไม่แตะ clipboard → sentinel คงเดิม) → จบรอบเดียว
    _script_ctrl_combo(monkeypatch, fake_clipboard, [None])
    actions._clear_focused_field()
    assert len(_deletes(fake_gui)) == 1


def test_clear_retries_until_leftover_gone(fake_gui, fake_clipboard, monkeypatch):
    # รอบแรกคีย์โดนกลืน ค่าเก่ายังค้าง ("MAT-001" ถูก copy ได้) → ลบแล้วตรวจซ้ำ
    # รอบสองว่างแล้ว → หยุด รวมกด delete 2 ครั้ง
    _script_ctrl_combo(monkeypatch, fake_clipboard, ["MAT-001", None])
    actions._clear_focused_field()
    assert len(_deletes(fake_gui)) == 2


def test_clear_gives_up_after_max_attempts(fake_gui, fake_clipboard, monkeypatch):
    # ค่าค้างตลอด (แอปกลืน delete ทุกรอบ) → พยายามครบ 3 รอบแล้วไปต่อ ไม่วนไม่รู้จบ
    _script_ctrl_combo(monkeypatch, fake_clipboard, ["X", "X", "X", "X"])
    actions._clear_focused_field()
    assert len(_deletes(fake_gui)) == actions._CLEAR_MAX_ATTEMPTS


def test_clear_falls_back_to_blind_single_pass_without_pyperclip(fake_gui, monkeypatch):
    # ไม่มี pyperclip → ตรวจไม่ได้ ต้องเคลียร์บอดรอบเดียวเท่าพฤติกรรมเดิม (ไม่ crash)
    import builtins
    real_import = builtins.__import__

    def no_pyperclip(name, *a, **kw):
        if name == "pyperclip":
            raise ImportError("no pyperclip")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_pyperclip)
    actions._clear_focused_field()
    assert len(_deletes(fake_gui)) == 1


def test_paste_uses_layout_proof_ctrl_combo(fake_gui, fake_clipboard, monkeypatch):
    combos = []
    monkeypatch.setattr("engine.actions._ctrl_combo",
                        lambda letter: combos.append(letter) or True)
    assert actions._paste_via_clipboard("hello") is True
    assert fake_clipboard.value == "hello"
    assert combos == ["v"]
    # ไม่ fallback ไป pyautogui.hotkey เมื่อ VK combo สำเร็จ
    assert ("hotkey", ("ctrl", "v")) not in fake_gui.calls


def test_paste_falls_back_to_pyautogui_hotkey(fake_gui, fake_clipboard, monkeypatch):
    # win32api ใช้ไม่ได้ (_ctrl_combo คืน False) → ต้องยังวางผ่าน pyautogui.hotkey เดิม
    monkeypatch.setattr("engine.actions._ctrl_combo", lambda letter: False)
    assert actions._paste_via_clipboard("hello") is True
    assert ("hotkey", ("ctrl", "v")) in fake_gui.calls
