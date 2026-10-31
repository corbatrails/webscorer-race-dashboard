import pytest

import data_processing
from app import create_app, poll_once
from tests.test_lap_overview import START, _group, _racer, _snapshot


def project(snapshot, observed=START + 2000):
    return data_processing.build_race_control_data(snapshot, observed)


def test_control_projection_keeps_rank_ties_statuses_and_lap_state():
    racers = [
        _racer("50K", "FINISHED", bib="A"),
        _racer("50K", "FINISHED", bib="B"),
        _racer("50K", crossings=[(1, 600), (2, 3000)], bib="C"),
        _racer("50K", "DNF", crossings=[(1, 600)], bib="D"),
        _racer("50K", start=START + 3000, bib="E"),
        _racer("50K", "DNS", bib="F"),
        _racer("50K", "DSQ", bib="G"),
    ]
    control = project(_snapshot([_group("50K", 4)], racers))
    rows = control["groups"][0]["racers"]
    assert [r["Place"] for r in rows] == ["1", "1", "-", "-", "-", "-", "-"]
    assert [r["Status"] for r in rows] == [
        "Finished", "Finished", "On course", "DNF", "Not started", "DNS", "DSQ",
    ]
    assert [r["Laps"] for r in rows] == [4, 4, 1, 1, 0, 0, 0]
    assert [r["GapSeconds"] for r in rows] == [0, 0, None, None, None, None, None]
    assert control["progress"]["totals"]["on_course"] == 1
    assert control["clock_seconds"] == 2000
    assert control["race_name"] == "Race"


def test_control_group_metadata_handles_blank_distances_and_category_only_members():
    member = {"distance": "", "category": "Open", "gender": "", "source_place": ""}
    racer = _racer("", "FINISHED", in_overall=False)
    racer["category_groups"] = [member]
    snapshot = _snapshot([_group(""), _group("", tier="category", category="Open")], [racer])
    control = project(snapshot)
    assert [g["distance"] for g in control["groups"]] == ["", ""]
    assert [g["title"] for g in control["groups"]] == ["Overall", "Open"]
    assert control["groups"][0]["racers"] == []
    assert len(control["groups"][1]["racers"]) == 1
    assert len({g["key"] for g in control["groups"]}) == 2


def test_latest_finishers_use_actual_finish_order_not_elapsed_rank():
    faster = _racer("5K", "FINISHED", bib="A")
    later = _racer("5K", "FINISHED", bib="B")
    faster.update(elapsed_seconds=100, finish_tod_seconds=START + 100)
    later.update(elapsed_seconds=200, finish_tod_seconds=START + 500)
    duplicate = dict(later, in_overall=False)
    control = project(_snapshot([_group("5K")], [faster, later, duplicate]))
    assert [r["Bib"] for r in control["latest_finishers"]] == ["B", "A"]
    assert control["latest_finishers"][0]["FinishSeconds"] == START + 500
    assert control["latest_finishers"][0]["Place"] == "2"
    assert control["groups"][0]["racers"][1]["GapSeconds"] == 100


def test_control_projection_returns_none_for_provider_error():
    assert project(_snapshot([], [], error="unavailable")) is None


def test_control_lap_splits_include_durations_and_ending_elapsed_without_mutating_snapshot():
    racer = _racer("50K", crossings=[(1, 600.125), (2, 1250.5), (3, 1900)])
    snapshot = _snapshot([_group("50K", 3)], [racer])
    row = project(snapshot)["groups"][0]["racers"][0]
    assert row.get("LapSplits") == [
        {"LapNumber": 1, "SplitSeconds": 600.125, "ElapsedSeconds": 600.125},
        {"LapNumber": 2, "SplitSeconds": 650.375, "ElapsedSeconds": 1250.5},
        {"LapNumber": 3, "SplitSeconds": 649.5, "ElapsedSeconds": 1900.0},
    ]
    assert "LapSplits" not in racer


def test_control_lap_splits_do_not_treat_missing_laps_as_one_split():
    racer = _racer("50K", crossings=[(2, 700), (4, 1500), (5, 1800)])
    row = project(_snapshot([_group("50K", 5)], [racer]))["groups"][0]["racers"][0]
    assert row.get("LapSplits") == [
        {"LapNumber": 2, "SplitSeconds": None, "ElapsedSeconds": 700.0},
        {"LapNumber": 4, "SplitSeconds": None, "ElapsedSeconds": 1500.0},
        {"LapNumber": 5, "SplitSeconds": 300.0, "ElapsedSeconds": 1800.0},
    ]


@pytest.mark.parametrize("status", ["IN_PROGRESS", "DNF", "FINISHED"])
def test_control_lap_splits_exclude_future_and_out_of_group_crossings(status):
    racer = _racer("50K", status, crossings=[(1, 600), (2, 1900), (3, 2500)])
    racer["category_groups"] = [
        {"distance": "50K", "category": "Open", "gender": "", "source_place": ""},
    ]
    snapshot = _snapshot([
        _group("50K", 3), _group("50K", 2, tier="category", category="Open"),
    ], [racer])
    rows = project(snapshot, START + 1000)["groups"][1]["racers"]
    assert rows[0].get("LapSplits") == [
        {"LapNumber": 1, "SplitSeconds": 600.0, "ElapsedSeconds": 600.0},
    ]
    rows = project(snapshot, START + 3000)["groups"][1]["racers"]
    assert [s["LapNumber"] for s in rows[0]["LapSplits"]] == [1, 2]


@pytest.mark.parametrize("status,start", [
    ("IN_PROGRESS", START + 3000), ("DNS", START), ("IN_PROGRESS", START),
])
def test_control_lap_splits_are_empty_without_visible_crossings(status, start):
    racer = _racer("50K", status, start=start)
    row = project(_snapshot([_group("50K", 2)], [racer]))["groups"][0]["racers"][0]
    assert row.get("LapSplits") == []


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_race_control_route_renders_configured_theme(scheme):
    app = create_app({"color_scheme": scheme}, start_polling=False)
    response = app.test_client().get("/race-control")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'data-theme="{scheme}"' in html
    for asset in ("theme.css", "race_control.css", "result_helpers.js", "race_control.js"):
        assert f"/static/{asset}?v=" in html
    assert 'id="theme"' not in html


def test_control_payload_ignores_tv_visibility_options_and_resets_on_race_switch(tmp_path):
    from pathlib import Path

    config = {
        "source": "csv", "data_file": str(Path(__file__).parents[1] / "docs" / "sample-results.csv"),
        "show_overall_results": False, "show_category_results": False, "show_lap_overview": False,
    }
    app = create_app(config, start_polling=False)
    poll_once(app)
    body = app.test_client().get("/api/data").get_json()
    assert not any(p["type"] == "category" for p in body["pages"])
    assert body["race_control"]["groups"]
    assert body["race_control"]["progress"]["distances"]
    old_control = body["race_control"]
    # Failed polls keep the last successful control snapshot.
    app.config["dashboard"] = {**config, "data_file": str(tmp_path / "missing.csv")}
    poll_once(app)
    body = app.test_client().get("/api/data").get_json()
    assert body["is_stale"] and body["error"]
    assert body["race_control"] == old_control
    from app import _apply_config
    _apply_config(app, {**config, "data_file": "other.csv"}, ["data_file"])
    assert app.test_client().get("/api/data").get_json()["race_control"] is None
