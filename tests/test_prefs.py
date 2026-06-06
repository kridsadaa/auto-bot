from engine import prefs


def test_set_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "PREFS_PATH", str(tmp_path / "p.json"))
    prefs.set("type_method", "type")
    prefs.set("type_clear_first", True)
    assert prefs.get("type_method") == "type"
    assert prefs.get("type_clear_first") is True


def test_get_missing_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "PREFS_PATH", str(tmp_path / "nope.json"))
    assert prefs.get("type_method", "paste") == "paste"
    assert prefs.get("unknown") is None


def test_set_persists_across_loads(tmp_path, monkeypatch):
    path = str(tmp_path / "p.json")
    monkeypatch.setattr(prefs, "PREFS_PATH", path)
    prefs.set("a", 1)
    prefs.set("b", 2)          # ต้องไม่ทับ a
    assert prefs.get("a") == 1
    assert prefs.get("b") == 2
