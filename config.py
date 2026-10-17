import os
import sys
from collections import namedtuple

import yaml
from dotenv import find_dotenv, load_dotenv


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
    Option("refresh_interval", "REFRESH_INTERVAL", 60, _parse_int, "restart"),
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


def _read_yaml(path):
    if not path or not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_option(opt, yaml_data):
    """Environment (process env, then .env) > config.yaml > built-in default."""
    raw = os.environ.get(opt.env)
    if raw is not None and raw.strip() != "":
        return opt.parse(raw)
    if yaml_data.get(opt.key) is not None:
        return opt.parse(yaml_data[opt.key])
    return opt.default


def load_config(config_path=None, env_path=None):
    env_path = env_path or find_dotenv()
    load_dotenv(env_path)
    yaml_data = _read_yaml(config_path or DEFAULT_CONFIG_PATH)

    values = {opt.key: _resolve_option(opt, yaml_data) for opt in OPTIONS}

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
