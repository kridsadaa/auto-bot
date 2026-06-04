"""
OCR helper — อ่านข้อความจากพื้นที่บนหน้าจอด้วย Tesseract

ต้องติดตั้ง:
  - pip install pytesseract
  - Tesseract OCR engine (โปรแกรมจริง) เช่น Windows: https://github.com/UB-Mannheim/tesseract/wiki
    แล้วตั้ง path ผ่าน env var TESSERACT_CMD ถ้าไม่ได้อยู่ใน PATH
"""
import os

import pyautogui

from engine.logger import get_logger

_AVAILABLE = None  # cache: None=ยังไม่เช็ก, True/False=เช็กแล้ว


class OcrNotAvailableError(Exception):
    pass


def _ensure_available() -> bool:
    """เช็กว่า pytesseract + tesseract binary พร้อมใช้ไหม (cache ผล)"""
    global _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:
        import pytesseract

        cmd = os.environ.get("TESSERACT_CMD")
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()  # จะ raise ถ้าไม่เจอ binary
        _AVAILABLE = True
    except Exception as e:
        get_logger().warning(f"OCR ใช้ไม่ได้: {e}")
        _AVAILABLE = False
    return _AVAILABLE


def is_available() -> bool:
    return _ensure_available()


def read_text(region: tuple = None) -> str:
    """
    อ่านข้อความจาก region = (x, y, w, h) หรือทั้งจอถ้าไม่ระบุ
    คืน string (strip แล้ว)
    """
    if not _ensure_available():
        raise OcrNotAvailableError(
            "ไม่พบ Tesseract OCR — ติดตั้ง pytesseract และ Tesseract engine "
            "หรือกำหนด env var TESSERACT_CMD"
        )
    import pytesseract

    resolved_region = None
    if region:
        if isinstance(region, str):
            try:
                resolved_region = tuple(int(p.strip()) for p in region.split(",") if p.strip())
            except ValueError:
                resolved_region = None
        else:
            try:
                resolved_region = tuple(int(x) for x in region)
            except (ValueError, TypeError):
                resolved_region = None

    img = pyautogui.screenshot(region=resolved_region if resolved_region and len(resolved_region) == 4 else None)
    text = pytesseract.image_to_string(img).strip()
    get_logger().info(f"OCR region={resolved_region} → {text!r}")
    return text


def region_has_text(region: tuple = None, min_chars: int = 1) -> bool:
    """True ถ้าอ่านเจอข้อความยาวอย่างน้อย min_chars (ใช้เช็ก 'ช่องไม่ว่าง')"""
    return len(read_text(region)) >= min_chars
