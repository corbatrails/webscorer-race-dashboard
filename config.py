import os
import sys
from collections import namedtuple

import yaml
from dotenv import find_dotenv, load_dotenv

from providers import get_provider, provider_names


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


def _parse_source(value):
    value = str(value).strip().lower()
    if value not in provider_names():
        raise ValueError(f"expected one of: {', '.join(provider_names())}")
    return value


# reload: "live" options can change mid-run (Phase 4); "restart" options are
# consumed once at startup and need a restart to change.
Option = namedtuple("Option", "key default parse reload")

OPTIONS = (
    Option("source", "webscorer", _parse_source, "restart"),
    Option("race_id", None, _parse_optional_str, "restart"),
    Option("data_file", None, _parse_optional_str, "restart"),
    Option("refresh_interval", 60, _parse_refresh_interval, "live"),
    Option("summary_display_time", 20, _parse_int, "live"),
    Option("scroll_speed", 100, _parse_int, "live"),
    Option("scroll_pause_time", 2, _parse_int, "live"),
    Option("pinned_leaders", 3, _parse_int, "live"),
    Option("show_summary", True, _parse_bool, "live"),
    Option("show_overall_results", True, _parse_bool, "live"),
    Option("show_category_results", True, _parse_bool, "live"),
    Option("show_demographics", False, _parse_bool, "live"),
    Option("pinned_leaders_on_overall_results", False, _parse_bool, "live"),
    Option("overall_results_layout", "standard", _parse_layout, "live"),
    Option("display_unfinished_in_category", False, _parse_bool, "live"),
    Option("display_unfinished_in_overall", False, _parse_bool, "live"),
    Option("chart_bucket_minutes", 15, _parse_int, "live"),
    Option("color_scheme", "dark", _parse_color_scheme, "live"),
    Option("show_toasts", True, _parse_bool, "live"),
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


def _resolve_option(opt, yaml_data, yaml_name):
    """config.yaml value, else the built-in default. The environment is never consulted."""
    raw = yaml_data.get(opt.key)
    if raw is None:
        return opt.default
    try:
        return opt.parse(raw)
    except ValueError as e:
        raise ConfigError(f"Invalid value {raw!r} for '{opt.key}' (from {yaml_name}): {e}")


def load_config(config_path=None, env_path=None):
    env_path = env_path or find_dotenv()
    load_dotenv(env_path)
    config_path = config_path or DEFAULT_CONFIG_PATH
    yaml_name = os.path.basename(config_path)
    try:
        yaml_data = _read_yaml(config_path)
        _check_yaml_keys(yaml_data, config_path)
        values = {opt.key: _resolve_option(opt, yaml_data, yaml_name) for opt in OPTIONS}
    except ConfigError as e:
        _fail(str(e))

    data_file = values["data_file"]
    provider = get_provider(values["source"])
    api_id = os.environ.get("WEBSCORER_API_ID")
    api_token = os.environ.get("WEBSCORER_API_TOKEN")

    if data_file:
        if not os.path.isfile(data_file):
            print(f"ERROR: DATA_FILE '{data_file}' not found.")
            sys.exit(1)
    elif provider.requires_data_file:
        _fail(f"source '{provider.name}' requires data_file.")
    else:
        for env_var in provider.required_secrets.values():
            if not os.environ.get(env_var):
                _fail(f"{env_var} is required. Set it in .env file.")

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

    Secrets are not re-read; they keep their startup values.
    """

    def __init__(self, config_path=None):
        self.path = config_path or DEFAULT_CONFIG_PATH
        self._applied = _signature(self.path)
        self._candidate = None
        self._last_error = None
        self._pending = []
        self._baseline = self._file_restart_values()

    def _file_restart_values(self):
        """Restart-key values config.yaml resolves to now, or None if it cannot be read."""
        try:
            yaml_data = _read_yaml(self.path)
            name = os.path.basename(self.path)
            return {
                opt.key: _resolve_option(opt, yaml_data, name)
                for opt in OPTIONS if opt.reload == "restart"
            }
        except ConfigError:
            return None

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
        try:
            result = self._reload(running)
        except ConfigError as e:
            if str(e) != self._last_error:
                self._last_error = str(e)
                _warn(f"Ignoring {os.path.basename(self.path)} edit, keeping previous settings: {e}")
            return None
        self._last_error = None
        return result

    def _reload(self, running):
        yaml_data = _read_yaml(self.path)
        _check_yaml_keys(yaml_data, self.path)
        yaml_name = os.path.basename(self.path)
        resolved = {opt.key: _resolve_option(opt, yaml_data, yaml_name) for opt in OPTIONS}
        live = {opt.key: resolved[opt.key] for opt in OPTIONS if opt.reload == "live"}
        changed = [key for key, value in live.items() if running.get(key) != value]
        restart_keys = [opt.key for opt in OPTIONS if opt.reload == "restart"]
        if self._baseline is None:
            self._baseline = {key: running.get(key) for key in restart_keys}
        pending = sorted(key for key in restart_keys if resolved[key] != self._baseline[key])
        newly_pending = [key for key in pending if key not in self._pending]
        if newly_pending:
            _warn(f"{', '.join(newly_pending)} changed in {yaml_name} and requires restart.")
        pending_changed = pending != self._pending
        self._pending = pending
        if not changed and not pending_changed:
            return None
        return Reload({**running, **live}, changed, pending)
