from engine import scheduler
from engine.headless import parse_cli_args


def test_build_run_command_script_mode():
    cmd = scheduler.build_run_command(
        "fill_b", frozen=False, executable=r"C:\Py\python.exe", script=r"C:\app\main.py"
    )
    assert cmd == r'"C:\Py\python.exe" "C:\app\main.py" --run-loop fill_b'


def test_build_run_command_frozen_mode():
    cmd = scheduler.build_run_command("fill_b", frozen=True, executable=r"C:\app\AutoBot.exe")
    assert cmd == r'"C:\app\AutoBot.exe" --run-loop fill_b'


def test_build_create_argv_daily():
    argv = scheduler.build_create_argv("fill_b", "daily", "08:30", run_cmd="X")
    assert argv == [
        "schtasks", "/create", "/tn", "AutoBot_fill_b",
        "/tr", "X", "/sc", "daily", "/st", "08:30", "/f",
    ]


def test_build_create_argv_once_includes_date():
    argv = scheduler.build_create_argv("fill_b", "once", "09:00", sd="06/05/2026", run_cmd="X")
    assert argv[-2:] == ["/sd", "06/05/2026"]
    assert "/sc" in argv and argv[argv.index("/sc") + 1] == "once"


def test_parse_task_names_filters_prefix():
    csv = (
        '"\\AutoBot_fill_b","6/5/2026 8:00:00 AM","Ready"\n'
        '"\\SomeOtherTask","N/A","Ready"\n'
        '"\\AutoBot_login","N/A","Disabled"\n'
    )
    assert scheduler.parse_task_names(csv) == ["AutoBot_fill_b", "AutoBot_login"]


def test_parse_cli_args():
    assert parse_cli_args(["--run-loop", "fill_b"]) == ("fill_b", "config/bot_config.yaml")
    assert parse_cli_args(["--run-loop", "x", "--config", "c.yaml"]) == ("x", "c.yaml")
    assert parse_cli_args([]) == (None, "config/bot_config.yaml")
