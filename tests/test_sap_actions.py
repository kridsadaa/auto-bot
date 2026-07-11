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


def test_pick_field_id_falls_back_to_baseline_field_on_timeout(monkeypatch):
    # focus ไม่เปลี่ยนเลยตลอด timeout (เช่น ผู้ใช้จิ้ม field เดิมซ้ำ) → ยังคืน field
    # ที่ focus อยู่ตอน timeout แทนที่จะคืน None (ไม่งั้นจิ้ม field เดิมซ้ำจะ fail เสมอ)
    fake_sess = _FakeSession(_FakeElement("wnd[0]/usr/ctxtMATNR"))
    monkeypatch.setattr("engine.sap_actions._get_session", lambda *a, **kw: fake_sess)

    result = pick_field_id(timeout=0.3)
    assert result == "wnd[0]/usr/ctxtMATNR"


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
