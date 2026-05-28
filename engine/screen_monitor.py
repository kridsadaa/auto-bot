import threading
import time
from typing import Callable

from engine.image_matcher import find_on_screen


class ScreenMonitor:
    """
    Thread แยกที่วน loop จับภาพหน้าจอและตรวจสอบว่าอยู่ใน state ไหน
    เมื่อเจอ state ใหม่จะเรียก on_state_detected callback
    """

    def __init__(
        self,
        states: list[dict],
        on_state_detected: Callable[[str], None],
        interval: float = 1.5,
    ):
        self._states = states
        self._on_state_detected = on_state_detected
        self._interval = interval
        self._running = False
        self._thread: threading.Thread = None
        self._current_state: str = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            detected = self._detect_state()
            if detected and detected != self._current_state:
                self._current_state = detected
                self._on_state_detected(detected)
            time.sleep(self._interval)

    def _detect_state(self) -> str | None:
        for state in self._states:
            trigger = state.get("trigger", {})
            if trigger.get("type") != "image":
                continue

            template_path = trigger.get("file", "")
            confidence = trigger.get("confidence", 0.85)

            try:
                result = find_on_screen(template_path, confidence)
                if result:
                    return state["name"]
            except FileNotFoundError:
                pass

        return None

    @property
    def current_state(self) -> str | None:
        return self._current_state
