"""
Pattern Observer — Full Copilot ขั้น 1 "Suggest from repetition"

เก็บสิ่งที่ผู้ใช้กรอกใน SAP (หน้าจอ, field_id, ค่า) ลงไฟล์ local เท่านั้น
เมื่อเจอ field เดิม + ค่าเดิม ซ้ำถึงเกณฑ์ (default 3 ครั้ง) จะเสนอสร้าง loop ให้
— ไม่จดช่อง password (กรองที่ SapCapture), ไม่ส่งข้อมูลออกนอกเครื่อง,
และการสร้าง loop ต้องให้ผู้ใช้ยืนยันเสมอ

วิธีใช้:
    store = PatternStore()
    cap = SapCapture(observer=store.record)
    cap.start()
    ...
    cap.stop()
    for sug in store.suggestions(min_repeats=3):
        # ถามผู้ใช้ → suggestion_to_loop(sug) → เซฟลง config
"""
import json
import os
import time
from engine.logger import get_logger

DEFAULT_PATH = os.path.join("config", "observed_patterns.json")

# เก็บ event ล่าสุดไม่เกินนี้ — กันไฟล์โตไม่รู้จบ
MAX_EVENTS = 2000


class PatternStore:
    """เก็บ event ที่สังเกตได้ + วิเคราะห์หาแพทเทิร์นซ้ำ (ไฟล์ JSON local)"""

    def __init__(self, path: str = DEFAULT_PATH):
        self._path = path
        self._events: list[dict] = []
        self._dismissed: set[str] = set()
        self._load()

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._events = list(data.get("events", []))
            self._dismissed = set(data.get("dismissed", []))
        except FileNotFoundError:
            pass
        except Exception as e:
            get_logger().warning(f"PatternStore: อ่านไฟล์ไม่ได้ เริ่มใหม่: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(
                    {"events": self._events[-MAX_EVENTS:],
                     "dismissed": sorted(self._dismissed)},
                    f, ensure_ascii=False, indent=1)
        except Exception as e:
            get_logger().warning(f"PatternStore: เซฟไฟล์ไม่ได้: {e}")

    def record(self, screen: str, field_id: str, value: str):
        """จด 1 event (เรียกจาก SapCapture observer callback — thread ไหนก็ได้)"""
        if not field_id or not value:
            return
        self._events.append({
            "screen": screen or "",
            "field_id": field_id,
            "value": value,
            "ts": time.time(),
        })
        if len(self._events) > MAX_EVENTS:
            self._events = self._events[-MAX_EVENTS:]
        self._save()

    @staticmethod
    def _key(screen: str, field_id: str, value: str) -> str:
        return f"{screen}|{field_id}|{value}"

    def suggestions(self, min_repeats: int = 3) -> list[dict]:
        """คืนแพทเทิร์นที่ซ้ำถึงเกณฑ์และยังไม่เคยถูกปัดตก
        รูปแบบ: [{"screen": ..., "fields": [{"field_id", "value", "count"}, ...]}, ...]"""
        counts: dict[tuple, int] = {}
        for ev in self._events:
            k = (ev.get("screen", ""), ev.get("field_id", ""), ev.get("value", ""))
            counts[k] = counts.get(k, 0) + 1

        by_screen: dict[str, list[dict]] = {}
        for (screen, fid, value), n in counts.items():
            if n < min_repeats:
                continue
            if self._key(screen, fid, value) in self._dismissed:
                continue
            by_screen.setdefault(screen, []).append(
                {"field_id": fid, "value": value, "count": n})

        result = []
        for screen, fields in sorted(by_screen.items()):
            fields.sort(key=lambda f: -f["count"])
            result.append({"screen": screen, "fields": fields})
        return result

    def dismiss(self, suggestion: dict):
        """ผู้ใช้ปัดตกข้อเสนอ — จำไว้จะได้ไม่ถามซ้ำ"""
        for f in suggestion.get("fields", []):
            self._dismissed.add(
                self._key(suggestion.get("screen", ""), f["field_id"], f["value"]))
        self._save()

    def clear(self):
        """ล้างข้อมูลที่สังเกตทั้งหมด (ปุ่มล้างใน GUI / ผู้ใช้ขอลบ)"""
        self._events = []
        self._dismissed = set()
        self._save()


def suggestion_to_loop(suggestion: dict) -> tuple[str, dict]:
    """แปลง suggestion เป็น (ชื่อ loop, loop config) พร้อมเซฟลง bot_config"""
    screen = suggestion.get("screen") or "screen"
    name = f"observed_{screen}".replace("/", "_").replace(" ", "_")
    steps = [
        {"action": "sap_set_field", "field_id": f["field_id"], "text": f["value"]}
        for f in suggestion.get("fields", [])
    ]
    return name, {"steps": steps}
