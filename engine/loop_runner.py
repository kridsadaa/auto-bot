import time
import traceback
from typing import Callable

import engine.actions as actions
from engine import ocr
from engine.actions import ActionError
from engine.data_source import DataSource
from engine.image_matcher import capture_screen, find_on_screen, ImageNotFoundError
from engine.interrupt_handler import InterruptHandler, BotStoppedError
from engine.logger import get_logger


DEFAULT_MAX_CONSECUTIVE_RECOVERIES = 3


class RowError(Exception):
    """แถว CSV ทำงานพลาด (action error/ภาพไม่เจอ) — กู้คืนได้ถ้า on_row_error=skip
    ต่างจาก BotStoppedError ที่ตั้งใจหยุดทั้งงาน (ผู้ใช้/stop_if_image/error_guard)"""
    pass


class SkipRowSignal(Exception):
    """สัญญาณ 'ข้ามแถวนี้ ไปแถว CSV ถัดไป' (จาก skip_row / skip_row_if_image)
    ไม่ใช่ error — เป็น control flow ปกติ"""
    pass


class LoopRunner:
    def __init__(
        self,
        interrupt: InterruptHandler,
        on_image_not_found: Callable[[ImageNotFoundError], str] = None,
        on_log: Callable[[str], None] = None,
        on_debug: Callable[[dict], dict] = None,
        sap_capture=None,  # SapCapture instance (optional) — shadow record ระหว่างรัน
        ai_heal: bool = False,
        ai_heal_timeout: int = 60,
        all_loops: dict = None,  # ชื่อ loop → config ทั้งหมดใน config นี้ — ใช้โดย action call_loop
    ):
        self._interrupt = interrupt
        self._on_image_not_found = on_image_not_found
        # on_debug: เปิด Debug Console เมื่อ step พลาด → คืน decision dict
        # (retry/skip/restart/stop/inject) ใช้คุมลำดับ step แบบ interactive
        self._on_debug = on_debug
        self._on_log = on_log or print
        self._error_guards: list = []
        self._sap_capture = sap_capture
        self._ai_heal = ai_heal
        self._ai_heal_timeout = ai_heal_timeout
        self._all_loops = all_loops or {}
        self._call_stack: list = []  # ชื่อ loop ที่กำลังถูกเรียกผ่าน call_loop อยู่ (กัน recursion)
        actions.set_log_callback(self._on_log)

    def run_loop(self, loop_config: dict, data_source: DataSource,
                 rows_filter: set[int] = None):
        """rows_filter: รัน CSV เฉพาะแถวใน set นี้ (1-indexed ต้นฉบับ) — None = ทั้งหมด"""
        steps = loop_config.get("steps", [])
        csv_path = loop_config.get("data_source")
        self._error_guards = loop_config.get("error_guards", []) or []
        # นโยบายเมื่อแถวพลาด: stop / skip / recover
        on_row_error = str(loop_config.get("on_row_error", "stop")).lower()
        recovery_steps = loop_config.get("recovery_steps", []) or []
        error_log_path = loop_config.get("error_log_path", "")
        setup_steps = loop_config.get("setup_steps", []) or []
        # กัน recover วนพังไม่จบ (เช่น SAP ยังพังต่อทุกครั้งหลัง relaunch) — นับเฉพาะ
        # แถวที่ต้อง recover ติดกันไปเรื่อยๆ โดยไม่มีแถวไหนผ่านคั่นกลาง ถ้าเกินที่ตั้งไว้
        # ถือว่า recovery_steps ไม่ได้แก้ปัญหาจริง หยุดทั้งงานแทนที่จะรันทิ้งจนกว่า CSV จะหมด
        # เช็ค None/"" แยกจาก 0 ตรงๆ (ไม่ใช้ `or`) เพราะ 0 เป็นค่าที่ตั้งใจได้ (หยุดทันที
        # ตั้งแต่ recover ครั้งแรกที่ไม่ผ่าน) ซึ่ง `0 or DEFAULT` จะกลืนกลายเป็น DEFAULT ผิดเจตนา
        raw_max_recoveries = loop_config.get("max_consecutive_recoveries")
        max_consecutive_recoveries = (
            int(raw_max_recoveries) if raw_max_recoveries not in (None, "")
            else DEFAULT_MAX_CONSECUTIVE_RECOVERIES
        )
        consecutive_recoveries = 0

        # ตัวแปรเฉพาะ loop (loop-scoped) — override global เฉพาะตัวที่ "มีค่า"
        # ค่าว่าง (เช่น loop ที่เพิ่ง import มายังไม่กรอก) จะ fall through ไปใช้ค่า global เดิม
        # ไม่ไปลบค่า global ทิ้ง; ถ้า global ก็ไม่มี → ตั้งเป็นค่าว่างให้ resolve ได้ (ไม่ค้าง {NAME})
        loop_vars = loop_config.get("variables") or {}
        base_static = dict(data_source._static)
        for k, v in loop_vars.items():
            if v not in (None, ""):
                base_static[k] = v
            else:
                base_static.setdefault(k, "")
        if loop_vars:
            overridden = [k for k, v in loop_vars.items() if v not in (None, "")]
            if overridden:
                get_logger().info(f"Loop variables override global: {overridden}")

        # สร้าง DataSource ตัวเดียวใช้ทั้ง setup และ steps — ค่าที่ setup เก็บไว้
        # (เช่น sap_get_field → {SESSION_ID}) ต้องมองเห็นได้ตอนรันแถว
        if csv_path:
            ds = DataSource(base_static, csv_path, rows_filter=rows_filter)
        else:
            # ใช้ data_source เดิมถ้าไม่มี loop var (รักษา runtime values); ถ้ามีก็สร้างใหม่ที่ merge แล้ว
            ds = DataSource(base_static) if loop_vars else data_source

        if setup_steps:
            # รันครั้งเดียวก่อนแถวแรก ({csv.X} ยังไม่มีค่า — resolve เป็นค่าว่าง) — พลาด = หยุดทั้งงานทันที
            # (ไม่จับ error ที่นี่ — ปล่อยขึ้นไปให้ run_loop's caller เห็นว่า setup ล้มเหลว)
            self._on_log(f"Setup — รันก่อนเริ่ม ({len(setup_steps)} steps)")
            self._execute_steps(setup_steps, ds)

        if csv_path:
            while ds.has_next_row():
                ds.next_row()
                row_num = ds.current_original_row_num()
                get_logger().info(f"--- CSV row {row_num} ---")
                try:
                    self._execute_steps(steps, ds)
                    consecutive_recoveries = 0  # แถวนี้ผ่านโดยไม่ต้อง recover → environment ยังโอเค
                except SkipRowSignal as e:
                    self._on_log(f"⏭️ ข้ามแถว {row_num}: {e}")
                    get_logger().info(f"Row {row_num} skipped: {e}")
                    consecutive_recoveries = 0  # ตั้งใจ skip เอง ไม่ใช่สัญญาณว่า environment พัง
                    continue
                except (RowError, ImageNotFoundError) as e:
                    if on_row_error == "skip":
                        self._on_log(f"⚠️ แถว {row_num} ผิดพลาด — ข้ามไปแถวถัดไป: {e}")
                        get_logger().error(f"Row {row_num} failed (skipped): {e}")
                        continue
                    if on_row_error == "recover":
                        consecutive_recoveries += 1
                        self._on_log(
                            f"⚠️ แถว {row_num} ผิดพลาด — กำลังกู้คืน "
                            f"({consecutive_recoveries}/{max_consecutive_recoveries}): {e}"
                        )
                        get_logger().error(f"Row {row_num} failed (recover): {e}")
                        if error_log_path:
                            from engine.file_writer import append_error_log
                            try:
                                append_error_log(error_log_path, row_num, str(e))
                            except Exception as log_err:
                                get_logger().warning(f"เขียน error log ไม่สำเร็จ: {log_err}")
                        if recovery_steps:
                            try:
                                self._execute_steps(recovery_steps, ds)
                                self._on_log("↩️ Recovery เสร็จ — ไปแถวถัดไป")
                            except BotStoppedError:
                                raise
                            except Exception as re_err:
                                self._on_log(f"⚠️ Recovery steps พลาดด้วย: {re_err}")
                                get_logger().error(f"Recovery failed for row {row_num}: {re_err}")
                        if consecutive_recoveries >= max_consecutive_recoveries:
                            msg = (f"recover ล้มเหลวติดกัน {consecutive_recoveries} ครั้ง "
                                   f"(เกิน max_consecutive_recoveries={max_consecutive_recoveries}) — หยุดทั้งงาน")
                            self._on_log(f"⛔ {msg}")
                            get_logger().error(msg)
                            raise BotStoppedError(msg)
                        continue
                    raise  # on_row_error=stop → หยุดทั้งงาน
                # BotStoppedError (ผู้ใช้/stop_if_image/error_guard) ไม่ถูกจับ → หยุดทั้งงานเสมอ
        else:
            try:
                self._execute_steps(steps, ds)
            except SkipRowSignal as e:
                # ไม่มี CSV ให้ข้ามไป — จบ loop อย่างสุภาพ
                self._on_log(f"skip_row ถูกเรียกแต่ไม่มี CSV — จบ loop: {e}")
                get_logger().info(f"skip_row with no CSV — ending loop: {e}")

    def _execute_steps(self, steps: list, data_source: DataSource):
        # step-index control → รองรับ retry/skip/restart/inject กลางคันผ่าน Debug Console
        i = 0
        while i < len(steps):
            self._interrupt.check()
            self._check_error_guards()
            get_logger().info(f"Step {i + 1}: {steps[i].get('action')}")
            try:
                self._execute_step(steps[i], data_source)
                i += 1
            except (ImageNotFoundError, RowError) as e:
                i = self._recover(steps, i, e, data_source)

    def _debug_context(self, step: dict, index: int, error: Exception) -> dict:
        is_image = isinstance(error, ImageNotFoundError)
        return {
            "step": step,
            "index": index,
            "error": error,
            "message": str(error),
            "is_image_error": is_image,
            "template_path": getattr(error, "template_path", None),
            "screenshot": getattr(error, "current_screenshot", None),
        }

    def _recover(self, steps: list, i: int, error: Exception, data_source: DataSource) -> int:
        """ตัดสินใจกู้คืนเมื่อ step ที่ index i พลาด → คืน index ถัดไป (หรือ raise BotStoppedError)"""
        # (0) AI self-heal — ลองให้ Claude Code หาตำแหน่ง element ให้ก่อน
        if self._ai_heal and isinstance(error, ImageNotFoundError):
            from engine import ai_healer
            self._on_log(f"🤖 AI heal: กำลังให้ Claude วิเคราะห์หน้าจอ — รอ {self._ai_heal_timeout}s...")
            coords = ai_healer.request_heal(
                error.template_path,
                error.current_screenshot,
                timeout=self._ai_heal_timeout,
            )
            if coords is not None:
                x, y = coords
                self._on_log(f"🤖 AI heal: คลิก ({x}, {y}) แทน template matching")
                actions.click(x, y)
                return i + 1
            self._on_log("🤖 AI heal: ไม่พบ element — ส่งต่อให้ Debug Console")

        # (1) Debug Console แบบ interactive
        if self._on_debug:
            d = self._on_debug(self._debug_context(steps[i], i, error)) or {}
            dec = d.get("decision", "skip")
            if dec == "stop":
                raise BotStoppedError(d.get("message", "หยุดจาก Debug Console"))
            # ผู้ใช้เลือก continue — clear stop flag เผื่อ ESC ถูกกดโดยไม่ตั้งใจขณะ dialog เปิด
            self._interrupt.clear_stop()
            if dec == "retry":
                return i
            if dec == "skip":
                return i + 1
            if dec == "restart":
                self._on_log("↩️ Restart — เริ่มลำดับนี้ใหม่")
                return 0
            if dec == "skip_row":
                self._annotate_and_skip_row(steps[i], i, error, data_source)
            if dec == "inject":
                inject = d.get("steps", []) or []
                self._on_log(f"💉 Inject {len(inject)} step แล้ว {d.get('then', 'retry')}")
                self._execute_steps(inject, data_source)
                return i if d.get("then", "retry") == "retry" else i + 1
            return i + 1
        # (2) legacy on_image_not_found (string) — รักษา behavior/tests เดิม
        if isinstance(error, ImageNotFoundError) and self._on_image_not_found:
            dec = self._on_image_not_found(error)
            if dec == "retry":
                return i
            if dec == "skip":
                return i + 1
            raise BotStoppedError()
        # (3) ไม่มี handler (เช่น headless) → โยนต่อให้ run_loop จัดการตาม on_row_error
        raise error

    def _annotate_and_skip_row(self, step: dict, step_idx: int, error: Exception,
                               data_source: DataSource):
        """บันทึก error + screenshot ลง CSV แล้ว raise SkipRowSignal"""
        import os
        from datetime import datetime

        # ── screenshot ──────────────────────────────────────────────────────
        screenshot = getattr(error, "current_screenshot", None)
        if screenshot is None:
            try:
                import pyautogui
                screenshot = pyautogui.screenshot()
            except Exception:
                pass

        screenshot_path = ""
        csv_path = data_source.csv_path
        if screenshot is not None:
            try:
                base_dir = os.path.dirname(os.path.abspath(csv_path)) if csv_path else "."
                errors_dir = os.path.join(base_dir, "errors")
                os.makedirs(errors_dir, exist_ok=True)
                row_num = data_source.current_original_row_num()
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(errors_dir, f"error_row{row_num}_{ts}.png")
                screenshot.save(screenshot_path)
                self._on_log(f"📸 Screenshot: {screenshot_path}")
            except Exception as e:
                get_logger().warning(f"screenshot save failed: {e}")

        # ── annotate CSV ─────────────────────────────────────────────────────
        if csv_path:
            row_num = data_source.current_original_row_num()
            action = step.get("action", "?")
            target = step.get("target") or step.get("text") or step.get("key") or ""
            step_info = f"Step {step_idx + 1}: {action}"
            if target:
                step_info += f" ({target})"
            from engine.file_writer import annotate_csv_row_error
            annotate_csv_row_error(csv_path, row_num, str(error), step_info, screenshot_path)
            self._on_log(f"📝 บันทึก error ใน CSV แถว {row_num}")

        raise SkipRowSignal(f"ข้าม row (debug console) — {error}")

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
            if isinstance(region, str):
                try:
                    region = tuple(int(p.strip()) for p in region.split(",") if p.strip())
                except ValueError:
                    region = None
            elif region:
                region = tuple(region)
            else:
                region = None
            has = ocr.region_has_text(region, int(step.get("min_chars", 1)))
            return has if until == "text_filled" else not has
        if until in ("window_appears", "window_disappears"):
            from engine import ui_element
            found = ui_element.window_exists(step["title"])
            return found if until == "window_appears" else not found
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

    def _do_wait_window(self, step: dict):
        until = "window_disappears" if step.get("mode") == "disappear" else "window_appears"
        timeout = float(step.get("timeout", 15))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._interrupt.check()
            if self._condition_met(step, until):
                return
            time.sleep(0.4)
        raise ActionError(f"wait_window หมดเวลา {timeout}s (mode={step.get('mode', 'appear')})")

    def _poll_until(self, check, wait_secs: float):
        """เช็ค check() ทันทีหนึ่งครั้ง; ถ้าไม่ผ่าน (falsy) และ wait_secs > 0
        → poll ซ้ำทุก 0.4s จนผ่านหรือหมดเวลา คืนผลของ check ครั้งล่าสุด"""
        result = check()
        if result or wait_secs <= 0:
            return result
        deadline = time.time() + wait_secs
        while not result and time.time() < deadline:
            self._interrupt.check()
            time.sleep(0.4)
            result = check()
        return result

    def _do_if_image(self, step: dict, data_source: DataSource):
        wait_secs = float(step.get("wait", 0) or 0)
        target, conf = step["target"], step.get("confidence", 0.85)
        found = bool(self._poll_until(
            lambda: find_on_screen(target, conf) is not None, wait_secs))
        branch = step.get("then", []) if found else step.get("else", [])
        self._on_log(
            f"if_image: {step['target']} → {'then' if found else 'else'} ({len(branch)} steps)"
        )
        self._execute_steps(branch, data_source)

    def _find_matching_case(self, cases: list, default_conf: float) -> tuple:
        """ไล่เช็ก cases ตามลำดับ คืน (index, case) ของอันแรกที่ตรง หรือ None
        ถ่ายจอครั้งเดียวแล้ว match ทุก template กับภาพเดียวกัน — เร็วกว่าและทุก case
        เห็นหน้าจอ ณ เวลาเดียวกัน"""
        screen = capture_screen() if cases else None
        for i, case in enumerate(cases, 1):
            if find_on_screen(case["target"], case.get("confidence", default_conf),
                              screen=screen) is not None:
                return (i, case)
        return None

    def _do_switch_image(self, step: dict, data_source: DataSource):
        """แตกหลายทาง: ไล่เช็ก cases ตามลำดับ เจอรูปแรกที่ตรง → รัน steps ของ case นั้น
        ถ้าไม่เข้า case ไหนเลย → รัน default (รอได้ด้วย 'wait' — เช่นรอหน้าจอเด้งมา)"""
        default_conf = step.get("confidence", 0.85)
        wait_secs = float(step.get("wait", 0) or 0)
        cases = step.get("cases", [])

        match = self._poll_until(
            lambda: self._find_matching_case(cases, default_conf), wait_secs)

        if match is not None:
            i, case = match
            self._on_log(
                f"switch_image: case {i} ({case['target']}) → {len(case.get('steps', []))} steps"
            )
            self._execute_steps(case.get("steps", []), data_source)
            return
        default_steps = step.get("default", [])
        self._on_log(f"switch_image: ไม่เข้า case ใด → default ({len(default_steps)} steps)")
        self._execute_steps(default_steps, data_source)

    @staticmethod
    def _selector(step: dict) -> dict:
        """ดึง selector dict ของ UI element จาก step (เฉพาะ key ที่ไม่ว่าง)"""
        keys = ("window", "auto_id", "name", "control_type", "class_name")
        return {k: step[k] for k in keys if step.get(k)}

    def _do_write_row(self, step: dict, data_source: DataSource):
        """เขียนค่าที่ resolve แล้ว ต่อท้ายไฟล์ csv/xlsx (ไม่ผ่านการพิมพ์หน้าจอ)"""
        from engine import file_writer
        cols = step.get("columns", [])
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(",")]
        values = [data_source.resolve(c) for c in cols]
        header = step.get("header")
        if isinstance(header, str):
            header = [h.strip() for h in header.split(",") if h.strip()]
        self._on_log(f"write_row → {step.get('path')}: {values}")
        file_writer.append_row(step["path"], values, header)

    def _do_stop_if_image(self, step: dict):
        if find_on_screen(step["target"], step.get("confidence", 0.85)) is not None:
            msg = step.get("message") or f"เจอรูปที่สั่งให้หยุด: {step['target']}"
            self._on_log(f"⛔ {msg}")
            raise BotStoppedError(msg)

    def _do_skip_row(self, step: dict):
        """ข้ามแถว CSV ปัจจุบันทันที ไปทำแถวถัดไป"""
        msg = step.get("message") or "skip_row"
        raise SkipRowSignal(msg)

    def _do_call_loop(self, step: dict, data_source: DataSource):
        """เรียก loop อื่นเป็น subroutine — รันเฉพาะ steps ของมัน (ไม่สน data_source/
        on_row_error/setup_steps ของ loop เป้าหมาย เพราะพวกนั้นมีผลเฉพาะตอนรันเป็น loop หลักเอง)
        ตัวแปรเฉพาะของ loop เป้าหมาย (ที่มีค่า) ถูก apply ระหว่างรันแล้วคืนค่าเดิมให้ผู้เรียกเมื่อจบ
        — loop ที่พึ่งตัวแปรตัวเองต้องทำงานเหมือนตอนรัน standalone"""
        name = step.get("loop", "")
        if not name:
            raise ActionError("call_loop: ไม่ได้ระบุชื่อ loop")
        if name not in self._all_loops:
            raise ActionError(f"call_loop: ไม่พบ loop '{name}'")
        if name in self._call_stack:
            chain = " → ".join(self._call_stack + [name])
            raise ActionError(f"call_loop: เรียกวนซ้ำ (recursion): {chain}")
        target_cfg = self._all_loops[name]
        target_steps = target_cfg.get("steps", [])
        # overlay ตัวแปรเฉพาะ loop เป้าหมาย (ค่าว่าง = fall through ไปใช้ค่าผู้เรียก เหมือน run_loop)
        overrides = {k: v for k, v in (target_cfg.get("variables") or {}).items()
                     if v not in (None, "")}
        _MISSING = object()
        saved = {k: data_source._static.get(k, _MISSING) for k in overrides}
        self._on_log(f"call_loop → {name} ({len(target_steps)} steps)")
        self._call_stack.append(name)
        try:
            for k, v in overrides.items():
                data_source.set_runtime(k, v)
            self._execute_steps(target_steps, data_source)
        finally:
            self._call_stack.pop()
            for k, prev in saved.items():
                if prev is _MISSING:
                    data_source._static.pop(k, None)
                else:
                    data_source._static[k] = prev

    def _do_skip_row_if_image(self, step: dict):
        """ถ้าเจอรูปที่กำหนด → ข้ามแถว CSV ปัจจุบัน ไปแถวถัดไป (ไม่หยุดทั้งงาน)"""
        if find_on_screen(step["target"], step.get("confidence", 0.85)) is not None:
            msg = step.get("message") or f"เจอ {step['target']}"
            raise SkipRowSignal(msg)

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
                actions.type_text(
                    data_source.resolve(step["text"]),
                    method=step.get("method", "paste"),
                    clear=bool(step.get("clear_first", False)),
                )
            elif action == "key":
                actions.press_key(step["key"])
            elif action == "hotkey":
                keys_val = step.get("keys", [])
                if isinstance(keys_val, str):
                    keys_val = [k.strip() for k in keys_val.split("+")]
                actions.hotkey(*keys_val)
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
            elif action == "switch_image":
                self._do_switch_image(step, data_source)
            elif action == "write_row":
                self._do_write_row(step, data_source)
            elif action == "click_element":
                actions.click_element(
                    self._selector(step),
                    timeout=step.get("timeout", 10),
                    button=step.get("button", "left"),
                )
            elif action == "set_element_text":
                actions.set_element_text(
                    self._selector(step),
                    data_source.resolve(step["text"]),
                    timeout=step.get("timeout", 10),
                )
            elif action == "wait_element":
                actions.wait_element(
                    self._selector(step),
                    timeout=step.get("timeout", 15),
                )
            elif action == "wait_window":
                self._do_wait_window(step)
            elif action == "focus_window":
                actions.focus_window(step["title"], timeout=step.get("timeout", 10))
            elif action == "minimize_window":
                actions.minimize_window(step["title"], timeout=step.get("timeout", 10))
            elif action == "kill_window":
                actions.kill_window(step["title"], timeout=step.get("timeout", 10))
            elif action == "launch_program":
                actions.launch_program(step["path"], args=step.get("args", ""))
            elif action == "stop_if_image":
                self._do_stop_if_image(step)
            elif action == "skip_row":
                self._do_skip_row(step)
            elif action == "skip_row_if_image":
                self._do_skip_row_if_image(step)
            elif action == "call_loop":
                self._do_call_loop(step, data_source)
            # ─── SAP Scripting actions ───────────────────────────────────────
            elif action == "sap_set_field":
                from engine.sap_actions import sap_set_field
                text = data_source.resolve(step.get("text", ""))
                sap_set_field(step["field_id"], text,
                              connection=step.get("connection", 0),
                              session=step.get("session", 0))
                self._on_log(f"SAP set '{step['field_id']}' = {repr(text)}")
            elif action == "sap_get_field":
                from engine.sap_actions import sap_get_field
                val = sap_get_field(step["field_id"],
                                    connection=step.get("connection", 0),
                                    session=step.get("session", 0))
                var_name = step.get("variable", "SAP_VALUE")
                data_source.set_runtime(var_name, val)
                self._on_log(f"SAP get '{step['field_id']}' → {{{var_name}}} = {repr(val)}")
            elif action == "sap_press":
                from engine.sap_actions import sap_press
                sap_press(field_id=step.get("field_id"),
                          vkey=step.get("vkey"),
                          connection=step.get("connection", 0),
                          session=step.get("session", 0))
                self._on_log(f"SAP press: {step.get('field_id') or 'vkey=' + str(step.get('vkey'))}")
            else:
                get_logger().warning(f"Unknown action: {action}")
                self._on_log(f"Unknown action: {action}")

        except ImageNotFoundError as e:
            # ไม่จัดการที่นี่ — ปล่อยขึ้นไปให้ _execute_steps/_recover คุมลำดับ step
            get_logger().error(f"Image not found: {e.template_path}")
            self._on_log(f"Image not found: {e.template_path}")
            raise

        except (BotStoppedError, SkipRowSignal, RowError):
            raise  # control-flow / pass-through — อย่าแปลงเป็น error ชนิดอื่น

        except ActionError as e:
            get_logger().error(f"Action error: {e}\n{traceback.format_exc()}")
            self._on_log(f"Error: {e}")
            raise RowError(str(e))

        except Exception as e:
            get_logger().error(f"Unexpected error in step '{action}': {e}\n{traceback.format_exc()}")
            self._on_log(f"Unexpected error: {e}")
            raise RowError(str(e))
