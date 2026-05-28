import csv
import os
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def tmp_csv(tmp_path):
    path = tmp_path / "tasks.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["MATERIAL_CODE", "QTY"])
        writer.writeheader()
        writer.writerow({"MATERIAL_CODE": "MAT-001", "QTY": "10"})
        writer.writerow({"MATERIAL_CODE": "MAT-002", "QTY": "5"})
        writer.writerow({"MATERIAL_CODE": "MAT-003", "QTY": "20"})
    return str(path)


@pytest.fixture
def mock_interrupt():
    interrupt = MagicMock()
    interrupt.is_stopped.return_value = False
    interrupt.is_paused.return_value = False
    interrupt.check.return_value = None
    return interrupt


@pytest.fixture(autouse=True)
def setup_logger_for_tests():
    """ป้องกัน logger crash ใน test environment"""
    import logging
    from engine import logger as lg
    test_logger = logging.getLogger("autobot")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())
    lg._logger = test_logger
