import os
import pytest
from unittest.mock import patch
from config import load_config


def test_load_config_with_all_values(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("WEBSCORER_RACE_ID", "99999")
    monkeypatch.setenv("REFRESH_INTERVAL", "30")
    monkeypatch.setenv("SUMMARY_DISPLAY_TIME", "15")
    monkeypatch.setenv("SCROLL_SPEED", "150")
    monkeypatch.setenv("SCROLL_PAUSE_TIME", "5")
    monkeypatch.setenv("PINNED_LEADERS", "5")
    cfg = load_config()
    assert cfg["api_id"] == "12345"
    assert cfg["api_token"] == "abc123de"
    assert cfg["race_id"] == "99999"
    assert cfg["refresh_interval"] == 30
    assert cfg["summary_display_time"] == 15
    assert cfg["scroll_speed"] == 150
    assert cfg["scroll_pause_time"] == 5
    assert cfg["pinned_leaders"] == 5


@patch("config.load_dotenv")
def test_load_config_defaults(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("WEBSCORER_RACE_ID", raising=False)
    monkeypatch.delenv("REFRESH_INTERVAL", raising=False)
    monkeypatch.delenv("SUMMARY_DISPLAY_TIME", raising=False)
    monkeypatch.delenv("SCROLL_SPEED", raising=False)
    monkeypatch.delenv("SCROLL_PAUSE_TIME", raising=False)
    monkeypatch.delenv("PINNED_LEADERS", raising=False)
    cfg = load_config()
    assert cfg["race_id"] is None
    assert cfg["refresh_interval"] == 60
    assert cfg["summary_display_time"] == 20
    assert cfg["scroll_speed"] == 100
    assert cfg["scroll_pause_time"] == 3
    assert cfg["pinned_leaders"] == 3


@patch("config.load_dotenv")
def test_load_config_missing_api_id(mock_dotenv, monkeypatch):
    monkeypatch.delenv("WEBSCORER_API_ID", raising=False)
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    with pytest.raises(SystemExit):
        load_config()


@patch("config.load_dotenv")
def test_load_config_missing_api_token(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.delenv("WEBSCORER_API_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        load_config()
