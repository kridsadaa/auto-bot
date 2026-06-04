from gui.recorder import events_to_steps


def test_chars_merge_into_single_type():
    steps = events_to_steps([("char", "A"), ("char", "B"), ("char", "C")])
    assert steps == [{"action": "type", "text": "ABC", "method": "type"}]


def test_special_key_flushes_buffer():
    steps = events_to_steps([("char", "h"), ("char", "i"), ("key", "tab")])
    assert steps == [
        {"action": "type", "text": "hi", "method": "type"},
        {"action": "key", "key": "tab"},
    ]


def test_click_flushes_buffer_and_records_coords():
    steps = events_to_steps([("char", "x"), ("click", 100, 200), ("char", "y")])
    assert steps == [
        {"action": "type", "text": "x", "method": "type"},
        {"action": "click", "x": 100, "y": 200},
        {"action": "type", "text": "y", "method": "type"},
    ]


def test_mixed_sequence():
    # พิมพ์ AB, Tab, พิมพ์ 10, Enter, คลิก
    events = [
        ("char", "A"), ("char", "B"),
        ("key", "tab"),
        ("char", "1"), ("char", "0"),
        ("key", "enter"),
        ("click", 5, 6),
    ]
    assert events_to_steps(events) == [
        {"action": "type", "text": "AB", "method": "type"},
        {"action": "key", "key": "tab"},
        {"action": "type", "text": "10", "method": "type"},
        {"action": "key", "key": "enter"},
        {"action": "click", "x": 5, "y": 6},
    ]


def test_empty_events():
    assert events_to_steps([]) == []


def test_click_image_event_becomes_click_image_step():
    steps = events_to_steps([("click_image", "elements/rec_1.png")])
    assert steps == [{"action": "click_image", "target": "elements/rec_1.png"}]


def test_click_image_mixed_with_typing():
    events = [("char", "h"), ("char", "i"), ("click_image", "elements/a.png"), ("key", "tab")]
    assert events_to_steps(events) == [
        {"action": "type", "text": "hi", "method": "type"},
        {"action": "click_image", "target": "elements/a.png"},
        {"action": "key", "key": "tab"},
    ]
