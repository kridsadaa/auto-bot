"""ทดสอบ PatternStore (Full Copilot ขั้น 1) — จดแพทเทิร์นลง local file,
เสนอเมื่อค่าซ้ำถึงเกณฑ์, จำการปัดตก, ข้อมูลคงอยู่ข้าม instance"""
from engine.pattern_observer import PatternStore, suggestion_to_loop


def _store(tmp_path):
    return PatternStore(path=str(tmp_path / "patterns.json"))


def test_suggests_when_repeated_enough(tmp_path):
    st = _store(tmp_path)
    for _ in range(3):
        st.record("VA01", "wnd[0]/usr/ctxtVBAK-AUART", "OR")
    sugs = st.suggestions(min_repeats=3)
    assert len(sugs) == 1
    assert sugs[0]["screen"] == "VA01"
    assert sugs[0]["fields"] == [
        {"field_id": "wnd[0]/usr/ctxtVBAK-AUART", "value": "OR", "count": 3}]


def test_below_threshold_not_suggested(tmp_path):
    st = _store(tmp_path)
    st.record("VA01", "wnd[0]/usr/ctxtVBAK-AUART", "OR")
    st.record("VA01", "wnd[0]/usr/ctxtVBAK-AUART", "OR")
    assert st.suggestions(min_repeats=3) == []


def test_same_field_different_values_counted_separately(tmp_path):
    st = _store(tmp_path)
    for _ in range(3):
        st.record("VA01", "wnd[0]/usr/ctxtVBAK-AUART", "OR")
    st.record("VA01", "wnd[0]/usr/ctxtVBAK-AUART", "ZOR")
    sugs = st.suggestions(min_repeats=3)
    assert len(sugs[0]["fields"]) == 1
    assert sugs[0]["fields"][0]["value"] == "OR"


def test_groups_by_screen(tmp_path):
    st = _store(tmp_path)
    for _ in range(3):
        st.record("VA01", "f1", "X")
        st.record("MM03", "f2", "Y")
    sugs = st.suggestions(min_repeats=3)
    assert [s["screen"] for s in sugs] == ["MM03", "VA01"]


def test_events_persist_across_instances(tmp_path):
    path = str(tmp_path / "patterns.json")
    st = PatternStore(path=path)
    st.record("VA01", "f1", "X")
    st.record("VA01", "f1", "X")
    # เปิดรอบใหม่ — event เก่าต้องยังนับต่อ (สะสมข้าม session)
    st2 = PatternStore(path=path)
    st2.record("VA01", "f1", "X")
    assert len(st2.suggestions(min_repeats=3)) == 1


def test_dismiss_persists(tmp_path):
    path = str(tmp_path / "patterns.json")
    st = PatternStore(path=path)
    for _ in range(3):
        st.record("VA01", "f1", "X")
    sug = st.suggestions(min_repeats=3)[0]
    st.dismiss(sug)
    assert st.suggestions(min_repeats=3) == []
    # ปัดตกแล้วต้องไม่กลับมาถามอีกแม้เปิดใหม่
    st2 = PatternStore(path=path)
    assert st2.suggestions(min_repeats=3) == []


def test_record_ignores_empty(tmp_path):
    st = _store(tmp_path)
    st.record("VA01", "", "X")
    st.record("VA01", "f1", "")
    assert st._events == []


def test_clear(tmp_path):
    st = _store(tmp_path)
    for _ in range(3):
        st.record("VA01", "f1", "X")
    st.clear()
    assert st.suggestions(min_repeats=1) == []


def test_suggestion_to_loop(tmp_path):
    sug = {"screen": "VA01", "fields": [
        {"field_id": "wnd[0]/usr/ctxtVBAK-AUART", "value": "OR", "count": 3}]}
    name, cfg = suggestion_to_loop(sug)
    assert name == "observed_VA01"
    assert cfg["steps"] == [
        {"action": "sap_set_field",
         "field_id": "wnd[0]/usr/ctxtVBAK-AUART", "text": "OR"}]


def test_load_survives_corrupt_file(tmp_path):
    path = tmp_path / "patterns.json"
    path.write_text("{not valid json", encoding="utf-8")
    st = PatternStore(path=str(path))  # ต้องไม่ raise — เริ่มว่าง
    assert st.suggestions(min_repeats=1) == []
