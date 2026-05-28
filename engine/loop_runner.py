import traceback
from typing import Callable

import engine.actions as actions
from engine.actions import ActionError
from engine.data_source import DataSource
from engine.image_matcher import ImageNotFoundError
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
        actions.set_log_callback(self._on_log)

    def run_loop(self, loop_config: dict, data_source: DataSource):
        steps = loop_config.get("steps", [])
        csv_path = loop_config.get("data_source")

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
            get_logger().info(f"Step {i}: {step.get('action')}")
            self._execute_step(step, data_source)

    def _execute_step(self, step: dict, data_source: DataSource):
        action = step.get("action")

        try:
            if action == "click_image":
                actions.click_image(
                    step["target"],
                    timeout=step.get("timeout", 10),
                    confidence=step.get("confidence", 0.85),
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
