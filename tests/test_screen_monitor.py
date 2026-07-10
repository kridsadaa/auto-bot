"""ทดสอบ ScreenMonitor — edge-triggered: ยิงเมื่อ state ปรากฏ, re-arm เมื่อหายไป
ไม่ยิงซ้ำระหว่างที่หน้าเดิมค้างอยู่บนจอ + option cooldown กันยิงถี่เกิน"""
import time

from engine.screen_monitor import ScreenMonitor


def _run_monitor(seq, expect_fired, cooldown=0.0, timeout=2.0):
    """รัน monitor ด้วยผล detect ปลอมตามลำดับ seq (ตัวสุดท้ายค้างตลอด)
    รอจนยิงครบ expect_fired ครั้งหรือหมดเวลา แล้วคืน list ของ state ที่ยิง"""
    fired = []
    mon = ScreenMonitor(states=[], on_state_detected=fired.append,
                        interval=0.01, cooldown=cooldown)
    remaining = list(seq)

    def fake_detect():
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    mon._detect_state = fake_detect
    mon.start()
    deadline = time.time() + timeout
    while len(fired) < expect_fired and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.08)  # เผื่อเวลาให้ยิงเกินเกณฑ์ (ต้องไม่เกิดขึ้น)
    mon.stop()
    mon._thread.join(timeout=1)
    return fired


def test_fires_once_while_state_stays_visible():
    # หน้าเดิมค้างบนจอ → ยิงครั้งเดียว ไม่ rerun รัวๆ ทุกรอบ poll
    fired = _run_monitor(["A"], expect_fired=1)
    assert fired == ["A"]


def test_rearms_after_state_disappears():
    # หน้า A หายไป (detect คืน None) แล้วเปิดกลับมาใหม่ → ต้องยิงซ้ำได้
    fired = _run_monitor(["A", None, "A"], expect_fired=2)
    assert fired == ["A", "A"]


def test_transition_between_states_fires_both():
    # เปลี่ยนจากหน้า A ไปหน้า B โดยตรง (ไม่มีช่วงว่าง) → ยิงทั้งสอง
    fired = _run_monitor(["A", "B"], expect_fired=2)
    assert fired == ["A", "B"]


def test_cooldown_blocks_rapid_refire():
    # state เดิมกลับมาเร็วเกิน cooldown → ข้ามการยิงรอบสอง
    fired = _run_monitor(["A", None, "A"], expect_fired=1, cooldown=999.0)
    assert fired == ["A"]


def test_cooldown_applies_per_state():
    # cooldown ผูกกับ state เดิมเท่านั้น — state ใหม่ยิงได้ทันที
    fired = _run_monitor(["A", None, "B"], expect_fired=2, cooldown=999.0)
    assert fired == ["A", "B"]
