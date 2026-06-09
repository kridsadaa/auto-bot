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
    """Shadow recorder — poll SAP scripting history เบื้องหลัง"""

    def __init__(self, poll_interval: float = 0.15):
        self._poll = poll_interval
        self._events: list[CapturedEvent] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._available = False
        self._last_focus_id: str | None = None
        self._last_field_value: dict[str, str] = {}

    def start(self) -> bool:
        """เริ่ม shadow recording คืน True ถ้า SAP scripting พร้อม"""
        try:
            from engine.sap_actions import _get_session
            self._sess = _get_session()
            self._available = True
        except Exception as e:
            get_logger().info(f"SAP Capture ไม่พร้อม (ไม่กระทบ loop): {e}")
            self._available = False
            return False

        self._events.clear()
        self._last_field_value.clear()
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
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

    def _poll_loop(self):
        while self._running:
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(self._poll)

    def _tick(self):
        """ตรวจ focus ที่เปลี่ยนไปและค่าใน field — บันทึกเมื่อเปลี่ยน"""
        try:
            win = self._sess.ActiveWindow
            focused = win.GuiFocus
            fid = str(focused.Id)

            # ตรวจว่า focus ย้ายมา field ที่มีข้อความ
            if hasattr(focused, "text"):
                cur_val = str(focused.text or "").strip()
                prev_val = self._last_field_value.get(fid, "__UNSET__")
                if cur_val != prev_val and prev_val != "__UNSET__" and cur_val:
                    # ค่าเปลี่ยน = ผู้ใช้/bot พิมพ์ลงช่อง
                    self._events.append(CapturedEvent(
                        kind="set_field", field_id=fid, value=cur_val))
                self._last_field_value[fid] = cur_val

            self._last_focus_id = fid
        except Exception:
            pass

    def record_vkey(self, vkey: int):
        """เรียกจากภายนอก (ถ้ามี hook) เมื่อรู้ว่ากด vkey"""
        self._events.append(CapturedEvent(kind="press", field_id="", vkey=vkey))
