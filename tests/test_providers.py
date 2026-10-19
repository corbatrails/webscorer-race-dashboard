import dataclasses

import pytest

import providers
from providers import Provider, get_provider, provider_names


def _stub(name="stub", **overrides):
    fields = dict(
        name=name,
        required_secrets={},
        requires_data_file=False,
        fetch=lambda config, secrets: {},
        normalize=lambda raw: {},
    )
    fields.update(overrides)
    return Provider(**fields)


def test_provider_is_frozen_and_list_races_defaults_to_none():
    provider = _stub()
    assert provider.list_races is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        provider.name = "other"


def test_get_provider_returns_registered_instance(monkeypatch):
    provider = _stub()
    monkeypatch.setitem(providers._REGISTRY, "stub", provider)
    assert get_provider("stub") is provider


def test_get_provider_unknown_name_lists_valid_names(monkeypatch):
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub())
    with pytest.raises(ValueError) as exc:
        get_provider("nope")
    assert "'nope'" in str(exc.value)
    assert "stub" in str(exc.value)


def test_provider_names_are_sorted(monkeypatch):
    monkeypatch.setattr(providers, "_REGISTRY", {"b": _stub("b"), "a": _stub("a")})
    assert provider_names() == ["a", "b"]


# --- WebScorer provider ---------------------------------------------------

import json
import os
from unittest.mock import patch

from normalizer import normalize_webscorer

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "race_a_finished.json")


def test_webscorer_provider_is_registered():
    provider = get_provider("webscorer")
    assert provider.name == "webscorer"
    assert provider.required_secrets == {"api_id": "WEBSCORER_API_ID", "api_token": "WEBSCORER_API_TOKEN"}
    assert provider.requires_data_file is False
    assert provider.list_races is not None


@patch("providers.webscorer.fetch_race_results")
def test_webscorer_fetch_reads_data_file_instead_of_api(mock_fetch):
    provider = get_provider("webscorer")
    raw = provider.fetch({"data_file": FIXTURE, "race_id": "1"}, {"api_id": "1", "api_token": "x"})
    with open(FIXTURE, encoding="utf-8") as f:
        assert raw == json.load(f)
    mock_fetch.assert_not_called()


@patch("providers.webscorer.fetch_race_results")
def test_webscorer_fetch_calls_api_without_data_file(mock_fetch):
    mock_fetch.return_value = {"RaceInfo": {}}
    provider = get_provider("webscorer")
    raw = provider.fetch({"race_id": "100", "data_file": None}, {"api_id": "12345", "api_token": "abc123de"})
    assert raw == {"RaceInfo": {}}
    mock_fetch.assert_called_once_with("100", "12345", "abc123de")


def test_webscorer_normalize_matches_normalize_webscorer():
    with open(FIXTURE, encoding="utf-8") as f:
        raw = json.load(f)
    assert get_provider("webscorer").normalize(raw) == normalize_webscorer(raw)


@patch("providers.webscorer.fetch_race_list")
def test_webscorer_list_races_maps_api_list(mock_list):
    mock_list.return_value = [
        {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
        {"RaceId": 200, "Name": "Trail 10K"},
    ]
    choices = get_provider("webscorer").list_races({}, {"api_id": "12345", "api_token": "abc123de"})
    mock_list.assert_called_once_with("12345", "abc123de")
    assert choices == [
        {"id": "100", "name": "Morning 5K", "date": "2026-08-07", "sport": "Running"},
        {"id": "200", "name": "Trail 10K", "date": "N/A", "sport": ""},
    ]


# --- CSV provider registration ----------------------------------------------


def test_csv_provider_is_registered():
    provider = get_provider("csv")
    assert provider.name == "csv"
    assert provider.required_secrets == {}
    assert provider.requires_data_file is True
    assert provider.list_races is None
    assert provider_names() == ["csv", "webscorer"]
