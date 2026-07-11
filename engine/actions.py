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


# virtual-key code ของปุ่มที่ใช้ทำ Ctrl+combo — ส่งตรงด้วย keybd_event ไม่ผ่านตาราง map
_VK_CONTROL = 0x11
_VK_LETTER = {"a": 0x41, "c": 0x43, "v": 0x56}


def _ctrl_combo(letter: str) -> bool:
    """กด Ctrl+<letter> ด้วย virtual-key code ตรงๆ — ใช้ได้ทุก keyboard layout

    pyautogui map ตัวอักษรเป็นปุ่มผ่าน VkKeyScanA **ครั้งเดียวตอน import** — ถ้าเปิด
    โปรแกรมตอน layout เป็นไทย (Kedmanee) ตัวอักษรละติน ('v','c','a') จะ map ไม่ได้ (-1)
    ทำให้ hotkey('ctrl','v') เงียบทั้งเซสชัน **ต่อให้ผู้ใช้สลับภาษากลับแล้วก็ตาม**
    VK code (เช่น 0x56 = ปุ่ม V ทางกายภาพ) ไม่ขึ้นกับ layout เพราะแอปตีความ
    Ctrl+ตัวอักษรจาก virtual key ไม่ใช่จากตัวอักษรที่พิมพ์ออกมา"""
    try:
        import win32api
        import win32con
        vk = _VK_LETTER[letter]
        win32api.keybd_event(_VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(vk, 0, 0, 0)
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(_VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


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
        if not _ctrl_combo("v"):
            pyautogui.hotkey("ctrl", "v")  # fallback ถ้า win32api ไม่มี (ดู _ctrl_combo)
        time.sleep(0.05)
        return True
    except Exception:
        return False


def _input_context() -> str:
    """สรุปบริบท input ณ ตอนนี้ไว้ใส่ log: หน้าต่างที่ focus อยู่ + ภาษา keyboard layout
    **ของหน้าต่างนั้น** (Windows จำภาษาแยกต่อหน้าต่าง — เปลี่ยนภาษาที่หน้าต่างหนึ่ง
    ไม่ได้เปลี่ยนให้หน้าต่างอื่น) — ปัญหาพิมพ์เพี้ยน/เคลียร์ไม่ออกที่ "เป็นบางครั้ง"
    ต้องการหลักฐานย้อนหลังว่าตอนนั้น focus อยู่ที่ไหนและภาษาอะไร"""
    try:
        import win32api
        import win32gui
        import win32process
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or "?"
        tid, _pid = win32process.GetWindowThreadProcessId(hwnd)
        lang_id = win32api.GetKeyboardLayout(tid) & 0xFFFF
        lang = {0x0409: "EN", 0x041E: "TH"}.get(lang_id, hex(lang_id))
        return f"focus={title!r} lang={lang}"
    except Exception:
        return "focus=?"


_CLEAR_SENTINEL = "__autobot_clipboard_sentinel__"
_CLEAR_MAX_ATTEMPTS = 3


def _clear_focused_field():
    """เคลียร์ค่าในช่องที่โฟกัส (End → Shift+Home → Delete) พร้อม**ตรวจผลจริง**

    จุดอ่อนของการเคลียร์แบบยิงคีย์ทิ้งคือมันบอด — ถ้าแอป (โดยเฉพาะ SAP ที่มี network
    roundtrip) ยัง busy หรือ focus ยังมาไม่ถึงช่อง คีย์จะถูกกลืนเงียบๆ แล้วค่าเก่าค้าง
    ต่อกับค่าใหม่ เลยตรวจสอบด้วย clipboard: หลังเลือกทั้งช่อง (End → Shift+Home)
    วาง sentinel ลง clipboard แล้วกด Ctrl+C (แบบ virtual-key, layout-proof) —
    ถ้า clipboard ยังเป็น sentinel = ไม่มีอะไรถูกเลือก = ช่องว่างจริง ถ้ามีข้อความ
    = ค่ายังค้าง ให้ลบแล้วตรวจซ้ำ สูงสุด 3 รอบ

    ตรวจไม่ได้ (ไม่มี pyperclip / copy พัง) → ถอยไปเคลียร์บอดรอบเดียวแบบเดิม
    หมายเหตุ: วิธีนี้เขียนทับ clipboard ของผู้ใช้ (method="paste" ก็ทับอยู่แล้ว)"""
    try:
        import pyperclip
    except Exception:
        pyperclip = None

    for attempt in range(_CLEAR_MAX_ATTEMPTS):
        pyautogui.press("end")
        pyautogui.hotkey("shift", "home")
        time.sleep(0.15)

        remaining = None  # None = ตรวจไม่ได้, "" = ยืนยันว่าว่าง, อื่นๆ = ค่าที่ยังค้าง
        if pyperclip is not None:
            try:
                pyperclip.copy(_CLEAR_SENTINEL)
                if _ctrl_combo("c"):
                    time.sleep(0.12)
                    got = pyperclip.paste()
                    # Ctrl+C ตอน selection ว่างจะไม่แตะ clipboard → sentinel คงเดิม
                    remaining = "" if got == _CLEAR_SENTINEL else (got or "").strip()
            except Exception:
                remaining = None

        pyautogui.press("delete")
        time.sleep(0.15)

        if not remaining:  # ว่างแล้ว หรือตรวจไม่ได้ (ทำ best effort เท่าพฤติกรรมเดิม)
            return
        _log(f"Clear field: ค่ายังค้าง {len(remaining)} ตัวอักษร — ลองใหม่ "
             f"(รอบ {attempt + 1}/{_CLEAR_MAX_ATTEMPTS})")

    # ครบทุกรอบยังเห็นค่าค้างตอนตรวจครั้งล่าสุด — ไปต่อได้เพราะรอบสุดท้ายเพิ่งกด Delete
    # ไปแล้ว และถ้า selection ยังค้างอยู่ การพิมพ์/วางทับจะแทนที่ selection นั้นเอง
    _log(f"Clear field: ตรวจครบ {_CLEAR_MAX_ATTEMPTS} รอบยังเห็นค่าค้าง — พิมพ์ทับต่อ", "error")


@_safe
def type_text(text: str, interval: float = 0.05, method: str = "paste", clear: bool = False):
    """พิมพ์ข้อความลงช่องที่กำลังโฟกัสอยู่
    method:
      - "paste" (default): วางผ่าน clipboard (Ctrl+V) — เร็ว/ชัวร์กับ SAP & เดสก์ท็อปแอป
                           ถ้า clipboard ใช้ไม่ได้ จะ fallback เป็นการจำลองคีย์ให้เอง
      - "type" / "keys":   จำลองการกดคีย์ทีละตัว (เหมือนพิมพ์มือ) — ใช้กับแอป/ฟิลด์ที่บล็อก paste
    clear=True: เคลียร์ค่าเดิมในช่องก่อน (End → Shift+Home → Delete พร้อมตรวจผล/ลองซ้ำ
                — ดู _clear_focused_field) กันค่าค้าง/ต่อกัน เช่นช่อง SAP ที่จำค่าเก่า
    """
    if clear:
        # ใช้ named keys (end/home/shift/delete) แทน 'ctrl+a' — ตัวอักษร 'a' ผ่าน VkKeyScan
        # ซึ่งพังเมื่อ keyboard layout เป็นไทย (Kedmanee) ทำให้ select-all เงียบ ไม่ล้างค่าเดิม
        _log(f"Clear field (End, Shift+Home, Delete + ตรวจผล) [{_input_context()}]")
        _clear_focused_field()
    ctx = _input_context()
    _log(f"Type ({method}): {repr(text)} [{ctx}]")
    if method in ("type", "keys"):
        if "lang=EN" not in ctx and text.isascii():
            # การจำลองคีย์ทีละตัวใช้ scan code ตาม layout — ภาษาไทยจะพิมพ์ข้อความ
            # อังกฤษเพี้ยน (paste ไม่มีปัญหานี้เพราะผ่าน clipboard ตรงๆ)
            _log(f"เตือน: หน้าต่างเป้าหมายไม่ได้ใช้ภาษา EN ({ctx}) — "
                 "method=type อาจพิมพ์เพี้ยน แนะนำเปลี่ยนภาษาหรือใช้ method=paste", "error")
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
        el.set_edit_text(text)  # เร็ว/ชัวร์สำหรับ Edit control — แทนที่ค่าเดิมทั้งหมดอยู่แล้ว
    except Exception:
        el.click_input()        # fallback: โฟกัสแล้วพิมพ์
        type_text(text, clear=True)  # clear=True กันค่าเดิมค้าง/ต่อกัน (set_edit_text แทนที่ทั้งหมด)


@_safe
def wait_element(selector: dict, timeout: float = 15):
    from engine import ui_element
    _log(f"Wait element: {selector} (timeout {timeout}s)")
    ui_element.find_element(selector, timeout)


@_safe
def focus_window(title: str, timeout: float = 10):
    from engine import ui_element
    _log(f"Focus window: {title!r} (timeout {timeout}s)")
    ui_element.focus_window(title, timeout)
