import numpy as np
import pytest
from PIL import Image
from unittest.mock import patch, MagicMock

from engine.image_matcher import find_on_screen, find_on_screen_or_raise, ImageNotFoundError


def _make_screenshot():
    return Image.fromarray(np.zeros((100, 200, 3), dtype=np.uint8))


def _make_match_result(max_val: float):
    result = np.zeros((1, 1), dtype=np.float32)
    result[0, 0] = max_val
    return result


@patch("engine.image_matcher.cv2.imread")
@patch("engine.image_matcher.pyautogui.screenshot")
def test_find_on_screen_found(mock_ss, mock_imread):
    mock_ss.return_value = _make_screenshot()
    mock_imread.return_value = np.zeros((10, 20, 3), dtype=np.uint8)

    with patch("engine.image_matcher.cv2.matchTemplate") as mock_match, \
         patch("engine.image_matcher.cv2.minMaxLoc") as mock_loc:
        mock_match.return_value = _make_match_result(0.95)
        mock_loc.return_value = (None, 0.95, None, (5, 5))

        result = find_on_screen("fake.png", confidence=0.85)
        assert result == (15, 10)  # (5 + 20//2, 5 + 10//2)


@patch("engine.image_matcher.cv2.imread")
@patch("engine.image_matcher.pyautogui.screenshot")
def test_find_on_screen_not_found(mock_ss, mock_imread):
    mock_ss.return_value = _make_screenshot()
    mock_imread.return_value = np.zeros((10, 20, 3), dtype=np.uint8)

    with patch("engine.image_matcher.cv2.matchTemplate") as mock_match, \
         patch("engine.image_matcher.cv2.minMaxLoc") as mock_loc:
        mock_match.return_value = _make_match_result(0.5)
        mock_loc.return_value = (None, 0.5, None, (0, 0))

        result = find_on_screen("fake.png", confidence=0.85)
        assert result is None


@patch("engine.image_matcher.cv2.imread", return_value=None)
@patch("engine.image_matcher.pyautogui.screenshot")
def test_find_on_screen_template_missing(mock_ss, mock_imread):
    mock_ss.return_value = _make_screenshot()
    with pytest.raises(FileNotFoundError):
        find_on_screen("missing.png")


@patch("engine.image_matcher.cv2.imread")
@patch("engine.image_matcher.pyautogui.screenshot")
def test_find_on_screen_or_raise_raises(mock_ss, mock_imread):
    mock_ss.return_value = _make_screenshot()
    mock_imread.return_value = np.zeros((10, 20, 3), dtype=np.uint8)

    with patch("engine.image_matcher.cv2.matchTemplate") as mock_match, \
         patch("engine.image_matcher.cv2.minMaxLoc") as mock_loc:
        mock_match.return_value = _make_match_result(0.4)
        mock_loc.return_value = (None, 0.4, None, (0, 0))

        with pytest.raises(ImageNotFoundError) as exc:
            find_on_screen_or_raise("fake.png", confidence=0.85)

        assert exc.value.template_path == "fake.png"
        assert exc.value.current_screenshot is not None
