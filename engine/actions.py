import time
import pyautogui
import keyboard
from PIL import Image
from typing import Callable

from engine.image_matcher import find_on_screen, find_on_screen_or_raise, ImageNotFoundError
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
def click_image(
    template_path: str,
    timeout: float = 10,
    confidence: float = 0.85,
    offset: tuple = None,
) -> tuple[int, int]:
    where = f" @offset{tuple(offset)}" if offset else ""
    _log(f"Looking for: {template_path}{where}")
    deadline = time.time() + timeout
    last_screenshot = None

    while time.time() < deadline:
        try:
            x, y = find_on_screen_or_raise(template_path, confidence, offset=offset)
            _log(f"Found & click ({x}, {y}): {template_path}")
            pyautogui.click(x, y)
            time.sleep(CLICK_SETTLE_DELAY)
            return (x, y)
        except ImageNotFoundError as e:
            last_screenshot = e.current_screenshot
            time.sleep(0.5)

    raise ImageNotFoundError(template_path, last_screenshot or pyautogui.screenshot())


def _paste_via_clipboard(text: str) -> bool:
    """พิมพ์ผ่าน clipboard (ctrl+v) — เร็ว/ชัวร์กว่าสำหรับ SAP & desktop apps
    คืน False ถ้า pyperclip ใช้ไม่ได้ เพื่อ fallback ไป keyboard.write"""
    try:
        import pyperclip
    except Exception:
        return False
    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
        return True
    except Exception:
        return False


@_safe
def type_text(text: str, interval: float = 0.05, method: str = "paste"):
    """พิมพ์ข้อความลงช่องที่กำลังโฟกัสอยู่
    method:
      - "paste" (default): วางผ่าน clipboard (Ctrl+V) — เร็ว/ชัวร์กับ SAP & เดสก์ท็อปแอป
                           ถ้า clipboard ใช้ไม่ได้ จะ fallback เป็นการจำลองคีย์ให้เอง
      - "type" / "keys":   จำลองการกดคีย์ทีละตัว (เหมือนพิมพ์มือ) — ใช้กับแอป/ฟิลด์ที่บล็อก paste
    """
    _log(f"Type ({method}): {repr(text)}")
    if method in ("type", "keys"):
        keyboard.write(text, delay=interval)
        return
    # default = paste: SAP/desktop รับ keystroke ทีละตัวไม่ทัน → ใช้ clipboard ก่อน
    if _paste_via_clipboard(text):
        return
    keyboard.write(text, delay=interval)


@_safe
def wait_image(
    target: str,
    timeout: float = 15,
    confidence: float = 0.85,
    mode: str = "appear",
) -> bool:
    """
    รอจนรูป 'โผล่' (mode=appear) หรือ 'หายไป' (mode=disappear) ภายใน timeout
    - appear: raise ImageNotFoundError ถ้าหมดเวลายังไม่เจอ (เพื่อเข้า error dialog เดิม)
    - disappear: raise ActionError ถ้าหมดเวลายังไม่หาย
    """
    _log(f"Wait image [{mode}]: {target} (timeout {timeout}s)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = find_on_screen(target, confidence) is not None
        if (mode == "appear" and found) or (mode == "disappear" and not found):
            _log(f"เงื่อนไข '{mode}' เป็นจริง: {target}")
            return True
        time.sleep(0.4)

    if mode == "appear":
        raise ImageNotFoundError(target, pyautogui.screenshot())
    raise ActionError(f"รูปยังไม่หายไปใน {timeout}s: {target}")


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


# ─── UI Automation (element-based — ทนกว่ารูปภาพ) ─────────────────────────────

@_safe
def click_element(selector: dict, timeout: float = 10, button: str = "left"):
    from engine import ui_element
    _log(f"Click element: {selector}")
    el = ui_element.find_element(selector, timeout)
    el.click_input(button=button)


@_safe
def set_element_text(selector: dict, text: str, timeout: float = 10):
    from engine import ui_element
    _log(f"Set element text: {selector} = {repr(text)}")
    el = ui_element.find_element(selector, timeout)
    try:
        el.set_edit_text(text)  # เร็ว/ชัวร์สำหรับ Edit control
    except Exception:
        el.click_input()        # fallback: โฟกัสแล้วพิมพ์
        type_text(text)


@_safe
def wait_element(selector: dict, timeout: float = 15):
    from engine import ui_element
    _log(f"Wait element: {selector} (timeout {timeout}s)")
    ui_element.find_element(selector, timeout)
