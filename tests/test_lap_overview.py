import json

import pytest

from data_processing import build_lap_overview_data, build_pages

START = 8 * 3600


def _group(distance, lap_count=1, tier="overall", category=""):
    return {"tier": tier, "distance": distance, "category": category, "gender": "", "lap_count": lap_count}


def _racer(distance, status="IN_PROGRESS", start=START, crossings=(), in_overall=True, bib="1"):
    return {
        "bib": bib, "name": f"R{bib}", "team": "", "distance": distance, "category": "", "gender": "",
        "age": None, "status": status, "time_display": "", "elapsed_seconds": 3600.0 if status == "FINISHED" else None,
        "start_seconds": start, "finish_tod_seconds": None, "source_place": "", "in_overall": in_overall,
        "category_groups": [],
        "lap_crossings": [{"lap_number": n, "elapsed_seconds": float(s)} for n, s in crossings],
    }


def _snapshot(groups, racers, error=None):
    return {
        "error": error,
        "race": {
            "name": "Race", "date": "", "sport": "", "start_seconds": START,
            "event_date_iso": None, "timezone_offset_minutes": None,
        },
        "groups": groups,
        "racers": racers,
    }


def _distance(data, name):
    (entry,) = [d for d in data["distances"] if d["name"] == name]
    return entry


def _reconciles(entry):
    on_course = sum(entry["on_course_by_lap"])
    assert entry["on_course"] == on_course
    assert entry["registered"] == (
        entry["dns"] + entry["not_started"] + on_course + entry["finished"] + entry["dnf"] + entry["dsq"]
    )
    assert entry["started"] == on_course + entry["finished"] + entry["dnf"] + entry["dsq"]
    assert entry["dnf"] == sum(entry["dnf_by_lap"]) + entry["dnf_without_crossing"]


def test_returns_none_for_provider_error():
    assert build_lap_overview_data(_snapshot([], [], error="nope"), START) is None


def test_returns_none_without_overall_groups():
    assert build_lap_overview_data(_snapshot([_group("10K", tier="category", category="Open")], []), START) is None


def test_every_overall_distance_appears_once_in_order_including_empty():
    groups = [_group("50K", 4), _group("50K", 4, tier="category", category="Open"), _group("5K"), _group("Relay", 4)]
    data = build_lap_overview_data(_snapshot(groups, [_racer("5K")]), START + 60)
    assert [d["name"] for d in data["distances"]] == ["50K", "5K", "Relay"]
    relay = _distance(data, "Relay")
    assert relay["registered"] == 0 and relay["on_course_by_lap"] == [0, 0, 0, 0]
    _reconciles(relay)


def test_blank_distance_is_labelled_overall():
    data = build_lap_overview_data(_snapshot([_group("")], [_racer("")]), START + 60)
    assert data["distances"][0]["name"] == "Overall"


def test_dns_with_stray_crossing_counts_only_as_dns():
    racer = _racer("50K", status="DNS", crossings=[(1, 600)])
    data = build_lap_overview_data(_snapshot([_group("50K", 4)], [racer]), START + 3600)
    entry = _distance(data, "50K")
    assert entry["dns"] == 1
    assert entry["started"] == 0 and entry["on_course_by_lap"] == [0, 0, 0, 0] and entry["dnf"] == 0
    _reconciles(entry)


def test_future_start_is_not_started():
    racer = _racer("5K", start=START + 600)
    entry = _distance(build_lap_overview_data(_snapshot([_group("5K")], [racer]), START + 60), "5K")
    assert entry["not_started"] == 1 and entry["on_course_by_lap"] == [0]
    _reconciles(entry)


def test_missing_start_is_never_not_started():
    racer = _racer("50K", start=None, crossings=[(1, 600)])
    entry = _distance(build_lap_overview_data(_snapshot([_group("50K", 4)], [racer]), 0), "50K")
    assert entry["not_started"] == 0 and entry["on_course_by_lap"] == [0, 1, 0, 0]


def test_on_course_lap_uses_crossings_at_or_before_observation():
    racers = [
        _racer("50K", bib="1"),
        _racer("50K", bib="2", crossings=[(1, 1800), (2, 3600)]),
        _racer("50K", bib="3", crossings=[(1, 1800), (2, 3600), (3, 5400)]),
    ]
    data = build_lap_overview_data(_snapshot([_group("50K", 4)], racers), START + 3600)
    assert _distance(data, "50K")["on_course_by_lap"] == [1, 0, 2, 0]


def test_on_course_lap_never_exceeds_lap_count():
    racer = _racer("25K", crossings=[(1, 1800), (2, 3600)])
    entry = _distance(build_lap_overview_data(_snapshot([_group("25K", 2)], [racer]), START + 7200), "25K")
    assert entry["on_course_by_lap"] == [0, 1]


def test_missing_intermediate_split_uses_highest_crossed_lap():
    racer = _racer("50K", crossings=[(1, 1800), (3, 5400)])
    entry = _distance(build_lap_overview_data(_snapshot([_group("50K", 4)], [racer]), START + 6000), "50K")
    assert entry["on_course_by_lap"] == [0, 0, 0, 1]


def test_finished_racers_only_count_as_finished():
    racer = _racer("25K", status="FINISHED", crossings=[(1, 1800), (2, 3600)])
    entry = _distance(build_lap_overview_data(_snapshot([_group("25K", 2)], [racer]), START + 7200), "25K")
    assert entry["finished"] == 1 and entry["on_course_by_lap"] == [0, 0]
    _reconciles(entry)


def test_dnf_note_on_last_recorded_crossing_lap():
    racers = [
        _racer("50K", status="DNF", bib="1", crossings=[(1, 1800)]),
        _racer("50K", status="DNF", bib="2", crossings=[(1, 1800), (2, 3600), (3, 5400)]),
    ]
    entry = _distance(build_lap_overview_data(_snapshot([_group("50K", 4)], racers), START + 9000), "50K")
    assert entry["dnf"] == 2
    assert entry["dnf_by_lap"] == [1, 0, 1, 0]
    assert entry["dnf_without_crossing"] == 0
    assert entry["on_course_by_lap"] == [0, 0, 0, 0]
    _reconciles(entry)


def test_dnf_without_crossing_is_counted_separately():
    racer = _racer("50K", status="DNF")
    entry = _distance(build_lap_overview_data(_snapshot([_group("50K", 4)], [racer]), START + 9000), "50K")
    assert entry["dnf"] == 1 and entry["dnf_without_crossing"] == 1 and entry["dnf_by_lap"] == [0, 0, 0, 0]
    _reconciles(entry)


def test_dnf_ignores_crossings_after_observation_when_start_known():
    racer = _racer("50K", status="DNF", crossings=[(1, 1800), (2, 3600)])
    entry = _distance(build_lap_overview_data(_snapshot([_group("50K", 4)], [racer]), START + 2000), "50K")
    assert entry["dnf_by_lap"] == [1, 0, 0, 0]


def test_dsq_is_its_own_state():
    racer = _racer("5K", status="DSQ")
    entry = _distance(build_lap_overview_data(_snapshot([_group("5K")], [racer]), START + 60), "5K")
    assert entry["dsq"] == 1 and entry["started"] == 1 and entry["on_course_by_lap"] == [0]
    _reconciles(entry)


def test_category_only_racers_are_excluded():
    racer = _racer("5K", in_overall=False)
    entry = _distance(build_lap_overview_data(_snapshot([_group("5K")], [racer]), START + 60), "5K")
    assert entry["registered"] == 0


def test_mixed_statuses_reconcile_per_distance_and_event():
    groups = [_group("5K"), _group("50K", 4)]
    racers = [
        _racer("5K", status="FINISHED", bib="1"),
        _racer("5K", status="DNS", bib="2"),
        _racer("5K", bib="3"),
        _racer("50K", bib="4", start=START + 99999),
        _racer("50K", bib="5", crossings=[(1, 1800)]),
        _racer("50K", status="DNF", bib="6"),
        _racer("50K", status="DSQ", bib="7"),
        _racer("50K", status="DNF", bib="8", crossings=[(1, 1800), (2, 3600)]),
    ]
    data = build_lap_overview_data(_snapshot(groups, racers), START + 4000)
    for entry in data["distances"]:
        _reconciles(entry)
    totals = data["totals"]
    for key in ("registered", "dns", "not_started", "on_course", "finished", "dnf", "dsq", "started"):
        assert totals[key] == sum(d[key] for d in data["distances"]), key
    assert totals == {
        "registered": 8, "dns": 1, "not_started": 1, "on_course": 2, "finished": 1, "dnf": 2, "dsq": 1, "started": 6,
    }


def test_payload_is_json_serializable():
    data = build_lap_overview_data(_snapshot([_group("5K")], [_racer("5K")]), START + 60)
    assert json.loads(json.dumps(data)) == data


def _summary():
    return {"categories": [{"name": "5K", "tier": "overall", "racers": []}]}


def test_build_pages_puts_lap_overview_after_summary_before_demographics():
    lap = {"totals": {}, "distances": []}
    pages = build_pages(_summary(), {"total_registrants": 1}, lap_overview=lap)
    assert [p["type"] for p in pages] == ["summary", "lap_overview", "demographics", "category"]
    assert pages[1] == {"type": "lap_overview", "title": "Lap Overview", "data": lap}


def test_build_pages_without_lap_overview_is_unchanged():
    assert [p["type"] for p in build_pages(_summary())] == ["summary", "category"]


def test_build_pages_keeps_positional_max_rows():
    lap = {"totals": {}, "distances": []}
    pages = build_pages(_summary(), None, 18, lap)
    assert [p["type"] for p in pages] == ["summary", "lap_overview", "category"]
