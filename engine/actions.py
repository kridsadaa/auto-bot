import time
import pyautogui
import keyboard
from PIL import Image
from typing import Callable

from engine.image_matcher import find_on_screen_or_raise, ImageNotFoundError
from engine.logger import get_logger

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

CLICK_SETTLE_DELAY = 0.4

_log_callback: Callable[[str], None] = print


class ActionError(Exception):
    pass


def set_log_callback(fn: Callable[[str], None]):
    global _log_callback
    _log_callback = fn


def _log(msg: str, level: str = "info"):
    _log_callback(msg)
    log = get_logger()
    if level == "error":
        log.error(msg)
    else:
        log.info(msg)


def _safe(fn):
    """decorator ป้องกัน FailSafeException และ Exception ทั่วไป"""
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except pyautogui.FailSafeException:
            from engine.interrupt_handler import BotStoppedError
            raise BotStoppedError("Failsafe triggered — mouse moved to corner")
        except (ActionError, ImageNotFoundError):
            raise
        except Exception as e:
            raise ActionError(f"{fn.__name__} failed: {e}") from e
    return wrapper


@_safe
def click(x: int, y: int):
    _log(f"Click ({x}, {y})")
    pyautogui.click(x, y)


@_safe
def click_image(template_path: str, timeout: float = 10, confidence: float = 0.85) -> tuple[int, int]:
    _log(f"Looking for: {template_path}")
    deadline = time.time() + timeout
    last_screenshot = None

    while time.time() < deadline:
        try:
            x, y = find_on_screen_or_raise(template_path, confidence)
            _log(f"Found & click ({x}, {y}): {template_path}")
            pyautogui.click(x, y)
            time.sleep(CLICK_SETTLE_DELAY)
            return (x, y)
        except ImageNotFoundError as e:
            last_screenshot = e.current_screenshot
            time.sleep(0.5)

    raise ImageNotFoundError(template_path, last_screenshot or pyautogui.screenshot())


@_safe
def type_text(text: str, interval: float = 0.05):
    _log(f"Type: {repr(text)}")
    keyboard.write(text, delay=interval)


@_safe
def press_key(key: str):
    _log(f"Key: {key}")
    pyautogui.press(key)


@_safe
def hotkey(*keys: str):
    _log(f"Hotkey: {'+'.join(keys)}")
    pyautogui.hotkey(*keys)


@_safe
def drag_and_drop(src_x: int, src_y: int, dst_x: int, dst_y: int, duration: float = 0.5):
    _log(f"Drag ({src_x},{src_y}) → ({dst_x},{dst_y})")
    pyautogui.moveTo(src_x, src_y)
    pyautogui.dragTo(dst_x, dst_y, duration=duration, button="left")


def wait(seconds: float):
    _log(f"Wait {seconds}s")
    time.sleep(seconds)


@_safe
def take_screenshot(save_path: str = None) -> Image.Image:
    img = pyautogui.screenshot()
    if save_path:
        img.save(save_path)
        _log(f"Screenshot saved: {save_path}")
    return img


@_safe
def scroll(x: int, y: int, clicks: int):
    _log(f"Scroll {clicks} at ({x},{y})")
    pyautogui.scroll(clicks, x=x, y=y)
