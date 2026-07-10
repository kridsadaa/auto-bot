import time

from engine.sap_actions import pick_field_id


class _FakeElement:
    def __init__(self, id_):
        self.Id = id_


class _FakeWindow:
    def __init__(self, element):
        self.GuiFocus = element


class _FakeSession:
    def __init__(self, element):
        self.ActiveWindow = _FakeWindow(element)


def test_pick_field_id_returns_none_when_scripting_not_available(monkeypatch):
    def raise_not_available(*a, **kw):
        from engine.sap_actions import SapNotAvailableError
        raise SapNotAvailableError("ไม่พบ SAP GUI")

    monkeypatch.setattr("engine.sap_actions._get_session", raise_not_available)
    assert pick_field_id(timeout=1) is None


def test_pick_field_id_ignores_field_focused_before_start(monkeypatch):
    # focus ไม่เปลี่ยนเลยตลอด timeout (ผู้ใช้ไม่ได้คลิกอะไรใหม่) → ต้องคืน None
    # ไม่ใช่ field เดิมที่ focus ค้างอยู่ก่อนเปิดตัวจิ้ม (bug เดิม: คืน field เดิมทันที)
    fake_sess = _FakeSession(_FakeElement("wnd[0]/usr/ctxtMATNR"))
    monkeypatch.setattr("engine.sap_actions._get_session", lambda *a, **kw: fake_sess)

    result = pick_field_id(timeout=0.3)
    assert result is None


def test_pick_field_id_returns_new_field_after_focus_changes(monkeypatch):
    element = _FakeElement("wnd[0]/usr/ctxtMATNR")
    fake_sess = _FakeSession(element)
    monkeypatch.setattr("engine.sap_actions._get_session", lambda *a, **kw: fake_sess)

    def click_new_field_after_delay():
        time.sleep(0.15)
        element.Id = "wnd[0]/usr/ctxtWERKS"  # ผู้ใช้คลิก field ใหม่

    import threading
    threading.Thread(target=click_new_field_after_delay, daemon=True).start()

    result = pick_field_id(timeout=2)
    assert result == "wnd[0]/usr/ctxtWERKS"


def test_pick_field_id_survives_focus_read_errors(monkeypatch):
    # ActiveWindow เข้าถึงไม่ได้ชั่วคราว (เช่น หน้าจอกำลังเปลี่ยน) ต้องไม่ raise ออกมา
    class _BrokenSession:
        @property
        def ActiveWindow(self):
            raise RuntimeError("temporarily unavailable")

    monkeypatch.setattr("engine.sap_actions._get_session", lambda *a, **kw: _BrokenSession())
    assert pick_field_id(timeout=0.3) is None
