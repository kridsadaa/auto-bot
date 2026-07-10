"""
SAP Shadow Recorder — บันทึก action ที่เกิดขึ้นใน SAP ระหว่างรัน loop ภาพ
ทำงานเบื้องหลัง ถ้า SAP scripting ไม่พร้อมก็ fail อย่างเงียบๆ (ไม่กระทบ loop)

วิธีใช้:
    cap = SapCapture()
    cap.start()               # เริ่ม shadow record
    ... (รัน loop ภาพตามปกติ)
    events = cap.stop()       # คืน list ของ CapturedEvent
    steps = to_sap_steps(events)  # แปลงเป็น step YAML
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from engine.logger import get_logger


@dataclass
class CapturedEvent:
    kind: Literal["set_field", "press", "get_field"]
    field_id: str
    value: str = ""           # ค่าที่ใส่ (set) หรืออ่านได้ (get)
    vkey: int | None = None   # สำหรับ sendVKey
    timestamp: float = field(default_factory=time.time)

    def to_step(self) -> dict:
        if self.kind == "set_field":
            return {"action": "sap_set_field", "field_id": self.field_id, "text": self.value}
        if self.kind == "press" and self.vkey is not None:
            return {"action": "sap_press", "vkey": self.vkey}
        if self.kind == "press":
            return {"action": "sap_press", "field_id": self.field_id}
        if self.kind == "get_field":
            return {"action": "sap_get_field", "field_id": self.field_id,
                    "variable": "CAPTURED_VALUE"}
        return {}


def to_sap_steps(events: list[CapturedEvent]) -> list[dict]:
    """แปลง list ของ CapturedEvent เป็น step YAML (กรอง event ซ้ำออก)"""
    steps = []
    seen = set()
    for ev in events:
        key = (ev.kind, ev.field_id, ev.value, ev.vkey)
        if key in seen:
            continue
        seen.add(key)
        s = ev.to_step()
        if s:
            steps.append(s)
    return steps


class SapCapture:
    """Shadow recorder — poll SAP scripting history เบื้องหลัง

    COM (STA) object ใช้ตรงๆ ข้าม thread ไม่ได้ตามกติกาของ COM — เดิมโค้ดนี้เชื่อม SAP
    บน caller thread แล้วให้ background thread เรียก self._sess ตรงๆ โดยไม่เคย
    CoInitialize/marshal อะไรเลย ทำให้ได้ access violation ระดับ native เป็นครั้งคราว
    (แก้ผิดครั้งแรกด้วยการย้ายการเชื่อมทั้งหมดเข้า background thread เอง แต่กลับพบว่า
    เรียก GetObject("SAPGUI") จาก thread ที่ไม่ใช่ thread เดิมที่ SAP Logon ผูก apartment ไว้
    จะ "ค้างตลอดกาล" ไม่ raise — แย่กว่าเดิม)

    วิธีที่ถูกต้อง (ยืนยันกับ SAP จริงแล้ว): เชื่อม SAP บน caller thread เหมือนเดิม (จุดนี้
    เชื่อถือได้) แล้ว marshal ตัว interface pointer ข้าม thread อย่างถูกกติกาด้วย
    CoMarshalInterThreadInterfaceInStream — background thread CoInitialize ของตัวเอง
    แล้ว unmarshal กลับเป็น proxy ที่ใช้ได้ในเธรดนั้นก่อนเริ่ม poll"""

    def __init__(self, poll_interval: float = 0.15, observer=None):
        self._poll = poll_interval
        self._events: list[CapturedEvent] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._available = False
        self._last_focus_id: str | None = None
        self._last_field_value: dict[str, str] = {}
        self._sess = None
        # observer(screen, field_id, value) — เรียกทุกครั้งที่จับ set_field ได้
        # (ใช้โดย PatternStore ใน Full Copilot observe mode)
        self._observer = observer

    def start(self) -> bool:
        """เชื่อม SAP บน thread ที่เรียก (จุดที่ทำงานได้เสถียร) แล้ว marshal session
        ไปให้ background thread ใช้ poll ต่อ คืน True ถ้าเชื่อม SAP scripting สำเร็จ"""
        try:
            import pythoncom
            from engine.sap_actions import _get_session
            sess = _get_session()
            stream = pythoncom.CoMarshalInterThreadInterfaceInStream(
                pythoncom.IID_IDispatch, sess._oleobj_)
            self._available = True
        except Exception as e:
            get_logger().info(f"SAP Capture ไม่พร้อม (ไม่กระทบ loop): {e}")
            self._available = False
            return False

        self._events.clear()
        self._last_field_value.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(stream,), daemon=True)
        self._thread.start()
        get_logger().info("SAP Shadow Capture เริ่มแล้ว")
        return True

    def stop(self) -> list[CapturedEvent]:
        """หยุด recording คืน events ที่จับได้"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        get_logger().info(f"SAP Shadow Capture จบ ({len(self._events)} events)")
        return list(self._events)

    def _run(self, stream):
        """unmarshal session ให้ใช้ได้ในเธรดนี้ + วน poll — CoInitialize/CoUninitialize คู่กันเสมอ"""
        import pythoncom
        import win32com.client as win32
        pythoncom.CoInitialize()
        try:
            try:
                raw = pythoncom.CoGetInterfaceAndReleaseStream(stream, pythoncom.IID_IDispatch)
                self._sess = win32.Dispatch(raw)
            except Exception as e:
                get_logger().warning(f"SAP Capture: unmarshal session ไม่สำเร็จ: {e}")
                return

            while self._running:
                try:
                    self._tick()
                except Exception:
                    pass
                time.sleep(self._poll)
        finally:
            pythoncom.CoUninitialize()

    def _tick(self):
        """ตรวจ focus ที่เปลี่ยนไปและค่าใน field — บันทึกเมื่อเปลี่ยน"""
        try:
            win = self._sess.ActiveWindow
            focused = win.GuiFocus
            fid = str(focused.Id)

            # ช่องรหัสผ่าน: ห้ามจดค่าเด็ดขาด (ทั้ง events และ observer)
            try:
                if focused.IsPassword:
                    self._last_field_value.pop(fid, None)
                    self._last_focus_id = fid
                    return
            except Exception:
                pass  # element ที่ไม่มี IsPassword = ไม่ใช่ช่องรหัสผ่าน

            # ตรวจว่า focus ย้ายมา field ที่มีข้อความ
            if hasattr(focused, "text"):
                cur_val = str(focused.text or "").strip()
                prev_val = self._last_field_value.get(fid, "__UNSET__")
                if cur_val != prev_val and prev_val != "__UNSET__" and cur_val:
                    # ค่าเปลี่ยน = ผู้ใช้/bot พิมพ์ลงช่อง
                    self._events.append(CapturedEvent(
                        kind="set_field", field_id=fid, value=cur_val))
                    if self._observer:
                        try:
                            self._observer(self._screen_key(), fid, cur_val)
                        except Exception:
                            pass
                self._last_field_value[fid] = cur_val

            self._last_focus_id = fid
        except Exception:
            pass

    def _screen_key(self) -> str:
        """ระบุ 'หน้าจอ' ปัจจุบันสำหรับจัดกลุ่มแพทเทิร์น — ใช้ transaction code ก่อน
        ถ้าไม่มีค่อย fallback เป็นชื่อ window"""
        try:
            t = str(self._sess.Info.Transaction or "").strip()
            if t:
                return t
        except Exception:
            pass
        try:
            return str(self._sess.ActiveWindow.Text or "").strip()
        except Exception:
            return ""

    def record_vkey(self, vkey: int):
        """เรียกจากภายนอก (ถ้ามี hook) เมื่อรู้ว่ากด vkey"""
        self._events.append(CapturedEvent(kind="press", field_id="", vkey=vkey))
