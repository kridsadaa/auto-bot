import time
import traceback
from typing import Callable

import engine.actions as actions
from engine import ocr
from engine.actions import ActionError
from engine.data_source import DataSource
from engine.image_matcher import find_on_screen, ImageNotFoundError
from engine.interrupt_handler import InterruptHandler, BotStoppedError
from engine.logger import get_logger


class LoopRunner:
    def __init__(
        self,
        interrupt: InterruptHandler,
        on_image_not_found: Callable[[ImageNotFoundError], str] = None,
        on_log: Callable[[str], None] = None,
    ):
        self._interrupt = interrupt
        self._on_image_not_found = on_image_not_found
        self._on_log = on_log or print
        self._error_guards: list = []
        actions.set_log_callback(self._on_log)

    def run_loop(self, loop_config: dict, data_source: DataSource):
        steps = loop_config.get("steps", [])
        csv_path = loop_config.get("data_source")
        # รูป error ที่ถ้าเจอระหว่างทำงาน ให้หยุดทันที (เช็กก่อนทุก step)
        self._error_guards = loop_config.get("error_guards", []) or []

        if csv_path:
            ds = DataSource(data_source._static, csv_path)
            row_num = 0
            while ds.has_next_row():
                row_num += 1
                ds.next_row()
                get_logger().info(f"--- CSV row {row_num} ---")
                self._execute_steps(steps, ds)
        else:
            self._execute_steps(steps, data_source)

    def _execute_steps(self, steps: list, data_source: DataSource):
        for i, step in enumerate(steps, 1):
            self._interrupt.check()
            self._check_error_guards()
            get_logger().info(f"Step {i}: {step.get('action')}")
            self._execute_step(step, data_source)

    def _check_error_guards(self):
        """ถ้าเจอรูป error ที่กำหนดไว้บนจอ → หยุดบอททันที"""
        for guard in self._error_guards:
            target = guard.get("target")
            if not target:
                continue
            if find_on_screen(target, guard.get("confidence", 0.85)) is not None:
                msg = guard.get("message") or f"เจอหน้า error: {target}"
                self._on_log(f"⛔ {msg}")
                get_logger().error(f"Error guard triggered: {target}")
                raise BotStoppedError(msg)

    def _condition_met(self, step: dict, until: str) -> bool:
        """เช็กเงื่อนไขสำหรับ repeat_key_until / wait_text"""
        conf = step.get("confidence", 0.85)
        if until in ("image_appears", "image_disappears"):
            found = find_on_screen(step["target"], conf) is not None
            return found if until == "image_appears" else not found
        if until in ("text_filled", "text_empty"):
            region = step.get("region")
            region = tuple(region) if region else None
            has = ocr.region_has_text(region, int(step.get("min_chars", 1)))
            return has if until == "text_filled" else not has
        raise ActionError(f"until ไม่รู้จัก: {until}")

    def _do_repeat_key_until(self, step: dict):
        key = step.get("key", "enter")
        until = step.get("until", "image_appears")
        max_attempts = int(step.get("max_attempts", 20))
        delay = float(step.get("delay", 0.5))
        self._on_log(f"กด '{key}' ซ้ำจนกว่า: {until} (สูงสุด {max_attempts} ครั้ง)")

        for attempt in range(max_attempts):
            self._interrupt.check()
            if self._condition_met(step, until):
                self._on_log(f"เงื่อนไขเป็นจริงหลังกด {attempt} ครั้ง")
                return
            actions.press_key(key)
            actions.wait(delay)

        if self._condition_met(step, until):
            return
        raise ActionError(f"เงื่อนไข '{until}' ไม่เป็นจริงหลังกด '{key}' {max_attempts} ครั้ง")

    def _do_wait_text(self, step: dict):
        until = "text_empty" if step.get("mode") == "empty" else "text_filled"
        timeout = float(step.get("timeout", 15))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._interrupt.check()
            if self._condition_met(step, until):
                return
            time.sleep(0.4)
        raise ActionError(f"wait_text หมดเวลา {timeout}s (mode={step.get('mode', 'filled')})")

    def _do_if_image(self, step: dict, data_source: DataSource):
        found = find_on_screen(step["target"], step.get("confidence", 0.85)) is not None
        branch = step.get("then", []) if found else step.get("else", [])
        self._on_log(
            f"if_image: {step['target']} → {'then' if found else 'else'} ({len(branch)} steps)"
        )
        self._execute_steps(branch, data_source)

    def _do_stop_if_image(self, step: dict):
        if find_on_screen(step["target"], step.get("confidence", 0.85)) is not None:
            msg = step.get("message") or f"เจอรูปที่สั่งให้หยุด: {step['target']}"
            self._on_log(f"⛔ {msg}")
            raise BotStoppedError(msg)

    def _execute_step(self, step: dict, data_source: DataSource):
        action = step.get("action")

        try:
            if action == "click_image":
                offset = None
                if step.get("offset_x") is not None and step.get("offset_y") is not None:
                    offset = (step["offset_x"], step["offset_y"])
                actions.click_image(
                    step["target"],
                    timeout=step.get("timeout", 10),
                    confidence=step.get("confidence", 0.85),
                    offset=offset,
                )
            elif action == "click":
                actions.click(step["x"], step["y"])
            elif action == "type":
                actions.type_text(data_source.resolve(step["text"]))
            elif action == "key":
                actions.press_key(step["key"])
            elif action == "hotkey":
                actions.hotkey(*step["keys"])
            elif action == "wait":
                actions.wait(step.get("seconds", 1))
            elif action == "screenshot":
                actions.take_screenshot(step.get("path"))
            elif action == "scroll":
                actions.scroll(step["x"], step["y"], step.get("clicks", 3))
            elif action == "drag":
                actions.drag_and_drop(
                    step["src_x"], step["src_y"],
                    step["dst_x"], step["dst_y"],
                    step.get("duration", 0.5),
                )
            elif action == "wait_image":
                actions.wait_image(
                    step["target"],
                    timeout=step.get("timeout", 15),
                    confidence=step.get("confidence", 0.85),
                    mode=step.get("mode", "appear"),
                )
            elif action == "wait_text":
                self._do_wait_text(step)
            elif action == "repeat_key_until":
                self._do_repeat_key_until(step)
            elif action == "if_image":
                self._do_if_image(step, data_source)
            elif action == "stop_if_image":
                self._do_stop_if_image(step)
            else:
                get_logger().warning(f"Unknown action: {action}")
                self._on_log(f"Unknown action: {action}")

        except ImageNotFoundError as e:
            get_logger().error(f"Image not found: {e.template_path}")
            self._on_log(f"Image not found: {e.template_path}")
            if self._on_image_not_found:
                decision = self._on_image_not_found(e)
                if decision == "retry":
                    self._execute_step(step, data_source)
                elif decision == "stop":
                    raise BotStoppedError()
            else:
                raise

        except ActionError as e:
            get_logger().error(f"Action error: {e}\n{traceback.format_exc()}")
            self._on_log(f"Error: {e}")
            raise BotStoppedError(str(e))

        except BotStoppedError:
            raise

        except Exception as e:
            get_logger().error(f"Unexpected error in step '{action}': {e}\n{traceback.format_exc()}")
            self._on_log(f"Unexpected error: {e}")
            raise BotStoppedError(str(e))
