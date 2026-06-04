import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import yaml

from engine.data_source import DataSource
from engine.interrupt_handler import InterruptHandler, BotStoppedError
from engine.loop_runner import LoopRunner
from engine.screen_monitor import ScreenMonitor
from engine.image_matcher import ImageNotFoundError
from gui.log_panel import LogPanel
from gui.capture_tool import CaptureTool
from gui.error_dialog import show_error_dialog
from gui.sequence_editor import SequenceEditor


CONFIG_PATH = "config/bot_config.yaml"


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Bot")
        self.geometry("860x560")
        self.minsize(860, 480)
        self.resizable(True, True)
        self.configure(bg="#2d2d2d")

        self._config = self._load_config()
        self._mode = tk.StringVar(value="agent")
        self._status = tk.StringVar(value="พร้อมใช้งาน")
        self._interrupt = InterruptHandler()
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

        # Mode toggle
        mode_frame = tk.Frame(header, bg="#1e1e1e")
        mode_frame.pack(side="right", padx=14)
        tk.Label(mode_frame, text="Mode:", bg="#1e1e1e", fg="#9cdcfe").pack(side="left")
        for val, label in [("copilot", "Copilot"), ("agent", "Agent")]:
            tk.Radiobutton(
                mode_frame, text=label, variable=self._mode, value=val,
                bg="#1e1e1e", fg="white", selectcolor="#0e639c",
                activebackground="#1e1e1e", activeforeground="white",
            ).pack(side="left", padx=4)

        # --- แถว 1: Bot controls ---
        ctrl1 = tk.Frame(self, bg="#2d2d2d", pady=5)
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

        tk.Label(ctrl1, text="ESC = Pause  |  Mouse มุมซ้ายบน = Stop ทันที",
                 bg="#2d2d2d", fg="#6e6e6e", font=("Segoe UI", 8)).pack(side="left", padx=14)

        # --- แถว Run Loop โดยตรง (ไม่ต้องมี state/trigger) ---
        run_loop_bar = tk.Frame(self, bg="#2d2d2d", pady=5)
        run_loop_bar.pack(fill="x", padx=10)

        tk.Label(run_loop_bar, text="Run Loop:", bg="#2d2d2d", fg="#9cdcfe",
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 8))

        self._loop_choice = tk.StringVar()
        self._loop_combo = ttk.Combobox(
            run_loop_bar, textvariable=self._loop_choice,
            state="readonly", width=28,
        )
        self._loop_combo.pack(side="left", padx=4)

        self._btn_run_loop = tk.Button(
            run_loop_bar, text="▶  Run Loop นี้", width=14,
            bg="#dcdcaa", fg="black", font=("Segoe UI", 9, "bold"),
            command=self._run_selected_loop,
        )
        self._btn_run_loop.pack(side="left", padx=6)

        tk.Label(run_loop_bar, text="(run ทันที ไม่ต้องรอ trigger image)",
                 bg="#2d2d2d", fg="#6e6e6e", font=("Segoe UI", 8)).pack(side="left", padx=8)

        self._refresh_loop_choices()

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
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_image_not_found=lambda e: self._handle_image_error(e),
            on_log=lambda msg: self._queue_log(msg),
        )

        def run():
            try:
                runner.run_loop(loop_cfg, data_source)
                self._queue_log(f"Loop {loop_name} เสร็จสิ้น", "ok")
            except BotStoppedError:
                self._queue_log("Bot หยุดโดยผู้ใช้", "warn")
            except Exception as ex:
                self._queue_log(f"Error: {ex}", "error")
            finally:
                self.after(0, lambda: self._set_running_state(False))
                self.after(0, lambda: self._status.set("เสร็จสิ้น"))

        self._bot_thread = threading.Thread(target=run, daemon=True)
        self._bot_thread.start()

    def _on_start(self):
        self._config = self._load_config()
        self._refresh_state_list()
        self._refresh_loop_choices()

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
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_image_not_found=lambda e: self._handle_image_error(e),
            on_log=lambda msg: self._queue_log(msg),
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
        self._status.set(f"State: {state_name}")

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
            self._on_stop()
        except Exception as ex:
            self._queue_log(f"Error: {ex}", "error")
            self._on_stop()

    def _start_copilot_mode(self, data_source: DataSource):
        self._status.set("Copilot Mode — รอ state ถัดไป...")
        runner = LoopRunner(
            interrupt=self._interrupt,
            on_image_not_found=lambda e: self._handle_image_error(e),
            on_log=lambda msg: self._queue_log(msg),
        )
        states = self._config.get("states", [])
        loops = self._config.get("loops", {})

        def on_state(name):
            self._queue_log(f"เจอ state: {name} — รอการยืนยัน", "warn")
            confirmed = messagebox.askyesno(
                "Copilot", f"เจอ state: {name}\nเริ่ม loop หรือไม่?", parent=self,
            )
            if confirmed:
                self._on_state_detected(name, runner, data_source, loops)

        self._monitor = ScreenMonitor(states=states, on_state_detected=on_state)
        self._monitor.start()

    def _handle_image_error(self, error: ImageNotFoundError) -> str:
        result = {"value": "stop"}
        event = threading.Event()

        def show():
            r = show_error_dialog(self, error, on_capture_new=self._recapture)
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
            self._btn_pause.configure(text="Pause (ESC)")
            self._status.set("กำลังทำงาน...")
        else:
            self._interrupt._paused = True
            self._btn_pause.configure(text="Resume (ESC)")
            self._status.set("Paused — กด Resume หรือ ESC เพื่อทำต่อ")

    def _on_stop(self):
        self._interrupt.request_stop()
        if self._monitor:
            self._monitor.stop()
        self._set_running_state(False)
        self._status.set("หยุดทำงาน")
        self._queue_log("Bot หยุดทำงาน", "warn")

    def _set_running_state(self, running: bool):
        self._btn_start.configure(state="disabled" if running else "normal")
        self._btn_run_loop.configure(state="disabled" if running else "normal")
        self._btn_pause.configure(state="normal" if running else "disabled")
        self._btn_stop.configure(state="normal" if running else "disabled")

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
