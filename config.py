import os
import sys
from collections import namedtuple

import yaml
from dotenv import dotenv_values, find_dotenv, load_dotenv


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

# Secrets are read from the environment (.env) only, never from config.yaml.
SECRET_ENV_VARS = ("WEBSCORER_API_ID", "WEBSCORER_API_TOKEN")

_OVERALL_RESULTS_LAYOUTS = {"standard", "detailed"}
_COLOR_SCHEMES = {"dark", "light"}


def _normalize_overall_results_layout(value):
    value = (value or "standard").strip().lower()
    if value in _OVERALL_RESULTS_LAYOUTS:
        return value
    return "standard"


def _parse_int(value):
    if isinstance(value, bool):
        raise ValueError("expected a whole number")
    if isinstance(value, int):
        return value
    return int(str(value).strip())


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    raise ValueError("expected true or false")


def _parse_refresh_interval(value):
    seconds = _parse_int(value)
    if seconds < 1:
        raise ValueError("expected a whole number of at least 1")
    return seconds


def _parse_optional_str(value):
    return str(value).strip() or None


def _parse_layout(value):
    return _normalize_overall_results_layout(str(value))


def _parse_color_scheme(value):
    value = str(value).strip().lower()
    return value if value in _COLOR_SCHEMES else "dark"


# reload: "live" options can change mid-run (Phase 4); "restart" options are
# consumed once at startup and need a restart to change.
Option = namedtuple("Option", "key env default parse reload")

OPTIONS = (
    Option("race_id", "WEBSCORER_RACE_ID", None, _parse_optional_str, "restart"),
    Option("data_file", "DATA_FILE", None, _parse_optional_str, "restart"),
    Option("refresh_interval", "REFRESH_INTERVAL", 60, _parse_refresh_interval, "restart"),
    Option("summary_display_time", "SUMMARY_DISPLAY_TIME", 20, _parse_int, "live"),
    Option("scroll_speed", "SCROLL_SPEED", 100, _parse_int, "live"),
    Option("scroll_pause_time", "SCROLL_PAUSE_TIME", 2, _parse_int, "live"),
    Option("pinned_leaders", "PINNED_LEADERS", 3, _parse_int, "live"),
    Option("show_summary", "SHOW_SUMMARY", True, _parse_bool, "live"),
    Option("show_overall_results", "SHOW_OVERALL_RESULTS", True, _parse_bool, "live"),
    Option("show_category_results", "SHOW_CATEGORY_RESULTS", True, _parse_bool, "live"),
    Option("show_demographics", "SHOW_DEMOGRAPHICS", False, _parse_bool, "live"),
    Option("pinned_leaders_on_overall_results", "PINNED_LEADERS_ON_OVERALL_RESULTS", False, _parse_bool, "live"),
    Option("overall_results_layout", "OVERALL_RESULTS_LAYOUT", "standard", _parse_layout, "live"),
    Option("display_unfinished_in_category", "DISPLAY_UNFINISHED_IN_CATEGORY", False, _parse_bool, "live"),
    Option("display_unfinished_in_overall", "DISPLAY_UNFINISHED_IN_OVERALL", False, _parse_bool, "live"),
    Option("chart_bucket_minutes", "CHART_BUCKET_MINUTES", 15, _parse_int, "live"),
    Option("color_scheme", "COLOR_SCHEME", "dark", _parse_color_scheme, "live"),
    Option("show_toasts", "SHOW_TOASTS", True, _parse_bool, "live"),
)


class ConfigError(Exception):
    """A config source is unreadable or holds an invalid value."""


def _fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


def _warn(message):
    print(f"WARNING: {message}", file=sys.stderr)


def _read_yaml(path):
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Could not parse {os.path.basename(path)}: {e}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{os.path.basename(path)} must be a mapping of option names to values.")
    return data


def _check_yaml_keys(yaml_data, path):
    known = {opt.key for opt in OPTIONS}
    secret_names = {"api_id", "api_token"} | {name.lower() for name in SECRET_ENV_VARS}
    name = os.path.basename(path)
    for key in yaml_data:
        if str(key).lower() in secret_names:
            _warn(f"{name} contains '{key}', which is ignored. Secrets belong in .env only.")
        elif key not in known:
            _warn(f"{name} contains unknown option '{key}', which is ignored.")


def _warn_legacy_dotenv(env_path):
    """Non-secret settings in .env still apply (as overrides) but are deprecated."""
    if not env_path or not os.path.isfile(env_path):
        return
    env_names = {opt.env for opt in OPTIONS}
    legacy = [k for k, v in dotenv_values(env_path).items() if k in env_names and (v or "").strip()]
    if legacy:
        _warn(
            f"Non-secret settings found in .env are deprecated ({', '.join(legacy)}). "
            "They still apply and override config.yaml; move them to config.yaml "
            "so .env only holds WEBSCORER_API_ID and WEBSCORER_API_TOKEN."
        )


def _resolve_option(opt, yaml_data, yaml_name):
    """Environment (process env, then .env) > config.yaml > built-in default."""
    raw = os.environ.get(opt.env)
    source = opt.env
    if raw is None or raw.strip() == "":
        raw = yaml_data.get(opt.key)
        source = yaml_name
    if raw is None:
        return opt.default
    try:
        return opt.parse(raw)
    except ValueError as e:
        raise ConfigError(f"Invalid value {raw!r} for '{opt.key}' (from {source}): {e}")


def load_config(config_path=None, env_path=None):
    env_path = env_path or find_dotenv()
    load_dotenv(env_path)
    config_path = config_path or DEFAULT_CONFIG_PATH
    yaml_name = os.path.basename(config_path)
    try:
        yaml_data = _read_yaml(config_path)
        _check_yaml_keys(yaml_data, config_path)
        _warn_legacy_dotenv(env_path)
        values = {opt.key: _resolve_option(opt, yaml_data, yaml_name) for opt in OPTIONS}
    except ConfigError as e:
        _fail(str(e))

    data_file = values["data_file"]
    api_id = os.environ.get("WEBSCORER_API_ID")
    api_token = os.environ.get("WEBSCORER_API_TOKEN")

    if data_file:
        if not os.path.isfile(data_file):
            print(f"ERROR: DATA_FILE '{data_file}' not found.")
            sys.exit(1)
    else:
        if not api_id:
            print("ERROR: WEBSCORER_API_ID is required. Set it in .env file.")
            sys.exit(1)
        if not api_token:
            print("ERROR: WEBSCORER_API_TOKEN is required. Set it in .env file.")
            sys.exit(1)

    return {"api_id": api_id, "api_token": api_token, **values}


Reload = namedtuple("Reload", "config changed restart_required")


def _signature(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class ConfigWatcher:
    """Detects config.yaml edits and builds a validated replacement config.

    The environment layer and secrets are not re-read; they keep their startup values.
    """

    def __init__(self, config_path=None):
        self.path = config_path or DEFAULT_CONFIG_PATH
        self._applied = _signature(self.path)
        self._candidate = None

    def check(self, running):
        """One watch tick. Returns a Reload when a settled edit changes the config, else None."""
        sig = _signature(self.path)
        if sig is None or sig == self._applied:
            self._candidate = None
            return None
        if sig != self._candidate:
            self._candidate = sig
            return None
        self._applied, self._candidate = sig, None
        return self._reload(running)

    def _reload(self, running):
        yaml_data = _read_yaml(self.path)
        _check_yaml_keys(yaml_data, self.path)
        yaml_name = os.path.basename(self.path)
        resolved = {opt.key: _resolve_option(opt, yaml_data, yaml_name) for opt in OPTIONS}
        live = {opt.key: resolved[opt.key] for opt in OPTIONS if opt.reload == "live"}
        changed = [key for key, value in live.items() if running.get(key) != value]
        if not changed:
            return None
        return Reload({**running, **live}, changed, [])
