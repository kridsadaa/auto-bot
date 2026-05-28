import pytest
from unittest.mock import patch, MagicMock, call

from engine.data_source import DataSource
from engine.image_matcher import ImageNotFoundError
from engine.interrupt_handler import BotStoppedError
from engine.loop_runner import LoopRunner
from PIL import Image
import numpy as np


def _dummy_screenshot():
    return Image.fromarray(np.zeros((10, 10, 3), dtype=np.uint8))


def make_runner(mock_interrupt, on_image_not_found=None):
    return LoopRunner(
        interrupt=mock_interrupt,
        on_image_not_found=on_image_not_found,
        on_log=lambda msg: None,
    )


def test_type_step_calls_type_text(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({"NAME": "hello"})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop({"steps": [{"action": "type", "text": "{NAME}"}]}, ds)
        mock_type.assert_called_once_with("hello")


def test_key_step_calls_press_key(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})

    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{"action": "key", "key": "enter"}]}, ds)
        mock_key.assert_called_once_with("enter")


def test_wait_step(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})

    with patch("engine.actions.wait") as mock_wait:
        runner.run_loop({"steps": [{"action": "wait", "seconds": 2}]}, ds)
        mock_wait.assert_called_once_with(2)


def test_image_not_found_skip(mock_interrupt):
    runner = make_runner(mock_interrupt, on_image_not_found=lambda e: "skip")
    ds = DataSource({})

    with patch("engine.actions.click_image", side_effect=ImageNotFoundError("x.png", _dummy_screenshot())):
        with patch("engine.actions.press_key") as mock_key:
            runner.run_loop({
                "steps": [
                    {"action": "click_image", "target": "x.png"},
                    {"action": "key", "key": "enter"},
                ]
            }, ds)
            mock_key.assert_called_once_with("enter")


def test_image_not_found_stop(mock_interrupt):
    runner = make_runner(mock_interrupt, on_image_not_found=lambda e: "stop")
    ds = DataSource({})

    with patch("engine.actions.click_image", side_effect=ImageNotFoundError("x.png", _dummy_screenshot())):
        with pytest.raises(BotStoppedError):
            runner.run_loop({"steps": [{"action": "click_image", "target": "x.png"}]}, ds)


def test_csv_loop_iterates_all_rows(mock_interrupt, tmp_csv):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})

    calls = []
    with patch("engine.actions.type_text", side_effect=lambda t: calls.append(t)):
        runner.run_loop(
            {"data_source": tmp_csv, "steps": [{"action": "type", "text": "{csv.MATERIAL_CODE}"}]},
            ds,
        )

    assert calls == ["MAT-001", "MAT-002", "MAT-003"]


def test_unknown_action_does_not_crash(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    runner.run_loop({"steps": [{"action": "nonexistent_action"}]}, ds)
