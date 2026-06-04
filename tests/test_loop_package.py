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
