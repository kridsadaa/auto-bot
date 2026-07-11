import time

import pytest

import engine.sap_actions as sap_actions
from engine.sap_actions import SapNotAvailableError, _click_scripting_popup_ok, _get_session, pick_field_id


@pytest.fixture(autouse=True)
def clear_sap_session_cache():
    # _get_session cache session ต่อ thread — ล้างก่อน/หลังทุก test กัน fake session
    # จาก test ก่อนหน้ารั่วมาถูกใช้ซ้ำ (pytest รันทุก test ใน thread เดียวกัน)
    sap_actions._tls.sessions = {}
    yield
    sap_actions._tls.sessions = {}


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


def test_get_session_retries_when_watcher_clicked_ok(monkeypatch):
    # SAP บางเวอร์ชัน raise แทนที่จะค้างตอน popup โชว์ — ถ้า watcher กด OK ได้
    # ต้องเชื่อมซ้ำอีกครั้งเดียวจนสำเร็จ แทนที่จะโยน error ทิ้งเลย
    calls = {"n": 0}

    def fake_connect(connection_idx, session_idx):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SapNotAvailableError("popup ค้างอยู่")
        return "connected-session"

    monkeypatch.setattr("engine.sap_actions._connect_session", fake_connect)
    monkeypatch.setattr("engine.sap_actions._click_scripting_popup_ok", lambda: True)

    assert _get_session() == "connected-session"
    assert calls["n"] == 2


def test_get_session_watcher_clicks_ok_while_connect_is_blocked(monkeypatch):
    # พฤติกรรมจริงของ popup: COM call ตอน attach "ค้างรอ" คำตอบ ไม่ raise —
    # watcher ต้องกด OK คู่ขนานระหว่างที่ _connect_session ยังไม่คืนค่า
    clicked = {"done": False}

    def fake_click():
        clicked["done"] = True
        return True

    def blocking_connect(connection_idx, session_idx):
        # ค้างจนกว่า watcher จะกด OK (เหมือน COM ที่รอ popup) สูงสุด 3 วิ
        deadline = time.time() + 3
        while not clicked["done"] and time.time() < deadline:
            time.sleep(0.05)
        if not clicked["done"]:
            raise AssertionError("watcher ไม่ได้กด OK ระหว่าง connect ค้าง")
        return "connected-session"

    monkeypatch.setattr("engine.sap_actions._connect_session", blocking_connect)
    monkeypatch.setattr("engine.sap_actions._click_scripting_popup_ok", fake_click)

    assert _get_session() == "connected-session"
    assert clicked["done"] is True


class _FakeButton:
    def __init__(self, exists=True):
        self._exists = exists
        self.clicked = False

    def exists(self):
        return self._exists

    def invoke(self):
        self.clicked = True

    def click_input(self):
        self.clicked = True


class _FakePopupWindow:
    def __init__(self, button=None):
        self._button = button

    def child_window(self, **kw):
        if self._button is None:
            raise Exception("ไม่มี child แบบนี้")
        return self._button


def test_click_popup_ok_skips_pad_window_finds_real_popup(monkeypatch):
    # จำลอง bug จริงที่เจอ: มี 2 หน้าต่าง title "SAP Logon" ชนกัน — pad หลักที่เปิดค้าง
    # (ไม่มีปุ่ม OK) กับ popup ยืนยัน scripting ตัวจริง (มีปุ่ม OK) ต้องข้าม pad แล้วเจอ/กด
    # popup จริงให้ได้ ไม่ใช่ผูกกับหน้าต่างแรกที่เจอ
    real_popup_btn = _FakeButton(exists=True)
    pad_window = _FakePopupWindow(button=None)
    popup_window = _FakePopupWindow(button=real_popup_btn)

    monkeypatch.setattr("engine.ui_element.find_all_windows",
                         lambda title: [pad_window, popup_window])

    assert _click_scripting_popup_ok() is True
    assert real_popup_btn.clicked is True


def test_click_popup_ok_falls_back_to_click_input(monkeypatch):
    # ปุ่มที่ invoke ไม่ได้ (UIA ไม่รองรับ pattern) ต้องกดด้วย click_input แทน ไม่เงียบหาย
    class _NoInvokeButton(_FakeButton):
        def invoke(self):
            raise RuntimeError("InvokePattern ไม่รองรับ")

    btn = _NoInvokeButton(exists=True)
    monkeypatch.setattr("engine.ui_element.find_all_windows",
                         lambda title: [_FakePopupWindow(button=btn)])

    assert _click_scripting_popup_ok() is True
    assert btn.clicked is True


def test_click_popup_ok_returns_false_when_no_window_matches(monkeypatch):
    monkeypatch.setattr("engine.ui_element.find_all_windows", lambda title: [])
    assert _click_scripting_popup_ok() is False


def test_get_session_reraises_when_popup_never_found(monkeypatch):
    # เชื่อมพัง แต่ไม่เจอ popup ให้กด (สาเหตุอื่น เช่น SAP ปิดอยู่จริง) → ต้อง raise ต่อ ไม่ retry เงียบๆ
    calls = {"n": 0}

    def fake_connect(connection_idx, session_idx):
        calls["n"] += 1
        raise SapNotAvailableError("ไม่พบ SAP GUI")

    monkeypatch.setattr("engine.sap_actions._connect_session", fake_connect)
    monkeypatch.setattr("engine.sap_actions._click_scripting_popup_ok", lambda: False)

    with pytest.raises(SapNotAvailableError):
        _get_session()
    assert calls["n"] == 1


class _CacheableSession:
    def __init__(self):
        self.alive = True

    def findById(self, fid):
        if not self.alive:
            raise RuntimeError("RPC server unavailable")
        return object()


def test_get_session_reuses_cached_session_single_attach(monkeypatch):
    # SAP action หลาย step ต้องใช้ attach เดียวกัน — ไม่งั้น popup ขออนุญาต scripting
    # เด้งถามทุก step (นี่คือเหตุผลหลักของ cache ไม่ใช่ความเร็ว)
    calls = {"n": 0}
    sess = _CacheableSession()

    def fake_connect(connection_idx, session_idx):
        calls["n"] += 1
        return sess

    monkeypatch.setattr("engine.sap_actions._connect_dismissing_popup", fake_connect)

    assert _get_session() is sess
    assert _get_session() is sess
    assert calls["n"] == 1


def test_get_session_reconnects_when_cached_session_dead(monkeypatch):
    # SAP ถูกปิด/logout ระหว่างรอบรัน → session ใน cache ตาย ต้อง ping เจอแล้วเชื่อมใหม่
    # ไม่ใช่คืนของตายไปให้ action พังต่อ
    dead = _CacheableSession()
    dead.alive = False
    fresh = _CacheableSession()
    sap_actions._tls.sessions = {(0, 0): dead}

    monkeypatch.setattr("engine.sap_actions._connect_dismissing_popup",
                         lambda c, s: fresh)

    assert _get_session() is fresh
    assert sap_actions._tls.sessions[(0, 0)] is fresh


def test_get_session_caches_per_connection_and_session_index(monkeypatch):
    # connection/session คนละ index ต้องไม่ปนกันใน cache
    sessions = {}

    def fake_connect(connection_idx, session_idx):
        return sessions.setdefault((connection_idx, session_idx), _CacheableSession())

    monkeypatch.setattr("engine.sap_actions._connect_dismissing_popup", fake_connect)

    a = _get_session(0, 0)
    b = _get_session(1, 0)
    assert a is not b
    assert _get_session(0, 0) is a
