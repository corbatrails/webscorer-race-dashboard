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


@patch("config.load_dotenv")
def test_load_config_show_demographics_default_false(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("SHOW_DEMOGRAPHICS", raising=False)
    cfg = load_config()
    assert cfg["show_demographics"] is False


@patch("config.load_dotenv")
def test_load_config_show_demographics_true(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("SHOW_DEMOGRAPHICS", "true")
    cfg = load_config()
    assert cfg["show_demographics"] is True


# --- config.yaml layering (Phase 2) ---------------------------------------

import yaml
from config import OPTIONS, SECRET_ENV_VARS

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def clean_env(monkeypatch):
    for opt in OPTIONS:
        monkeypatch.delenv(opt.env, raising=False)
    for name in SECRET_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")


def _write_yaml(tmp_path, data):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def _load(tmp_path, data=None, env_text=None, **kwargs):
    config_path = _write_yaml(tmp_path, data) if data is not None else str(tmp_path / "missing.yaml")
    env_path = tmp_path / ".env"
    if env_text is not None:
        env_path.write_text(env_text, encoding="utf-8")
    return load_config(config_path=config_path, env_path=str(env_path), **kwargs)


def test_missing_config_yaml_uses_defaults(clean_env, tmp_path):
    cfg = _load(tmp_path)
    assert cfg["refresh_interval"] == 60
    assert cfg["color_scheme"] == "dark"
    assert cfg["show_demographics"] is False
    assert cfg["race_id"] is None
    assert cfg["data_file"] is None


def test_config_yaml_values_are_applied(clean_env, tmp_path):
    cfg = _load(tmp_path, {
        "race_id": 4242,
        "refresh_interval": 15,
        "show_summary": False,
        "show_demographics": True,
        "overall_results_layout": "detailed",
        "color_scheme": "light",
        "chart_bucket_minutes": 5,
    })
    assert cfg["race_id"] == "4242"
    assert cfg["refresh_interval"] == 15
    assert cfg["show_summary"] is False
    assert cfg["show_demographics"] is True
    assert cfg["overall_results_layout"] == "detailed"
    assert cfg["color_scheme"] == "light"
    assert cfg["chart_bucket_minutes"] == 5
    assert cfg["scroll_speed"] == 100


def test_partial_config_yaml_falls_back_to_defaults(clean_env, tmp_path):
    cfg = _load(tmp_path, {"scroll_speed": 200})
    assert cfg["scroll_speed"] == 200
    assert cfg["pinned_leaders"] == 3


def test_empty_config_yaml_uses_defaults(clean_env, tmp_path):
    (tmp_path / "config.yaml").write_text("", encoding="utf-8")
    cfg = load_config(config_path=str(tmp_path / "config.yaml"), env_path=str(tmp_path / ".env"))
    assert cfg["refresh_interval"] == 60


def test_env_overrides_config_yaml(clean_env, tmp_path, monkeypatch):
    monkeypatch.setenv("REFRESH_INTERVAL", "10")
    monkeypatch.setenv("SHOW_SUMMARY", "false")
    cfg = _load(tmp_path, {"refresh_interval": 15, "show_summary": True})
    assert cfg["refresh_interval"] == 10
    assert cfg["show_summary"] is False


def test_dotenv_file_overrides_config_yaml(clean_env, tmp_path):
    cfg = _load(tmp_path, {"scroll_speed": 200}, env_text="SCROLL_SPEED=300\n")
    assert cfg["scroll_speed"] == 300


def test_process_env_overrides_dotenv_file(clean_env, tmp_path, monkeypatch):
    monkeypatch.setenv("SCROLL_SPEED", "400")
    cfg = _load(tmp_path, {"scroll_speed": 200}, env_text="SCROLL_SPEED=300\n")
    assert cfg["scroll_speed"] == 400


def test_blank_env_value_does_not_override_config_yaml(clean_env, tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSCORER_RACE_ID", "")
    monkeypatch.setenv("REFRESH_INTERVAL", "")
    cfg = _load(tmp_path, {"race_id": 777, "refresh_interval": 15})
    assert cfg["race_id"] == "777"
    assert cfg["refresh_interval"] == 15


def test_secrets_come_from_dotenv_file(clean_env, tmp_path, monkeypatch):
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    cfg = _load(tmp_path, {}, env_text="WEBSCORER_API_ID=987\nWEBSCORER_API_TOKEN=tok12345\n")
    assert cfg["api_id"] == "987"
    assert cfg["api_token"] == "tok12345"


def test_data_file_from_config_yaml_skips_credentials(clean_env, tmp_path, monkeypatch):
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    data_file = tmp_path / "dump.json"
    data_file.write_text("{}", encoding="utf-8")
    cfg = _load(tmp_path, {"data_file": str(data_file)})
    assert cfg["data_file"] == str(data_file)


def test_missing_credentials_message_mentions_dotenv(clean_env, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WEBSCORER_API_ID")
    with pytest.raises(SystemExit):
        _load(tmp_path, {})
    assert ".env" in capsys.readouterr().out


def test_committed_config_yaml_lists_every_option_with_defaults(clean_env):
    with open(os.path.join(REPO_ROOT, "config.yaml"), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert set(data) == {opt.key for opt in OPTIONS}
    cfg = load_config(
        config_path=os.path.join(REPO_ROOT, "config.yaml"),
        env_path=os.path.join(REPO_ROOT, "does-not-exist.env"),
    )
    defaults = load_config(
        config_path=os.path.join(REPO_ROOT, "does-not-exist.yaml"),
        env_path=os.path.join(REPO_ROOT, "does-not-exist.env"),
    )
    assert cfg == defaults


def test_every_option_declares_reload_mode():
    assert {opt.reload for opt in OPTIONS} <= {"live", "restart"}
    assert {opt.key for opt in OPTIONS if opt.reload == "restart"} == {
        "race_id", "data_file", "refresh_interval",
    }
