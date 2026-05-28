import re
from datetime import date
from typing import Any

import pandas as pd


class DataSource:
    """
    รวม 3 แหล่งข้อมูล:
    - static: variables จาก config + runtime input
    - csv: iterate row by row จาก CSV file
    """

    def __init__(self, static_vars: dict[str, str], csv_path: str = None):
        self._static = dict(static_vars)
        self._csv_path = csv_path
        self._csv_rows: list[dict] = []
        self._csv_index = 0

        if csv_path:
            df = pd.read_csv(csv_path, dtype=str)
            self._csv_rows = df.fillna("").to_dict(orient="records")

    def set_runtime(self, key: str, value: str):
        self._static[key] = value

    def has_next_row(self) -> bool:
        return self._csv_index < len(self._csv_rows)

    def next_row(self) -> dict:
        row = self._csv_rows[self._csv_index]
        self._csv_index += 1
        return row

    def reset_csv(self):
        self._csv_index = 0

    def current_row(self) -> dict | None:
        if self._csv_index == 0:
            return None
        return self._csv_rows[self._csv_index - 1]

    def resolve(self, template: str) -> str:
        """
        แปลง template string:
          {TODAY}          → วันที่วันนี้ DD.MM.YYYY
          {TODAY_ISO}      → YYYY-MM-DD
          {csv.COLUMN}     → ค่าจาก CSV row ปัจจุบัน
          {VAR_NAME}       → ค่าจาก static/runtime variables
        """
        def replacer(m: re.Match) -> str:
            key = m.group(1)

            if key == "TODAY":
                return date.today().strftime("%d.%m.%Y")
            if key == "TODAY_ISO":
                return date.today().isoformat()

            if key.startswith("csv."):
                col = key[4:]
                row = self.current_row()
                if row is None:
                    raise ValueError(f"No current CSV row for {{csv.{col}}}")
                return row.get(col, "")

            if key in self._static:
                return self._static[key]

            return m.group(0)

        return re.sub(r"\{([^}]+)\}", replacer, str(template))

    def get_runtime_fields(self, config_vars: dict) -> list[str]:
        """คืน list ของ variable ที่ยังไม่มีค่า (ต้องถามผู้ใช้ตอน Start)"""
        return [k for k, v in config_vars.items() if not v or v == ""]
