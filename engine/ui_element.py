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
import time

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


def find_all_windows(title: str) -> list:
    """คืน WindowSpecification ของหน้าต่างบนสุด**ทุกอัน**ที่ title ตรง regex `title`
    (list ว่างถ้าไม่เจอ) ต่างจาก find_element/window_exists ตรงที่ไม่ผูกกับหน้าต่างแรก
    ที่เจอ — จำเป็นเวลามีหลายหน้าต่าง title ซ้ำกัน (เช่น SAP Logon pad หลักที่เปิดค้าง
    ตลอด ชื่อชนกับ popup ยืนยัน scripting ที่ title เดียวกันแต่เป็นคนละ instance)

    Desktop.windows() คืน UIAWrapper (wrap เสร็จแล้ว ไม่มี .wrapper_object() และไม่มี
    .child_window()) — ต้องแปลงกลับเป็น spec ที่ผูกกับ handle ของหน้าต่างนั้นๆ เพื่อให้
    ฝั่งคนเรียกใช้ child_window(...) ต่อได้เหมือน find_element"""
    try:
        desktop = _desktop()
        return [desktop.window(handle=w.handle) for w in desktop.windows(title_re=title)]
    except Exception as e:
        get_logger().error(f"find_all_windows({title!r}) failed: {e}")
        return []


def focus_window(title: str, timeout: float = 10):
    """ดึงหน้าต่างที่ title ตรง regex `title` ขึ้น foreground + ตั้ง keyboard focus
    ใช้ก่อน step ที่พึ่งคีย์บอร์ดจริง (key/type/hotkey) กัน input หลงไปหน้าต่างอื่นที่
    เผลอถูก focus ไว้ก่อนหน้า (เช่น popup ที่เพิ่งปิดไป หรือหน้าต่างที่ SAP scripting
    ใส่ค่าให้โดยไม่ย้าย focus ของ Windows เลย)

    ใช้ find_all_windows แทน desktop.window(title_re=...) ตรงๆ — ถ้า regex ตรงมากกว่า
    1 หน้าต่าง (เช่น "SAP" ตรงทั้ง "SAP Logon 760" ที่เปิดค้างตลอดและหน้าต่าง session
    จริง) desktop.window() จะ raise ambiguity error ทันทีไม่ลองอันไหนเลย (เจอจริงกับ
    ผู้ใช้) — วนดูทุกหน้าต่างที่ตรงแทน เลือกอันแรกที่ visible+enabled+ไม่ minimize จริง
    (poll จนกว่าจะเจอหรือหมด timeout เผื่อหน้าต่างยังไม่ทันขึ้น) — คืน wrapper ถ้าสำเร็จ,
    raise ElementNotFoundError ถ้าไม่มีอันไหนผ่านภายใน timeout

    หมายเหตุ: is_visible() เช็ค WS_VISIBLE style เท่านั้น หน้าต่างที่ minimize ไปแล้ว
    (เช่นหลังใช้ minimize_window พับ SAP Logon เก็บ) ก็ยัง is_visible()=True อยู่ดี —
    ต้องเช็ค is_minimized() เพิ่มด้วย ไม่งั้นการพับ SAP Logon จะไม่ช่วยให้เลือกหน้าต่าง
    ที่ถูกต้องได้เลยเมื่อ title ยังชนกันอยู่ (เช่น regex "SAP" ที่ตรงทั้งคู่)"""
    deadline = time.time() + timeout
    last_err = "ไม่พบหน้าต่างที่ visible + enabled + ไม่ minimize ตรงเงื่อนไข"
    while time.time() < deadline:
        for win in find_all_windows(title):
            try:
                wrapper = win.wrapper_object()
                if wrapper.is_visible() and wrapper.is_enabled() and not wrapper.is_minimized():
                    wrapper.set_focus()
                    return wrapper
            except Exception as e:
                last_err = str(e)
        time.sleep(0.3)
    get_logger().error(f"focus_window({title!r}) failed: {last_err}")
    raise ElementNotFoundError({"window": title}, last_err)


def minimize_window(title: str, timeout: float = 10) -> int:
    """ย่อ (minimize) หน้าต่างทุกอันที่ title ตรง regex `title` ลง taskbar

    ใช้พับ SAP Logon pad ที่เปิดค้างตลอดหลัง login สำเร็จแล้ว เพื่อไม่ให้มันแย่ง
    foreground/keyboard focus กับ session จริงอีก (โดยเฉพาะตอน popup guard ไปกด OK
    ให้ popup ที่เป็นลูกของมัน ซึ่งมักดึง SAP Logon ขึ้นมาแนบด้วย) — ต่างจาก
    focus_window ที่ต้องเลือกให้ถูกตัวเดียว ตัวนี้พับทุกอันที่ตรงได้เลยเพราะ "พับเก็บ"
    ไม่มีความเสี่ยงเหมือนการเลือกโฟกัสผิดตัว

    poll จนกว่าจะเจออย่างน้อยหนึ่งหน้าต่างหรือหมด timeout (เผื่อเรียกตอนหน้าต่างยัง
    ไม่ทันขึ้น) คืนจำนวนหน้าต่างที่ย่อสำเร็จจริง (ข้ามอันที่ minimize อยู่แล้ว) —
    คืน 0 เฉยๆถ้าหา title ไม่เจอเลย ไม่ raise เพราะไม่มีอะไรให้พับก็ไม่ถือเป็น error"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        wins = find_all_windows(title)
        if wins:
            minimized = 0
            for win in wins:
                try:
                    wrapper = win.wrapper_object()
                    if wrapper.is_visible() and not wrapper.is_minimized():
                        wrapper.minimize()
                        minimized += 1
                except Exception as e:
                    get_logger().error(f"minimize_window({title!r}) failed on one window: {e}")
            return minimized
        time.sleep(0.3)
    return 0


def kill_window(title: str, timeout: float = 10) -> int:
    """หา process ที่เป็นเจ้าของหน้าต่างทุกอันที่ title ตรง regex `title` แล้ว
    force-terminate ทันที (TerminateProcess) — ไม่ยิง WM_CLOSE ให้โปรแกรมปิดตัวเอง

    เหตุผลที่ต้อง force: โปรแกรมหลายตัว (SAP GUI เป็นตัวอย่างเด่น) เด้ง popup ถาม
    ยืนยันตอนปิดปกติ ("Do you want to end this session?") ซึ่งบล็อก automation
    ต่อไม่ได้ถ้าเป้าหมายคือ "ปิดแล้วรันต่อ" ตอนเจอ error — TerminateProcess ข้าม
    ขั้นตอนนั้นไปเลย เหมือนกด End Task ใน Task Manager

    หา PID จาก window handle ผ่าน win32process.GetWindowThreadProcessId (ไม่ใช่
    เดาจาก process name เพราะชื่อ .exe อาจไม่ตรงกับที่ผู้ใช้คาดไว้ — ใช้ title เดียวกับ
    step อื่นๆที่มีอยู่แล้ว focus_window/minimize_window ตรงไปตรงมากว่า)

    poll จนกว่าจะเจออย่างน้อยหนึ่งหน้าต่างหรือหมด timeout คืนจำนวน process ที่
    terminate สำเร็จ (นับ unique PID — หลายหน้าต่างอาจเป็น process เดียวกัน)
    คืน 0 ถ้าหา title ไม่เจอเลย ไม่ raise เพราะไม่มีอะไรให้ปิดก็ไม่ถือเป็น error"""
    import win32api
    import win32con
    import win32process

    deadline = time.time() + timeout
    while time.time() < deadline:
        wins = find_all_windows(title)
        if wins:
            pids = set()
            for win in wins:
                try:
                    wrapper = win.wrapper_object()
                    _, pid = win32process.GetWindowThreadProcessId(wrapper.handle)
                    pids.add(pid)
                except Exception as e:
                    get_logger().error(f"kill_window({title!r}) failed reading pid: {e}")
            killed = 0
            for pid in pids:
                handle = None
                try:
                    handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
                    win32api.TerminateProcess(handle, 0)
                    killed += 1
                except Exception as e:
                    get_logger().error(f"kill_window({title!r}) failed terminating pid={pid}: {e}")
                finally:
                    if handle:
                        win32api.CloseHandle(handle)
            return killed
        time.sleep(0.3)
    return 0


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
