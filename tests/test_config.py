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
    monkeypatch.delenv("SHOW_OVERALL_RESULTS", raising=False)
    monkeypatch.delenv("SHOW_CATEGORY_RESULTS", raising=False)
    cfg = load_config()
    assert cfg["race_id"] is None
    assert cfg["refresh_interval"] == 60
    assert cfg["summary_display_time"] == 20
    assert cfg["scroll_speed"] == 100
    assert cfg["scroll_pause_time"] == 2
    assert cfg["pinned_leaders"] == 3
    assert cfg["show_overall_results"] is True
    assert cfg["show_category_results"] is True


@patch("config.load_dotenv")
def test_load_config_missing_api_id(mock_dotenv, monkeypatch):
    monkeypatch.delenv("DATA_FILE", raising=False)
    monkeypatch.delenv("WEBSCORER_API_ID", raising=False)
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    with pytest.raises(SystemExit):
        load_config()


@patch("config.load_dotenv")
def test_load_config_missing_api_token(mock_dotenv, monkeypatch):
    monkeypatch.delenv("DATA_FILE", raising=False)
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.delenv("WEBSCORER_API_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        load_config()


@patch("config.load_dotenv")
def test_load_config_missing_data_file(mock_dotenv, monkeypatch):
    monkeypatch.setenv("DATA_FILE", "nonexistent_file_that_does_not_exist.json")
    monkeypatch.delenv("WEBSCORER_API_ID", raising=False)
    monkeypatch.delenv("WEBSCORER_API_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        load_config()


def test_chart_bucket_minutes_default(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.delenv("CHART_BUCKET_MINUTES", raising=False)
    from config import load_config
    cfg = load_config()
    assert cfg["chart_bucket_minutes"] == 15


def test_chart_bucket_minutes_custom(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("CHART_BUCKET_MINUTES", "30")
    from config import load_config
    cfg = load_config()
    assert cfg["chart_bucket_minutes"] == 30


@patch("config.load_dotenv")
def test_color_scheme_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.delenv("COLOR_SCHEME", raising=False)
    cfg = load_config()
    assert cfg["color_scheme"] == "dark"


@patch("config.load_dotenv")
def test_color_scheme_light(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("COLOR_SCHEME", "light")
    cfg = load_config()
    assert cfg["color_scheme"] == "light"


@patch("config.load_dotenv")
def test_load_config_show_toasts_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("SHOW_TOASTS", raising=False)
    cfg = load_config()
    assert cfg["show_toasts"] is True


@patch("config.load_dotenv")
def test_load_config_show_toasts_disabled(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("SHOW_TOASTS", "false")
    cfg = load_config()
    assert cfg["show_toasts"] is False


@patch("config.load_dotenv")
def test_color_scheme_invalid_falls_back_to_dark(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("COLOR_SCHEME", "neon")
    cfg = load_config()
    assert cfg["color_scheme"] == "dark"


@patch("config.load_dotenv")
def test_load_config_pinned_leaders_on_overall_results_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("PINNED_LEADERS_ON_OVERALL_RESULTS", raising=False)
    cfg = load_config()
    assert cfg["pinned_leaders_on_overall_results"] is False


@patch("config.load_dotenv")
def test_load_config_pinned_leaders_on_overall_results_enabled(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("PINNED_LEADERS_ON_OVERALL_RESULTS", "true")
    cfg = load_config()
    assert cfg["pinned_leaders_on_overall_results"] is True


@patch("config.load_dotenv")
def test_load_config_overall_results_layout_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("OVERALL_RESULTS_LAYOUT", raising=False)
    cfg = load_config()
    assert cfg["overall_results_layout"] == "standard"


@patch("config.load_dotenv")
def test_load_config_overall_results_layout_detailed(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("OVERALL_RESULTS_LAYOUT", "detailed")
    cfg = load_config()
    assert cfg["overall_results_layout"] == "detailed"


@patch("config.load_dotenv")
def test_load_config_overall_results_layout_invalid_falls_back_to_standard(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("OVERALL_RESULTS_LAYOUT", "wide")
    cfg = load_config()
    assert cfg["overall_results_layout"] == "standard"


@patch("config.load_dotenv")
def test_load_config_display_unfinished_result_pages_defaults(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("DISPLAY_UNFINISHED_IN_CATEGORY", raising=False)
    monkeypatch.delenv("DISPLAY_UNFINISHED_IN_OVERALL", raising=False)
    cfg = load_config()
    assert cfg["display_unfinished_in_category"] is False
    assert cfg["display_unfinished_in_overall"] is False


@patch("config.load_dotenv")
def test_load_config_display_unfinished_result_pages_enabled(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("DISPLAY_UNFINISHED_IN_CATEGORY", "true")
    monkeypatch.setenv("DISPLAY_UNFINISHED_IN_OVERALL", "true")
    cfg = load_config()
    assert cfg["display_unfinished_in_category"] is True
    assert cfg["display_unfinished_in_overall"] is True
