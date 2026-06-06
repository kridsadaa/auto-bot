"""
Runtime bootstrap — จัดการ path/ไฟล์ตั้งต้นให้ทำงานได้ทั้งตอนรันเป็น script และเป็น .exe (PyInstaller)

ปัญหาที่แก้: ตอนรันเป็น .exe ถ้าไม่มี config/bot_config.yaml จะเปิดไม่ได้
- frozen (.exe): ให้ใช้โฟลเดอร์ "ข้างๆ exe" เป็นฐาน (เก็บ config/elements/... ถาวร)
  แล้วสร้าง config/bot_config.yaml จากไฟล์ตัวอย่างที่ bundle มา ถ้ายังไม่มี
- dev (script): ใช้ working directory เดิมตามปกติ
"""
import os
import shutil
import sys

CONFIG_REL = os.path.join("config", "bot_config.yaml")
EXAMPLE_REL = os.path.join("config", "bot_config.example.yaml")

# config ขั้นต่ำ ถ้าหาไฟล์ตัวอย่างไม่เจอ
_MINIMAL_CONFIG = "variables: {}\nstates: []\nloops: {}\n"


def is_frozen() -> bool:
    """True ถ้ากำลังรันเป็น .exe ที่ build ด้วย PyInstaller"""
    return bool(getattr(sys, "frozen", False))


def app_base_dir() -> str:
    """โฟลเดอร์ฐานสำหรับไฟล์ผู้ใช้ (config/, elements/, triggers/, data/)
    - frozen: โฟลเดอร์ที่มี AutoBot.exe อยู่ (ถาวร แก้ไขได้)
    - dev: working directory ปัจจุบัน
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.getcwd()


def bundled_example_path() -> str | None:
    """path ของ bot_config.example.yaml ที่ถูก bundle (อยู่ใน _MEIPASS เมื่อ frozen)"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, EXAMPLE_REL)
    return EXAMPLE_REL if os.path.exists(EXAMPLE_REL) else None


def ensure_config(base_dir: str, example_path: str | None,
                  config_rel: str = CONFIG_REL) -> str:
    """สร้าง config/bot_config.yaml ใน base_dir ถ้ายังไม่มี — คืน absolute path
    คัดลอกจาก example_path ถ้ามี ไม่งั้นเขียน config ขั้นต่ำ
    """
    target = os.path.join(base_dir, config_rel)
    if not os.path.exists(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if example_path and os.path.exists(example_path):
            shutil.copyfile(example_path, target)
        else:
            with open(target, "w", encoding="utf-8") as f:
                f.write(_MINIMAL_CONFIG)
    return target


def bootstrap() -> None:
    """เรียกครั้งเดียวตอนเริ่มโปรแกรม:
    - ถ้าเป็น .exe ให้ chdir ไปข้างๆ exe (ให้ relative path ทั้งหมด config/elements/... ชี้ที่เดียวกัน)
    - สร้าง config/bot_config.yaml ถ้ายังไม่มี
    """
    base = app_base_dir()
    if is_frozen():
        os.chdir(base)
    ensure_config(base, bundled_example_path())
