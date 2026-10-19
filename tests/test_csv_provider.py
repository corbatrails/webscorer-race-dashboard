import pytest

from providers.csv_provider import PROVIDER, CsvFormatError, _parse_rows, fetch, normalize


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


# --- metadata, groups and snapshot ------------------------------------------


def _snapshot(*lines, name="results"):
    return normalize({"name": name, "text": _text(*lines)})


def test_metadata_comment_lines_set_race_fields():
    snap = _snapshot(
        "# name: 2026 Coon Fork 40",
        "# date: Aug 13, 2026",
        "# sport: Cycling - gravel",
        "# start: 14:08",
        "",
        "bib,name,time",
        "1,A,10:00",
    )
    assert snap["race"] == {
        "name": "2026 Coon Fork 40", "date": "Aug 13, 2026",
        "sport": "Cycling - gravel", "start_seconds": 14 * 3600 + 8 * 60,
    }
    assert snap["error"] is None


def test_metadata_defaults_to_file_stem_and_blank_fields():
    snap = _snapshot("bib,name,time", "1,A,10:00", name="my-race")
    assert snap["race"] == {"name": "my-race", "date": "", "sport": "", "start_seconds": 0}


def test_start_defaults_to_earliest_racer_start():
    snap = _snapshot("bib,name,time,start time", "1,A,10:00,9:30", "2,B,11:00,8:15", "3,C,12:00,")
    assert snap["race"]["start_seconds"] == 8 * 3600 + 15 * 60


def test_metadata_start_overrides_racer_starts():
    snap = _snapshot("# start: 7:00", "bib,name,time,start time", "1,A,10:00,8:15")
    assert snap["race"]["start_seconds"] == 7 * 3600


def test_unknown_metadata_key_is_an_error():
    msg = _error("# colour: red", "bib,name,time", "1,A,10:00")
    assert "row 1" in msg and "colour" in msg


def test_malformed_comment_line_is_an_error():
    assert "row 2" in _error("# name: X", "# just a note", "bib,name,time", "1,A,10:00")


def test_invalid_metadata_start_is_an_error():
    assert "row 1" in _error("# start: soon", "bib,name,time", "1,A,10:00")


def test_row_numbers_count_comment_lines():
    assert "row 4, column 'time'" in _error("# name: X", "", "bib,name,time", "1,A,bad")


def test_metadata_errors_and_row_errors_are_reported_together():
    msg = _error("# colour: red", "bib,name,time", "1,A,bad")
    assert "row 1" in msg and "row 3, column 'time'" in msg


def test_next_day_start_gets_a_day_added():
    snap = _snapshot(
        "# start: 23:30",
        "bib,name,time,start time",
        "1,A,1:00:00,23:30",
        "2,B,1:00:00,0:15",
    )
    a, b = snap["racers"]
    assert a["start_seconds"] == 23 * 3600 + 30 * 60
    assert b["start_seconds"] == 86400 + 15 * 60
    assert b["finish_tod_seconds"] == 86400 + 15 * 60 + 3600


def test_overall_groups_per_distance_in_first_appearance_order():
    snap = _snapshot("bib,name,time,distance", "1,A,10:00,40", "2,B,11:00,20", "3,C,12:00,40")
    overall = [g for g in snap["groups"] if g["tier"] == "overall"]
    assert [g["distance"] for g in overall] == ["40", "20"]
    assert all(g["category"] == "" and g["gender"] == "" for g in overall)


def test_blank_distance_is_a_single_overall_group():
    snap = _snapshot("bib,name,time", "1,A,10:00", "2,B,11:00")
    assert snap["groups"] == [{"tier": "overall", "distance": "", "category": "", "gender": ""}]


def test_category_groups_per_distance_and_category():
    snap = _snapshot(
        "bib,name,time,distance,category",
        "1,A,10:00,40,Men",
        "2,B,11:00,40,Women",
        "3,C,12:00,20,Men",
        "4,D,13:00,40,Men",
        "5,E,14:00,40,",
    )
    cats = [(g["distance"], g["category"], g["gender"]) for g in snap["groups"] if g["tier"] == "category"]
    assert cats == [("40", "Men", ""), ("40", "Women", ""), ("20", "Men", "")]


def test_racers_get_category_membership_only_when_category_set():
    snap = _snapshot("bib,name,time,distance,category", "1,A,10:00,40,Men", "2,B,11:00,40,")
    a, b = snap["racers"]
    assert a["category_groups"] == [{"distance": "40", "category": "Men", "gender": "", "source_place": ""}]
    assert b["category_groups"] == []
    assert a["in_overall"] is True and a["source_place"] == ""


def test_normalize_raises_csv_format_error():
    with pytest.raises(CsvFormatError):
        _snapshot("bib,name", "1,A")


def test_fetch_reads_data_file_and_uses_stem_as_name(tmp_path):
    path = tmp_path / "gravel-40.csv"
    path.write_text("\ufeffbib,name,time\n1,Zoë,10:00\n", encoding="utf-8")
    raw = fetch({"data_file": str(path)}, {})
    assert raw["name"] == "gravel-40"
    assert normalize(raw)["racers"][0]["name"] == "Zoë"


def test_fetch_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        fetch({"data_file": str(tmp_path / "nope.csv")}, {})


def test_provider_declaration():
    assert PROVIDER.name == "csv"
    assert PROVIDER.required_secrets == {}
    assert PROVIDER.requires_data_file is True
    assert PROVIDER.list_races is None
    assert PROVIDER.fetch is fetch and PROVIDER.normalize is normalize


# --- sample file through the real pipeline ----------------------------------

import os

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "sample-results.csv")


def _sample_snapshot():
    return PROVIDER.normalize(PROVIDER.fetch({"data_file": SAMPLE}, {}))


def test_sample_file_metadata_and_counts():
    snapshot = _sample_snapshot()
    assert snapshot["race"]["name"] == "Sample Gravel Grinder"
    assert snapshot["race"]["date"] == "Saturday, June 6, 2026"
    assert snapshot["race"]["start_seconds"] == 8 * 3600
    statuses = [r["status"] for r in snapshot["racers"]]
    assert len(statuses) == 21
    assert {"FINISHED", "DNF", "DNS", "DSQ", "IN_PROGRESS"} <= set(statuses)


def test_sample_file_renders_overall_and_category_pages():
    from data_processing import build_demographics_data, build_pages, process_race_data

    snapshot = _sample_snapshot()
    data = process_race_data(snapshot)
    pages = build_pages(data, build_demographics_data(snapshot))
    by_title = {p["title"]: p for p in pages if p["type"] == "category"}
    assert pages[0]["type"] == "summary"
    assert pages[0]["data"]["total_racers"] == 21
    assert by_title["Overall - 40 mile"]["tier"] == "overall"
    assert by_title["Overall - 20 mile"]["tier"] == "overall"
    assert by_title["Men 40-49"]["tier"] == "category"
    leader = by_title["Overall - 40 mile"]["racers"][0]
    assert (leader["Place"], leader["Name"]) == ("1", "Luis Ortega")
    names = [r["Name"] for r in by_title["Men 40-49"]["racers"]]
    assert "Okafor, Daniel" in names


def test_sample_file_feeds_the_finish_chart():
    from data_processing import build_finish_chart_data

    chart = build_finish_chart_data(_sample_snapshot(), 15)
    assert [d["label"] for d in chart["datasets"]] == ["40 mile", "20 mile"]
    assert sum(sum(d["data"]) for d in chart["datasets"]) == 14
