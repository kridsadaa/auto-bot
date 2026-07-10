"""
เล็ง element ด้วย UI Automation (pywinauto, backend="uia") แทนการพึ่งรูปภาพ
ทนต่อการเปลี่ยน resolution/theme/zoom — เหมือนหลักการของ Power Automate

selector dict keys (ใส่เท่าที่จำเป็น):
  window        : regex ของชื่อหน้าต่างบนสุด (เช่น ".*Notepad")
  auto_id       : AutomationId ของ control
  name          : ชื่อ (Name property) ของ control
  control_type  : ชนิด เช่น "Edit", "Button", "CheckBox"
  class_name    : ClassName ของ control
"""
from engine.logger import get_logger

# map selector key ของเรา → ชื่อ argument ของ pywinauto child_window
_CRITERIA_MAP = {
    "auto_id": "auto_id",
    "name": "title",
    "control_type": "control_type",
    "class_name": "class_name",
}


class ElementNotFoundError(Exception):
    def __init__(self, selector: dict, detail: str = ""):
        self.selector = selector
        msg = f"หา element ไม่เจอ: {selector}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


def _desktop():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _criteria(selector: dict) -> dict:
    return {arg: selector[key] for key, arg in _CRITERIA_MAP.items() if selector.get(key)}


def find_element(selector: dict, timeout: float = 10):
    """หา element ตาม selector ภายใน timeout — คืน pywinauto wrapper หรือ raise ElementNotFoundError"""
    if not selector:
        raise ElementNotFoundError(selector, "selector ว่าง")
    try:
        desktop = _desktop()
        window = selector.get("window")
        scope = desktop.window(title_re=window) if window else desktop
        criteria = _criteria(selector)
        spec = scope.child_window(**criteria) if criteria else scope
        spec.wait("exists enabled visible ready", timeout=timeout)
        return spec.wrapper_object()
    except ElementNotFoundError:
        raise
    except Exception as e:
        get_logger().error(f"find_element failed: {selector} → {e}")
        raise ElementNotFoundError(selector, str(e)) from e


def window_exists(title: str) -> bool:
    """เช็คว่ามีหน้าต่างบนสุดที่ title ตรง regex `title` อยู่บนจอไหม (ไม่ raise ถ้าไม่เจอ) — ใช้กับ wait_window"""
    try:
        return _desktop().window(title_re=title).exists()
    except Exception:
        return False


def element_from_point(x: int, y: int) -> dict:
    """อ่าน property ของ element ที่อยู่ใต้พิกัด (x,y) → คืน selector dict สำหรับ inspector"""
    try:
        el = _desktop().from_point(x, y)
        info = el.element_info
        try:
            window = el.top_level_parent().window_text()
        except Exception:
            window = ""
        return {
            "window": window or "",
            "auto_id": getattr(info, "automation_id", "") or "",
            "name": getattr(info, "name", "") or "",
            "control_type": getattr(info, "control_type", "") or "",
            "class_name": getattr(info, "class_name", "") or "",
        }
    except Exception as e:
        get_logger().error(f"element_from_point({x},{y}) failed: {e}")
        raise ElementNotFoundError({"point": (x, y)}, str(e)) from e
