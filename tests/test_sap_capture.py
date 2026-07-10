import time

from engine.sap_capture import CapturedEvent, SapCapture, to_sap_steps


def test_captured_event_to_step_set_field():
    ev = CapturedEvent(kind="set_field", field_id="wnd[0]/usr/ctxtMATNR", value="1234")
    step = ev.to_step()
    assert step == {"action": "sap_set_field", "field_id": "wnd[0]/usr/ctxtMATNR", "text": "1234"}


def test_captured_event_to_step_press_vkey():
    ev = CapturedEvent(kind="press", field_id="", vkey=0)
    step = ev.to_step()
    assert step == {"action": "sap_press", "vkey": 0}


def test_captured_event_to_step_get_field():
    ev = CapturedEvent(kind="get_field", field_id="wnd[0]/sbar")
    step = ev.to_step()
    assert step["action"] == "sap_get_field"
    assert step["field_id"] == "wnd[0]/sbar"


def test_to_sap_steps_deduplicates():
    events = [
        CapturedEvent(kind="set_field", field_id="wnd[0]/usr/ctxtMATNR", value="A"),
        CapturedEvent(kind="set_field", field_id="wnd[0]/usr/ctxtMATNR", value="A"),  # ซ้ำ
        CapturedEvent(kind="press", field_id="", vkey=0),
    ]
    steps = to_sap_steps(events)
    assert len(steps) == 2
    assert steps[0]["action"] == "sap_set_field"
    assert steps[1]["action"] == "sap_press"


def test_to_sap_steps_empty():
    assert to_sap_steps([]) == []


# ─── SapCapture threading ────────────────────────────────────────────────────
# COM (STA) interface ใช้ตรงๆ ข้าม thread ไม่ได้ — SapCapture เชื่อม SAP บน caller
# thread แล้ว marshal (CoMarshalInterThreadInterfaceInStream) ไปให้ background thread
# unmarshal ใช้ต่อ mock engine.sap_actions._get_session แทนการพึ่งว่าเครื่อง test
# เปิด/ปิด SAP อยู่จริง — แต่การ marshal ต้องใช้ COM object จริง (fake python object ทำไม่ได้)
# จึงใช้ Scripting.Dictionary (มีในทุกเครื่อง Windows) เป็น stand-in สำหรับพิสูจน์ว่า
# pipeline เชื่อม→marshal→thread→unmarshal→poll→stop ไม่ crash/ค้าง โดยไม่ต้องพึ่ง SAP จริง

import pytest


class _FakeElement:
    def __init__(self, id_, text=""):
        self.Id = id_
        self.text = text


class _FakeWindow:
    def __init__(self, element):
        self.GuiFocus = element


class _FakeSession:
    def __init__(self, element):
        self.ActiveWindow = _FakeWindow(element)


def _raise_not_available(*args, **kwargs):
    from engine.sap_actions import SapNotAvailableError
    raise SapNotAvailableError("ไม่พบ SAP GUI")


def test_sap_capture_start_fails_gracefully_without_sap(monkeypatch):
    monkeypatch.setattr("engine.sap_actions._get_session", _raise_not_available)
    cap = SapCapture()
    ok = cap.start()   # เชื่อม SAP ไม่ได้ → ต้อง False ไม่ raise
    assert ok is False
    events = cap.stop()
    assert events == []
    assert cap._thread is None  # ไม่เคย spawn thread เลยตั้งแต่แรก (เชื่อมไม่สำเร็จ)


def test_sap_capture_start_marshals_and_polls_without_crash(monkeypatch):
    """พิสูจน์ pipeline เชื่อม (caller thread) → marshal → background thread → unmarshal
    → poll → stop ไม่ crash/ค้าง — mock ขอบเขต pythoncom/win32com เอง (deterministic,
    ไม่ต้องพึ่ง threading-model ของ COM object จริงที่ต่างกันไปตามแต่ละ COM server —
    Scripting.Dictionary ต้องการ apartment message pump ที่ Tk mainloop มีให้ตอน production
    แต่สคริปต์ทดสอบเปล่าไม่มี ส่วน SAP session ไม่ต้องพึ่ง pump เลย ได้ verify กับ SAP
    จริงด้วยมือแยกต่างหากแล้วว่า pipeline นี้เชื่อม+poll ต่อเนื่องได้จริงไม่ค้าง/ไม่ crash)"""
    import pythoncom
    import win32com.client as win32

    class _FakeOleobj:
        pass

    class _FakeRawSess:
        pass

    fake_elem = _FakeElement("wnd[0]/usr/ctxtMATNR", text="")
    fake_high_level_sess = _FakeSession(fake_elem)
    fake_high_level_sess._oleobj_ = _FakeOleobj()

    monkeypatch.setattr("engine.sap_actions._get_session", lambda *a, **kw: fake_high_level_sess)
    monkeypatch.setattr(pythoncom, "CoMarshalInterThreadInterfaceInStream",
                        lambda iid, oleobj: "FAKE_STREAM")
    monkeypatch.setattr(pythoncom, "CoGetInterfaceAndReleaseStream",
                        lambda stream, iid: _FakeRawSess())
    monkeypatch.setattr(win32, "Dispatch", lambda raw: fake_high_level_sess)

    cap = SapCapture(poll_interval=0.02)
    assert cap.start() is True
    time.sleep(0.05)          # ให้ tick แรกอ่านค่าว่างเริ่มต้น (ไม่นับเป็น event)
    fake_elem.text = "1234"   # ผู้ใช้/บอทพิมพ์ค่าลงช่อง
    time.sleep(0.08)          # ให้ poll รอบถัดไปเห็นค่าที่เปลี่ยน
    events = cap.stop()

    assert any(
        e.kind == "set_field" and e.field_id == "wnd[0]/usr/ctxtMATNR" and e.value == "1234"
        for e in events
    )
    assert not cap._thread.is_alive()  # stop() ต้องรอ thread จบสะอาด ไม่ทิ้งค้าง


def test_tick_records_field_change():
    # ทดสอบ logic การจับ event ของ _tick() โดยตรง (sync ไม่ผ่าน thread/marshal)
    cap = SapCapture()
    fake_elem = _FakeElement("wnd[0]/usr/ctxtMATNR", text="")
    cap._sess = _FakeSession(fake_elem)

    cap._tick()  # ครั้งแรก: ค่าว่าง → ยังไม่นับเป็น event (prev เป็น __UNSET__)
    assert cap._events == []

    fake_elem.text = "1234"
    cap._tick()  # ค่าเปลี่ยนจากว่าง → มีค่า → บันทึก event
    assert len(cap._events) == 1
    assert cap._events[0].kind == "set_field"
    assert cap._events[0].field_id == "wnd[0]/usr/ctxtMATNR"
    assert cap._events[0].value == "1234"

    cap._tick()  # ค่าเดิมซ้ำ → ไม่เพิ่ม event ใหม่
    assert len(cap._events) == 1


def test_tick_survives_broken_session():
    # _sess ที่ throw ตอนเข้าถึง property ต้องไม่ทำให้ _tick raise ออกมา
    class _BrokenSession:
        @property
        def ActiveWindow(self):
            raise RuntimeError("SAP disconnected")

    cap = SapCapture()
    cap._sess = _BrokenSession()
    cap._tick()  # ต้องไม่ raise
    assert cap._events == []


def test_sap_capture_stop_without_start_does_not_raise():
    cap = SapCapture()
    assert cap.stop() == []


# ─── Password guard + observer (Full Copilot observe mode) ──────────────────


def test_tick_never_records_password_field():
    # ช่อง IsPassword=True ต้องไม่ถูกจดทั้งใน events และ observer
    observed = []
    cap = SapCapture(observer=lambda *a: observed.append(a))
    pw = _FakeElement("wnd[0]/usr/pwdRSYST-BCODE", text="")
    pw.IsPassword = True
    cap._sess = _FakeSession(pw)

    cap._tick()
    pw.text = "secret"
    cap._tick()

    assert cap._events == []
    assert observed == []


def test_tick_calls_observer_with_screen_key():
    observed = []
    cap = SapCapture(observer=lambda screen, fid, val: observed.append((screen, fid, val)))
    fake_elem = _FakeElement("wnd[0]/usr/ctxtMATNR", text="")
    sess = _FakeSession(fake_elem)

    class _Info:
        Transaction = "VA01"

    sess.Info = _Info()
    cap._sess = sess

    cap._tick()
    fake_elem.text = "1234"
    cap._tick()

    assert observed == [("VA01", "wnd[0]/usr/ctxtMATNR", "1234")]
    assert len(cap._events) == 1  # event ปกติยังถูกจดคู่กันด้วย


def test_screen_key_falls_back_to_window_title():
    cap = SapCapture()
    sess = _FakeSession(_FakeElement("x"))
    sess.ActiveWindow.Text = "SAP Easy Access"  # ไม่มี Info.Transaction
    cap._sess = sess
    assert cap._screen_key() == "SAP Easy Access"


def test_observer_exception_does_not_break_capture():
    def boom(*a):
        raise RuntimeError("observer พัง")

    cap = SapCapture(observer=boom)
    fake_elem = _FakeElement("wnd[0]/usr/ctxtMATNR", text="")
    cap._sess = _FakeSession(fake_elem)

    cap._tick()
    fake_elem.text = "1234"
    cap._tick()  # observer raise → ต้องไม่หลุดออกมา และ event ปกติยังถูกจด

    assert len(cap._events) == 1
