"""Projection tests: views read only a hand-built RaceSnapshot, never the raw payload."""
import json
from pathlib import Path

import pytest

from data_processing import (
    _category_members,
    _membership_key,
    _place_text,
    _rank_racers,
    process_race_data,
)
from normalizer import normalize_webscorer

FIXTURES = Path(__file__).parent / "fixtures"


def _racer(bib, elapsed=None, status=None, **overrides):
    racer = {
        "bib": bib,
        "name": f"Racer {bib}",
        "team": "",
        "distance": "10K",
        "category": "Open",
        "gender": "Male",
        "age": 30,
        "status": status or ("FINISHED" if elapsed is not None else "IN_PROGRESS"),
        "time_display": "t" if elapsed is not None else "-",
        "elapsed_seconds": elapsed,
        "start_seconds": None,
        "finish_tod_seconds": None,
        "source_place": "",
        "in_overall": True,
        "category_groups": [],
    }
    racer.update(overrides)
    return racer


def _snapshot(racers, groups=None, error=None):
    if groups is None:
        groups = [{"tier": "overall", "distance": "10K", "category": "", "gender": ""}]
    return {
        "error": error,
        "race": {"name": "R", "date": "D", "sport": "S", "start_seconds": 0},
        "groups": groups,
        "racers": racers,
    }


def _member(category="Open", gender="Male", distance="10K"):
    return {"distance": distance, "category": category, "gender": gender, "source_place": ""}


def test_error_snapshot_returns_error_dict():
    result = process_race_data(_snapshot([], error="boom"))
    assert result["error"] == "boom"
    assert result["categories"] == []
    assert result["distance_stats"] == []


def test_places_are_derived_from_elapsed_time_not_input_order():
    snap = _snapshot([_racer("1", 300), _racer("2", 100), _racer("3", 200)])
    rows = process_race_data(snap)["categories"][0]["racers"]
    assert [(r["Bib"], r["Place"]) for r in rows] == [("2", "1"), ("3", "2"), ("1", "3")]


def test_tied_finishers_share_a_place_and_next_place_is_skipped():
    snap = _snapshot([_racer("1", 100), _racer("2", 100), _racer("3", 200), _racer("4", 50)])
    rows = process_race_data(snap)["categories"][0]["racers"]
    assert [(r["Bib"], r["Place"]) for r in rows] == [("4", "1"), ("1", "2"), ("2", "2"), ("3", "4")]


def test_unplaced_racers_follow_finishers_in_input_order_with_dash():
    snap = _snapshot([
        _racer("1", status="DNF"),
        _racer("2"),
        _racer("3", 100),
        _racer("4", status="DNS"),
        _racer("5", status="FINISHED", elapsed=None),
    ])
    rows = process_race_data(snap)["categories"][0]["racers"]
    assert [r["Bib"] for r in rows] == ["3", "1", "2", "4", "5"]
    assert [r["Place"] for r in rows] == ["1", "-", "-", "-", "-"]


def test_overall_page_only_contains_overall_racers_of_that_distance():
    groups = [
        {"tier": "overall", "distance": "10K", "category": "", "gender": ""},
        {"tier": "overall", "distance": "5K", "category": "", "gender": ""},
    ]
    snap = _snapshot([
        _racer("1", 100),
        _racer("2", 100, distance="5K"),
        _racer("3", 100, in_overall=False, category_groups=[_member()]),
    ], groups)
    result = process_race_data(snap)
    assert [r["Bib"] for r in result["categories"][0]["racers"]] == ["1"]
    assert [r["Bib"] for r in result["categories"][1]["racers"]] == ["2"]
    assert result["total_racers"] == 2


def test_category_page_contains_members_and_ranks_within_the_group():
    groups = [
        {"tier": "overall", "distance": "10K", "category": "", "gender": ""},
        {"tier": "category", "distance": "10K", "category": "Open", "gender": "Male"},
    ]
    snap = _snapshot([
        _racer("1", 100, category="Elite", category_groups=[]),
        _racer("2", 200, category_groups=[_member()]),
        _racer("3", 300, category_groups=[_member()]),
        _racer("4", 50, category_groups=[_member("Open", "Female")]),
    ], groups)
    result = process_race_data(snap)
    overall, category = result["categories"]
    assert category["name"] == "Open Male"
    assert [(r["Bib"], r["Place"]) for r in category["racers"]] == [("2", "1"), ("3", "2")]
    overall_by_bib = {r["Bib"]: r for r in overall["racers"]}
    assert overall_by_bib["2"]["Place"] == "3"
    assert overall_by_bib["2"]["CategoryPlace"] == "1"
    assert "CategoryPlace" not in overall_by_bib["1"]
    assert overall_by_bib["4"]["Place"] == "1"
    assert overall_by_bib["4"]["CategoryPlace"] == "1"


def test_category_place_uses_membership_matching_own_category_else_first():
    groups = [
        {"tier": "overall", "distance": "10K", "category": "", "gender": ""},
        {"tier": "category", "distance": "10K", "category": "Open", "gender": "Male"},
        {"tier": "category", "distance": "10K", "category": "E-bike", "gender": "Male"},
    ]
    both = [_member("E-bike", "Male"), _member("Open", "Male")]
    snap = _snapshot([
        _racer("1", 100, category="Open", category_groups=both),
        _racer("2", 200, category="Open", category_groups=[_member("E-bike", "Male")]),
        _racer("3", 300, category="Other", category_groups=both),
    ], groups)
    overall = process_race_data(snap)["categories"][0]["racers"]
    by_bib = {r["Bib"]: r["CategoryPlace"] for r in overall}
    # Open+Male membership: racers 1, 3 -> places 1, 2. E-bike: 1, 2, 3 -> 1, 2, 3.
    assert by_bib["1"] == "1"
    assert by_bib["2"] == "2"
    assert by_bib["3"] == "3"


def test_relay_style_gender_mismatch_still_lists_racer_on_category_page():
    groups = [
        {"tier": "overall", "distance": "Relay", "category": "", "gender": ""},
        {"tier": "category", "distance": "Relay", "category": "Relay", "gender": "Male"},
    ]
    snap = _snapshot([
        _racer("5", 100, distance="Relay", category="Relay", gender="", category_groups=[_member("Relay", "Male", "Relay")]),
    ], groups)
    overall, category = process_race_data(snap)["categories"]
    assert overall["racers"][0]["CategoryPlace"] == "1"
    assert overall["racers"][0]["Gender"] == ""
    assert [r["Bib"] for r in category["racers"]] == ["5"]


def test_rows_carry_only_frontend_fields_and_name_and_team_from_snapshot():
    snap = _snapshot([_racer("1", 100, name="DOE, Jane", team="", time_display="0:01:40")])
    (row,) = process_race_data(snap)["categories"][0]["racers"]
    assert row == {
        "Place": "1",
        "Bib": "1",
        "Name": "DOE, Jane",
        "Time": "0:01:40",
        "TeamName": "",
        "Category": "Open",
        "Gender": "Male",
    }


def test_distance_stats_and_totals_come_from_overall_racers():
    groups = [
        {"tier": "overall", "distance": "10K", "category": "", "gender": ""},
        {"tier": "overall", "distance": "", "category": "", "gender": ""},
    ]
    snap = _snapshot([
        _racer("1", 100),
        _racer("2", status="DNF"),
        _racer("3"),
        _racer("4", status="DSQ", in_overall=True),
    ], groups)
    result = process_race_data(snap)
    assert result["distance_stats"] == [
        {"name": "10K", "total": 4, "finished": 1, "resolved": 3},
        {"name": "Overall", "total": 0, "finished": 0, "resolved": 0},
    ]
    assert (result["total_racers"], result["total_finished"], result["total_dnf"], result["total_dsq"]) == (4, 1, 1, 1)


def test_group_order_and_filters_follow_snapshot_groups():
    groups = [
        {"tier": "overall", "distance": "B", "category": "", "gender": ""},
        {"tier": "overall", "distance": "A", "category": "", "gender": ""},
        {"tier": "category", "distance": "A", "category": "Open", "gender": ""},
        {"tier": "category", "distance": "B", "category": "Open", "gender": ""},
    ]
    snap = _snapshot([], groups)
    names = [(c["tier"], c["name"]) for c in process_race_data(snap)["categories"]]
    assert names == [("overall", "B"), ("category", "Open"), ("overall", "A"), ("category", "Open")]
    only_cat = process_race_data(snap, show_overall_results=False)["categories"]
    assert [c["tier"] for c in only_cat] == ["category", "category"]
    assert [c["name"] for c in only_cat] == ["Open", "Open"]


def test_views_do_not_read_raw_results():
    source = (Path(__file__).parent.parent / "data_processing.py").read_text(encoding="utf-8")
    for raw_key in ('"Results"', '"Racers"', '"Grouping"', "api_response"):
        assert raw_key not in source


@pytest.mark.parametrize("fixture", ["race_a_finished", "race_a_live", "race_b_teamname"])
def test_derived_places_reconcile_with_source_places(fixture):
    raw = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    snapshot = normalize_webscorer(raw)
    racers = snapshot["racers"]

    checked = 0
    for group in snapshot["groups"]:
        if group["tier"] != "overall":
            continue
        in_group = [r for r in racers if r["in_overall"] and r["distance"] == group["distance"]]
        for racer, place in _rank_racers(in_group):
            assert _place_text(place) == racer["source_place"]
            checked += 1

    for key, members in _category_members(racers).items():
        for racer, place in _rank_racers(members):
            membership = next(m for m in racer["category_groups"] if _membership_key(m) == key)
            assert _place_text(place) == membership["source_place"]
            checked += 1

    assert checked > 0
