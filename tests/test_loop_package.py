import os
import zipfile

import yaml

from engine.loop_package import _walk_targets, build_package, import_package


def test_walk_targets_collects_nested():
    steps = [
        {"action": "click_image", "target": "a.png"},
        {"action": "if_image", "target": "b.png",
         "then": [{"action": "click_image", "target": "c.png"}], "else": []},
        {"action": "switch_image",
         "cases": [{"target": "d.png", "steps": [{"action": "click_image", "target": "e.png"}]}],
         "default": [{"action": "click_image", "target": "f.png"}]},
    ]
    found = []
    _walk_targets(steps, lambda c, k: found.append(c[k]))
    assert sorted(found) == ["a.png", "b.png", "c.png", "d.png", "e.png", "f.png"]


def _png(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"PNG")


def test_build_package_blanks_vars_and_bundles_images(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/save.png")
    _png("triggers/t.png")
    config = {
        "variables": {"USERNAME": "bob", "PASSWORD": "secret"},
        "states": [{"name": "S", "trigger": {"type": "image", "file": "triggers/t.png"}, "loop": "L"}],
        "loops": {"L": {"steps": [
            {"action": "click_image", "target": "elements/save.png"},
            {"action": "type", "text": "{USERNAME}"},
            {"action": "type", "text": "{csv.X}"},  # csv.* ไม่นับเป็นตัวแปร
        ]}},
    }
    summary = build_package(config, "L", "L.botpack", include_data=False)
    assert os.path.exists("L.botpack")
    with zipfile.ZipFile("L.botpack") as zf:
        names = zf.namelist()
        man = yaml.safe_load(zf.read("manifest.yaml"))
    assert "assets/save.png" in names and "assets/t.png" in names
    # ค่าตัวแปรว่างเสมอ (ไม่ส่ง PASSWORD), เอาเฉพาะ USERNAME
    assert man["variables"] == {"USERNAME": ""}
    assert man["loop"]["steps"][0]["target"] == "assets/save.png"
    assert man["states"][0]["trigger"]["file"] == "assets/t.png"
    assert summary["missing"] == []


def test_build_package_blanks_loop_scoped_variable_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/a.png")
    config = {"variables": {}, "states": [], "loops": {"L": {
        "variables": {"COMPANY_CODE": "2000", "TOKEN": "secret"},  # ค่า sensitive เฉพาะ loop
        "steps": [{"action": "click_image", "target": "elements/a.png"}],
    }}}
    build_package(config, "L", "L.botpack")
    with zipfile.ZipFile("L.botpack") as zf:
        man = yaml.safe_load(zf.read("manifest.yaml"))
    # ค่าถูกล้างเป็นว่าง แต่ "ชื่อ" ยังอยู่ (ทั้งใน loop และ summary)
    assert man["loop"]["variables"] == {"COMPANY_CODE": "", "TOKEN": ""}
    assert man["variables"]["COMPANY_CODE"] == "" and man["variables"]["TOKEN"] == ""


def test_build_package_reports_missing_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"variables": {}, "states": [], "loops": {"L": {"steps": [
        {"action": "click_image", "target": "elements/nope.png"},
    ]}}}
    summary = build_package(config, "L", "L.botpack")
    assert summary["missing"] and "nope.png" in summary["missing"][0]


def test_export_import_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/save.png")
    config = {"variables": {}, "states": [], "loops": {"income": {"steps": [
        {"action": "click_image", "target": "elements/save.png"},
        {"action": "type", "text": "{USERNAME}"},
    ]}}}
    build_package(config, "income", "p.botpack")

    merged, summary = import_package({"variables": {}, "states": [], "loops": {}}, "p.botpack")
    assert summary["loop_name"] == "income"
    assert "income" in merged["loops"]
    tgt = merged["loops"]["income"]["steps"][0]["target"]
    assert os.path.exists(tgt)  # รูปที่แตกออกมามีจริง
    assert merged["variables"].get("USERNAME") == ""  # เพิ่มตัวแปรค่าว่าง


def test_import_name_collision_renames_and_preserves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/a.png")
    config = {"variables": {"USERNAME": "keep"}, "states": [],
              "loops": {"L": {"steps": [{"action": "click_image", "target": "elements/a.png"}]}}}
    build_package(config, "L", "p.botpack")

    existing = {"variables": {"USERNAME": "keep"}, "states": [], "loops": {"L": {"steps": []}}}
    merged, summary = import_package(existing, "p.botpack")
    assert summary["loop_name"] == "L_imported"        # เปลี่ยนชื่อ ไม่ทับ
    assert merged["loops"]["L"]["steps"] == []          # ของเดิมไม่โดนแตะ
    assert merged["variables"]["USERNAME"] == "keep"    # ตัวแปรเดิมไม่ถูกทับ


def test_export_import_with_data_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/a.png")
    os.makedirs("data", exist_ok=True)
    with open("data/src.csv", "w", encoding="utf-8") as f:
        f.write("A\n1\n")
    config = {"variables": {}, "states": [], "loops": {"L": {
        "data_source": "data/src.csv",
        "steps": [{"action": "click_image", "target": "elements/a.png"}],
    }}}
    build_package(config, "L", "p.botpack", include_data=True)

    merged, _ = import_package({"variables": {}, "states": [], "loops": {}}, "p.botpack")
    ds = merged["loops"]["L"]["data_source"]
    assert os.path.exists(ds)


def test_export_without_data_drops_data_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/a.png")
    config = {"variables": {}, "states": [], "loops": {"L": {
        "data_source": "data/src.csv",
        "steps": [{"action": "click_image", "target": "elements/a.png"}],
    }}}
    build_package(config, "L", "p.botpack", include_data=False)
    with zipfile.ZipFile("p.botpack") as zf:
        man = yaml.safe_load(zf.read("manifest.yaml"))
    assert "data_source" not in man["loop"]


# ─── call_loop bundling (subroutine loops) ───────────────────────────────────

def test_build_package_bundles_called_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/main.png")
    _png("elements/login.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [
            {"action": "click_image", "target": "elements/main.png"},
            {"action": "call_loop", "loop": "login"},
        ]},
        "login": {"steps": [{"action": "click_image", "target": "elements/login.png"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert summary["called_loops"] == ["login"]
    with zipfile.ZipFile("p.botpack") as zf:
        names = zf.namelist()
        man = yaml.safe_load(zf.read("manifest.yaml"))
    assert "assets/main.png" in names and "assets/login.png" in names
    assert "login" in man["called_loops"]
    assert man["called_loops"]["login"]["steps"][0]["target"] == "assets/login.png"


def test_build_package_bundles_called_loops_recursively(tmp_path, monkeypatch):
    # main → call_loop(a) → call_loop(b) — ต้องตามเก็บ b ด้วยแม้ main ไม่ได้เรียกตรง
    monkeypatch.chdir(tmp_path)
    _png("elements/b.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "a"}]},
        "a": {"steps": [{"action": "call_loop", "loop": "b"}]},
        "b": {"steps": [{"action": "click_image", "target": "elements/b.png"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert sorted(summary["called_loops"]) == ["a", "b"]


def test_build_package_finds_call_loop_in_nested_branch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/login.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{
            "action": "if_image", "target": "elements/login.png",
            "then": [{"action": "call_loop", "loop": "login"}],
            "else": [],
        }]},
        "login": {"steps": [{"action": "key", "key": "enter"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert summary["called_loops"] == ["login"]


def test_build_package_reports_missing_call_loop_ref(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "nope"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert summary["called_loops"] == []
    assert summary["missing_loop_refs"] == ["nope"]


def test_build_package_ignores_direct_self_recursion(tmp_path, monkeypatch):
    # main เรียกตัวเอง — ต้อง export ได้โดยไม่ค้าง (visited กันซ้ำ) และไม่นับตัวเองเป็น called_loops
    monkeypatch.chdir(tmp_path)
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "main"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert summary["called_loops"] == []


def test_build_package_scrubs_called_loop_variables_and_data_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "login"}]},
        "login": {
            "data_source": "data/secret.csv",
            "variables": {"TOKEN": "secret"},
            "steps": [{"action": "type", "text": "{TOKEN}"}],
        },
    }}
    build_package(config, "main", "p.botpack")
    with zipfile.ZipFile("p.botpack") as zf:
        man = yaml.safe_load(zf.read("manifest.yaml"))
    assert man["called_loops"]["login"]["variables"] == {"TOKEN": ""}
    assert "data_source" not in man["called_loops"]["login"]
    assert man["variables"] == {"TOKEN": ""}  # ตัวแปรของ loop ลูกก็ต้องถูกรวบรวมมาด้วย


def test_import_bundles_called_loop_and_rewrites_call_loop_ref(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _png("elements/login.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "login"}]},
        "login": {"steps": [{"action": "click_image", "target": "elements/login.png"}]},
    }}
    build_package(config, "main", "p.botpack")

    merged, summary = import_package({"variables": {}, "states": [], "loops": {}}, "p.botpack")
    assert summary["called_loops"] == ["login"]
    assert "login" in merged["loops"]
    assert os.path.exists(merged["loops"]["login"]["steps"][0]["target"])
    # call_loop step ของ main ต้องยังชี้ไปที่ 'login' ถูกต้อง
    assert merged["loops"]["main"]["steps"][0]["loop"] == "login"


def test_build_package_bundles_call_loop_in_setup_and_recovery_steps(tmp_path, monkeypatch):
    # pattern แนะนำ: setup_steps เรียก login, recovery_steps เรียก close_program
    # ทั้งคู่ต้องถูกแนบไปใน .botpack แม้ไม่ถูกเรียกจาก steps ปกติ
    monkeypatch.chdir(tmp_path)
    _png("elements/login.png")
    _png("elements/close.png")
    _png("elements/recover_extra.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {
            "setup_steps": [{"action": "call_loop", "loop": "login"}],
            "recovery_steps": [
                {"action": "call_loop", "loop": "close_program"},
                {"action": "click_image", "target": "elements/recover_extra.png"},
            ],
            "steps": [{"action": "key", "key": "enter"}],
        },
        "login": {"steps": [{"action": "click_image", "target": "elements/login.png"}]},
        "close_program": {"steps": [{"action": "click_image", "target": "elements/close.png"}]},
    }}
    summary = build_package(config, "main", "p.botpack")
    assert sorted(summary["called_loops"]) == ["close_program", "login"]
    with zipfile.ZipFile("p.botpack") as zf:
        names = zf.namelist()
        man = yaml.safe_load(zf.read("manifest.yaml"))
    # รูปของ loop ลูก + รูปใน recovery_steps ของ loop หลัก ต้องถูกแนบและ rewrite path
    assert "assets/login.png" in names and "assets/close.png" in names
    assert "assets/recover_extra.png" in names
    assert man["loop"]["recovery_steps"][1]["target"] == "assets/recover_extra.png"
    assert summary["missing"] == []


def test_import_rewrites_call_loop_refs_in_setup_and_recovery(tmp_path, monkeypatch):
    # ปลายทางมี 'login' อยู่แล้ว → loop ลูกถูก rename และ call_loop ใน
    # setup_steps/recovery_steps ของ loop หลักต้องชี้ชื่อใหม่ตาม
    monkeypatch.chdir(tmp_path)
    _png("elements/login.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {
            "setup_steps": [{"action": "call_loop", "loop": "login"}],
            "recovery_steps": [{"action": "call_loop", "loop": "login"}],
            "steps": [{"action": "key", "key": "enter"}],
        },
        "login": {"steps": [{"action": "click_image", "target": "elements/login.png"}]},
    }}
    build_package(config, "main", "p.botpack")

    existing = {"variables": {}, "states": [], "loops": {"login": {"steps": []}}}
    merged, summary = import_package(existing, "p.botpack")
    new_login = summary["called_loops"][0]
    assert new_login != "login"
    assert merged["loops"]["main"]["setup_steps"][0]["loop"] == new_login
    assert merged["loops"]["main"]["recovery_steps"][0]["loop"] == new_login


def test_build_package_collects_variables_from_setup_steps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {"variables": {"SETUP_USER": "secret"}, "states": [], "loops": {
        "main": {
            "setup_steps": [{"action": "type", "text": "{SETUP_USER}"}],
            "steps": [{"action": "key", "key": "enter"}],
        },
    }}
    build_package(config, "main", "p.botpack")
    with zipfile.ZipFile("p.botpack") as zf:
        man = yaml.safe_load(zf.read("manifest.yaml"))
    assert man["variables"] == {"SETUP_USER": ""}  # ชื่อถูกเก็บ ค่าถูกล้าง


def test_import_renames_called_loop_on_name_collision(tmp_path, monkeypatch):
    # ปลายทางมี loop ชื่อ 'login' อยู่แล้ว → loop ลูกที่ import มาต้องถูกเปลี่ยนชื่อ
    # และ call_loop ใน main (ที่ import มา) ต้องอ้างชื่อใหม่ตาม ไม่ใช่ 'login' เดิม
    monkeypatch.chdir(tmp_path)
    _png("elements/login.png")
    config = {"variables": {}, "states": [], "loops": {
        "main": {"steps": [{"action": "call_loop", "loop": "login"}]},
        "login": {"steps": [{"action": "click_image", "target": "elements/login.png"}]},
    }}
    build_package(config, "main", "p.botpack")

    existing = {"variables": {}, "states": [], "loops": {"login": {"steps": []}}}
    merged, summary = import_package(existing, "p.botpack")
    assert summary["loop_name"] == "main"
    new_login_name = summary["called_loops"][0]
    assert new_login_name != "login"  # ต้องเปลี่ยนชื่อกันชน
    assert merged["loops"]["login"]["steps"] == []  # ของเดิมไม่โดนแตะ
    assert merged["loops"]["main"]["steps"][0]["loop"] == new_login_name  # อ้างชื่อใหม่ถูกต้อง
