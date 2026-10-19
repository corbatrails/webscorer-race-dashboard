"""Contract tests every provider must pass. Add a provider by adding a case to CASES."""
import os
from unittest.mock import patch

import pytest

import app as app_module
from data_processing import (
    build_demographics_data,
    build_finish_chart_data,
    build_pages,
    process_race_data,
)
from providers import get_provider

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASES = {
    "webscorer": os.path.join(ROOT, "tests", "fixtures", "race_a_finished.json"),
    "csv": os.path.join(ROOT, "docs", "sample-results.csv"),
}

SNAPSHOT_KEYS = {"error", "race", "groups", "racers"}
RACE_KEYS = {"name", "date", "sport", "start_seconds"}
GROUP_KEYS = {"tier", "distance", "category", "gender"}
RACER_KEYS = {
    "bib", "name", "team", "distance", "category", "gender", "age", "status", "time_display",
    "elapsed_seconds", "start_seconds", "finish_tod_seconds", "source_place", "in_overall",
    "category_groups",
}
MEMBERSHIP_KEYS = {"distance", "category", "gender", "source_place"}
STATUSES = {"FINISHED", "IN_PROGRESS", "DNS", "DNF", "DSQ"}


@pytest.fixture(params=sorted(CASES))
def source(request):
    return request.param


def _config(source):
    return {"source": source, "data_file": CASES[source], "race_id": None, "api_id": None, "api_token": None}


def _snapshot(source):
    provider = get_provider(source)
    return provider.normalize(provider.fetch(_config(source), {}))


def test_provider_is_registered_under_its_own_name(source):
    provider = get_provider(source)
    assert provider.name == source
    assert isinstance(provider.required_secrets, dict)
    assert isinstance(provider.requires_data_file, bool)
    assert callable(provider.fetch) and callable(provider.normalize)
    assert provider.list_races is None or callable(provider.list_races)


def test_fetch_with_data_file_makes_no_network_call(source):
    with patch("requests.get", side_effect=AssertionError("network used")):
        raw = get_provider(source).fetch(_config(source), {})
    assert raw is not None


def test_snapshot_has_the_documented_shape(source):
    snapshot = _snapshot(source)
    assert set(snapshot) == SNAPSHOT_KEYS
    assert snapshot["error"] is None
    assert set(snapshot["race"]) == RACE_KEYS
    assert isinstance(snapshot["race"]["name"], str) and snapshot["race"]["name"]
    assert snapshot["racers"] and snapshot["groups"]
    for group in snapshot["groups"]:
        assert set(group) == GROUP_KEYS
        assert group["tier"] in {"overall", "category"}
    for racer in snapshot["racers"]:
        assert set(racer) == RACER_KEYS
        assert racer["status"] in STATUSES
        assert racer["age"] is None or isinstance(racer["age"], int)
        assert isinstance(racer["in_overall"], bool)
        for membership in racer["category_groups"]:
            assert set(membership) == MEMBERSHIP_KEYS


def test_finished_iff_elapsed_seconds_is_set(source):
    for racer in _snapshot(source)["racers"]:
        assert (racer["status"] == "FINISHED") == (racer["elapsed_seconds"] is not None), racer


def test_finish_time_of_day_needs_start_and_elapsed(source):
    for racer in _snapshot(source)["racers"]:
        start, elapsed, finish = racer["start_seconds"], racer["elapsed_seconds"], racer["finish_tod_seconds"]
        if start is None or elapsed is None:
            assert finish is None, racer
        else:
            assert finish == pytest.approx(start + elapsed), racer


def test_every_in_overall_racer_has_an_overall_group(source):
    snapshot = _snapshot(source)
    overall_distances = {g["distance"] for g in snapshot["groups"] if g["tier"] == "overall"}
    for racer in snapshot["racers"]:
        if racer["in_overall"]:
            assert racer["distance"] in overall_distances, racer


def test_every_membership_matches_a_category_group(source):
    snapshot = _snapshot(source)
    categories = {
        (g["distance"], g["category"], g["gender"]) for g in snapshot["groups"] if g["tier"] == "category"
    }
    for racer in snapshot["racers"]:
        for m in racer["category_groups"]:
            assert (m["distance"], m["category"], m["gender"]) in categories, racer


def test_snapshot_flows_through_every_view(source):
    snapshot = _snapshot(source)
    data = process_race_data(snapshot)
    pages = build_pages(data, build_demographics_data(snapshot))
    assert pages[0]["type"] == "summary"
    assert any(c["tier"] == "overall" for c in pages[0]["data"]["categories"])
    assert any(p["type"] == "category" and p["tier"] == "overall" for p in pages)
    chart = build_finish_chart_data(snapshot, 15)
    assert chart is None or "datasets" in chart


def test_poll_once_succeeds_for_the_source(source):
    app = app_module.create_app(_config(source), start_polling=False)
    app_module._cache.update({"pages": [], "is_stale": False, "error": None, "waiting": True})
    app_module.poll_once(app)
    assert app_module._cache["is_stale"] is False
    assert app_module._cache["error"] is None
    assert app_module._cache["pages"][0]["type"] == "summary"
