"""
สร้าง/ลบ scheduled task ผ่าน Windows Task Scheduler (schtasks)
รันบอทแบบ headless ตามเวลา: python main.py --run-loop <ชื่อ>
"""
import os
import subprocess
import sys

TASK_PREFIX = "AutoBot_"


def task_name(loop: str) -> str:
    return f"{TASK_PREFIX}{loop}"


def build_run_command(loop: str, frozen: bool = None,
                      executable: str = None, script: str = None) -> str:
    """คำสั่งที่ task จะรัน (ค่า /tr) — รองรับทั้งโหมด .exe (frozen) และ script"""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if executable is None:
        executable = sys.executable
    if frozen:
        return f'"{executable}" --run-loop {loop}'
    if script is None:
        script = os.path.abspath("main.py")
    return f'"{executable}" "{script}" --run-loop {loop}'


def build_create_argv(loop: str, sc: str, st: str, sd: str = None,
                      run_cmd: str = None) -> list:
    """argv ของ schtasks /create
    sc: 'daily' | 'once'  ·  st: 'HH:MM'  ·  sd: 'MM/DD/YYYY' (จำเป็นสำหรับ once)
    """
    if run_cmd is None:
        run_cmd = build_run_command(loop)
    argv = ["schtasks", "/create", "/tn", task_name(loop),
            "/tr", run_cmd, "/sc", sc, "/st", st, "/f"]
    if sd:
        argv += ["/sd", sd]
    return argv


def create_task(loop: str, sc: str, st: str, sd: str = None) -> str:
    argv = build_create_argv(loop, sc, st, sd)
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return task_name(loop)


def parse_task_names(query_csv: str) -> list:
    """ดึงชื่อ task ที่ขึ้นต้น AutoBot_ จากผลลัพธ์ schtasks /query /fo csv /nh"""
    names = []
    for line in query_csv.splitlines():
        line = line.strip()
        if not line:
            continue
        first = line.split('","')[0].strip().strip('"').lstrip("\\")
        if first.startswith(TASK_PREFIX):
            names.append(first)
    return sorted(set(names))


def list_tasks() -> list:
    r = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"],
                       capture_output=True, text=True)
    return parse_task_names(r.stdout or "")


def delete_task(name: str):
    r = subprocess.run(["schtasks", "/delete", "/tn", name, "/f"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
