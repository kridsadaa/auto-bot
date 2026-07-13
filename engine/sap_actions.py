"""
SAP GUI Scripting backend — คุยกับ SAP โดยตรงผ่าน COM (win32com)
ทำงานแทน image matching สำหรับ SAP: แม่นกว่า / ไม่เพี้ยนเมื่อ resolution เปลี่ยน

ต้องการ: SAP Logon → Options → Accessibility & Scripting → Enable scripting

Actions:
  sap_set_field  — ใส่ข้อความลง SAP field
  sap_get_field  — อ่านค่าจาก SAP field → เก็บลงตัวแปร
  sap_press      — กดปุ่ม/element / กด virtual key (Enter, F3, F12 ฯลฯ)
"""
import threading
import time

from engine.logger import get_logger

# virtual key numbers ที่ใช้บ่อยใน SAP
VKEY = {
    "enter": 0, "f1": 112, "f2": 113, "f3": 114, "f4": 115,
    "f5": 116, "f6": 117, "f7": 118, "f8": 119, "f9": 120,
    "f10": 121, "f11": 122, "f12": 123,
    "back": 3, "end": 15, "save": 11,
}


class SapNotAvailableError(Exception):
    pass


class SapFieldError(Exception):
    pass


# GuiComponent.Type ของ "container" ที่ไม่ใช่ field กรอกได้จริง — เจอ id ประเภทนี้
# มักแปลว่าจิ้ม/พิมพ์ field_id ตื้นเกินไป (หยุดที่ container แทนช่อง input ข้างใน)
# ปัญหาจริงที่เจอ: GuiUserArea รับ .text = ... ได้เงียบๆไม่ throw แต่ไม่มีที่ให้ค่าไปโผล่
# เลย "สำเร็จ" แบบไม่ error ทั้งที่ไม่ได้กรอกอะไรลงจอจริง (ดู sap_set_field/pick_field_id)
_CONTAINER_TYPES = {
    "GuiUserArea", "GuiContainerShell", "GuiSimpleContainer", "GuiScrollContainer",
    "GuiSplitterContainer", "GuiFrameWindow", "GuiMainWindow", "GuiDialogShell",
    "GuiTableControl", "GuiToolbar", "GuiStatusBar", "GuiMenu", "GuiMenubar",
}


def _is_container_element(el) -> bool:
    try:
        return str(el.Type) in _CONTAINER_TYPES
    except Exception:
        return False


_SCRIPTING_POPUP_OK = {"window": "SAP Logon", "auto_id": "1",
                       "name": "OK", "control_type": "Button"}

# เวลาที่กด OK ให้ popup ยืนยัน scripting ครั้งล่าสุด (stamp โดย watcher/guard ที่จุดเรียก
# ไม่ stamp ใน _click_scripting_popup_ok เอง เพื่อให้ test mock ฟังก์ชันนั้นได้โดย
# retry logic ยังทำงาน) — _connect_dismissing_popup ใช้ตัดสินว่าควรเชื่อมซ้ำไหม
_last_popup_click = 0.0


def _note_popup_clicked():
    global _last_popup_click
    _last_popup_click = time.time()


def _click_scripting_popup_ok() -> bool:
    """สแกนหารอบเดียว: popup "SAP Logon" ที่ถามอนุญาตให้ script คุม SAP GUI Scripting
    ถ้าเจอปุ่ม OK ให้กดแล้วคืน True (selector มาจากการจิ้ม element จริง: window
    "SAP Logon", auto_id "1", name "OK", control_type Button) — ไม่ poll ในตัว
    คนเรียก (watcher thread ใน _connect_dismissing_popup) คุมจังหวะวนเอง

    "SAP Logon" ก็เป็น title ของ SAP Logon pad หลักที่เปิดค้างอยู่ตลอดเวลาด้วย (คนละ
    instance จาก popup ยืนยัน scripting แต่ title ชนกัน) เลยต้องวนเช็คทุกหน้าต่างที่ title
    ตรง แทนที่จะผูกกับหน้าต่างแรกที่เจอ — ไม่งั้นจะไปหาปุ่ม OK ผิดหน้าต่าง (ใน pad หลัก
    ไม่มีปุ่มนี้) แล้วไม่เจอทุกครั้งทั้งที่ popup จริงเปิดอยู่ข้างๆ

    กดด้วย UIA invoke ก่อน (ไม่แย่งเมาส์จริง — สำคัญเพราะ bot อาจกำลังใช้เมาส์คลิกภาพ
    อยู่ขนานกัน) ถ้า invoke ใช้ไม่ได้ค่อย fallback เป็น click_input"""
    from engine import ui_element
    for win in ui_element.find_all_windows(_SCRIPTING_POPUP_OK["window"]):
        try:
            btn = win.child_window(auto_id=_SCRIPTING_POPUP_OK["auto_id"],
                                    title=_SCRIPTING_POPUP_OK["name"],
                                    control_type=_SCRIPTING_POPUP_OK["control_type"])
            if btn.exists():
                try:
                    btn.invoke()
                except Exception:
                    btn.click_input()
                get_logger().info("ปิด popup ยืนยัน SAP GUI Scripting อัตโนมัติ (กด OK)")
                return True
        except Exception:
            continue
    return False


def _connect_dismissing_popup(connection_idx: int, session_idx: int):
    """เชื่อม SAP โดยมี watcher thread คอยกด OK ให้ popup ยืนยัน scripting **คู่ขนาน**

    จุดสำคัญ: ตอน popup โชว์อยู่ COM call ฝั่ง attach จะ "ค้างรอ" คำตอบอยู่ข้างใน
    ไม่ raise ออกมา — แบบเดิมที่รอให้เชื่อมพังก่อนแล้วค่อยไปหา popup กด จึงไม่มีวัน
    ได้กดเลย เพราะโค้ดยังติดอยู่ใน _connect_session จนกว่าจะมีคนกดปุ่ม ต้องให้อีก
    thread สแกน/กดไปพร้อมกันระหว่างเชื่อมแทน (watcher ใช้ UIA ล้วน ไม่แตะ COM
    ของ SAP — ห้ามย้ายการเชื่อมเข้า background thread เพราะ GetObject จะค้าง)

    ถ้า popup guard ระดับแอปกำลังเฝ้าอยู่แล้ว (start_popup_guard) จะไม่ spawn
    watcher ซ้ำ — guard ทำหน้าที่เดียวกันอยู่ตลอดเวลาอยู่แล้ว

    เผื่อกรณี SAP บางเวอร์ชัน raise แทนที่จะค้าง: ถ้าเชื่อมพังแต่มีการกด OK เกิดขึ้น
    ระหว่าง/หลังพยายามเชื่อม (ดูจาก _last_popup_click รอสูงสุด 1.5 วิ) จะเชื่อมซ้ำ
    อีกครั้งเดียว — ถ้าไม่มี popup เลย (พังด้วยสาเหตุอื่น เช่น SAP ปิดอยู่) raise ต่อ
    ไม่ retry มั่ว"""
    t0 = time.time()
    stop = threading.Event()
    watcher = None
    if not popup_guard_running():
        def _watch():
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass
            while not stop.is_set():
                try:
                    if _click_scripting_popup_ok():
                        _note_popup_clicked()
                except Exception:
                    pass
                stop.wait(0.3)

        watcher = threading.Thread(target=_watch, daemon=True, name="sap-popup-watcher")
        watcher.start()
    try:
        try:
            return _connect_session(connection_idx, session_idx)
        except SapNotAvailableError:
            deadline = time.time() + 1.5
            while time.time() < deadline:
                if _last_popup_click >= t0:
                    return _connect_session(connection_idx, session_idx)
                time.sleep(0.1)
            raise
    finally:
        stop.set()
        if watcher is not None:
            watcher.join(timeout=1)  # ตื่นทันทีที่ stop ถูก set — กัน watcher ค้างไปสแกนต่อหลังจบ


_guard_lock = threading.Lock()
_guard_stop: threading.Event | None = None


def start_popup_guard(interval: float = 0.7) -> None:
    """เริ่มเฝ้า popup ยืนยัน SAP scripting **ตลอดอายุแอป** — เจอเมื่อไหร่กด OK ให้ทันที
    ไม่ว่าจะมี SAP action กำลังเรียกอยู่หรือไม่ (popup โผล่ได้จากทุกการ attach เช่น
    shadow capture ตอนเริ่มรัน หรือเครื่องมืออื่นในเครื่อง) เรียกซ้ำได้ปลอดภัย —
    ถ้าเฝ้าอยู่แล้วจะไม่ spawn thread ซ้ำ

    ใช้ UIA ล้วนผ่าน _click_scripting_popup_ok ไม่แตะ COM ของ SAP จึงไม่ชนกับ
    กติกา threading ของ SAP scripting"""
    global _guard_stop
    with _guard_lock:
        if _guard_stop is not None and not _guard_stop.is_set():
            return
        stop = threading.Event()
        _guard_stop = stop

    def _run():
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        while not stop.is_set():
            try:
                if _click_scripting_popup_ok():
                    _note_popup_clicked()
            except Exception:
                pass
            stop.wait(interval)

    threading.Thread(target=_run, daemon=True, name="sap-popup-guard").start()
    get_logger().info("เริ่มเฝ้า popup ยืนยัน SAP GUI Scripting (กด OK ให้อัตโนมัติ)")


def stop_popup_guard() -> None:
    """หยุด popup guard (ใช้ใน test / ตอนปิดแอป — thread เป็น daemon ตายเองอยู่แล้ว)"""
    global _guard_stop
    with _guard_lock:
        if _guard_stop is not None:
            _guard_stop.set()
            _guard_stop = None


def popup_guard_running() -> bool:
    stop = _guard_stop
    return stop is not None and not stop.is_set()


def _connect_session(connection_idx: int, session_idx: int):
    try:
        import pythoncom
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass  # init ไปแล้วในเธรดนี้ หรือไม่มี pythoncom — ปล่อยผ่าน ไม่ critical
        import win32com.client as win32
        sap_gui = win32.GetObject("SAPGUI")
        if not sap_gui:
            raise SapNotAvailableError("ไม่พบ SAP GUI")
        engine = sap_gui.GetScriptingEngine
        if not engine:
            raise SapNotAvailableError("SAP Scripting Engine ไม่พร้อม — เปิด Enable scripting ใน SAP Logon")
        conn = engine.Children(connection_idx)
        sess = conn.Children(session_idx)
        return sess
    except SapNotAvailableError:
        raise
    except Exception as e:
        raise SapNotAvailableError(f"เชื่อม SAP ไม่ได้: {e}") from e


_tls = threading.local()


def _session_alive(sess) -> bool:
    """ping เบาๆ ว่า session ที่ cache ไว้ยังใช้ได้อยู่ (SAP ยังเปิด/attach ยังไม่หลุด)"""
    try:
        sess.findById("wnd[0]")
        return True
    except Exception:
        return False


def _get_session(connection_idx: int = 0, session_idx: int = 0):
    """ดึง SAP GUI session ที่เปิดอยู่ — raise SapNotAvailableError ถ้าเชื่อมไม่ได้

    Cache session ต่อ thread: attach SAP ครั้งเดียวแล้วใช้ซ้ำทุก action ในรอบรัน
    เหตุผลหลักไม่ใช่ความเร็ว แต่เพราะ SAP เด้ง popup ขออนุญาต scripting ทุกครั้งที่มี
    script attach ใหม่ — ถ้าเชื่อมใหม่ทุก step ผู้ใช้ (หรือ watcher) ต้องกด OK ซ้ำทุก
    step ที่เป็น SAP action พอ cache แล้วถามแค่ครั้งเดียวต่อ thread ไม่ว่า step จะวาง
    ติดกันหรือไม่ ก่อนใช้ของใน cache จะ ping ก่อน ถ้าตายแล้ว (SAP ถูกปิด/logout)
    ค่อยเชื่อมใหม่ — cache แยกตาม thread เพราะ COM object ห้ามใช้ข้าม thread ตรงๆ
    (access violation ที่ except จับไม่ได้ — ดู engine/sap_capture.py)

    COM ต้อง CoInitialize ในทุก thread ที่จะใช้มันก่อน (ไม่ใช่แค่ thread ที่สร้าง object)
    ฟังก์ชันนี้ถูกเรียกได้ทั้งจาก main thread (SequenceEditor/StepDialog picker) และจาก
    bot thread (LoopRunner._execute_step) — _connect_session เรียก CoInitialize() แบบ
    idempotent กันไว้เผื่อ thread นั้นยังไม่เคย init

    ระหว่างเชื่อมมี watcher คอยกด OK ให้ popup ขออนุญาต scripting อัตโนมัติ
    (ดู _connect_dismissing_popup)"""
    cache = getattr(_tls, "sessions", None)
    if cache is None:
        cache = _tls.sessions = {}
    key = (connection_idx, session_idx)
    sess = cache.get(key)
    if sess is not None:
        if _session_alive(sess):
            return sess
        del cache[key]
    sess = _connect_dismissing_popup(connection_idx, session_idx)
    cache[key] = sess
    return sess


def is_available() -> bool:
    """True ถ้า SAP GUI เปิดอยู่และ scripting เปิดใช้งาน"""
    try:
        _get_session()
        return True
    except Exception:
        return False


def sap_set_field(field_id: str, text: str,
                  connection: int = 0, session: int = 0) -> None:
    """ใส่ข้อความลง SAP field ตาม element ID เช่น 'wnd[0]/usr/ctxtMATNR'"""
    sess = _get_session(connection, session)
    try:
        el = sess.findById(field_id)
        if _is_container_element(el):
            raise SapFieldError(
                f"sap_set_field '{field_id}': element เป็น container ({el.Type}) ไม่ใช่ field "
                "กรอกได้จริง — field_id นี้ตื้นเกินไป (มักเกิดจากจิ้ม/พิมพ์ id ไม่ตรงกล่องกรอก) "
                "ลองจิ้ม SAP field ใหม่ให้ตรงช่อง input ไม่ใช่พื้นที่รอบๆ"
            )
        el.text = text
        get_logger().info(f"SAP set '{field_id}' = {repr(text)}")
    except SapFieldError:
        raise
    except Exception as e:
        raise SapFieldError(f"sap_set_field '{field_id}': {e}") from e


def sap_get_field(field_id: str,
                  connection: int = 0, session: int = 0) -> str:
    """อ่านค่าจาก SAP field — คืน string (ว่างถ้าไม่มีค่า)"""
    sess = _get_session(connection, session)
    try:
        el = sess.findById(field_id)
        val = str(el.text or "").strip()
        get_logger().info(f"SAP get '{field_id}' = {repr(val)}")
        return val
    except Exception as e:
        raise SapFieldError(f"sap_get_field '{field_id}': {e}") from e


def sap_press(field_id: str = None, vkey: int | str = None,
              connection: int = 0, session: int = 0) -> None:
    """กดปุ่ม/element ใน SAP
    - field_id: กดปุ่มตาม ID เช่น 'wnd[0]/tbar[0]/btn[0]'
    - vkey: กด virtual key เช่น 0 (Enter), 'f3', 'save'
    """
    sess = _get_session(connection, session)
    try:
        if field_id:
            sess.findById(field_id).press()
            get_logger().info(f"SAP press '{field_id}'")
        elif vkey is not None:
            # รับได้ทั้ง int และ string ("enter", "f3" ฯลฯ)
            key_num = VKEY.get(str(vkey).lower(), vkey) if isinstance(vkey, str) else int(vkey)
            sess.findById("wnd[0]").sendVKey(key_num)
            get_logger().info(f"SAP vkey {key_num}")
        else:
            raise SapFieldError("sap_press ต้องระบุ field_id หรือ vkey")
    except SapFieldError:
        raise
    except Exception as e:
        raise SapFieldError(f"sap_press: {e}") from e


def pick_field_id(timeout: float = 30) -> str | None:
    """เปิดโหมด "จิ้มเลย" — รอให้ผู้ใช้คลิก field ใหม่ใน SAP แล้วคืน element ID
    จับ focus ตอนเริ่ม (baseline) ไว้ก่อน แล้ว poll จนกว่า focus จะเปลี่ยนไปเป็น field
    อื่นจริงๆ (ไม่ใช่แค่เช็คว่ามี focus อยู่ — SAP แทบมี element โฟกัสอยู่ตลอดเวลาอยู่แล้ว
    ถ้าไม่เทียบกับ baseline จะได้ field เดิมที่ค้าง focus อยู่ก่อนเปิดตัวจิ้มเสมอ)
    ถ้าครบ timeout แล้วยังไม่เห็น focus เปลี่ยน แต่ตอนนี้มี field focus อยู่ (เช่น ผู้ใช้
    จิ้ม field เดิมซ้ำ ทำให้ id เท่า baseline) จะคืน field นั้นแทน — ไม่งั้นการจิ้ม field
    เดิมซ้ำจะ fail ทุกครั้งทั้งที่คลิกแล้วจริง

    ไม่นับ container (GuiUserArea ฯลฯ — ดู _CONTAINER_TYPES) เป็น field ที่ใช้ได้เลย
    ไม่ว่าจะเจอตอน diff-กับ-baseline หรือตอน fallback ที่ timeout — บั๊กจริงที่เจอ: ถ้า
    หน้าจอไม่ auto-focus field ไหนตอนเปิด (GuiFocus ค้างที่ container) แล้วผู้ใช้คลิกไม่
    ทันภายใน timeout เดิมจะคืน id ของ container ไปเงียบๆ (ไม่ error) พอเอาไปตั้งเป็น
    field_id จริงจะ "sap_set_field สำเร็จ" แบบไม่ error แต่ไม่มีอะไรถูกกรอกลงจอเลย

    คืน None ถ้า timeout โดยไม่เจอ field จริงเลย หรือ scripting ไม่พร้อม
    """
    try:
        sess = _get_session()
    except Exception:
        return None

    def real_field_id() -> str | None:
        try:
            el = sess.ActiveWindow.GuiFocus
        except Exception:
            return None
        if _is_container_element(el):
            return None
        try:
            return str(el.Id)
        except Exception:
            return None

    baseline_id = real_field_id()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.2)
        fid = real_field_id()
        if fid and fid != baseline_id:
            return fid
    fallback = real_field_id()
    if fallback:
        return fallback
    get_logger().warning(
        "pick_field_id: หมดเวลาแต่ยังไม่เจอ field จริง (focus อาจอยู่ที่ container) "
        "— ลองคลิกให้ตรงกล่องกรอกอีกครั้ง"
    )
    return None
