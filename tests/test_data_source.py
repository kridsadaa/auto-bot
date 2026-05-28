import pytest
from datetime import date
from engine.data_source import DataSource, DataSourceError


def test_resolve_static_variable():
    ds = DataSource({"USERNAME": "somrak"})
    assert ds.resolve("{USERNAME}") == "somrak"


def test_resolve_today():
    ds = DataSource({})
    result = ds.resolve("{TODAY}")
    assert result == date.today().strftime("%d.%m.%Y")


def test_resolve_today_iso():
    ds = DataSource({})
    result = ds.resolve("{TODAY_ISO}")
    assert result == date.today().isoformat()


def test_resolve_unknown_variable_left_as_is():
    ds = DataSource({})
    result = ds.resolve("{UNKNOWN_VAR}")
    assert result == "{UNKNOWN_VAR}"


def test_resolve_mixed_text():
    ds = DataSource({"CODE": "1000"})
    result = ds.resolve("Company: {CODE}, Date: {TODAY_ISO}")
    assert "1000" in result
    assert str(date.today().year) in result


def test_csv_iteration(tmp_csv):
    ds = DataSource({}, csv_path=tmp_csv)
    assert ds.has_next_row()

    ds.next_row()
    assert ds.resolve("{csv.MATERIAL_CODE}") == "MAT-001"
    assert ds.resolve("{csv.QTY}") == "10"

    ds.next_row()
    assert ds.resolve("{csv.MATERIAL_CODE}") == "MAT-002"

    ds.next_row()
    assert not ds.has_next_row()


def test_csv_reset(tmp_csv):
    ds = DataSource({}, csv_path=tmp_csv)
    ds.next_row()
    ds.next_row()
    ds.reset_csv()
    assert ds.has_next_row()
    ds.next_row()
    assert ds.resolve("{csv.MATERIAL_CODE}") == "MAT-001"


def test_csv_missing_column(tmp_csv):
    ds = DataSource({}, csv_path=tmp_csv)
    ds.next_row()
    result = ds.resolve("{csv.NONEXISTENT}")
    assert result == ""


def test_csv_no_current_row():
    ds = DataSource({})
    result = ds.resolve("{csv.COL}")
    assert result == ""


def test_csv_file_not_found():
    with pytest.raises(DataSourceError, match="not found"):
        DataSource({}, csv_path="nonexistent/path/file.csv")


def test_runtime_variable():
    ds = DataSource({"PASSWORD": ""})
    ds.set_runtime("PASSWORD", "secret123")
    assert ds.resolve("{PASSWORD}") == "secret123"
