import cv2
import numpy as np
import pyautogui
from PIL import Image


class ImageNotFoundError(Exception):
    def __init__(self, template_path: str, current_screenshot: Image.Image):
        self.template_path = template_path
        self.current_screenshot = current_screenshot
        super().__init__(f"Image not found on screen: {template_path}")


def _click_point(max_loc, template, offset: tuple = None) -> tuple[int, int]:
    """
    คำนวณจุดที่จะคลิกจากตำแหน่งมุมซ้ายบนของ match (max_loc)
    - ถ้า offset = (ox, oy) → คลิกที่ (มุมซ้ายบน + offset) ตาม pixel ของ template
    - ถ้าไม่มี offset → คลิกกลางรูป
    """
    h, w = template.shape[:2]
    if offset is not None:
        ox = max(0, min(int(offset[0]), w - 1))
        oy = max(0, min(int(offset[1]), h - 1))
        return (max_loc[0] + ox, max_loc[1] + oy)
    return (max_loc[0] + w // 2, max_loc[1] + h // 2)


def capture_screen() -> np.ndarray:
    """ถ่ายภาพหน้าจอทั้งจอเป็น BGR array — ใช้ส่งเข้า find_on_screen(screen=...)
    เพื่อถ่ายครั้งเดียวแล้ว match หลาย template กับภาพเดียวกัน (เร็วกว่า + สอดคล้องกัน)"""
    screenshot = pyautogui.screenshot()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def find_on_screen(
    template_path: str,
    confidence: float = 0.85,
    region: tuple = None,
    offset: tuple = None,
    screen: np.ndarray = None,
) -> tuple[int, int] | None:
    """
    ค้นหา template image บนหน้าจอ
    คืนค่า (x, y) จุดที่จะคลิก (กลางรูป หรือ offset ที่กำหนด) หรือ None ถ้าไม่เจอ
    screen: ภาพหน้าจอ (BGR) ที่ถ่ายไว้แล้วจาก capture_screen() — ไม่ส่ง = ถ่ายใหม่เอง
    """
    if screen is not None:
        screen_np = screen if region is None else screen[
            region[1]:region[1]+region[3], region[0]:region[0]+region[2]
        ]
    else:
        screenshot = pyautogui.screenshot(region=region)
        screen_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    template = cv2.imread(template_path)
    if template is None:
        raise FileNotFoundError(f"Template image not found: {template_path}")

    result = cv2.matchTemplate(screen_np, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        cx, cy = _click_point(max_loc, template, offset)
        if region:
            cx += region[0]
            cy += region[1]
        return (cx, cy)

    return None


def find_on_screen_or_raise(
    template_path: str,
    confidence: float = 0.85,
    region: tuple = None,
    offset: tuple = None,
) -> tuple[int, int]:
    """
    เหมือน find_on_screen แต่ raise ImageNotFoundError ถ้าไม่เจอ
    พร้อมแนบ screenshot ปัจจุบันไปด้วยเพื่อแสดงใน error dialog
    """
    screenshot = pyautogui.screenshot()
    screen_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    template = cv2.imread(template_path)
    if template is None:
        raise FileNotFoundError(f"Template image not found: {template_path}")

    search_area = screen_np if region is None else screen_np[
        region[1]:region[1]+region[3], region[0]:region[0]+region[2]
    ]

    result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        cx, cy = _click_point(max_loc, template, offset)
        if region:
            cx += region[0]
            cy += region[1]
        return (cx, cy)

    raise ImageNotFoundError(template_path, screenshot)
