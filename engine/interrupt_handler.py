import threading
from pynput import keyboard


class InterruptHandler:
    """
    จัดการ interrupt สองแบบ:
    1. pyautogui FAILSAFE — ขยับ mouse ไปมุมซ้ายบน → ยกเลิกทันที (built-in)
    2. ESC key → pause/resume
    """

    def __init__(self):
        self._paused = False
        self._stopped = False
        self._listener: keyboard.Listener = None

    def start(self):
        self._paused = False
        self._stopped = False
        self._listener = keyboard.Listener(on_press=self._on_key)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        self._stopped = True
        if self._listener:
            self._listener.stop()

    def _on_key(self, key):
        if key == keyboard.Key.esc:
            if self._paused:
                self._paused = False
            else:
                self._paused = True

    def is_paused(self) -> bool:
        return self._paused

    def is_stopped(self) -> bool:
        return self._stopped

    def request_stop(self):
        self._stopped = True

    def wait_if_paused(self):
        """เรียกใน loop — block จนกว่าจะ resume หรือ stop"""
        import time
        while self._paused and not self._stopped:
            time.sleep(0.2)

    def check(self):
        """เรียกก่อนทุก action — raise ถ้าต้องหยุด"""
        self.wait_if_paused()
        if self._stopped:
            raise BotStoppedError()


class BotStoppedError(Exception):
    pass
