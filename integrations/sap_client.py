"""
SAP GUI Scripting ผ่าน win32com
ต้องเปิด SAP GUI Scripting ใน SAP Logon ก่อน:
  Options → Accessibility & Scripting → Scripting → Enable scripting
"""


def get_sap_session():
    try:
        import win32com.client
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        conn = app.Children(0)
        session = conn.Children(0)
        return session
    except Exception as e:
        raise RuntimeError(f"เชื่อมต่อ SAP ไม่ได้: {e}")


class SAPClient:
    def __init__(self):
        self._session = None

    def connect(self):
        self._session = get_sap_session()

    def navigate(self, tcode: str):
        self._session.findById("wnd[0]/tbar[0]/okcd").text = f"/n{tcode}"
        self._session.findById("wnd[0]").sendVKey(0)

    def set_field(self, field_id: str, value: str):
        self._session.findById(field_id).text = value

    def press_key(self, vkey: int):
        """vkey: 0=Enter, 8=Save, 12=Cancel, ฯลฯ"""
        self._session.findById("wnd[0]").sendVKey(vkey)

    def get_field(self, field_id: str) -> str:
        return self._session.findById(field_id).text

    def click_button(self, button_id: str):
        self._session.findById(button_id).press()
