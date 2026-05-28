import time
import pyautogui
import pyperclip
import keyboard
from PIL import Image
from typing import Callable

from engine.image_matcher import find_on_screen_or_raise, ImageNotFoundError

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# delay หลัง click_image ก่อนเริ่ม type (วินาที)
CLICK_SETTLE_DELAY = 0.4

_log_callback: Callable[[str], None] = print


def set_log_callback(fn: Callable[[str], None]):
    global _log_callback
    _log_callback = fn


def _log(msg: str):
    _log_callback(msg)


def click(x: int, y: int):
    _log(f"Click ({x}, {y})")
    pyautogui.click(x, y)


def click_image(template_path: str, timeout: float = 10, confidence: float = 0.85) -> tuple[int, int]:
    """คลิกที่ตำแหน่งของ image — รอจนถึง timeout วินาที"""
    _log(f"Looking for: {template_path}")
    deadline = time.time() + timeout
    last_screenshot = None

    while time.time() < deadline:
        try:
            x, y = find_on_screen_or_raise(template_path, confidence)
            _log(f"Found & click ({x}, {y}): {template_path}")
            pyautogui.click(x, y)
            time.sleep(CLICK_SETTLE_DELAY)  # รอ app focus field ก่อน type
            return (x, y)
        except ImageNotFoundError as e:
            last_screenshot = e.current_screenshot
            time.sleep(0.5)

    raise ImageNotFoundError(template_path, last_screenshot or pyautogui.screenshot())


def type_text(text: str, interval: float = 0.05):
    """
    พิมพ์ข้อความโดยใช้ keyboard.write() inject keystroke ตรงๆ
    รองรับอักขระพิเศษและทำงานได้กับ SAP ที่ block Ctrl+V
    """
    _log(f"Type: {repr(text)}")
    keyboard.write(text, delay=interval)


def press_key(key: str):
    _log(f"Key: {key}")
    pyautogui.press(key)


def hotkey(*keys: str):
    _log(f"Hotkey: {'+'.join(keys)}")
    pyautogui.hotkey(*keys)


def drag_and_drop(src_x: int, src_y: int, dst_x: int, dst_y: int, duration: float = 0.5):
    _log(f"Drag ({src_x},{src_y}) → ({dst_x},{dst_y})")
    pyautogui.moveTo(src_x, src_y)
    pyautogui.dragTo(dst_x, dst_y, duration=duration, button="left")


def wait(seconds: float):
    _log(f"Wait {seconds}s")
    time.sleep(seconds)


def take_screenshot(save_path: str = None) -> Image.Image:
    img = pyautogui.screenshot()
    if save_path:
        img.save(save_path)
        _log(f"Screenshot saved: {save_path}")
    return img


def scroll(x: int, y: int, clicks: int):
    """เลื่อน scroll wheel ที่ตำแหน่ง (x,y) — clicks บวก = ขึ้น, ลบ = ลง"""
    _log(f"Scroll {clicks} at ({x},{y})")
    pyautogui.scroll(clicks, x=x, y=y)
