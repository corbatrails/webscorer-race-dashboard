import os

import pytest
import yaml

import config
from config import (
    OPTIONS,
    ConfigConflict,
    ConfigError,
    ConfigValidationError,
    read_config_snapshot,
    resolve_config,
    save_config,
)

SECRETS = {"api_id": "12345", "api_token": "abc123de"}

COMMENTED = """\
# Operator notes for race day.
refresh_interval: 30  # keep polling gentle
color_scheme: dark
operator_note: bring spare HDMI cable
"""


@pytest.fixture
def cfg_path(tmp_path):
    path = tmp_path / "dir with spaces" / "config.yaml"
    path.parent.mkdir()
    path.write_text(COMMENTED, encoding="utf-8")
    return path


def _leftover_temp_files(path):
    return [name for name in os.listdir(path.parent) if name != path.name]


def test_snapshot_returns_resolved_settings_and_revision(cfg_path):
    settings, revision = read_config_snapshot(str(cfg_path), SECRETS)
    assert settings["refresh_interval"] == 30
    assert settings["scroll_speed"] == 100
    assert settings["api_token"] == "abc123de"
    assert len(revision) == 64

    cfg_path.write_text(COMMENTED + "scroll_speed: 120\n", encoding="utf-8")
    assert read_config_snapshot(str(cfg_path), SECRETS)[1] != revision


def test_save_preserves_comments_unknown_keys_and_all_options(cfg_path):
    _, revision = read_config_snapshot(str(cfg_path), SECRETS)
    saved = save_config(str(cfg_path), {"scroll_speed": "150"}, SECRETS, expected_revision=revision)

    text = cfg_path.read_text(encoding="utf-8")
    assert "# Operator notes for race day." in text
    assert "# keep polling gentle" in text
    data = yaml.safe_load(text)
    assert data["operator_note"] == "bring spare HDMI cable"
    assert data["scroll_speed"] == 150
    assert data["refresh_interval"] == 30
    assert {o.key for o in OPTIONS} <= data.keys()
    assert saved["scroll_speed"] == 150
    assert saved["api_id"] == "12345"
    assert _leftover_temp_files(cfg_path) == []


def test_save_creates_missing_file_with_all_options(tmp_path):
    path = tmp_path / "new.yaml"
    save_config(str(path), {"color_scheme": "light"}, SECRETS)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["color_scheme"] == "light"
    assert {o.key for o in OPTIONS} == set(data)


def test_save_never_writes_secrets_from_existing_file(cfg_path):
    cfg_path.write_text(COMMENTED + "api_token: leaked\n", encoding="utf-8")
    save_config(str(cfg_path), {"scroll_speed": 120}, SECRETS)
    assert "leaked" not in cfg_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("updates,field", [
    ({"show_summary": "yes"}, "show_summary"),
    ({"show_toasts": 1}, "show_toasts"),
    ({"color_scheme": "neon"}, "color_scheme"),
    ({"overall_results_layout": "wide"}, "overall_results_layout"),
    ({"source": "ftp"}, "source"),
    ({"scroll_speed": "1.5"}, "scroll_speed"),
    ({"refresh_interval": 0}, "refresh_interval"),
    ({"summary_display_time": 0}, "summary_display_time"),
    ({"scroll_speed": 0}, "scroll_speed"),
    ({"chart_bucket_minutes": 0}, "chart_bucket_minutes"),
    ({"scroll_pause_time": -1}, "scroll_pause_time"),
    ({"pinned_leaders": -1}, "pinned_leaders"),
    ({"data_file": "does-not-exist.json"}, "data_file"),
    ({"source": "csv"}, "data_file"),
])
def test_rejects_invalid_values_without_writing(cfg_path, updates, field):
    before = cfg_path.read_bytes()
    with pytest.raises(ConfigValidationError) as exc:
        save_config(str(cfg_path), updates, SECRETS)
    assert field in exc.value.errors
    assert cfg_path.read_bytes() == before
    assert _leftover_temp_files(cfg_path) == []


def test_reports_every_invalid_field(cfg_path):
    with pytest.raises(ConfigValidationError) as exc:
        save_config(str(cfg_path), {"scroll_speed": "fast", "show_summary": "maybe"}, SECRETS)
    assert set(exc.value.errors) == {"scroll_speed", "show_summary"}


def test_webscorer_without_file_requires_credentials(cfg_path):
    with pytest.raises(ConfigValidationError) as exc:
        save_config(str(cfg_path), {"race_id": "999"}, {"api_id": None, "api_token": None})
    assert "WEBSCORER_API_ID" in exc.value.errors["api_id"]


def test_save_failure_is_atomic(cfg_path, monkeypatch):
    before = cfg_path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(config.os, "replace", boom)
    with pytest.raises(ConfigError, match="disk full"):
        save_config(str(cfg_path), {"scroll_speed": 120}, SECRETS)
    assert cfg_path.read_bytes() == before
    assert _leftover_temp_files(cfg_path) == []


def test_stale_revision_preserves_external_edit(cfg_path):
    _, revision = read_config_snapshot(str(cfg_path), SECRETS)
    external = (COMMENTED + "scroll_speed: 175\n").encode("utf-8")
    cfg_path.write_bytes(external)
    with pytest.raises(ConfigConflict):
        save_config(str(cfg_path), {"scroll_speed": 120}, SECRETS, expected_revision=revision)
    assert cfg_path.read_bytes() == external


def test_edit_during_save_is_detected(cfg_path, monkeypatch):
    external = (COMMENTED + "scroll_speed: 175\n").encode("utf-8")
    real_fsync = config.os.fsync

    def fsync_then_external_edit(fd):
        real_fsync(fd)
        cfg_path.write_bytes(external)

    monkeypatch.setattr(config.os, "fsync", fsync_then_external_edit)
    with pytest.raises(ConfigConflict):
        save_config(str(cfg_path), {"scroll_speed": 120}, SECRETS)
    assert cfg_path.read_bytes() == external
    assert _leftover_temp_files(cfg_path) == []


@pytest.mark.parametrize("field", ["api_token", "api_id", "ADMIN_PASSWORD", "WEBSCORER_API_TOKEN", "operator_note"])
def test_secrets_and_unknown_fields_cannot_be_submitted(cfg_path, field):
    before = cfg_path.read_bytes()
    with pytest.raises(ConfigValidationError) as exc:
        save_config(str(cfg_path), {field: "s3cret-value"}, SECRETS)
    assert field in exc.value.errors
    assert "s3cret-value" not in str(exc.value)
    assert "s3cret-value" not in " ".join(exc.value.errors.values())
    assert cfg_path.read_bytes() == before


def test_malformed_existing_file_is_not_overwritten(cfg_path):
    cfg_path.write_text("refresh_interval: [unclosed\n", encoding="utf-8")
    before = cfg_path.read_bytes()
    with pytest.raises(ConfigError):
        save_config(str(cfg_path), {"scroll_speed": 120}, SECRETS)
    assert cfg_path.read_bytes() == before


def test_resolve_config_fills_defaults_and_secrets():
    cfg = resolve_config({"scroll_speed": 120}, SECRETS)
    assert cfg["scroll_speed"] == 120
    assert cfg["refresh_interval"] == 60
    assert cfg["api_id"] == "12345"


def test_resolve_config_accepts_text_booleans_and_numbers():
    cfg = resolve_config({"show_summary": "False", "pinned_leaders": "0", "race_id": 4242}, SECRETS)
    assert cfg["show_summary"] is False
    assert cfg["pinned_leaders"] == 0
    assert cfg["race_id"] == "4242"

def test_save_round_trips_committed_config_except_changed_line(tmp_path):
    repo_config = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    original = open(repo_config, encoding="utf-8").read()
    path = tmp_path / "config.yaml"
    path.write_text(original, encoding="utf-8")
    save_config(str(path), {"scroll_speed": 120}, SECRETS)
    before = original.splitlines()
    after = path.read_text(encoding="utf-8").splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after)
    assert changed == [("scroll_speed: 100", "scroll_speed: 120")]
