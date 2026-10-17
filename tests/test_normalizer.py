import json
from pathlib import Path

import pytest

from normalizer import normalize_webscorer

FIXTURES = Path(__file__).parent / "fixtures"


def _response(*groups, start="Saturday, August 9, 2026 2:00 PM (GMT-5)"):
    return {
        "RaceInfo": {"RaceId": 1, "Name": "Test Race", "Date": "Aug 9, 2026", "Sport": "Running", "StartTime": start},
        "Results": list(groups),
    }


def _overall(distance, *racers):
    return {"Grouping": {"Distance": distance, "Overall": True}, "Racers": list(racers)}


def _category(distance, category, gender, *racers):
    grouping = {"Distance": distance, "Category": category}
    if gender is not None:
        grouping["Gender"] = gender
    return {"Grouping": grouping, "Racers": list(racers)}


def _racer(bib="1", **fields):
    base = {"Place": "1", "Bib": bib, "Name": f"Racer {bib}", "Time": "0:20:00.0", "StartTime": "14:00:00.0"}
    base.update(fields)
    return base


def test_error_response_yields_empty_snapshot():
    snap = normalize_webscorer({"Error": "PRO Results subscription required"})
    assert snap["error"] == "PRO Results subscription required"
    assert snap["racers"] == []
    assert snap["groups"] == []
    assert snap["race"]["name"] == ""


def test_race_meta():
    snap = normalize_webscorer(_response(start="Thursday, August 13, 2026 2:08 PM (GMT-5)"))
    assert snap["error"] is None
    assert snap["race"] == {
        "name": "Test Race",
        "date": "Aug 9, 2026",
        "sport": "Running",
        "start_seconds": 14 * 3600 + 8 * 60,
    }


def test_race_meta_defaults_when_missing():
    snap = normalize_webscorer({"Results": []})
    assert snap["race"] == {"name": "", "date": "", "sport": "", "start_seconds": 0}


def test_overall_racer_fields():
    snap = normalize_webscorer(_response(_overall("10K", _racer(
        bib=" 42 ", Name="Alice", TeamName="Corba", Category="Open", Gender="Female", Age="31",
        Place="3", Time="0:41:05.5",
    ))))
    (racer,) = snap["racers"]
    assert racer["bib"] == "42"
    assert racer["name"] == "Alice"
    assert racer["team"] == "Corba"
    assert racer["distance"] == "10K"
    assert racer["category"] == "Open"
    assert racer["gender"] == "Female"
    assert racer["age"] == 31
    assert racer["status"] == "FINISHED"
    assert racer["time_display"] == "0:41:05.5"
    assert racer["elapsed_seconds"] == pytest.approx(41 * 60 + 5.5)
    assert racer["start_seconds"] == 14 * 3600
    assert racer["finish_tod_seconds"] == pytest.approx(14 * 3600 + 41 * 60 + 5.5)
    assert racer["source_place"] == "3"
    assert racer["in_overall"] is True
    assert racer["category_groups"] == []


def test_missing_optional_fields_default_to_empty():
    snap = normalize_webscorer(_response(_overall("10K", {"Bib": "9"})))
    (racer,) = snap["racers"]
    assert racer["name"] == ""
    assert racer["team"] == ""
    assert racer["category"] == ""
    assert racer["gender"] == ""
    assert racer["age"] is None
    assert racer["status"] == "IN_PROGRESS"
    assert racer["time_display"] == ""
    assert racer["elapsed_seconds"] is None
    assert racer["start_seconds"] is None
    assert racer["finish_tod_seconds"] is None
    assert racer["source_place"] == ""


def test_empty_name_falls_back_to_team_name():
    snap = normalize_webscorer(_response(_overall("10K", _racer(Name="", TeamName="DOE, Jane"))))
    (racer,) = snap["racers"]
    assert racer["name"] == "DOE, Jane"
    assert racer["team"] == ""


def test_missing_name_key_falls_back_to_team_name():
    raw = _racer(TeamName="DOE, Jane")
    del raw["Name"]
    (racer,) = normalize_webscorer(_response(_overall("10K", raw)))["racers"]
    assert racer["name"] == "DOE, Jane"
    assert racer["team"] == ""


def test_name_and_team_both_present_are_kept():
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Name="A", TeamName="T"))))["racers"]
    assert (racer["name"], racer["team"]) == ("A", "T")


def test_null_name_and_team():
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Name=None, TeamName=None))))["racers"]
    assert (racer["name"], racer["team"]) == ("", "")


@pytest.mark.parametrize("time_value,status", [
    ("0:20:00.0", "FINISHED"),
    ("DNS", "DNS"),
    ("dnf", "DNF"),
    (" DSQ ", "DSQ"),
    ("-", "IN_PROGRESS"),
    ("", "IN_PROGRESS"),
    (None, "IN_PROGRESS"),
])
def test_status_classification(time_value, status):
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Time=time_value))))["racers"]
    assert racer["status"] == status
    if status != "FINISHED":
        assert racer["elapsed_seconds"] is None
        assert racer["finish_tod_seconds"] is None


@pytest.mark.parametrize("time_value,seconds", [
    ("5:16:43.87", 5 * 3600 + 16 * 60 + 43.87),
    ("51:11.6", 51 * 60 + 11.6),
    ("45.5", 45.5),
])
def test_elapsed_formats(time_value, seconds):
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Time=time_value))))["racers"]
    assert racer["elapsed_seconds"] == pytest.approx(seconds)


def test_unparseable_time_does_not_raise():
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Time="1:2x:00"))))["racers"]
    assert racer["status"] == "FINISHED"
    assert racer["elapsed_seconds"] is None
    assert racer["finish_tod_seconds"] is None


def test_missing_or_bad_start_time_has_no_finish_tod():
    snap = normalize_webscorer(_response(_overall(
        "10K",
        _racer("1", StartTime=None),
        _racer("2", StartTime=""),
        _racer("3", StartTime="not-a-time"),
    )))
    for racer in snap["racers"]:
        assert racer["start_seconds"] is None
        assert racer["finish_tod_seconds"] is None
        assert racer["elapsed_seconds"] == pytest.approx(1200)


def test_finish_past_midnight_is_not_wrapped():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer(StartTime="23:30:00.0", Time="1:00:00.0")),
        start="Saturday, August 9, 2026 11:20 PM (GMT-5)",
    ))
    (racer,) = snap["racers"]
    assert racer["start_seconds"] == 23 * 3600 + 30 * 60
    assert racer["finish_tod_seconds"] == 24 * 3600 + 30 * 60


def test_next_day_wave_start_rolls_over():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer(StartTime="00:05:00.0", Time="0:30:00.0")),
        start="Saturday, August 9, 2026 11:50 PM (GMT-5)",
    ))
    (racer,) = snap["racers"]
    assert racer["start_seconds"] == 86400 + 5 * 60
    assert racer["finish_tod_seconds"] == 86400 + 35 * 60


def test_earlier_start_within_twelve_hours_is_not_rolled_over():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer(StartTime="13:50:00.0")),
        start="Saturday, August 9, 2026 2:00 PM (GMT-5)",
    ))
    assert snap["racers"][0]["start_seconds"] == 13 * 3600 + 50 * 60


@pytest.mark.parametrize("age,expected", [(30, 30), ("30", 30), (30.7, 30), (None, None), ("x", None), (True, None)])
def test_age_parsing(age, expected):
    (racer,) = normalize_webscorer(_response(_overall("10K", _racer(Age=age))))["racers"]
    assert racer["age"] == expected


def test_overall_racers_keep_api_order_across_groups():
    snap = normalize_webscorer(_response(
        _overall("Long", _racer("1"), _racer("2")),
        _overall("Short", _racer("3")),
    ))
    assert [(r["bib"], r["distance"]) for r in snap["racers"]] == [("1", "Long"), ("2", "Long"), ("3", "Short")]


def test_overall_listings_are_not_deduplicated_against_each_other():
    snap = normalize_webscorer(_response(_overall("10K", _racer("1"), _racer("1"))))
    assert len(snap["racers"]) == 2


def test_category_listing_attaches_to_overall_racer():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer("1", Place="4", Category="Open", Gender="Male")),
        _category("10K", "Open", "Male", _racer("1", Place="2", Category="Open", Gender="Male")),
    ))
    (racer,) = snap["racers"]
    assert racer["source_place"] == "4"
    assert racer["category_groups"] == [
        {"distance": "10K", "category": "Open", "gender": "Male", "source_place": "2"},
    ]


def test_category_listing_matches_even_when_racer_gender_differs_from_group():
    snap = normalize_webscorer(_response(
        _overall("Relay", _racer("5", Category="Relay", Gender="")),
        _category("Relay", "Relay", "Male", _racer("5", Category="Relay", Gender="Male")),
    ))
    (racer,) = snap["racers"]
    assert racer["gender"] == ""
    assert [m["gender"] for m in racer["category_groups"]] == ["Male"]


def test_category_listing_does_not_cross_distances():
    snap = normalize_webscorer(_response(
        _overall("Long", _racer("10")),
        _category("Short", "Open", "X", _racer("10")),
    ))
    assert len(snap["racers"]) == 2
    long_racer, short_only = snap["racers"]
    assert long_racer["category_groups"] == []
    assert short_only["in_overall"] is False
    assert short_only["distance"] == "Short"


def test_category_listing_uses_racer_distance_when_grouping_has_none():
    snap = normalize_webscorer(_response(
        _overall("Long", _racer("10")),
        {"Grouping": {"Category": "Open"}, "Racers": [_racer("10", Distance="Long")]},
    ))
    assert len(snap["racers"]) == 1
    assert snap["racers"][0]["category_groups"][0]["distance"] == ""


def test_blank_bib_matches_on_name():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer("", Name="Pat")),
        _category("10K", "Open", None, _racer("", Name="Pat", Place="1")),
    ))
    assert len(snap["racers"]) == 1
    assert snap["racers"][0]["category_groups"][0]["gender"] == ""


def test_blank_bib_and_name_never_match():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer("", Name="")),
        _category("10K", "Open", None, _racer("", Name="")),
    ))
    assert len(snap["racers"]) == 2


def test_category_only_racer_is_created_without_overall_membership():
    snap = normalize_webscorer(_response(
        _category("Long", "Open", "X", _racer("8", Place="3", Time="1:03:00")),
    ))
    (racer,) = snap["racers"]
    assert racer["in_overall"] is False
    assert racer["source_place"] == ""
    assert racer["distance"] == "Long"
    assert racer["category_groups"] == [{"distance": "Long", "category": "Open", "gender": "X", "source_place": "3"}]
    assert racer["status"] == "FINISHED"


def test_racer_in_two_category_groups_gets_two_memberships():
    snap = normalize_webscorer(_response(
        _overall("10K", _racer("1")),
        _category("10K", "Open", "Male", _racer("1", Place="1")),
        _category("10K", "E-bike", "Male", _racer("1", Place="2")),
    ))
    assert [m["category"] for m in snap["racers"][0]["category_groups"]] == ["Open", "E-bike"]


def test_groups_in_api_order_skip_untiered_and_deduplicate():
    snap = normalize_webscorer(_response(
        _overall("Long"),
        {"Grouping": {"Distance": "Long", "Gender": "Male"}, "Racers": [_racer("1")]},
        _category("Long", "Open", "Male"),
        _overall("Long"),
        {"Grouping": {"Category": "Overall", "Overall": True}, "Racers": []},
        {"Grouping": {"Category": "Masters"}, "Racers": []},
    ))
    assert snap["groups"] == [
        {"tier": "overall", "distance": "Long", "category": "", "gender": ""},
        {"tier": "category", "distance": "Long", "category": "Open", "gender": "Male"},
        {"tier": "overall", "distance": "", "category": "Overall", "gender": ""},
        {"tier": "category", "distance": "", "category": "Masters", "gender": ""},
    ]
    assert snap["racers"] == []


def test_untiered_groups_contribute_no_racers():
    snap = normalize_webscorer(_response(
        {"Grouping": {"Distance": "Long", "Gender": "Male"}, "Racers": [_racer("1")]},
    ))
    assert snap["racers"] == []


def test_snapshot_is_json_serializable():
    snap = normalize_webscorer(_response(_overall("10K", _racer())))
    assert json.loads(json.dumps(snap)) == snap


def test_does_not_mutate_input():
    raw = _response(
        _overall("10K", _racer("1", Category="Open", Gender="Male")),
        _category("10K", "Open", "Male", _racer("1")),
    )
    before = json.dumps(raw, sort_keys=True)
    normalize_webscorer(raw)
    assert json.dumps(raw, sort_keys=True) == before


@pytest.mark.parametrize("fixture", ["race_a_finished", "race_a_live", "race_b_teamname"])
def test_fixtures_normalize_one_racer_per_overall_listing(fixture):
    raw = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    snap = normalize_webscorer(raw)

    overall_listings = sum(len(g["Racers"]) for g in raw["Results"] if g["Grouping"].get("Overall"))
    assert sum(1 for r in snap["racers"] if r["in_overall"]) == overall_listings

    category_listings = sum(len(g["Racers"]) for g in raw["Results"] if g["Grouping"].get("Category"))
    assert sum(len(r["category_groups"]) for r in snap["racers"]) == category_listings
    assert all(r["in_overall"] for r in snap["racers"])


def test_race_b_names_come_from_team_name():
    raw = json.loads((FIXTURES / "race_b_teamname.json").read_text(encoding="utf-8"))
    snap = normalize_webscorer(raw)
    assert all(r["name"] and r["team"] == "" for r in snap["racers"])
