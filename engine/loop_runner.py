from typing import Callable

import engine.actions as actions
from engine.data_source import DataSource
from engine.image_matcher import ImageNotFoundError
from engine.interrupt_handler import InterruptHandler, BotStoppedError


class LoopRunner:
    def __init__(
        self,
        interrupt: InterruptHandler,
        on_image_not_found: Callable[[ImageNotFoundError], str] = None,
        on_log: Callable[[str], None] = None,
    ):
        self._interrupt = interrupt
        self._on_image_not_found = on_image_not_found  # คืน "retry" | "skip" | "stop"
        self._on_log = on_log or print
        actions.set_log_callback(self._on_log)

    def run_loop(self, loop_config: dict, data_source: DataSource):
        """
        รัน loop config หนึ่งตัว
        ถ้ามี data_source → iterate CSV rows
        """
        steps = loop_config.get("steps", [])
        csv_path = loop_config.get("data_source")

        if csv_path:
            ds = DataSource(data_source._static, csv_path)
            while ds.has_next_row():
                ds.next_row()
                self._execute_steps(steps, ds)
        else:
            self._execute_steps(steps, data_source)

    def _execute_steps(self, steps: list, data_source: DataSource):
        for step in steps:
            self._interrupt.check()
            self._execute_step(step, data_source)

    def _execute_step(self, step: dict, data_source: DataSource):
        action = step.get("action")

        try:
            if action == "click_image":
                target = step["target"]
                timeout = step.get("timeout", 10)
                confidence = step.get("confidence", 0.85)
                actions.click_image(target, timeout=timeout, confidence=confidence)

            elif action == "click":
                actions.click(step["x"], step["y"])

            elif action == "type":
                text = data_source.resolve(step["text"])
                actions.type_text(text)

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

            else:
                self._on_log(f"Unknown action: {action}")

        except ImageNotFoundError as e:
            self._on_log(f"Image not found: {e.template_path}")
            if self._on_image_not_found:
                decision = self._on_image_not_found(e)
                if decision == "retry":
                    self._execute_step(step, data_source)
                elif decision == "stop":
                    raise BotStoppedError()
                # "skip" → ทำต่อ step ถัดไป
            else:
                raise
