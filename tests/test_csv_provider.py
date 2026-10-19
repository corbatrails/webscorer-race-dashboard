import pytest

from providers.csv_provider import CsvFormatError, _parse_rows


def _text(*lines):
    return "\n".join(lines) + "\n"


def _racers(*lines):
    return _parse_rows(_text(*lines))[1]


def _error(*lines):
    with pytest.raises(CsvFormatError) as exc:
        _parse_rows(_text(*lines))
    return str(exc.value)


def test_minimal_sheet_yields_racers():
    racers = _racers("bib,name,time", "101,Alice,1:02:03", "102,Bob,45:10")
    assert [(r["bib"], r["name"]) for r in racers] == [("101", "Alice"), ("102", "Bob")]
    alice = racers[0]
    assert alice["status"] == "FINISHED"
    assert alice["in_overall"] is True
    assert alice["source_place"] == ""
    assert alice["category_groups"] == []
    assert alice["team"] == alice["distance"] == alice["category"] == alice["gender"] == ""
    assert alice["age"] is None and alice["start_seconds"] is None and alice["finish_tod_seconds"] is None


def test_header_matching_ignores_case_spaces_and_underscore():
    racers = _racers(" BIB , Name ,TIME,Start_Time", "1,A,10:00,8:00:00")
    assert racers[0]["start_seconds"] == 8 * 3600


def test_start_time_with_space_in_header():
    assert _racers("bib,name,time,start time", "1,A,10:00,8:00")[0]["start_seconds"] == 8 * 3600


def test_bom_quoted_commas_and_blank_rows():
    text = "\ufeffbib,name,time\r\n\r\n1,\"Smith, Ann\",10:00\r\n,,\r\n2,Bob,11:00\r\n"
    racers = _parse_rows(text)[1]
    assert [r["name"] for r in racers] == ["Smith, Ann", "Bob"]


def test_extra_columns_are_ignored():
    racers = _racers("bib,name,time,email", "1,A,10:00,a@example.com")
    assert "email" not in racers[0] and racers[0]["name"] == "A"


def test_optional_text_columns_are_mapped():
    racers = _racers(
        "bib,name,time,team,distance,category,gender",
        "1,A,10:00,Corba,40 mile,Women 40-49,F",
    )
    r = racers[0]
    assert (r["team"], r["distance"], r["category"], r["gender"]) == ("Corba", "40 mile", "Women 40-49", "F")


@pytest.mark.parametrize("value,seconds", [
    ("1:02:03", 3723.0),
    ("1:02:03.5", 3723.5),
    ("45:10", 2710.0),
    ("45:10.25", 2710.25),
    ("75:30", 4530.0),
    ("26:00:01", 93601.0),
    ("0:00", 0.0),
])
def test_time_formats_set_elapsed_seconds(value, seconds):
    r = _racers("bib,name,time", f"1,A,{value}")[0]
    assert r["status"] == "FINISHED"
    assert r["elapsed_seconds"] == seconds
    assert r["time_display"] == value


@pytest.mark.parametrize("value", ["abc", "1:75", "1:60:00", "1:2:03", "12", "-5:00", "1:02:03:04", "1.5"])
def test_invalid_time_is_rejected(value):
    assert "row 2, column 'time'" in _error("bib,name,time", f"1,A,{value}")


@pytest.mark.parametrize("value,status", [("DNS", "DNS"), ("dnf", "DNF"), (" Dsq ", "DSQ")])
def test_non_finish_statuses_any_case(value, status):
    r = _racers("bib,name,time", f"1,A,{value}")[0]
    assert r["status"] == status
    assert r["elapsed_seconds"] is None
    assert r["time_display"] == value.strip()


@pytest.mark.parametrize("value", ["", "-"])
def test_blank_or_dash_time_is_in_progress(value):
    r = _racers("bib,name,time", f"1,A,{value}")[0]
    assert r["status"] == "IN_PROGRESS"
    assert r["elapsed_seconds"] is None
    assert r["time_display"] == "-"


def test_age_is_parsed():
    racers = _racers("bib,name,time,age", "1,A,10:00,42", "2,B,11:00,")
    assert [r["age"] for r in racers] == [42, None]


@pytest.mark.parametrize("value", ["x", "-1", "121", "4.5"])
def test_invalid_age_is_rejected(value):
    assert "row 2, column 'age'" in _error("bib,name,time,age", f"1,A,10:00,{value}")


@pytest.mark.parametrize("value,seconds", [
    ("8:00", 28800.0),
    ("08:30:15", 30615.0),
    ("14:08:00.5", 50880.5),
])
def test_start_time_is_parsed(value, seconds):
    assert _racers("bib,name,time,start time", f"1,A,10:00,{value}")[0]["start_seconds"] == seconds


@pytest.mark.parametrize("value", ["24:00", "8", "8:60", "8:00 AM", "x"])
def test_invalid_start_time_is_rejected(value):
    assert "row 2, column 'start time'" in _error("bib,name,time,start time", f"1,A,10:00,{value}")


def test_finish_tod_is_start_plus_elapsed_for_finishers_only():
    racers = _racers(
        "bib,name,time,start time",
        "1,A,1:00:00.5,8:00:00",
        "2,B,DNF,8:00:00",
        "3,C,10:00,",
    )
    assert [r["finish_tod_seconds"] for r in racers] == [32400.5, None, None]


def test_blank_name_is_rejected():
    assert "row 2, column 'name'" in _error("bib,name,time", "1,  ,10:00")


def test_duplicate_bib_within_distance_is_rejected():
    msg = _error("bib,name,time,distance", "1,A,10:00,40", "1,B,11:00,40")
    assert "row 3, column 'bib'" in msg and "row 2" in msg


def test_same_bib_in_different_distances_and_blank_bibs_are_allowed():
    racers = _racers("bib,name,time,distance", "1,A,10:00,40", "1,B,11:00,20", ",C,12:00,40", ",D,13:00,40")
    assert len(racers) == 4


@pytest.mark.parametrize("header,column", [("bib,name", "time"), ("name,time", "bib"), ("bib,time", "name")])
def test_missing_required_column_is_rejected(header, column):
    msg = _error(header, "1,A")
    assert f"'{column}'" in msg and "missing" in msg


def test_duplicate_header_is_rejected():
    msg = _error("bib,name,time,Name", "1,A,10:00,B")
    assert "column 'name'" in msg and "duplicate" in msg


def test_no_racer_rows_is_rejected():
    assert "no racer rows" in _error("bib,name,time", "", ",,")


def test_empty_file_is_rejected():
    assert "header" in _error("")


def test_several_errors_are_reported_together_with_row_and_column():
    msg = _error("bib,name,time,age", "1,A,bad,10", "2,,10:00,10", "3,C,10:00,xx")
    assert "row 2, column 'time'" in msg
    assert "row 3, column 'name'" in msg
    assert "row 4, column 'age'" in msg


def test_errors_are_capped_at_ten_with_remaining_count():
    rows = [f"{i},A{i},bad" for i in range(15)]
    msg = _error("bib,name,time", *rows)
    assert msg.count("column 'time'") == 10
    assert msg.endswith("and 5 more")
