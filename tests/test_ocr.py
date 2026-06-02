from unittest.mock import patch

from engine import ocr


def test_region_has_text_true_when_text_present():
    with patch("engine.ocr.read_text", return_value="31.12.2026"):
        assert ocr.region_has_text((0, 0, 10, 10)) is True


def test_region_has_text_false_when_empty():
    with patch("engine.ocr.read_text", return_value=""):
        assert ocr.region_has_text((0, 0, 10, 10)) is False


def test_region_has_text_respects_min_chars():
    with patch("engine.ocr.read_text", return_value="12"):
        assert ocr.region_has_text(min_chars=5) is False
        assert ocr.region_has_text(min_chars=2) is True
