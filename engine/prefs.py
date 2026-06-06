"""
จดจำการตั้งค่าล่าสุดของ editor (เช่น วิธีพิมพ์ที่ชอบใช้) เก็บเป็น JSON เล็กๆ
ใช้เป็น "ค่าเริ่มต้นของ step ใหม่" — ไม่ยุ่งกับค่าของ step ที่บันทึกไว้แล้ว

ไฟล์อยู่ที่ config/editor_prefs.json (เฉพาะเครื่อง, ไม่ขึ้น git)
"""
import json
import os

from engine.logger import get_logger

PREFS_PATH = os.path.join("config", "editor_prefs.json")


def _load() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get(key: str, default=None):
    return _load().get(key, default)


def set(key: str, value) -> None:
    data = _load()
    data[key] = value
    try:
        parent = os.path.dirname(PREFS_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        get_logger().warning(f"บันทึก prefs ไม่สำเร็จ: {e}")
