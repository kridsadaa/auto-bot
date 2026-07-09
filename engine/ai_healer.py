"""
AI Self-Healing layer for auto-bot.

When OpenCV template matching fails (ImageNotFoundError), this module
saves the current screen + request to ai_heal/ directory, then waits
for Claude Code (running as watcher) to respond with corrected coordinates.

Protocol:
  auto-bot writes  → ai_heal/screen.png  (current screenshot)
                   → ai_heal/request.json (what was being looked for)
  Claude Code reads → ai_heal/screen.png  (natively, no API key needed)
  Claude Code writes → ai_heal/response.json (x,y or fallback:true)
  auto-bot reads   → ai_heal/response.json, clicks corrected coords
"""

import json
import time
from pathlib import Path
from typing import Tuple, Optional
from engine.logger import get_logger

AI_HEAL_DIR = Path(__file__).resolve().parent.parent / "ai_heal"


def request_heal(
    template_path: str,
    screenshot,
    timeout: int = 60,
) -> Optional[Tuple[int, int]]:
    """
    Save heal request and wait for Claude Code to respond.
    Returns (x, y) of the corrected click position, or None if fallback needed.
    """
    AI_HEAL_DIR.mkdir(exist_ok=True)

    screen_path = AI_HEAL_DIR / "screen.png"
    request_path = AI_HEAL_DIR / "request.json"
    response_path = AI_HEAL_DIR / "response.json"

    screenshot.save(str(screen_path))

    # ลบ response เก่าก่อนเขียน request ใหม่เสมอ — กัน race ที่ response.json ค้างจากรอบก่อน
    # ถูกอ่านเป็นคำตอบของ request รอบนี้ (ถ้าลบทีหลังอาจไปลบ response ใหม่ที่เพิ่งเขียนทัน)
    if response_path.exists():
        response_path.unlink()

    request_data = {
        "template_path": template_path,
        "timestamp": time.time(),
        "instructions": (
            f"Image matching failed for: {template_path}\n"
            "Look at screen.png and find where this element is now.\n"
            "Write response.json with {\"x\": <int>, \"y\": <int>} to click it,\n"
            "or {\"fallback\": true} if you cannot find it."
        ),
    }
    request_path.write_text(json.dumps(request_data, ensure_ascii=False, indent=2))

    get_logger().info(f"AI heal requested for: {template_path} — waiting up to {timeout}s")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if response_path.exists():
            try:
                resp = json.loads(response_path.read_text(encoding="utf-8"))
                response_path.unlink()
                if resp.get("fallback"):
                    get_logger().info("AI heal: fallback (not found by AI)")
                    return None
                x, y = int(resp["x"]), int(resp["y"])
                get_logger().info(f"AI heal: coordinates ({x}, {y})")
                return (x, y)
            except Exception as e:
                get_logger().warning(f"AI heal: bad response — {e}")
        time.sleep(1)

    get_logger().warning(f"AI heal: timeout after {timeout}s")
    return None


def is_available() -> bool:
    return True
