from engine.sap_capture import CapturedEvent, to_sap_steps


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


def test_sap_capture_start_fails_gracefully_without_sap():
    from engine.sap_capture import SapCapture
    cap = SapCapture()
    ok = cap.start()   # SAP ไม่ได้เปิด → ต้อง False ไม่ raise
    assert ok is False
    events = cap.stop()
    assert events == []
