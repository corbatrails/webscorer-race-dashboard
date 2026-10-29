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
        "source", "race_id", "data_file",
    }


# --- source option and per-provider credentials ------------------------------


def _stub_provider(**overrides):
    from providers.base import Provider
    fields = dict(
        name="stub", required_secrets={}, requires_data_file=False,
        fetch=lambda config, secrets: None, normalize=lambda raw: None,
    )
    fields.update(overrides)
    return Provider(**fields)


def test_source_defaults_to_webscorer(clean_env, tmp_path):
    assert _load(tmp_path)["source"] == "webscorer"


def test_source_from_config_yaml(clean_env, tmp_path, monkeypatch):
    import providers
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub_provider())
    assert _load(tmp_path, {"source": "stub"})["source"] == "stub"


def test_source_env_overrides_config_yaml_and_is_case_insensitive(clean_env, tmp_path, monkeypatch):
    import providers
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub_provider())
    monkeypatch.setenv("RACE_SOURCE", " STUB ")
    assert _load(tmp_path, {"source": "webscorer"})["source"] == "stub"


def test_unknown_source_exits_naming_option_and_valid_names(clean_env, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _load(tmp_path, {"source": "nope"})
    out = capsys.readouterr().out
    assert out.startswith("ERROR:")
    assert "source" in out and "webscorer" in out


def test_provider_requiring_data_file_exits_without_one(clean_env, tmp_path, monkeypatch, capsys):
    import providers
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub_provider(requires_data_file=True))
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    with pytest.raises(SystemExit):
        _load(tmp_path, {"source": "stub"})
    out = capsys.readouterr().out
    assert "requires data_file" in out
    assert "WEBSCORER_API" not in out


def test_provider_without_secrets_needs_no_credentials(clean_env, tmp_path, monkeypatch):
    import providers
    monkeypatch.setitem(providers._REGISTRY, "stub", _stub_provider())
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    cfg = _load(tmp_path, {"source": "stub"})
    assert cfg["api_id"] is None and cfg["api_token"] is None


@pytest.mark.parametrize("missing", ["WEBSCORER_API_ID", "WEBSCORER_API_TOKEN"])
def test_webscorer_missing_credential_message_is_unchanged(clean_env, tmp_path, monkeypatch, capsys, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(SystemExit):
        _load(tmp_path, {})
    assert capsys.readouterr().out.strip() == f"ERROR: {missing} is required. Set it in .env file."


# --- validation, warnings, legacy back-compat -------------------------------


def test_unknown_config_yaml_key_warns_and_is_ignored(clean_env, tmp_path, capsys):
    cfg = _load(tmp_path, {"refresh_interval": 15, "refresh_intervl": 99})
    assert cfg["refresh_interval"] == 15
    assert "refresh_intervl" in capsys.readouterr().err


def test_secrets_in_config_yaml_are_ignored_with_warning(clean_env, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    with pytest.raises(SystemExit):
        _load(tmp_path, {"api_token": "from-yaml"})
    err = capsys.readouterr().err
    assert "api_token" in err
    assert ".env" in err


def test_malformed_config_yaml_exits_with_message(clean_env, tmp_path, capsys):
    (tmp_path / "config.yaml").write_text("refresh_interval: [unclosed\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(config_path=str(tmp_path / "config.yaml"), env_path=str(tmp_path / ".env"))
    assert "config.yaml" in capsys.readouterr().out


def test_non_mapping_config_yaml_exits(clean_env, tmp_path, capsys):
    (tmp_path / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(config_path=str(tmp_path / "config.yaml"), env_path=str(tmp_path / ".env"))
    assert "mapping" in capsys.readouterr().out


def test_invalid_integer_in_config_yaml_names_option(clean_env, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _load(tmp_path, {"refresh_interval": "soon"})
    out = capsys.readouterr().out
    assert "refresh_interval" in out
    assert "config.yaml" in out


def test_invalid_integer_in_env_names_variable(clean_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCROLL_SPEED", "fast")
    with pytest.raises(SystemExit):
        _load(tmp_path, {})
    assert "SCROLL_SPEED" in capsys.readouterr().out


def test_non_boolean_yaml_value_exits(clean_env, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _load(tmp_path, {"show_summary": 5})
    assert "show_summary" in capsys.readouterr().out


def test_invalid_enum_values_fall_back_to_defaults(clean_env, tmp_path):
    cfg = _load(tmp_path, {"overall_results_layout": "wide", "color_scheme": "neon"})
    assert cfg["overall_results_layout"] == "standard"
    assert cfg["color_scheme"] == "dark"


def test_legacy_env_only_setup_still_works_and_warns(clean_env, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    cfg = _load(
        tmp_path,
        env_text=(
            "WEBSCORER_API_ID=111\nWEBSCORER_API_TOKEN=tok11111\n"
            "REFRESH_INTERVAL=45\nSHOW_DEMOGRAPHICS=true\nCOLOR_SCHEME=light\n"
        ),
    )
    assert cfg["api_id"] == "111"
    assert cfg["refresh_interval"] == 45
    assert cfg["show_demographics"] is True
    assert cfg["color_scheme"] == "light"
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()
    for name in ("REFRESH_INTERVAL", "SHOW_DEMOGRAPHICS", "COLOR_SCHEME"):
        assert name in err
    assert "WEBSCORER_API_ID" not in err.split("(", 1)[1].split(")", 1)[0]


def test_legacy_env_values_override_committed_config_yaml(clean_env, tmp_path):
    cfg = _load(tmp_path, {"refresh_interval": 15}, env_text="REFRESH_INTERVAL=45\n")
    assert cfg["refresh_interval"] == 45


def test_secrets_only_dotenv_does_not_warn(clean_env, tmp_path, capsys):
    _load(tmp_path, {}, env_text="WEBSCORER_API_ID=111\nWEBSCORER_API_TOKEN=tok11111\n")
    assert capsys.readouterr().err == ""


def test_blank_legacy_dotenv_keys_do_not_warn(clean_env, tmp_path, capsys):
    _load(tmp_path, {}, env_text="WEBSCORER_API_ID=111\nWEBSCORER_RACE_ID=\nREFRESH_INTERVAL=\n")
    assert capsys.readouterr().err == ""


def test_process_env_overrides_do_not_warn(clean_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REFRESH_INTERVAL", "30")
    _load(tmp_path, {})
    assert capsys.readouterr().err == ""


def test_env_example_lists_only_secrets():
    from dotenv import dotenv_values

    keys = set(dotenv_values(os.path.join(REPO_ROOT, ".env.example")))
    assert keys == set(SECRET_ENV_VARS)


def test_csv_source_needs_no_credentials(clean_env, tmp_path, monkeypatch):
    monkeypatch.delenv("WEBSCORER_API_ID")
    monkeypatch.delenv("WEBSCORER_API_TOKEN")
    data_file = tmp_path / "results.csv"
    data_file.write_text("bib,name,time\n1,A,1:00:00\n", encoding="utf-8")
    cfg = _load(tmp_path, {"source": "csv", "data_file": str(data_file)})
    assert cfg["source"] == "csv"
    assert cfg["api_id"] is None and cfg["api_token"] is None


def test_csv_source_without_data_file_exits_naming_data_file(clean_env, tmp_path, capsys):
    with pytest.raises(SystemExit):
        _load(tmp_path, {"source": "csv"})
    out = capsys.readouterr().out
    assert out.startswith("ERROR:")
    assert "data_file" in out


# --- ConfigError (loaders raise, load_config exits) --------------------------


def test_read_yaml_raises_config_error_on_malformed_yaml(tmp_path):
    from config import ConfigError, _read_yaml

    path = tmp_path / "config.yaml"
    path.write_text("refresh_interval: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="config.yaml"):
        _read_yaml(str(path))


def test_read_yaml_raises_config_error_on_non_mapping(tmp_path):
    from config import ConfigError, _read_yaml

    path = tmp_path / "config.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        _read_yaml(str(path))


def test_resolve_option_raises_config_error_on_invalid_value(clean_env):
    from config import ConfigError, _resolve_option

    opt = next(o for o in OPTIONS if o.key == "scroll_speed")
    with pytest.raises(ConfigError, match="scroll_speed"):
        _resolve_option(opt, {"scroll_speed": "fast"}, "config.yaml")


@pytest.mark.parametrize("value", [0, -5])
def test_refresh_interval_below_one_exits(clean_env, tmp_path, capsys, value):
    with pytest.raises(SystemExit):
        _load(tmp_path, {"refresh_interval": value})
    assert "refresh_interval" in capsys.readouterr().out


def test_refresh_interval_of_one_is_accepted(clean_env, tmp_path):
    assert _load(tmp_path, {"refresh_interval": 1})["refresh_interval"] == 1


# --- ConfigWatcher (Phase 4 hot-reload) --------------------------------------

_edit_counter = [0]


def _edit_config(path, data):
    """Rewrite config.yaml and force a distinct mtime so signatures always differ."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)
    _edit_counter[0] += 1
    stamp = 1_700_000_000_000_000_000 + _edit_counter[0] * 1_000_000_000
    os.utime(path, ns=(stamp, stamp))


def _start_watcher(tmp_path, data):
    from config import ConfigWatcher

    path = _write_yaml(tmp_path, data)
    running = load_config(config_path=path, env_path=str(tmp_path / ".env"))
    return path, running, ConfigWatcher(path)


def _settle(watcher, running):
    """Two ticks: the first notices a new signature, the second sees it settled."""
    watcher.check(running)
    return watcher.check(running)


def test_watcher_returns_none_when_file_is_unchanged(clean_env, tmp_path):
    _, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    assert watcher.check(running) is None
    assert watcher.check(running) is None


def test_watcher_applies_live_change_once_file_settles(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _edit_config(path, {"scroll_speed": 200, "color_scheme": "light"})

    assert watcher.check(running) is None
    result = watcher.check(running)

    assert result.changed == ["scroll_speed", "color_scheme"]
    assert result.config["scroll_speed"] == 200
    assert result.config["color_scheme"] == "light"
    assert result.config["pinned_leaders"] == running["pinned_leaders"]
    assert result.config["api_token"] == "abc123de"
    assert running["scroll_speed"] == 150
    assert watcher.check(result.config) is None


def test_watcher_waits_while_file_keeps_changing(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _edit_config(path, {"scroll_speed": 200})
    assert watcher.check(running) is None
    _edit_config(path, {"scroll_speed": 250})
    assert watcher.check(running) is None
    assert watcher.check(running).config["scroll_speed"] == 250


def test_watcher_ignores_edit_with_no_live_change(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _edit_config(path, {"scroll_speed": 150})
    assert _settle(watcher, running) is None


def test_watcher_env_override_keeps_winning(clean_env, tmp_path, monkeypatch):
    monkeypatch.setenv("SCROLL_SPEED", "300")
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _edit_config(path, {"scroll_speed": 200})
    assert _settle(watcher, running) is None
    assert running["scroll_speed"] == 300


def test_watcher_ignores_missing_file(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    os.remove(path)
    assert _settle(watcher, running) is None


def test_watcher_warns_about_unknown_keys(clean_env, tmp_path, capsys):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _edit_config(path, {"scroll_speed": 200, "scrol_speed": 5})
    result = _settle(watcher, running)
    assert result.config["scroll_speed"] == 200
    assert "scrol_speed" in capsys.readouterr().err


def _write_raw(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    _edit_counter[0] += 1
    stamp = 1_700_000_000_000_000_000 + _edit_counter[0] * 1_000_000_000
    os.utime(path, ns=(stamp, stamp))


@pytest.mark.parametrize("text,fragment", [
    ("scroll_speed: [unclosed\n", "config.yaml"),
    ("- a\n- b\n", "mapping"),
    ("scroll_speed: fast\n", "scroll_speed"),
    ("refresh_interval: 0\n", "refresh_interval"),
])
def test_watcher_keeps_last_good_config_on_bad_edit(clean_env, tmp_path, capsys, text, fragment):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _write_raw(path, text)

    assert _settle(watcher, running) is None

    err = capsys.readouterr().err
    assert "WARNING" in err
    assert fragment in err
    assert "keeping" in err


def test_watcher_warns_once_per_distinct_error(clean_env, tmp_path, capsys):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _write_raw(path, "scroll_speed: fast\n")
    for _ in range(4):
        watcher.check(running)
    assert capsys.readouterr().err.count("WARNING") == 1

    _write_raw(path, "scroll_speed: fast\n")  # same error, new mtime
    assert _settle(watcher, running) is None
    assert capsys.readouterr().err == ""

    _write_raw(path, "pinned_leaders: many\n")  # different error
    assert _settle(watcher, running) is None
    assert capsys.readouterr().err.count("WARNING") == 1


def test_watcher_recovers_when_file_is_fixed(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _write_raw(path, "scroll_speed: [unclosed\n")
    assert _settle(watcher, running) is None
    _edit_config(path, {"scroll_speed": 200})
    assert _settle(watcher, running).config["scroll_speed"] == 200


def test_watcher_warns_again_if_same_error_returns_after_recovery(clean_env, tmp_path, capsys):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    _write_raw(path, "scroll_speed: fast\n")
    _settle(watcher, running)
    _edit_config(path, {"scroll_speed": 200})
    _settle(watcher, running)
    capsys.readouterr()
    _write_raw(path, "scroll_speed: fast\n")
    _settle(watcher, running)
    assert capsys.readouterr().err.count("WARNING") == 1


def test_watcher_reports_restart_only_change_without_applying_it(clean_env, tmp_path, capsys):
    path, running, watcher = _start_watcher(tmp_path, {"race_id": 111})
    _edit_config(path, {"race_id": 222, "data_file": "other.json"})

    result = _settle(watcher, running)

    assert result.restart_required == ["data_file", "race_id"]
    assert result.changed == []
    assert result.config == running
    err = capsys.readouterr().err
    assert "requires restart" in err
    assert "other.json" not in err
    assert _settle(watcher, result.config) is None


def test_watcher_warns_once_per_restart_change(clean_env, tmp_path, capsys):
    path, running, watcher = _start_watcher(tmp_path, {"race_id": 111})
    _edit_config(path, {"race_id": 222})
    _settle(watcher, running)
    capsys.readouterr()

    _edit_config(path, {"race_id": 222, "scroll_speed": 150})
    result = _settle(watcher, running)

    assert result.restart_required == ["race_id"]
    assert result.changed == ["scroll_speed"]
    assert "requires restart" not in capsys.readouterr().err


def test_watcher_clears_restart_required_when_file_reverts(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"race_id": 111})
    _edit_config(path, {"race_id": 222})
    assert _settle(watcher, running).restart_required == ["race_id"]

    _edit_config(path, {"race_id": 111})
    result = _settle(watcher, running)

    assert result.restart_required == []
    assert result.changed == []


def test_watcher_ignores_interactively_chosen_race_id(clean_env, tmp_path):
    path, running, watcher = _start_watcher(tmp_path, {"scroll_speed": 150})
    running = {**running, "race_id": "999"}
    _edit_config(path, {"scroll_speed": 200})

    result = _settle(watcher, running)

    assert result.restart_required == []
    assert result.config["race_id"] == "999"
