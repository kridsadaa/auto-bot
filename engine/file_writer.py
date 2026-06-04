"""
เขียน/ต่อแถวข้อมูลลงไฟล์โดยตรง (ไม่ผ่านการพิมพ์หน้าจอ)
รองรับ .csv และ .xlsx — ใช้กับ action write_row
"""
import csv
import os

from engine.logger import get_logger


class FileWriteError(Exception):
    pass


def append_row(path: str, values: list, header: list = None):
    """ต่อหนึ่งแถวลงท้ายไฟล์ path
    - ถ้าไฟล์ยังไม่มี/ว่าง และมี header → เขียน header เป็นแถวแรกก่อน
    - .xlsx/.xlsm → ใช้ openpyxl, อื่นๆ → csv
    """
    ext = os.path.splitext(path)[1].lower()
    values = ["" if v is None else str(v) for v in values]
    try:
        if ext in (".xlsx", ".xlsm"):
            _append_xlsx(path, values, header)
        else:
            _append_csv(path, values, header)
        get_logger().info(f"write_row → {path}: {values}")
    except FileWriteError:
        raise
    except Exception as e:
        raise FileWriteError(f"เขียนไฟล์ '{path}' ไม่สำเร็จ: {e}") from e


def _append_csv(path: str, values: list, header: list = None):
    new_file = (not os.path.exists(path)) or os.path.getsize(path) == 0
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file and header:
            writer.writerow(header)
        writer.writerow(values)


def _append_xlsx(path: str, values: list, header: list = None):
    try:
        from openpyxl import Workbook, load_workbook
    except Exception as e:
        raise FileWriteError(f"ต้องติดตั้ง openpyxl เพื่อเขียน .xlsx: {e}") from e

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if os.path.exists(path):
        wb = load_workbook(path)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        if header:
            ws.append(list(header))

    ws.append(values)
    wb.save(path)
