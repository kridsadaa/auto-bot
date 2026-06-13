import re
from datetime import date
from typing import Any

import pandas as pd

from engine.logger import get_logger


class DataSourceError(Exception):
    pass


class DataSource:
    def __init__(self, static_vars: dict[str, str], csv_path: str = None,
                 rows_filter: set[int] = None):
        """rows_filter: set ของ row number ต้นฉบับ (1-indexed) ที่ต้องการรัน (None = ทั้งหมด)"""
        self._static = dict(static_vars)
        self._csv_path = csv_path
        self._csv_rows: list[dict] = []
        self._csv_original_nums: list[int] = []
        self._csv_index = 0

        if csv_path:
            all_rows = self._load_rows(csv_path)
            if rows_filter:
                for i, row in enumerate(all_rows, 1):
                    if i in rows_filter:
                        self._csv_rows.append(row)
                        self._csv_original_nums.append(i)
                get_logger().info(f"rows_filter: {len(self._csv_rows)}/{len(all_rows)} rows selected")
            else:
                self._csv_rows = all_rows
                self._csv_original_nums = list(range(1, len(all_rows) + 1))

    @staticmethod
    def read_headers(path: str) -> list:
        """อ่านเฉพาะชื่อคอลัมน์ (header) จาก csv/xlsx — คืน [] ถ้าอ่านไม่ได้"""
        if not path:
            return []
        import os
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in (".xlsx", ".xls", ".xlsm"):
                df = pd.read_excel(path, nrows=0)
            else:
                df = pd.read_csv(path, nrows=0)
            return [str(c) for c in df.columns]
        except Exception as e:
            get_logger().warning(f"read_headers('{path}') ไม่สำเร็จ: {e}")
            return []

    @staticmethod
    def _load_rows(path: str) -> list[dict]:
        """อ่านข้อมูลตาราง — รองรับ .csv และ .xlsx/.xls (ทุกค่าเป็น string)"""
        import os
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in (".xlsx", ".xls", ".xlsm"):
                df = pd.read_excel(path, dtype=str)
            else:
                df = pd.read_csv(path, dtype=str)
            rows = df.fillna("").to_dict(orient="records")
            get_logger().info(f"Loaded data: {path} ({len(rows)} rows)")
            return rows
        except FileNotFoundError:
            raise DataSourceError(f"Data file not found: {path}")
        except Exception as e:
            raise DataSourceError(f"Failed to read '{path}': {e}") from e

    @property
    def csv_path(self) -> str | None:
        return self._csv_path

    def set_runtime(self, key: str, value: str):
        self._static[key] = value

    def has_next_row(self) -> bool:
        return self._csv_index < len(self._csv_rows)

    def next_row(self) -> dict:
        row = self._csv_rows[self._csv_index]
        self._csv_index += 1
        get_logger().info(f"CSV row {self._csv_index}/{len(self._csv_rows)}")
        return row

    def reset_csv(self):
        self._csv_index = 0

    def current_row(self) -> dict | None:
        if self._csv_index == 0:
            return None
        return self._csv_rows[self._csv_index - 1]

    def current_original_row_num(self) -> int:
        """หมายเลขแถวต้นฉบับใน CSV (1-indexed) — ถูกต้องแม้ใช้ rows_filter"""
        if self._csv_index == 0:
            return 0
        if self._csv_original_nums:
            return self._csv_original_nums[self._csv_index - 1]
        return self._csv_index

    def resolve(self, template: str) -> str:
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
                    get_logger().warning(f"{{csv.{col}}} used but no current CSV row")
                    return ""
                if col not in row:
                    get_logger().warning(f"Column '{col}' not found in CSV (available: {list(row.keys())})")
                    return ""
                return row.get(col, "")

            if key in self._static:
                return self._static[key]

            get_logger().warning(f"Variable '{{{key}}}' not defined — left as-is")
            return m.group(0)

        return re.sub(r"\{([^}]+)\}", replacer, str(template))

    def get_runtime_fields(self, config_vars: dict) -> list[str]:
        return [k for k, v in config_vars.items() if not v or v == ""]
