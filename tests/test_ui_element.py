"""Test engine.ui_element.focus_window/minimize_window — mock find_all_windows/wrapper
ทั้งหมด (pywinauto Desktop จริงต้องพึ่ง state ของเครื่อง ไม่ hermetic)
"""
import engine.ui_element as ui_element
from engine.ui_element import ElementNotFoundError, focus_window, minimize_window


class _FakeWrapper:
    def __init__(self, visible=True, enabled=True, minimized=False):
        self._visible = visible
        self._enabled = enabled
        self._minimized = minimized
        self.focused = False
        self.minimize_calls = 0

    def is_visible(self):
        return self._visible

    def is_enabled(self):
        return self._enabled

    def is_minimized(self):
        return self._minimized

    def set_focus(self):
        self.focused = True

    def minimize(self):
        self.minimize_calls += 1
        self._minimized = True


class _FakeSpec:
    def __init__(self, wrapper):
        self._wrapper = wrapper

    def wrapper_object(self):
        return self._wrapper


# ─── focus_window ─────────────────────────────────────────────────────────────

def test_focus_window_picks_first_visible_enabled_when_title_is_ambiguous(monkeypatch):
    # จำลอง bug จริงที่เจอ: regex "SAP" ตรง 2 หน้าต่าง (Logon pad ที่เปิดค้าง +
    # session จริง) — desktop.window(title_re=...) ตรงๆ จะ raise ambiguity error
    # ทันที ต้องข้ามไปใช้ find_all_windows แล้วเลือกอันที่ visible+enabled แทน
    pad = _FakeWrapper(visible=False, enabled=True)   # Logon pad: มองไม่เห็น (ถูกซ่อน/minimized)
    session = _FakeWrapper(visible=True, enabled=True)  # session จริง: โฟกัสได้

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(pad), _FakeSpec(session)])

    result = focus_window("SAP", timeout=1)
    assert result is session
    assert session.focused is True
    assert pad.focused is False


def test_focus_window_skips_disabled_window(monkeypatch):
    disabled = _FakeWrapper(visible=True, enabled=False)
    ok = _FakeWrapper(visible=True, enabled=True)

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(disabled), _FakeSpec(ok)])

    result = focus_window("SAP", timeout=1)
    assert result is ok
    assert ok.focused is True
    assert disabled.focused is False


def test_focus_window_skips_minimized_window_even_if_visible(monkeypatch):
    # is_visible() เช็คแค่ WS_VISIBLE style — หน้าต่างที่ minimize ไปแล้วก็ยัง
    # is_visible()=True อยู่ดี ต้องเช็ค is_minimized() แยกไม่งั้นการพับ SAP Logon
    # (minimize_window) จะไม่ช่วยให้ focus_window เลือกถูกตัวเลย
    minimized_pad = _FakeWrapper(visible=True, enabled=True, minimized=True)
    session = _FakeWrapper(visible=True, enabled=True, minimized=False)

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(minimized_pad), _FakeSpec(session)])

    result = focus_window("SAP", timeout=1)
    assert result is session
    assert session.focused is True
    assert minimized_pad.focused is False


def test_focus_window_raises_when_no_window_matches(monkeypatch):
    monkeypatch.setattr(ui_element, "find_all_windows", lambda title: [])
    try:
        focus_window("Nope", timeout=0.3)
        assert False, "ควร raise ElementNotFoundError"
    except ElementNotFoundError:
        pass


def test_focus_window_raises_when_none_visible_or_enabled(monkeypatch):
    hidden = _FakeWrapper(visible=False, enabled=True)
    disabled = _FakeWrapper(visible=True, enabled=False)

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(hidden), _FakeSpec(disabled)])

    try:
        focus_window("SAP", timeout=0.3)
        assert False, "ควร raise ElementNotFoundError"
    except ElementNotFoundError:
        pass
    assert hidden.focused is False
    assert disabled.focused is False


def test_focus_window_retries_until_window_becomes_ready(monkeypatch):
    # หน้าต่างยังไม่ทัน visible ตอน poll แรก (กำลังเปิด) → ต้อง poll ซ้ำจนกว่าจะพร้อม
    late = _FakeWrapper(visible=False, enabled=True)
    calls = {"n": 0}

    def fake_find_all(title):
        calls["n"] += 1
        if calls["n"] >= 2:
            late._visible = True
        return [_FakeSpec(late)]

    monkeypatch.setattr(ui_element, "find_all_windows", fake_find_all)
    monkeypatch.setattr(ui_element.time, "sleep", lambda s: None)

    result = focus_window("SAP", timeout=2)
    assert result is late
    assert late.focused is True


# ─── minimize_window ──────────────────────────────────────────────────────────

def test_minimize_window_minimizes_every_match(monkeypatch):
    pad = _FakeWrapper(visible=True, minimized=False)
    other = _FakeWrapper(visible=True, minimized=False)

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(pad), _FakeSpec(other)])

    n = minimize_window("SAP Logon", timeout=1)
    assert n == 2
    assert pad.minimize_calls == 1
    assert other.minimize_calls == 1


def test_minimize_window_skips_already_minimized(monkeypatch):
    already = _FakeWrapper(visible=True, minimized=True)
    fresh = _FakeWrapper(visible=True, minimized=False)

    monkeypatch.setattr(ui_element, "find_all_windows",
                         lambda title: [_FakeSpec(already), _FakeSpec(fresh)])

    n = minimize_window("SAP Logon", timeout=1)
    assert n == 1
    assert already.minimize_calls == 0
    assert fresh.minimize_calls == 1


def test_minimize_window_returns_zero_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(ui_element, "find_all_windows", lambda title: [])
    monkeypatch.setattr(ui_element.time, "sleep", lambda s: None)
    assert minimize_window("Nope", timeout=0.3) == 0


def test_minimize_window_retries_until_window_appears(monkeypatch):
    calls = {"n": 0}
    win = _FakeWrapper(visible=True, minimized=False)

    def fake_find_all(title):
        calls["n"] += 1
        return [_FakeSpec(win)] if calls["n"] >= 2 else []

    monkeypatch.setattr(ui_element, "find_all_windows", fake_find_all)
    monkeypatch.setattr(ui_element.time, "sleep", lambda s: None)

    assert minimize_window("SAP Logon", timeout=2) == 1
    assert win.minimize_calls == 1
