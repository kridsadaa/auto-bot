import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import yaml

from engine.data_source import DataSource
from engine.runtime import apply_window_icon
from engine.interrupt_handler import InterruptHandler, BotStoppedError
from engine.loop_runner import LoopRunner
from engine.screen_monitor import ScreenMonitor
from gui.log_panel import LogPanel
from gui.capture_tool import CaptureTool
from gui.error_dialog import show_debug_console
from gui.sequence_editor import SequenceEditor


CONFIG_PATH = "config/bot_config.yaml"

# วินาทีนับถอยหลังก่อนเริ่ม "Run Loop นี้" — ให้ผู้ใช้ทันคลิกหน้าต่างปลายทาง
START_COUNTDOWN = 3


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Bot")
        self.geometry("860x560")
        self.minsize(860, 480)
        self.resizable(True, True)
        self.configure(bg="#2d2d2d")
        apply_window_icon(self)

        self._config = self._load_config()
        self._mode = tk.StringVar(value="agent")
        # รันแบบ: "direct" = เลือก loop รันทันที, "trigger" = เฝ้าหน้าจอหา trigger image
        self._run_mode = tk.StringVar(value="direct")
        self._status = tk.StringVar(value="พร้อมใช้งาน")
        self._running = False
        self._interrupt = InterruptHandler(
            on_stop_hotkey=lambda: self.after(0, self._stop_from_hotkey)
        )
        self._log_queue: queue.Queue = queue.Queue()
        self._monitor: ScreenMonitor = None
        self._bot_thread: threading.Thread = None

        self._build()
        self._poll_log_queue()

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            messagebox.showerror("Config Error", str(e))
            return {"variables": {}, "states": [], "loops": {}}

    def _build(self):
        # --- Header ---
        header = tk.Frame(self, bg="#1e1e1e", pady=8)
        header.pack(fill="x")

        tk.Label(
            header, text="Auto Bot", font=("Segoe UI", 14, "bold"),
            bg="#1e1e1e", fg="white",
        ).pack(side="left", padx=14)

        # --- แถว: รันแบบ (เลือกว่า Start จะทำอะไร) ---
        runmode_bar = tk.Frame(self, bg="#2d2d2d", pady=6)
        runmode_bar.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(runmode_bar, text="รันแบบ:", bg="#2d2d2d", fg="#9cdcfe",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(4, 8))
        self._run_mode_radios = []
        for val, label in [("direct", "เลือก Loop รันทันที"),
                           ("trigger", "เฝ้า Trigger อัตโนมัติ")]:
            rb = tk.Radiobutton(
                runmode_bar, text=label, variable=self._run_mode, value=val,
                bg="#2d2d2d", fg="white", selectcolor="#0e639c",
                activebackground="#2d2d2d", activeforeground="white",
                command=self._on_run_mode_change,
            )
            rb.pack(side="left", padx=6)
            self._run_mode_radios.append(rb)

        # --- แถว: Loop (สำหรับ direct) + Mode (สำหรับ trigger) ---
        cfg_bar = tk.Frame(self, bg="#2d2d2d", pady=4)
        cfg_bar.pack(fill="x", padx=10)

        tk.Label(cfg_bar, text="Loop:", bg="#2d2d2d", fg="#9cdcfe",
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 8))
        self._loop_choice = tk.StringVar()
        self._loop_combo = ttk.Combobox(
            cfg_bar, textvariable=self._loop_choice, state="readonly", width=26,
        )
        self._loop_combo.pack(side="left", padx=4)

        tk.Label(cfg_bar, text="Mode:", bg="#2d2d2d", fg="#9cdcfe",
                 font=("Segoe UI", 9)).pack(side="left", padx=(18, 4))
        self._mode_radios = []
        for val, label in [("copilot", "Copilot"), ("agent", "Agent")]:
            rb = tk.Radiobutton(
                cfg_bar, text=label, variable=self._mode, value=val,
                bg="#2d2d2d", fg="white", selectcolor="#0e639c",
                activebackground="#2d2d2d", activeforeground="white",
            )
            rb.pack(side="left", padx=4)
            self._mode_radios.append(rb)
        self._refresh_loop_choices()

        # --- แถว: ปุ่มควบคุม ---
        ctrl1 = tk.Frame(self, bg="#2d2d2d", pady=6)
        ctrl1.pack(fill="x", padx=10)

        self._btn_start = tk.Button(
            ctrl1, text="▶  Start", width=12,
            bg="#4ec9b0", fg="black", font=("Segoe UI", 10, "bold"),
            command=self._on_start,
        )
        self._btn_start.pack(side="left", padx=4)

        self._btn_pause = tk.Button(
            ctrl1, text="⏸  Pause", width=12,
            state="disabled", command=self._on_pause,
        )
        self._btn_pause.pack(side="left", padx=4)

        self._btn_stop = tk.Button(
            ctrl1, text="⏹  Stop", width=12,
            bg="#f44747", fg="white",
            state="disabled", command=self._on_stop,
        )
        self._btn_stop.pack(side="left", padx=4)

        tk.Label(ctrl1, text="ESC = หยุดบอท (ทุกหน้าต่าง)  |  Mouse มุมซ้ายบน = หยุดทันที",
                 bg="#2d2d2d", fg="#6e6e6e", font=("Segoe UI", 8)).pack(side="left", padx=14)

        self._on_run_mode_change()  # ตั้งสถานะ enable/disable ของ Loop/Mode ให้ตรงค่าเริ่มต้น

        # --- แถว 2: Tools ---
        ctrl2 = tk.Frame(self, bg="#252526", pady=5)
        ctrl2.pack(fill="x", padx=10)

        tk.Label(ctrl2, text="Tools:", bg="#252526", fg="#9cdcfe",
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 8))

        tk.Button(
            ctrl2, text="+ Capture Trigger", width=16,
            command=self._on_capture_trigger,
        ).pack(side="left", padx=4)

        tk.Button(
            ctrl2, text="+ Capture Element", width=16,
            command=self._on_capture_element,
        ).pack(side="left", padx=4)

        tk.Button(
            ctrl2, text="Sequence Editor", width=16,
            bg="#569cd6", fg="white", font=("Segoe UI", 9, "bold"),
            command=self._open_sequence_editor,
        ).pack(side="left", padx=4)

        tk.Button(
            ctrl2, text="🕒 Schedule", width=12,
            command=self._open_schedule,
        ).pack(side="left", padx=4)

        # --- Status bar ---
        status_bar = tk.Frame(self, bg="#007acc", pady=3)
        status_bar.pack(fill="x")
        tk.Label(
            status_bar, textvariable=self._status,
            bg="#007acc", fg="white", font=("Segoe UI", 9),
        ).pack(side="left", padx=10)

        # --- State list ---
        state_frame = tk.LabelFrame(
            self, text="States ที่ตั้งค่า", bg="#2d2d2d", fg="#9cdcfe",
            font=("Segoe UI", 9),
        )
        state_frame.pack(fill="x", padx=10, pady=(6, 0))

        self._state_list = tk.Listbox(
            state_frame, height=4, bg="#1e1e1e", fg="#d4d4d4",
            selectbackground="#0e639c", font=("Consolas", 9),
        )
        self._state_list.pack(fill="x", padx=6, pady=4)
        self._refresh_state_list()

        # --- Log panel ---
        log_frame = tk.LabelFrame(
            self, text="Activity Log", bg="#2d2d2d", fg="#9cdcfe",
            font=("Segoe UI", 9),
        )
        log_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self._log = LogPanel(log_frame, bg="#1e1e1e")
        self._log.pack(fill="both", expand=True)

    def _refresh_loop_choices(self):
        loops = list(self._config.get("loops", {}).keys())
        self._loop_combo["values"] = loops
        if loops and self._loop_choice.get() not in loops:
            self._loop_choice.set(loops[0])
        elif not loops:
            self._loop_choice.set("")

    def _refresh_state_list(self):
        self._state_list.delete(0, "end")
        for state in self._config.get("states", []):
            trigger = state.get("trigger", {})
            self._state_list.insert(
                "end",
                f"  {state['name']}  →  loop: {state.get('loop', '?')}  |  trigger: {trigger.get('file', '?')}",
            )

    def _poll_log_queue(self):
        while not self._log_queue.empty():
            msg, level = self._log_queue.get_nowait()
            self._log.log(msg, level)
        self.after(100, self._poll_log_queue)

    def _queue_log(self, msg: str, level: str = "info"):
        self._log_queue.put((msg, level))

    def _prompt_runtime_vars(self) -> dict | None:
        """ถามค่า runtime variables ที่ยังว่างอยู่ คืน None ถ้าผู้ใช้ยกเลิก"""
        runtime_vars = {}
        for k, v in self._config.get("variables", {}).items():
            if not v:
                val = simpledialog.askstring("Runtime Input", f"กรุณาใส่ค่า: {k}", parent=self)
                if val is None:
                    return None
                runtime_vars[k] = val
            else:
                runtime_vars[k] = v
        return runtime_vars

    def _run_selected_loop(self):
        self._config = self._load_config()
        self._refresh_state_list()
        self._refresh_loop_choices()

        loop_name = self._loop_choice.get()
        loops = self._config.get("loops", {})
        if not loop_name or loop_name not in loops:
            messagebox.showwarning("", "เลือก loop ที่จะ run ก่อน")
            return

        runtime_vars = self._prompt_runtime_vars()
        if runtime_vars is None:
            return

        self._interrupt.start()
        self._set_running_state(True)
        self._log.clear()
        self._queue_log(f"เริ่ม run loop: {loop_name}", "ok")
        self._status.set(f"กำลัง run loop: {loop_name}")

        data_source = DataSource(runtime_vars)
        loop_cfg = loops[loop_name]

        # SAP Shadow Capture — เริ่มเบื้องหลัง ถ้าไม่พร้อมก็ fail เงียบๆ
        from engine.sap_capture import SapCapture
        sap_cap = SapCapture()
        sap_available = sap_cap.start()
        if sap_available:
            self._queue_log("🔍 SAP Shadow Capture เริ่มแล้ว (จะแสดง Compare เมื่อจบ)", "info")

        ai_heal_cfg = self._config.get("ai_heal", {})
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_debug=lambda ctx: self._handle_debug(ctx),
            on_log=lambda msg: self._queue_log(msg),
            sap_capture=sap_cap,
            ai_heal=bool(ai_heal_cfg.get("enabled", False)),
            ai_heal_timeout=int(ai_heal_cfg.get("timeout", 60)),
        )

        def run():
            success = False
            try:
                for i in range(START_COUNTDOWN, 0, -1):
                    if self._interrupt.is_stopped():
                        return
                    self._queue_log(f"เริ่มใน {i}... → คลิกหน้าต่าง/ช่องปลายทางตอนนี้", "warn")
                    time.sleep(1)
                runner.run_loop(loop_cfg, data_source)
                self._queue_log(f"Loop {loop_name} เสร็จสิ้น", "ok")
                success = True
            except BotStoppedError:
                self._queue_log("Bot หยุดโดยผู้ใช้", "warn")
            except Exception as ex:
                self._queue_log(f"Error: {ex}", "error")
            finally:
                sap_events = sap_cap.stop()
                self.after(0, lambda: self._set_running_state(False))
                self.after(0, lambda: self._status.set("เสร็จสิ้น"))
                if success and sap_available and sap_events:
                    self.after(0, lambda: self._show_sap_compare(
                        loop_name, loop_cfg.get("steps", []), sap_events))
                # เช็ก error log หลัง loop จบ — ถ้ามีแถวพลาดให้ถามรัน retry
                if loop_cfg.get("on_row_error") == "recover":
                    _ln, _lc, _rv = loop_name, loop_cfg, runtime_vars
                    self.after(400, lambda: self._check_and_offer_retry(_ln, _lc, _rv))

        self._bot_thread = threading.Thread(target=run, daemon=True)
        self._bot_thread.start()

    def _check_and_offer_retry(self, loop_name: str, loop_cfg: dict, runtime_vars: dict):
        """หลัง loop จบ: ถ้ามีแถวที่พลาดใน error log → ถามว่าจะรันซ้ำไหม"""
        error_log = loop_cfg.get("error_log_path", "")
        if not error_log or not os.path.exists(error_log):
            return
        from engine.file_writer import read_error_log_row_nums
        failed = read_error_log_row_nums(error_log)
        if not failed:
            return
        rows_preview = str(sorted(failed)[:10])
        if len(failed) > 10:
            rows_preview += "..."
        ans = messagebox.askyesno(
            "มีแถวที่พลาด",
            f"มี {len(failed)} แถวที่ผิดพลาด\nแถว: {rows_preview}\n\n"
            f"ต้องการรัน {len(failed)} แถวนั้นซ้ำไหม?",
            parent=self,
        )
        if not ans:
            return
        try:
            os.remove(error_log)
        except Exception:
            pass
        self._run_failed_rows(loop_name, loop_cfg, runtime_vars, failed)

    def _run_failed_rows(self, loop_name: str, loop_cfg: dict, runtime_vars: dict, rows_filter: set):
        """รัน loop เฉพาะแถวใน rows_filter (original CSV row numbers)"""
        self._interrupt.start()
        self._set_running_state(True)
        self._log.clear()
        self._queue_log(f"Re-run {len(rows_filter)} แถวที่พลาด: {sorted(rows_filter)}", "warn")
        self._status.set(f"Re-run failed rows: {loop_name}")

        data_source = DataSource(runtime_vars)

        from engine.sap_capture import SapCapture
        sap_cap = SapCapture()
        sap_cap.start()

        _ai = self._config.get("ai_heal", {})
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_debug=lambda ctx: self._handle_debug(ctx),
            on_log=lambda msg: self._queue_log(msg),
            sap_capture=sap_cap,
            ai_heal=bool(_ai.get("enabled", False)),
            ai_heal_timeout=int(_ai.get("timeout", 60)),
        )

        def run():
            try:
                for i in range(START_COUNTDOWN, 0, -1):
                    if self._interrupt.is_stopped():
                        return
                    self._queue_log(f"เริ่มใน {i}...", "warn")
                    time.sleep(1)
                runner.run_loop(loop_cfg, data_source, rows_filter=rows_filter)
                self._queue_log("Re-run เสร็จสิ้น", "ok")
            except BotStoppedError:
                self._queue_log("Bot หยุดโดยผู้ใช้", "warn")
            except Exception as ex:
                self._queue_log(f"Error: {ex}", "error")
            finally:
                sap_cap.stop()
                self.after(0, lambda: self._set_running_state(False))
                self.after(0, lambda: self._status.set("เสร็จสิ้น"))
                # วนเช็กซ้ำถ้ายังมีแถวพลาดอีก
                if loop_cfg.get("on_row_error") == "recover":
                    _ln, _lc, _rv = loop_name, loop_cfg, runtime_vars
                    self.after(400, lambda: self._check_and_offer_retry(_ln, _lc, _rv))

        self._bot_thread = threading.Thread(target=run, daemon=True)
        self._bot_thread.start()

    def _show_sap_compare(self, loop_name: str, image_steps: list, sap_events: list):
        """เปิด Compare dialog หลัง loop จบสำเร็จ + มี SAP events"""
        from gui.sap_compare_dialog import SapCompareDialog
        def on_save(new_name: str, new_steps: list):
            self._config.setdefault("loops", {})[new_name] = {"steps": new_steps}
            # เซฟ config ทันที
            import yaml
            with open("config/bot_config.yaml", "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, allow_unicode=True, sort_keys=False)
            self._queue_log(f"✅ สร้าง loop '{new_name}' (SAP script) แล้ว", "ok")
        SapCompareDialog(self, image_steps, sap_events, loop_name, on_save=on_save)

    def _on_start(self):
        """ปุ่ม Start เดียว — ทำตาม 'รันแบบ' ที่เลือก"""
        if self._run_mode.get() == "direct":
            self._run_selected_loop()      # เลือก loop รันทันที (ไม่รอ trigger)
        else:
            self._start_trigger_mode()     # เฝ้าหน้าจอหา trigger แล้วรัน loop อัตโนมัติ

    def _start_trigger_mode(self):
        self._config = self._load_config()
        self._refresh_state_list()
        self._refresh_loop_choices()

        if not self._config.get("states"):
            messagebox.showwarning(
                "ยังไม่มี Trigger",
                "โหมด 'เฝ้า Trigger' ต้องตั้ง state/trigger image ก่อน\n"
                "(ตั้งใน Sequence Editor → States) — หรือใช้ 'เลือก Loop รันทันที' แทน",
            )
            return

        # ถามค่า runtime variables ที่ยังว่างอยู่
        runtime_vars = self._prompt_runtime_vars()
        if runtime_vars is None:
            return

        self._interrupt.start()
        self._set_running_state(True)
        self._log.clear()
        self._queue_log("Bot เริ่มทำงาน", "ok")

        data_source = DataSource(runtime_vars)

        if self._mode.get() == "agent":
            self._start_agent_mode(data_source)
        else:
            self._start_copilot_mode(data_source)

    def _start_agent_mode(self, data_source: DataSource):
        _ai = self._config.get("ai_heal", {})
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_debug=lambda ctx: self._handle_debug(ctx),
            on_log=lambda msg: self._queue_log(msg),
            ai_heal=bool(_ai.get("enabled", False)),
            ai_heal_timeout=int(_ai.get("timeout", 60)),
        )
        states = self._config.get("states", [])
        loops = self._config.get("loops", {})

        def run():
            self._monitor = ScreenMonitor(
                states=states,
                on_state_detected=lambda name: self._on_state_detected(name, runner, data_source, loops),
                interval=1.5,
            )
            self._monitor.start()

        self._bot_thread = threading.Thread(target=run, daemon=True)
        self._bot_thread.start()
        self._status.set("Agent Mode — กำลัง monitor หน้าจอ...")

    def _on_state_detected(self, state_name: str, runner: LoopRunner, data_source: DataSource, loops: dict):
        self._queue_log(f"เจอ state: {state_name}", "ok")
        self.after(0, lambda: self._status.set(f"State: {state_name}"))

        state_cfg = next((s for s in self._config["states"] if s["name"] == state_name), None)
        if not state_cfg:
            return

        loop_name = state_cfg.get("loop")
        loop_cfg = loops.get(loop_name)
        if not loop_cfg:
            self._queue_log(f"ไม่พบ loop: {loop_name}", "warn")
            return

        try:
            runner.run_loop(loop_cfg, data_source)
            self._queue_log(f"Loop {loop_name} เสร็จสิ้น", "ok")
        except BotStoppedError:
            self._queue_log("Bot หยุดโดยผู้ใช้", "warn")
            self.after(0, self._on_stop)
        except Exception as ex:
            self._queue_log(f"Error: {ex}", "error")
            self.after(0, self._on_stop)

    def _start_copilot_mode(self, data_source: DataSource):
        self._status.set("Copilot Mode — รอ state ถัดไป...")
        _ai = self._config.get("ai_heal", {})
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_debug=lambda ctx: self._handle_debug(ctx),
            on_log=lambda msg: self._queue_log(msg),
            ai_heal=bool(_ai.get("enabled", False)),
            ai_heal_timeout=int(_ai.get("timeout", 60)),
        )
        states = self._config.get("states", [])
        loops = self._config.get("loops", {})

        def on_state(name):
            result = {"confirmed": False}
            event = threading.Event()

            def ask():
                self._queue_log(f"เจอ state: {name} — รอการยืนยัน", "warn")
                r = messagebox.askyesno(
                    "Copilot", f"เจอ state: {name}\nเริ่ม loop หรือไม่?", parent=self,
                )
                result["confirmed"] = r
                event.set()

            self.after(0, ask)
            event.wait()

            if result["confirmed"]:
                self._on_state_detected(name, runner, data_source, loops)

        self._monitor = ScreenMonitor(states=states, on_state_detected=on_state)
        self._monitor.start()

    def _handle_debug(self, context: dict) -> dict:
        """เปิด Debug Console บน main thread แล้วรอ decision dict (เรียกจาก bot thread)"""
        result = {"value": {"decision": "stop"}}
        event = threading.Event()

        def show():
            r = show_debug_console(self, context, on_recapture=self._recapture)
            result["value"] = r
            event.set()

        self.after(0, show)
        event.wait()
        return result["value"]

    def _recapture(self, original_path: str):
        self._queue_log(f"เปิด capture tool สำหรับ: {original_path}", "warn")
        import os
        save_dir = os.path.dirname(original_path)
        name = os.path.splitext(os.path.basename(original_path))[0]

        def on_done(path):
            import shutil
            shutil.copy(path, original_path)
            self._queue_log(f"บันทึก trigger ใหม่: {original_path}", "ok")

        tool = CaptureTool(self, save_dir=save_dir, on_done=on_done)
        tool.start()

    def _on_pause(self):
        if self._interrupt.is_paused():
            self._interrupt._paused = False
            self._btn_pause.configure(text="⏸  Pause")
            self._status.set("กำลังทำงาน...")
        else:
            self._interrupt._paused = True
            self._btn_pause.configure(text="▶  Resume")
            self._status.set("Paused — กด Resume เพื่อทำต่อ")

    def _stop_from_hotkey(self):
        """เรียกจาก InterruptHandler เมื่อกด ESC (รันบน main thread ผ่าน after)"""
        if self._running:
            self._queue_log("ESC — หยุดบอท", "warn")
            self._on_stop()

    def _on_stop(self):
        self._interrupt.request_stop()
        if self._monitor:
            self._monitor.stop()
        self._set_running_state(False)
        self._status.set("หยุดทำงาน")
        self._queue_log("Bot หยุดทำงาน", "warn")

    def _on_run_mode_change(self):
        """เปิด/ปิดคอนโทรลให้ตรงกับ 'รันแบบ' ที่เลือก — ลดความงงว่าอันไหนมีผล
        - direct: ใช้ Loop dropdown (Mode ไม่เกี่ยว → ปิด)
        - trigger: ใช้ Mode Copilot/Agent (Loop dropdown ไม่เกี่ยว → ปิด)
        """
        if self._running:
            return
        direct = self._run_mode.get() == "direct"
        self._loop_combo.configure(state="readonly" if direct else "disabled")
        for rb in self._mode_radios:
            rb.configure(state="disabled" if direct else "normal")

    def _set_running_state(self, running: bool):
        self._running = running
        self._btn_start.configure(state="disabled" if running else "normal")
        self._btn_pause.configure(state="normal" if running else "disabled")
        self._btn_stop.configure(state="normal" if running else "disabled")
        # ปิดตัวเลือกขณะรัน, เปิดคืนตาม run mode เมื่อหยุด
        for rb in getattr(self, "_run_mode_radios", []):
            rb.configure(state="disabled" if running else "normal")
        if running:
            self._loop_combo.configure(state="disabled")
            for rb in self._mode_radios:
                rb.configure(state="disabled")
        else:
            self._on_run_mode_change()

    def _on_capture_trigger(self):
        tool = CaptureTool(self, save_dir="triggers", on_done=self._on_captured_trigger)
        self.after(300, tool.start)

    def _on_captured_trigger(self, path: str):
        self._queue_log(f"บันทึก trigger: {path}", "ok")
        messagebox.showinfo(
            "บันทึกแล้ว",
            f"Trigger image บันทึกที่:\n{path}\n\nเพิ่ม state ใน config/bot_config.yaml เพื่อใช้งาน",
            parent=self,
        )

    def _open_schedule(self):
        from gui.schedule_dialog import ScheduleDialog
        self._config = self._load_config()
        ScheduleDialog(self, list(self._config.get("loops", {}).keys()))

    def _open_sequence_editor(self):
        editor = SequenceEditor(self)
        # reload config หลัง editor ปิด
        editor.bind("<Destroy>", lambda e: self._reload_config())

    def _reload_config(self):
        self._config = self._load_config()
        self._refresh_state_list()
        self._refresh_loop_choices()

    def _on_capture_element(self):
        tool = CaptureTool(self, save_dir="elements", on_done=self._on_captured_element)
        self.after(300, tool.start)

    def _on_captured_element(self, path: str):
        self._queue_log(f"บันทึก element: {path}", "ok")
