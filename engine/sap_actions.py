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


def _get_session(connection_idx: int = 0, session_idx: int = 0):
    """ดึง SAP GUI session ที่เปิดอยู่ — raise SapNotAvailableError ถ้าเชื่อมไม่ได้"""
    try:
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
    """เปิด SAP ในโหมด "จิ้มเลย" — รอให้ผู้ใช้คลิก field ใน SAP แล้วคืน element ID
    ใช้ script recording API ของ SAP เพื่อจับ event ที่เกิดขึ้น
    คืน None ถ้า timeout หรือ scripting ไม่พร้อม
    """
    try:
        sess = _get_session()
        # เปิด recording สั้นๆ แล้วจับ event แรกที่เกิด
        sess.record(True)
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.2)
            history = sess.ActiveWindow.GuiFocus if hasattr(sess, "ActiveWindow") else None
            if history:
                sess.record(False)
                return str(history.Id)
        sess.record(False)
        return None
    except Exception:
        return None
