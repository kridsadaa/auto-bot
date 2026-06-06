import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from engine.headless import parse_cli_args, run_loop_headless
from engine.runtime import bootstrap


def main() -> int:
    """entry point — รองรับทั้ง GUI และ CLI headless (--run-loop)"""
    # ตั้ง working dir + สร้าง config ตั้งต้น (สำคัญตอนรันเป็น .exe ที่ยังไม่มี config)
    bootstrap()

    loop_name, config_path = parse_cli_args(sys.argv[1:])
    if loop_name:
        # โหมด CLI/headless (สำหรับ scheduled task) — ไม่เปิด GUI
        return run_loop_headless(loop_name, config_path)

    from engine.logger import setup_logger
    from gui.main_window import MainWindow

    setup_logger()
    MainWindow().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
