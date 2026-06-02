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


# ─── error guards ────────────────────────────────────────────────────────────

def test_error_guard_stops_before_step(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=(5, 5)), \
         patch("engine.actions.press_key") as mock_key:
        with pytest.raises(BotStoppedError):
            runner.run_loop({
                "error_guards": [{"target": "err.png", "message": "boom"}],
                "steps": [{"action": "key", "key": "enter"}],
            }, ds)
        mock_key.assert_not_called()


def test_no_error_guard_when_image_absent(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({
            "error_guards": [{"target": "err.png"}],
            "steps": [{"action": "key", "key": "enter"}],
        }, ds)
        mock_key.assert_called_once_with("enter")


# ─── repeat_key_until ────────────────────────────────────────────────────────

def test_repeat_key_until_presses_until_image_appears(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    # not found, not found, found → กด 2 ครั้ง
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, None, (1, 1)]), \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.actions.wait"):
        runner.run_loop({"steps": [{
            "action": "repeat_key_until", "key": "enter",
            "until": "image_appears", "target": "end.png",
            "max_attempts": 5, "delay": 0,
        }]}, ds)
    assert mock_key.call_count == 2


def test_repeat_key_until_gives_up_after_max(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key"), patch("engine.actions.wait"):
        with pytest.raises(BotStoppedError):
            runner.run_loop({"steps": [{
                "action": "repeat_key_until", "until": "image_appears",
                "target": "x.png", "max_attempts": 3, "delay": 0,
            }]}, ds)


def test_repeat_key_until_text_filled_uses_ocr(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.ocr.region_has_text", side_effect=[False, True]), \
         patch("engine.actions.press_key") as mock_key, patch("engine.actions.wait"):
        runner.run_loop({"steps": [{
            "action": "repeat_key_until", "key": "enter",
            "until": "text_filled", "region": [0, 0, 10, 10],
            "max_attempts": 5, "delay": 0,
        }]}, ds)
    assert mock_key.call_count == 1


# ─── if_image branching ──────────────────────────────────────────────────────

def test_if_image_runs_then_branch_when_found(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=(1, 1)), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{
            "action": "if_image", "target": "popup.png",
            "then": [{"action": "key", "key": "esc"}],
            "else": [{"action": "key", "key": "enter"}],
        }]}, ds)
    mock_key.assert_called_once_with("esc")


def test_if_image_runs_else_branch_when_absent(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{
            "action": "if_image", "target": "popup.png",
            "then": [{"action": "key", "key": "esc"}],
            "else": [{"action": "key", "key": "enter"}],
        }]}, ds)
    mock_key.assert_called_once_with("enter")


# ─── stop_if_image ───────────────────────────────────────────────────────────

def test_stop_if_image_raises_when_found(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=(1, 1)):
        with pytest.raises(BotStoppedError):
            runner.run_loop({"steps": [{"action": "stop_if_image", "target": "err.png"}]}, ds)


def test_stop_if_image_continues_when_absent(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [
            {"action": "stop_if_image", "target": "err.png"},
            {"action": "key", "key": "enter"},
        ]}, ds)
    mock_key.assert_called_once_with("enter")


# ─── wait_text ───────────────────────────────────────────────────────────────

def test_wait_text_waits_until_filled(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.ocr.region_has_text", side_effect=[False, True]), \
         patch("engine.loop_runner.time.sleep"):
        runner.run_loop({"steps": [{
            "action": "wait_text", "region": [0, 0, 10, 10],
            "mode": "filled", "timeout": 5,
        }]}, ds)
