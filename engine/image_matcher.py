import cv2
import numpy as np
import pyautogui
from PIL import Image


class ImageNotFoundError(Exception):
    def __init__(self, template_path: str, current_screenshot: Image.Image):
        self.template_path = template_path
        self.current_screenshot = current_screenshot
        super().__init__(f"Image not found on screen: {template_path}")


def find_on_screen(
    template_path: str,
    confidence: float = 0.85,
    region: tuple = None,
) -> tuple[int, int] | None:
    """
    ค้นหา template image บนหน้าจอ
    คืนค่า (x, y) จุดกึ่งกลางของที่เจอ หรือ None ถ้าไม่เจอ
    """
    screenshot = pyautogui.screenshot(region=region)
    screen_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    template = cv2.imread(template_path)
    if template is None:
        raise FileNotFoundError(f"Template image not found: {template_path}")

    result = cv2.matchTemplate(screen_np, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        h, w = template.shape[:2]
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        if region:
            cx += region[0]
            cy += region[1]
        return (cx, cy)

    return None


def find_on_screen_or_raise(
    template_path: str,
    confidence: float = 0.85,
    region: tuple = None,
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
        h, w = template.shape[:2]
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        if region:
            cx += region[0]
            cy += region[1]
        return (cx, cy)

    raise ImageNotFoundError(template_path, screenshot)
