"""
ทดสอบ AI Self-Healing end-to-end:
1. จำลอง ImageNotFoundError พร้อม screenshot จริง
2. เรียก request_heal() → เขียน ai_heal/request.json + screen.png
3. รอ Claude Code ตอบกลับด้วย response.json
4. พิมพ์ผลลัพธ์
"""
import sys
import time
import pyautogui
from engine.ai_healer import request_heal

print("=== AI Heal Test ===")
print("กำลังถ่าย screenshot หน้าจอปัจจุบัน...")

screenshot = pyautogui.screenshot()
screenshot.save("ai_heal_test_before.png")
print("บันทึก: ai_heal_test_before.png")

print("\nส่ง heal request (template สมมุติ: elements/save_button.png)...")
print("รอ Claude Code อ่านหน้าจอและตอบกลับ...\n")

start = time.time()
result = request_heal(
    template_path="elements/save_button.png",
    screenshot=screenshot,
    timeout=90,
)
elapsed = round(time.time() - start, 1)

if result is not None:
    x, y = result
    print(f"[OK] AI Heal success! ({elapsed}s)")
    print(f"     Coordinates: x={x}, y={y}")
else:
    print(f"[FAIL] AI Heal: fallback or timeout ({elapsed}s)")
    sys.exit(1)
