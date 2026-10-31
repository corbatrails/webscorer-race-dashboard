"""Golden-file characterization tests for the TV/announcer /api/data contract.

Inputs are small, anonymized subsets of real WebScorer dumps (tests/fixtures).
Expected outputs live in tests/golden. Racer rows are compared on the fields the
frontend reads (see CONTRACT_FIELDS); regenerate with UPDATE_GOLDEN=1 when an
intentional output change is made, and review the diff.
The independent race-control projection is covered by test_race_control.py.
"""
import json
import os
from pathlib import Path

import pytest

import app as app_module
from app import create_app, poll_once

TESTS_DIR = Path(__file__).parent
FIXTURES = TESTS_DIR / "fixtures"
GOLDEN = TESTS_DIR / "golden"

CONTRACT_FIELDS = ("Place", "Bib", "Name", "Time", "TeamName", "Category", "Gender")

CASES = [
    ("race_a_finished", "default", {}),
    ("race_a_finished", "overall_off", {"show_overall_results": False}),
    ("race_a_finished", "category_off", {"show_category_results": False}),
    ("race_a_finished", "bucket30", {"chart_bucket_minutes": 30}),
    ("race_a_live", "default", {}),
    ("race_b_teamname", "default", {}),
]


@pytest.fixture(autouse=True)
def fixed_observation_time(monkeypatch):
    """The lap overview depends on wall-clock time; pin it to the end of the event day."""
    monkeypatch.setattr(app_module, "_observation_seconds", lambda race, now=None: 86399)


@pytest.fixture(autouse=True)
def reset_cache():
    with app_module._cache_lock:
        app_module._cache.update({
            "pages": [],
            "last_refresh": None,
            "is_stale": False,
            "waiting": True,
            "error": None,
            "race_name": "",
            "race_date": "",
            "race_sport": "",
            "finish_chart": None,
        })


def _contract_row(racer):
    row = {field: racer.get(field, "") for field in CONTRACT_FIELDS}
    if "CategoryPlace" in racer:
        row["CategoryPlace"] = racer["CategoryPlace"]
    return row


def _contract_rows(racers):
    return [_contract_row(r) for r in racers]


def _contract(payload):
    payload = json.loads(json.dumps(payload))
    payload.pop("last_refresh", None)
    payload.pop("server_time", None)
    payload.pop("race_control", None)
    for page in payload["pages"]:
        if "racers" in page:
            page["racers"] = _contract_rows(page["racers"])
        if page["type"] == "summary":
            for category in page["data"]["categories"]:
                category["racers"] = _contract_rows(category["racers"])
                category["leaders"] = _contract_rows(category["leaders"])
    return payload


def _fmt(value, level=0):
    pad = " " * (level + 1)
    if isinstance(value, dict):
        if all(not isinstance(v, (dict, list)) for v in value.values()):
            return json.dumps(value)
        items = [f"{pad}{json.dumps(k)}: {_fmt(v, level + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + " " * level + "}"
    if isinstance(value, list):
        if all(not isinstance(v, (dict, list)) for v in value):
            return json.dumps(value)
        items = [f"{pad}{_fmt(v, level + 1)}" for v in value]
        return "[\n" + ",\n".join(items) + "\n" + " " * level + "]"
    return json.dumps(value)


def _run(fixture, overrides):
    config = {
        "data_file": str(FIXTURES / f"{fixture}.json"),
        "race_id": "1",
        "refresh_interval": 60,
        "show_overall_results": True,
        "show_category_results": True,
        "chart_bucket_minutes": 15,
    }
    config.update(overrides)
    app = create_app(config, start_polling=False)
    poll_once(app)
    return _contract(app.test_client().get("/api/data").get_json())


@pytest.mark.parametrize("fixture,variant,overrides", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_api_data_matches_golden(fixture, variant, overrides):
    actual = _run(fixture, overrides)
    golden_path = GOLDEN / f"{fixture}__{variant}.json"

    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.mkdir(exist_ok=True)
        golden_path.write_text(_fmt(actual) + "\n", encoding="utf-8")

    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert actual == expected


def test_golden_inputs_contain_no_contact_data():
    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "@" not in text, f"{path.name} contains an email-like value"
