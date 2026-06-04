"""
รัน loop แบบไม่มี GUI (สำหรับ scheduled task / CLI)
  python main.py --run-loop <ชื่อ> [--config <path>]
ไม่พึ่ง tkinter — ใช้ actions(pyautogui/keyboard) + InterruptHandler(pynput) ได้ตรงๆ
"""
import sys

from engine.logger import setup_logger, get_logger

DEFAULT_CONFIG = "config/bot_config.yaml"


def _safe_print(msg):
    """พิมพ์แบบไม่พังบน console codepage แคบ (cp874) หรือตอนไม่มี console (scheduled task)"""
    try:
        print(msg)
    except Exception:
        try:
            sys.stdout.write(str(msg).encode("ascii", "replace").decode("ascii") + "\n")
        except Exception:
            pass


def parse_cli_args(argv: list) -> tuple:
    """คืน (loop_name, config_path) — loop_name=None ถ้าไม่ได้สั่ง --run-loop"""
    loop = None
    config = DEFAULT_CONFIG
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--run-loop" and i + 1 < len(argv):
            loop = argv[i + 1]
            i += 2
        elif a == "--config" and i + 1 < len(argv):
            config = argv[i + 1]
            i += 2
        else:
            i += 1
    return loop, config


def run_loop_headless(loop_name: str, config_path: str = DEFAULT_CONFIG) -> int:
    """รัน loop หนึ่งตัวจาก config แล้วคืน exit code (0=สำเร็จ, 1=ผิดพลาด/หยุด, 2=config ผิด)"""
    import yaml
    from engine.data_source import DataSource
    from engine.interrupt_handler import InterruptHandler, BotStoppedError
    from engine.loop_runner import LoopRunner

    setup_logger()
    log = get_logger()
    # console บางตัว (cp874) encode อักษรไทย/สัญลักษณ์ไม่ได้ → บังคับ utf-8 + replace
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        _safe_print(f"Config error: {e}")
        return 2

    loops = config.get("loops", {}) or {}
    if loop_name not in loops:
        _safe_print(f"ไม่พบ loop: {loop_name} (มี: {list(loops)})")
        return 2

    variables = config.get("variables", {}) or {}
    data_source = DataSource({k: (v or "") for k, v in variables.items()})

    interrupt = InterruptHandler()
    interrupt.start()
    # headless: ห้ามเปิด Tk dialog → on_image_not_found=None (เจอภาพไม่ได้ = หยุด/ข้ามตาม on_row_error)
    runner = LoopRunner(interrupt=interrupt, on_image_not_found=None, on_log=_safe_print)
    try:
        runner.run_loop(loops[loop_name], data_source)
        _safe_print(f"Loop {loop_name} เสร็จสิ้น")
        return 0
    except BotStoppedError as e:
        _safe_print(f"หยุด: {e}")
        return 1
    except Exception as e:
        log.error(f"headless error: {e}")
        _safe_print(f"Error: {e}")
        return 1
    finally:
        interrupt.stop()
