import os
import pytest
from unittest.mock import patch
from config import load_config


def test_load_config_with_all_values(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("WEBSCORER_RACE_ID", "99999")
    monkeypatch.setenv("REFRESH_INTERVAL", "30")
    monkeypatch.setenv("PAGE_ROTATION_INTERVAL", "15")
    cfg = load_config()
    assert cfg["api_id"] == "12345"
    assert cfg["api_token"] == "abc123de"
    assert cfg["race_id"] == "99999"
    assert cfg["refresh_interval"] == 30
    assert cfg["page_rotation_interval"] == 15


@patch("config.load_dotenv")
def test_load_config_defaults(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("WEBSCORER_RACE_ID", raising=False)
    monkeypatch.delenv("REFRESH_INTERVAL", raising=False)
    monkeypatch.delenv("PAGE_ROTATION_INTERVAL", raising=False)
    cfg = load_config()
    assert cfg["race_id"] is None
    assert cfg["refresh_interval"] == 60
    assert cfg["page_rotation_interval"] == 20


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
