import os

from engine import runtime


def test_ensure_config_copies_from_example(tmp_path):
    base = tmp_path / "app"
    base.mkdir()
    example = tmp_path / "bot_config.example.yaml"
    example.write_text("variables: {FOO: bar}\nstates: []\nloops: {}\n", encoding="utf-8")

    target = runtime.ensure_config(str(base), str(example))

    assert os.path.exists(target)
    assert target == os.path.join(str(base), "config", "bot_config.yaml")
    assert "FOO" in open(target, encoding="utf-8").read()


def test_ensure_config_writes_minimal_when_no_example(tmp_path):
    base = tmp_path / "app"
    base.mkdir()

    target = runtime.ensure_config(str(base), None)

    assert os.path.exists(target)
    content = open(target, encoding="utf-8").read()
    assert "loops" in content and "states" in content and "variables" in content


def test_ensure_config_does_not_overwrite_existing(tmp_path):
    base = tmp_path / "app"
    (base / "config").mkdir(parents=True)
    existing = base / "config" / "bot_config.yaml"
    existing.write_text("variables: {KEEP: me}\nstates: []\nloops: {}\n", encoding="utf-8")
    example = tmp_path / "bot_config.example.yaml"
    example.write_text("variables: {OTHER: x}\nstates: []\nloops: {}\n", encoding="utf-8")

    target = runtime.ensure_config(str(base), str(example))

    # ของเดิมต้องไม่ถูกทับ
    assert "KEEP" in open(target, encoding="utf-8").read()


def test_app_base_dir_uses_cwd_when_not_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "is_frozen", lambda: False)
    monkeypatch.chdir(tmp_path)
    assert runtime.app_base_dir() == os.getcwd()
