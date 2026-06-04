import re
from datetime import date
from typing import Any

import pandas as pd

from engine.logger import get_logger


class DataSourceError(Exception):
    pass


class DataSource:
    def __init__(self, static_vars: dict[str, str], csv_path: str = None):
        self._static = dict(static_vars)
        self._csv_path = csv_path
        self._csv_rows: list[dict] = []
        self._csv_index = 0

        if csv_path:
            self._csv_rows = self._load_rows(csv_path)

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
