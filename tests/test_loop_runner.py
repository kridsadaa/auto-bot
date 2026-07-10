import pytest
from unittest.mock import patch, MagicMock, call

from engine.data_source import DataSource
from engine.image_matcher import ImageNotFoundError
from engine.interrupt_handler import BotStoppedError
from engine.loop_runner import LoopRunner, RowError
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
        mock_type.assert_called_once_with("hello", method="paste", clear=False)


def test_loop_scoped_variable_overrides_global(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({"NAME": "global"})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop(
            {"variables": {"NAME": "loopval"},
             "steps": [{"action": "type", "text": "{NAME}"}]},
            ds,
        )
        mock_type.assert_called_once_with("loopval", method="paste", clear=False)
    # ตัวแปร global เดิมไม่ถูกแก้ (loop var แค่ override เฉพาะตอนรัน loop นี้)
    assert ds._static["NAME"] == "global"


def test_loop_scoped_variable_without_global(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop(
            {"variables": {"CITY": "BKK"},
             "steps": [{"action": "type", "text": "{CITY}"}]},
            ds,
        )
        mock_type.assert_called_once_with("BKK", method="paste", clear=False)


def test_empty_loop_variable_falls_through_to_global(mock_interrupt):
    # loop var ค่าว่าง (เช่นเพิ่ง import ยังไม่กรอก) ต้องไม่ลบค่า global ทิ้ง
    runner = make_runner(mock_interrupt)
    ds = DataSource({"NAME": "global"})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop(
            {"variables": {"NAME": ""},
             "steps": [{"action": "type", "text": "{NAME}"}]},
            ds,
        )
        mock_type.assert_called_once_with("global", method="paste", clear=False)


def test_type_step_passes_method(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({"NAME": "hello"})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop({"steps": [{"action": "type", "text": "{NAME}", "method": "type"}]}, ds)
        mock_type.assert_called_once_with("hello", method="type", clear=False)


def test_type_step_passes_clear_first(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({"NAME": "hi"})

    with patch("engine.actions.type_text") as mock_type:
        runner.run_loop({"steps": [{"action": "type", "text": "{NAME}", "clear_first": True}]}, ds)
        mock_type.assert_called_once_with("hi", method="paste", clear=True)


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
    with patch("engine.actions.type_text", side_effect=lambda t, **kw: calls.append(t)):
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
        with pytest.raises(RowError):
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


# ─── if_image wait (รอรูปก่อนตัดสิน) ──────────────────────────────────────────

def test_if_image_wait_zero_checks_once_like_before(mock_interrupt):
    # wait=0 (default) → เช็คครั้งเดียว ไม่ poll — พฤติกรรมเดิมเป๊ะ
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None) as mock_find, \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep") as mock_sleep:
        runner.run_loop({"steps": [{
            "action": "if_image", "target": "popup.png", "wait": 0,
            "then": [{"action": "key", "key": "esc"}],
            "else": [{"action": "key", "key": "enter"}],
        }]}, ds)
    mock_key.assert_called_once_with("enter")
    assert mock_find.call_count == 1
    mock_sleep.assert_not_called()


def test_if_image_wait_finds_image_that_appears_late(mock_interrupt):
    # ไม่เจอ 2 ครั้งแรก (หน้าต่างกำลังเด้ง) เจอครั้งที่ 3 → ต้องเข้า THEN ไม่ใช่ ELSE
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, None, (1, 1)]), \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep"):
        runner.run_loop({"steps": [{
            "action": "if_image", "target": "popup.png", "wait": 5,
            "then": [{"action": "key", "key": "esc"}],
            "else": [{"action": "key", "key": "enter"}],
        }]}, ds)
    mock_key.assert_called_once_with("esc")


def test_if_image_wait_times_out_to_else(mock_interrupt):
    # ไม่เจอเลยตลอด wait → หมดเวลาแล้วไป ELSE
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep"):
        runner.run_loop({"steps": [{
            "action": "if_image", "target": "popup.png", "wait": 0.05,
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


# ─── switch_image (multi-way branch) ─────────────────────────────────────────

def test_switch_image_runs_first_matching_case(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    # case1 ไม่เจอ, case2 เจอ → รันเฉพาะ case2
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, (1, 1)]), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{
            "action": "switch_image",
            "cases": [
                {"target": "a.png", "steps": [{"action": "key", "key": "f1"}]},
                {"target": "b.png", "steps": [{"action": "key", "key": "f2"}]},
            ],
            "default": [{"action": "key", "key": "esc"}],
        }]}, ds)
    mock_key.assert_called_once_with("f2")


def test_switch_image_runs_default_when_no_case_matches(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{
            "action": "switch_image",
            "cases": [
                {"target": "a.png", "steps": [{"action": "key", "key": "f1"}]},
                {"target": "b.png", "steps": [{"action": "key", "key": "f2"}]},
            ],
            "default": [{"action": "key", "key": "esc"}],
        }]}, ds)
    mock_key.assert_called_once_with("esc")


def test_switch_image_no_default_no_match_does_nothing(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{
            "action": "switch_image",
            "cases": [{"target": "a.png", "steps": [{"action": "key", "key": "f1"}]}],
        }]}, ds)
    mock_key.assert_not_called()


# ─── switch_image wait (รอรูปก่อนตัดสิน) ──────────────────────────────────────

def test_switch_image_wait_zero_checks_once_like_before(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, (1, 1)]) as mock_find, \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep") as mock_sleep:
        runner.run_loop({"steps": [{
            "action": "switch_image", "wait": 0,
            "cases": [
                {"target": "a.png", "steps": [{"action": "key", "key": "f1"}]},
                {"target": "b.png", "steps": [{"action": "key", "key": "f2"}]},
            ],
            "default": [{"action": "key", "key": "esc"}],
        }]}, ds)
    mock_key.assert_called_once_with("f2")
    assert mock_find.call_count == 2
    mock_sleep.assert_not_called()


def test_switch_image_wait_finds_late_matching_case(mock_interrupt):
    # case ที่ตรง (b.png) มาช้า — poll รอบแรกทั้งคู่ไม่เจอ, รอบสองเจอ b.png
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, None, None, (1, 1)]), \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep"):
        runner.run_loop({"steps": [{
            "action": "switch_image", "wait": 5,
            "cases": [
                {"target": "a.png", "steps": [{"action": "key", "key": "f1"}]},
                {"target": "b.png", "steps": [{"action": "key", "key": "f2"}]},
            ],
            "default": [{"action": "key", "key": "esc"}],
        }]}, ds)
    mock_key.assert_called_once_with("f2")


def test_switch_image_wait_times_out_to_default(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.find_on_screen", return_value=None), \
         patch("engine.actions.press_key") as mock_key, \
         patch("engine.loop_runner.time.sleep"):
        runner.run_loop({"steps": [{
            "action": "switch_image", "wait": 0.05,
            "cases": [{"target": "a.png", "steps": [{"action": "key", "key": "f1"}]}],
            "default": [{"action": "key", "key": "esc"}],
        }]}, ds)
    mock_key.assert_called_once_with("esc")


# ─── UI element actions ──────────────────────────────────────────────────────

def test_click_element_builds_selector(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.click_element") as m:
        runner.run_loop({"steps": [{
            "action": "click_element", "window": "Notepad",
            "auto_id": "15", "control_type": "Edit", "class_name": "",
            "timeout": 5,
        }]}, ds)
    # class_name ว่าง → ไม่เข้า selector
    m.assert_called_once_with(
        {"window": "Notepad", "auto_id": "15", "control_type": "Edit"},
        timeout=5, button="left",
    )


def test_set_element_text_resolves_text(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({"X": "hi"})
    with patch("engine.actions.set_element_text") as m:
        runner.run_loop({"steps": [{
            "action": "set_element_text", "name": "Field", "text": "{X}",
        }]}, ds)
    m.assert_called_once_with({"name": "Field"}, "hi", timeout=10)


def test_wait_element_passes_timeout(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.wait_element") as m:
        runner.run_loop({"steps": [{
            "action": "wait_element", "auto_id": "ok", "timeout": 8,
        }]}, ds)
    m.assert_called_once_with({"auto_id": "ok"}, timeout=8)


# ─── write_row ───────────────────────────────────────────────────────────────

def test_write_row_resolves_and_appends(mock_interrupt, tmp_csv):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.file_writer.append_row") as mock_append:
        runner.run_loop({
            "data_source": tmp_csv,
            "steps": [{
                "action": "write_row",
                "path": "out.csv",
                "columns": ["{csv.MATERIAL_CODE}", "{csv.QTY}"],
                "header": ["CODE", "QTY"],
            }],
        }, ds)
    # 3 แถวใน CSV → เรียก append_row 3 ครั้ง ด้วยค่า resolve แล้ว
    assert mock_append.call_count == 3
    mock_append.assert_any_call("out.csv", ["MAT-001", "10"], ["CODE", "QTY"])
    mock_append.assert_any_call("out.csv", ["MAT-003", "20"], ["CODE", "QTY"])


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


# ─── Interactive Live Debugger (step-index control via on_debug) ──────────────

def _debug_runner(mock_interrupt, on_debug):
    return LoopRunner(interrupt=mock_interrupt, on_log=lambda m: None, on_debug=on_debug)


def test_debug_retry_reruns_same_step(mock_interrupt):
    from engine.actions import ActionError
    runner = _debug_runner(mock_interrupt, on_debug=lambda ctx: {"decision": "retry"})
    n = []

    def press(key):
        n.append(key)
        if len(n) == 1:
            raise ActionError("first attempt fails")

    with patch("engine.actions.press_key", side_effect=press):
        runner.run_loop({"steps": [{"action": "key", "key": "enter"}]}, DataSource({}))
    assert n == ["enter", "enter"]  # retry → กดซ้ำจนผ่าน


def test_debug_skip_advances_to_next_step(mock_interrupt):
    from engine.actions import ActionError
    runner = _debug_runner(mock_interrupt, on_debug=lambda ctx: {"decision": "skip"})
    pressed = []

    def press(key):
        if key == "f1":
            raise ActionError("always fails")
        pressed.append(key)

    with patch("engine.actions.press_key", side_effect=press):
        runner.run_loop({"steps": [
            {"action": "key", "key": "f1"},
            {"action": "key", "key": "enter"},
        ]}, DataSource({}))
    assert pressed == ["enter"]  # ข้าม f1 → enter ทำงาน


def test_debug_restart_returns_to_first_step(mock_interrupt):
    from engine.actions import ActionError
    a, b, dbg = [], [], []

    def on_debug(ctx):
        dbg.append(1)
        return {"decision": "restart"}

    def press(key):
        if key == "f1":
            a.append(1)
        else:
            b.append(1)
            if len(b) == 1:
                raise ActionError("B fails first time")

    runner = _debug_runner(mock_interrupt, on_debug)
    with patch("engine.actions.press_key", side_effect=press):
        runner.run_loop({"steps": [
            {"action": "key", "key": "f1"},
            {"action": "key", "key": "enter"},
        ]}, DataSource({}))
    assert len(a) == 2 and len(dbg) == 1  # restart → f1 ทำซ้ำ, debug เรียกครั้งเดียว


def test_debug_inject_runs_steps_then_retries(mock_interrupt):
    from engine.actions import ActionError
    main, esc = [], []

    def on_debug(ctx):
        return {"decision": "inject", "steps": [{"action": "key", "key": "esc"}], "then": "retry"}

    def press(key):
        if key == "esc":
            esc.append(1)
        else:
            main.append(1)
            if len(main) == 1:
                raise ActionError("boom")

    runner = _debug_runner(mock_interrupt, on_debug)
    with patch("engine.actions.press_key", side_effect=press):
        runner.run_loop({"steps": [{"action": "key", "key": "enter"}]}, DataSource({}))
    assert esc == [1] and len(main) == 2  # inject esc → retry enter จนผ่าน


def test_debug_stop_raises(mock_interrupt):
    from engine.actions import ActionError
    runner = _debug_runner(mock_interrupt, on_debug=lambda ctx: {"decision": "stop"})
    with patch("engine.actions.press_key", side_effect=ActionError("x")):
        with pytest.raises(BotStoppedError):
            runner.run_loop({"steps": [{"action": "key", "key": "enter"}]}, DataSource({}))


# ─── skip_row / skip_row_if_image ────────────────────────────────────────────

def test_skip_row_if_image_skips_only_matching_row(mock_interrupt, tmp_csv):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    calls = []
    # find_on_screen ถูกเรียก 1 ครั้ง/แถว (จาก skip_row_if_image) — เจอเฉพาะแถว 2
    with patch("engine.loop_runner.find_on_screen", side_effect=[None, (1, 1), None]), \
         patch("engine.actions.type_text", side_effect=lambda t, **kw: calls.append(t)):
        runner.run_loop({
            "data_source": tmp_csv,
            "steps": [
                {"action": "skip_row_if_image", "target": "no_work.png"},
                {"action": "type", "text": "{csv.MATERIAL_CODE}"},
            ],
        }, ds)
    # แถว 2 (MAT-002) ถูกข้าม ไม่พิมพ์
    assert calls == ["MAT-001", "MAT-003"]


def test_skip_row_unconditional_skips_rest_of_row(mock_interrupt, tmp_csv):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({
            "data_source": tmp_csv,
            "steps": [
                {"action": "skip_row"},
                {"action": "key", "key": "enter"},  # ต้องไม่ถูกเรียกเลยทุกแถว
            ],
        }, ds)
    mock_key.assert_not_called()


def test_skip_row_with_no_csv_ends_loop_gracefully(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        # ไม่มี data_source → skip_row จบ loop เฉยๆ ไม่ raise
        runner.run_loop({"steps": [
            {"action": "skip_row"},
            {"action": "key", "key": "enter"},
        ]}, ds)
    mock_key.assert_not_called()


# ─── on_row_error policy ─────────────────────────────────────────────────────

def test_on_row_error_skip_continues_to_next_row(mock_interrupt, tmp_csv):
    from engine.actions import ActionError
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    calls = []

    def type_side(text, **kw):
        if text == "MAT-002":
            raise ActionError("ฟิลด์หาย")
        calls.append(text)

    with patch("engine.actions.type_text", side_effect=type_side):
        runner.run_loop({
            "data_source": tmp_csv,
            "on_row_error": "skip",
            "steps": [{"action": "type", "text": "{csv.MATERIAL_CODE}"}],
        }, ds)
    # แถวที่ error ถูกข้าม batch ไม่ล้ม
    assert calls == ["MAT-001", "MAT-003"]


def test_on_row_error_stop_aborts_whole_batch(mock_interrupt, tmp_csv):
    from engine.actions import ActionError
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    calls = []

    def type_side(text, **kw):
        if text == "MAT-002":
            raise ActionError("ฟิลด์หาย")
        calls.append(text)

    # default on_row_error=stop → row 2 พัง → ทั้ง batch หยุด (RowError)
    with patch("engine.actions.type_text", side_effect=type_side):
        with pytest.raises(RowError):
            runner.run_loop({
                "data_source": tmp_csv,
                "steps": [{"action": "type", "text": "{csv.MATERIAL_CODE}"}],
            }, ds)
    assert calls == ["MAT-001"]  # หยุดที่แถว 2 ไม่ถึงแถว 3


def test_hotkey_list_keys(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.hotkey") as mock_hotkey:
        runner.run_loop({
            "steps": [{"action": "hotkey", "keys": ["ctrl", "s"]}],
        }, ds)
        mock_hotkey.assert_called_once_with("ctrl", "s")


def test_hotkey_string_keys(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.hotkey") as mock_hotkey:
        runner.run_loop({
            "steps": [{"action": "hotkey", "keys": "ctrl+shift+s"}],
        }, ds)
        mock_hotkey.assert_called_once_with("ctrl", "shift", "s")


# ─── call_loop (subroutine) ──────────────────────────────────────────────────

def test_call_loop_runs_target_loop_steps(mock_interrupt):
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={"login": {"steps": [{"action": "key", "key": "enter"}]}},
    )
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{"action": "call_loop", "loop": "login"}]}, ds)
    mock_key.assert_called_once_with("enter")


def test_call_loop_missing_loop_name_raises(mock_interrupt):
    runner = LoopRunner(interrupt=mock_interrupt, on_log=lambda m: None, all_loops={})
    ds = DataSource({})
    with pytest.raises(RowError):
        runner.run_loop({"steps": [{"action": "call_loop", "loop": "nope"}]}, ds)


def test_call_loop_empty_loop_name_raises(mock_interrupt):
    runner = LoopRunner(interrupt=mock_interrupt, on_log=lambda m: None, all_loops={})
    ds = DataSource({})
    with pytest.raises(RowError):
        runner.run_loop({"steps": [{"action": "call_loop", "loop": ""}]}, ds)


def test_call_loop_direct_recursion_raises(mock_interrupt):
    # loop "a" เรียกตัวเอง — ต้อง error ไม่ใช่วนไม่รู้จบ
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={"a": {"steps": [{"action": "call_loop", "loop": "a"}]}},
    )
    ds = DataSource({})
    with pytest.raises(RowError):
        runner.run_loop({"steps": [{"action": "call_loop", "loop": "a"}]}, ds)


def test_call_loop_indirect_recursion_raises(mock_interrupt):
    # a → b → a — ต้องจับ recursion ข้ามหลาย loop ได้ด้วย
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={
            "a": {"steps": [{"action": "call_loop", "loop": "b"}]},
            "b": {"steps": [{"action": "call_loop", "loop": "a"}]},
        },
    )
    ds = DataSource({})
    with pytest.raises(RowError):
        runner.run_loop({"steps": [{"action": "call_loop", "loop": "a"}]}, ds)


def test_call_loop_same_loop_called_twice_sequentially_is_fine(mock_interrupt):
    # เรียก loop เดียวกัน 2 ครั้งไม่ซ้อนกัน (ไม่ใช่ recursion) ต้องรันได้ปกติ
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={"beep": {"steps": [{"action": "key", "key": "f1"}]}},
    )
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [
            {"action": "call_loop", "loop": "beep"},
            {"action": "call_loop", "loop": "beep"},
        ]}, ds)
    assert mock_key.call_count == 2


def test_call_loop_applies_called_loops_variables_and_restores(mock_interrupt):
    # loop ที่พึ่งตัวแปรเฉพาะตัวเอง ต้องทำงานผ่าน call_loop เหมือนรัน standalone
    # และค่าของผู้เรียกต้องกลับมาเหมือนเดิมหลังจบ
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={"login": {
            "variables": {"SAP_USER": "bob", "EMPTY_VAR": ""},
            "steps": [{"action": "type", "text": "{SAP_USER}/{GLOBAL}"}],
        }},
    )
    ds = DataSource({"SAP_USER": "caller", "GLOBAL": "g"})
    typed = []
    with patch("engine.actions.type_text", side_effect=lambda t, **kw: typed.append(t)):
        runner.run_loop({"steps": [
            {"action": "call_loop", "loop": "login"},
            {"action": "type", "text": "{SAP_USER}"},
        ]}, ds)
    # ใน login: SAP_USER = ค่าของ login เอง, GLOBAL fall through จากผู้เรียก
    # หลังจบ: SAP_USER กลับเป็นของผู้เรียก
    assert typed == ["bob/g", "caller"]


def test_call_loop_restores_variables_even_on_error(mock_interrupt):
    from engine.actions import ActionError
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={"sub": {
            "variables": {"X": "subval"},
            "steps": [{"action": "key", "key": "boom"}],
        }},
    )
    ds = DataSource({"X": "orig"})
    with patch("engine.actions.press_key", side_effect=ActionError("fail")):
        with pytest.raises(RowError):
            runner.run_loop({"steps": [{"action": "call_loop", "loop": "sub"}]}, ds)
    assert ds._static["X"] == "orig"  # ค่าเดิมกลับมาแม้ sub loop พัง


def test_call_loop_nested_non_recursive_chain_works(mock_interrupt):
    # a → b → c (ไม่ซ้ำชื่อ) ต้องรันได้ปกติทั้ง chain
    runner = LoopRunner(
        interrupt=mock_interrupt, on_log=lambda m: None,
        all_loops={
            "a": {"steps": [{"action": "call_loop", "loop": "b"}]},
            "b": {"steps": [{"action": "call_loop", "loop": "c"}]},
            "c": {"steps": [{"action": "key", "key": "ok"}]},
        },
    )
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{"action": "call_loop", "loop": "a"}]}, ds)
    mock_key.assert_called_once_with("ok")


# ─── setup_steps (รันครั้งเดียวก่อนแถวแรก) ────────────────────────────────────

def test_setup_steps_run_once_before_csv_rows(mock_interrupt, tmp_csv):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    calls = []
    with patch("engine.actions.press_key", side_effect=lambda k: calls.append(("key", k))), \
         patch("engine.actions.type_text", side_effect=lambda t, **kw: calls.append(("type", t))):
        runner.run_loop({
            "data_source": tmp_csv,
            "setup_steps": [{"action": "key", "key": "login"}],
            "steps": [{"action": "type", "text": "{csv.MATERIAL_CODE}"}],
        }, ds)
    # setup ("login") ต้องรันแค่ครั้งเดียว แม้ CSV มี 3 แถว
    assert calls == [
        ("key", "login"),
        ("type", "MAT-001"),
        ("type", "MAT-002"),
        ("type", "MAT-003"),
    ]


def test_setup_steps_run_once_without_csv(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({
            "setup_steps": [{"action": "key", "key": "login"}],
            "steps": [{"action": "key", "key": "main"}],
        }, ds)
    assert mock_key.call_args_list == [call("login"), call("main")]


def test_setup_steps_failure_aborts_whole_loop(mock_interrupt, tmp_csv):
    from engine.actions import ActionError
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.press_key", side_effect=ActionError("login failed")), \
         patch("engine.actions.type_text") as mock_type:
        with pytest.raises(RowError):
            runner.run_loop({
                "data_source": tmp_csv,
                "on_row_error": "skip",  # แม้ policy เป็น skip, setup พลาด ต้องหยุดทั้งงาน ไม่ข้ามไปแถวถัดไป
                "setup_steps": [{"action": "key", "key": "login"}],
                "steps": [{"action": "type", "text": "{csv.MATERIAL_CODE}"}],
            }, ds)
    mock_type.assert_not_called()  # ไม่ควรถึงแถวไหนเลย


def test_setup_steps_runtime_var_visible_in_row_steps(mock_interrupt, tmp_csv):
    # ค่าที่ setup เก็บ (เช่น sap_get_field → ตัวแปร) ต้องใช้ได้ตอนรันแถว CSV
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    typed = []
    with patch("engine.sap_actions.sap_get_field", return_value="S-42"), \
         patch("engine.actions.type_text", side_effect=lambda t, **kw: typed.append(t)):
        runner.run_loop({
            "data_source": tmp_csv,
            "setup_steps": [{"action": "sap_get_field", "field_id": "wnd[0]/sbar",
                             "variable": "SESSION_ID"}],
            "steps": [{"action": "type", "text": "{SESSION_ID}:{csv.MATERIAL_CODE}"}],
        }, ds)
    assert typed == ["S-42:MAT-001", "S-42:MAT-002", "S-42:MAT-003"]


def test_setup_steps_runtime_var_visible_without_csv(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    typed = []
    with patch("engine.sap_actions.sap_get_field", return_value="S-42"), \
         patch("engine.actions.type_text", side_effect=lambda t, **kw: typed.append(t)):
        runner.run_loop({
            "setup_steps": [{"action": "sap_get_field", "field_id": "wnd[0]/sbar",
                             "variable": "SESSION_ID"}],
            "steps": [{"action": "type", "text": "{SESSION_ID}"}],
        }, ds)
    assert typed == ["S-42"]


def test_no_setup_steps_behaves_as_before(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.actions.press_key") as mock_key:
        runner.run_loop({"steps": [{"action": "key", "key": "main"}]}, ds)
    mock_key.assert_called_once_with("main")


def test_wait_text_with_string_region(mock_interrupt):
    runner = make_runner(mock_interrupt)
    ds = DataSource({})
    with patch("engine.loop_runner.ocr.region_has_text", return_value=True) as mock_has_text:
        runner.run_loop({
            "steps": [{
                "action": "wait_text",
                "region": "100, 200, 300, 400",
                "timeout": 5,
                "min_chars": 1
            }],
        }, ds)
        mock_has_text.assert_called_once_with((100, 200, 300, 400), 1)
