import time

from engine.sap_actions import SapNotAvailableError, _dismiss_scripting_popup, _get_session, pick_field_id


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


def test_get_session_retries_after_dismissing_scripting_popup(monkeypatch):
    # เชื่อมครั้งแรกพัง (popup "อนุญาต SAP GUI Scripting" ค้างรอกด OK) → ต้องกด OK ให้
    # แล้วเชื่อมซ้ำอีกครั้งเดียวจนสำเร็จ แทนที่จะโยน error ทิ้งเลย
    calls = {"n": 0}

    def fake_connect(connection_idx, session_idx):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SapNotAvailableError("popup ค้างอยู่")
        return "connected-session"

    monkeypatch.setattr("engine.sap_actions._connect_session", fake_connect)
    monkeypatch.setattr("engine.sap_actions._dismiss_scripting_popup", lambda *a, **kw: True)

    assert _get_session() == "connected-session"
    assert calls["n"] == 2


class _FakeButton:
    def __init__(self, exists=True):
        self._exists = exists
        self.clicked = False

    def exists(self):
        return self._exists

    def click_input(self):
        self.clicked = True


class _FakePopupWindow:
    def __init__(self, button=None):
        self._button = button

    def child_window(self, **kw):
        if self._button is None:
            raise Exception("ไม่มี child แบบนี้")
        return self._button


def test_dismiss_scripting_popup_skips_pad_window_finds_real_popup(monkeypatch):
    # จำลอง bug จริงที่เจอ: มี 2 หน้าต่าง title "SAP Logon" ชนกัน — pad หลักที่เปิดค้าง
    # (ไม่มีปุ่ม OK) กับ popup ยืนยัน scripting ตัวจริง (มีปุ่ม OK) ต้องข้าม pad แล้วเจอ/กด
    # popup จริงให้ได้ ไม่ใช่ผูกกับหน้าต่างแรกที่เจอแล้ว timeout ทิ้ง
    real_popup_btn = _FakeButton(exists=True)
    pad_window = _FakePopupWindow(button=None)
    popup_window = _FakePopupWindow(button=real_popup_btn)

    monkeypatch.setattr("engine.ui_element.find_all_windows",
                         lambda title: [pad_window, popup_window])

    assert _dismiss_scripting_popup(timeout=1) is True
    assert real_popup_btn.clicked is True


def test_dismiss_scripting_popup_returns_false_when_no_window_matches(monkeypatch):
    monkeypatch.setattr("engine.ui_element.find_all_windows", lambda title: [])
    assert _dismiss_scripting_popup(timeout=0.3) is False


def test_get_session_reraises_when_popup_never_found(monkeypatch):
    # เชื่อมพัง แต่ไม่เจอ popup ให้กด (สาเหตุอื่น เช่น SAP ปิดอยู่จริง) → ต้อง raise ต่อ ไม่ retry เงียบๆ
    def fake_connect(connection_idx, session_idx):
        raise SapNotAvailableError("ไม่พบ SAP GUI")

    monkeypatch.setattr("engine.sap_actions._connect_session", fake_connect)
    monkeypatch.setattr("engine.sap_actions._dismiss_scripting_popup", lambda *a, **kw: False)

    try:
        _get_session()
        assert False, "ควร raise SapNotAvailableError"
    except SapNotAvailableError:
        pass
