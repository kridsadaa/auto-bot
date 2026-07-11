"""
SAP GUI Scripting backend — คุยกับ SAP โดยตรงผ่าน COM (win32com)
ทำงานแทน image matching สำหรับ SAP: แม่นกว่า / ไม่เพี้ยนเมื่อ resolution เปลี่ยน

ต้องการ: SAP Logon → Options → Accessibility & Scripting → Enable scripting

Actions:
  sap_set_field  — ใส่ข้อความลง SAP field
  sap_get_field  — อ่านค่าจาก SAP field → เก็บลงตัวแปร
  sap_press      — กดปุ่ม/element / กด virtual key (Enter, F3, F12 ฯลฯ)
"""
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


_SCRIPTING_POPUP_OK = {"window": "SAP Logon", "auto_id": "1",
                       "name": "OK", "control_type": "Button"}


def _dismiss_scripting_popup(timeout: float = 5) -> bool:
    """ปิด popup "SAP Logon" ที่ถามอนุญาตให้ script คุม SAP GUI Scripting ให้อัตโนมัติ
    (กด OK — selector มาจากการจิ้ม element จริง: window "SAP Logon", auto_id "1",
    name "OK", control_type Button) poll สูงสุด `timeout` วิ

    "SAP Logon" ก็เป็น title ของ SAP Logon pad หลักที่เปิดค้างอยู่ตลอดเวลาด้วย (คนละ
    instance จาก popup ยืนยัน scripting แต่ title ชนกัน) เลยต้องวนเช็คทุกหน้าต่างที่ title
    ตรง แทนที่จะผูกกับหน้าต่างแรกที่เจอ — ไม่งั้นจะไปหาปุ่ม OK ผิดหน้าต่าง (ใน pad หลัก
    ไม่มีปุ่มนี้) แล้ว timeout ทุกครั้งทั้งที่ popup จริงเปิดอยู่ข้างๆ

    คืน True ถ้ากดสำเร็จ, False ถ้าไม่เจอ popup เลยภายใน timeout"""
    from engine import ui_element
    deadline = time.time() + timeout
    while time.time() < deadline:
        for win in ui_element.find_all_windows(_SCRIPTING_POPUP_OK["window"]):
            try:
                btn = win.child_window(auto_id=_SCRIPTING_POPUP_OK["auto_id"],
                                        title=_SCRIPTING_POPUP_OK["name"],
                                        control_type=_SCRIPTING_POPUP_OK["control_type"])
                if btn.exists():
                    btn.click_input()
                    get_logger().info("ปิด popup ยืนยัน SAP GUI Scripting อัตโนมัติ (กด OK)")
                    return True
            except Exception:
                continue
        time.sleep(0.3)
    return False


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


def _get_session(connection_idx: int = 0, session_idx: int = 0):
    """ดึง SAP GUI session ที่เปิดอยู่ — raise SapNotAvailableError ถ้าเชื่อมไม่ได้

    COM ต้อง CoInitialize ในทุก thread ที่จะใช้มันก่อน (ไม่ใช่แค่ thread ที่สร้าง object)
    ฟังก์ชันนี้ถูกเรียกได้ทั้งจาก main thread (SequenceEditor/StepDialog picker) และจาก
    bot thread (LoopRunner._execute_step) — เรียก CoInitialize() แบบ idempotent กันไว้เผื่อ
    thread นั้นยังไม่เคย init (เรียกซ้ำใน thread เดิมไม่พัง แค่เป็น no-op)

    ถ้าเชื่อมครั้งแรกไม่สำเร็จ (เช่น popup "อนุญาต SAP GUI Scripting" ค้างรอกด OK อยู่)
    จะลองหา popup นั้นแล้วกด OK ให้ก่อน แล้วเชื่อมซ้ำอีกครั้งเดียว — ไม่กระทบ path ปกติ
    ที่เชื่อมสำเร็จตั้งแต่ครั้งแรก (ไม่มีการสแกนหา popup เพิ่ม)"""
    try:
        return _connect_session(connection_idx, session_idx)
    except SapNotAvailableError:
        if _dismiss_scripting_popup():
            return _connect_session(connection_idx, session_idx)
        raise


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
        el.text = text
        get_logger().info(f"SAP set '{field_id}' = {repr(text)}")
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
    คืน None ถ้า timeout โดยไม่มี focus เลย หรือ scripting ไม่พร้อม
    """
    try:
        sess = _get_session()
    except Exception:
        return None

    def current_focus_id() -> str | None:
        try:
            return str(sess.ActiveWindow.GuiFocus.Id)
        except Exception:
            return None

    baseline_id = current_focus_id()
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.2)
        fid = current_focus_id()
        if fid and fid != baseline_id:
            return fid
    return current_focus_id()
