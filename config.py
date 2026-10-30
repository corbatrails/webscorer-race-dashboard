import hashlib
import io
import os
import sys
import tempfile
from collections import namedtuple

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from dotenv import find_dotenv, load_dotenv

from providers import get_provider, provider_names


DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

# Secrets are read from the environment (.env) only, never from config.yaml.
SECRET_ENV_VARS = ("WEBSCORER_API_ID", "WEBSCORER_API_TOKEN", "ADMIN_PASSWORD")

_OVERALL_RESULTS_LAYOUTS = ("standard", "detailed")
_COLOR_SCHEMES = ("dark", "light")


def _parse_int(value, minimum=None):
    if isinstance(value, bool):
        raise ValueError("expected a whole number")
    if isinstance(value, int):
        number = value
    else:
        try:
            number = int(str(value).strip())
        except ValueError:
            raise ValueError("expected a whole number") from None
    if minimum is not None and number < minimum:
        raise ValueError(f"expected a whole number of at least {minimum}")
    return number


def _int_at_least(minimum):
    def parse(value):
        return _parse_int(value, minimum)
    parse.minimum = minimum
    return parse


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError("expected true or false")


def _parse_optional_str(value):
    return str(value).strip() or None


def _parse_choice(choices):
    def parse(value):
        text = str(value).strip().lower()
        if text not in choices:
            raise ValueError(f"expected one of: {', '.join(choices)}")
        return text
    parse.choices = tuple(choices)
    return parse


def _parse_source(value):
    return _parse_choice(tuple(provider_names()))(value)


def option_choices(opt):
    """Allowed values for a choice option, or None for free-form options."""
    if opt.parse is _parse_source:
        return tuple(provider_names())
    return getattr(opt.parse, "choices", None)


def option_minimum(opt):
    """Smallest allowed value for an integer option, or None."""
    return getattr(opt.parse, "minimum", None)


# Every option applies while the app runs, including source, race_id and data_file.
Option = namedtuple("Option", "key default parse")

OPTIONS = (
    Option("source", "webscorer", _parse_source),
    Option("race_id", None, _parse_optional_str),
    Option("data_file", None, _parse_optional_str),
    Option("refresh_interval", 60, _int_at_least(1)),
    Option("summary_display_time", 20, _int_at_least(1)),
    Option("scroll_speed", 100, _int_at_least(1)),
    Option("scroll_pause_time", 2, _int_at_least(0)),
    Option("pinned_leaders", 3, _int_at_least(0)),
    Option("show_summary", True, _parse_bool),
    Option("show_overall_results", True, _parse_bool),
    Option("show_category_results", True, _parse_bool),
    Option("show_demographics", False, _parse_bool),
    Option("pinned_leaders_on_overall_results", False, _parse_bool),
    Option("overall_results_layout", "standard", _parse_choice(_OVERALL_RESULTS_LAYOUTS)),
    Option("display_unfinished_in_category", False, _parse_bool),
    Option("display_unfinished_in_overall", False, _parse_bool),
    Option("chart_bucket_minutes", 15, _int_at_least(1)),
    Option("color_scheme", "dark", _parse_choice(_COLOR_SCHEMES)),
    Option("show_toasts", True, _parse_bool),
)


class ConfigError(Exception):
    """A config source is unreadable or holds an invalid value."""


class ConfigValidationError(ConfigError):
    """One or more settings are invalid; ``errors`` maps field name to a message."""

    def __init__(self, errors):
        self.errors = dict(errors)
        super().__init__("; ".join(f"{key}: {msg}" for key, msg in self.errors.items()))


class ConfigConflict(ConfigError):
    """The config file changed since the caller read it."""


_SECRET_FIELD_NAMES = {"api_id", "api_token", "admin_password"} | {name.lower() for name in SECRET_ENV_VARS}


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
    name = os.path.basename(path)
    for key in yaml_data:
        if str(key).lower() in _SECRET_FIELD_NAMES:
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


def resolve_config(yaml_data, secrets):
    """Validate YAML option values plus provider requirements; return the full config.

    ``secrets`` holds the startup credentials (``api_id``, ``api_token``); the
    environment is not read here. Raises ConfigValidationError listing every bad field.
    """
    errors = {}
    values = {}
    for opt in OPTIONS:
        raw = yaml_data.get(opt.key)
        if raw is None:
            values[opt.key] = opt.default
            continue
        try:
            values[opt.key] = opt.parse(raw)
        except ValueError as e:
            errors[opt.key] = str(e)

    if "source" not in errors and "data_file" not in errors:
        provider = get_provider(values["source"])
        data_file = values["data_file"]
        if data_file:
            if not os.path.isfile(data_file):
                errors["data_file"] = f"file not found: {data_file}"
        elif provider.requires_data_file:
            errors["data_file"] = f"source '{provider.name}' requires data_file"
        else:
            for key, env_var in provider.required_secrets.items():
                if not secrets.get(key):
                    errors[key] = f"{env_var} is required. Set it in .env file."
    if errors:
        raise ConfigValidationError(errors)
    return {"api_id": secrets.get("api_id"), "api_token": secrets.get("api_token"), **values}


def _format_validation_errors(errors, yaml_name):
    option_keys = {opt.key for opt in OPTIONS}
    return [
        f"Invalid value for '{key}' in {yaml_name}: {msg}" if key in option_keys else msg
        for key, msg in errors.items()
    ]


def load_config(config_path=None, env_path=None):
    env_path = env_path or find_dotenv()
    load_dotenv(env_path)
    config_path = config_path or DEFAULT_CONFIG_PATH
    yaml_name = os.path.basename(config_path)
    secrets = {
        "api_id": os.environ.get("WEBSCORER_API_ID"),
        "api_token": os.environ.get("WEBSCORER_API_TOKEN"),
    }
    try:
        yaml_data = _read_yaml(config_path)
        _check_yaml_keys(yaml_data, config_path)
        return resolve_config(yaml_data, secrets)
    except ConfigValidationError as e:
        for line in _format_validation_errors(e.errors, yaml_name):
            print(f"ERROR: {line}")
        sys.exit(1)
    except ConfigError as e:
        _fail(str(e))


def _read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return b""
    except OSError as e:
        raise ConfigError(f"Could not read {os.path.basename(path)}: {e}")


def _revision(data):
    return hashlib.sha256(data).hexdigest()


def _parse_mapping(data, path):
    name = os.path.basename(path)
    try:
        parsed = yaml.safe_load(data.decode("utf-8")) if data else None
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise ConfigError(f"Could not parse {name}: {e}")
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError(f"{name} must be a mapping of option names to values.")
    return parsed


def config_revision(config_path):
    """Revision of the file's current bytes, readable even when its contents are invalid."""
    return _revision(_read_bytes(config_path))


def read_config_snapshot(config_path, secrets):
    """Return (resolved config, revision) for the file's current bytes."""
    data = _read_bytes(config_path)
    return resolve_config(_parse_mapping(data, config_path), secrets), _revision(data)


def _round_trip_yaml():
    rt = YAML()
    rt.preserve_quotes = True
    rt.indent(mapping=2, sequence=4, offset=2)
    rt.representer.add_representer(
        type(None), lambda rep, _: rep.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return rt


def save_config(config_path, updates, secrets, *, expected_revision=None):
    """Validate ``updates`` against the file and atomically write it.

    Comments and unknown non-secret keys survive; secret keys are dropped; every
    supported option is present afterwards. Raises ConfigConflict when the file no
    longer matches ``expected_revision`` (or changes while saving).
    """
    option_keys = {opt.key: opt for opt in OPTIONS}
    errors = {}
    for key in updates:
        if str(key).lower() in _SECRET_FIELD_NAMES:
            errors[key] = "secrets cannot be changed here; set them in .env"
        elif key not in option_keys:
            errors[key] = "unknown option"
    if errors:
        raise ConfigValidationError(errors)

    original = _read_bytes(config_path)
    revision = _revision(original)
    if expected_revision is not None and expected_revision != revision:
        raise ConfigConflict(f"{os.path.basename(config_path)} changed since it was loaded")

    rt = _round_trip_yaml()
    try:
        doc = rt.load(original.decode("utf-8")) if original else None
    except Exception as e:
        raise ConfigError(f"Could not parse {os.path.basename(config_path)}: {e}")
    if doc is None:
        doc = CommentedMap()
    if not isinstance(doc, dict):
        raise ConfigError(f"{os.path.basename(config_path)} must be a mapping of option names to values.")

    for key in [k for k in doc if str(k).lower() in _SECRET_FIELD_NAMES]:
        del doc[key]
    for key, value in updates.items():
        doc[key] = value
    for opt in OPTIONS:
        if opt.key not in doc:
            doc[opt.key] = opt.default

    resolved = resolve_config(dict(doc), secrets)
    for key in updates:
        doc[key] = resolved[key]

    stream = io.StringIO()
    rt.dump(doc, stream)
    directory = os.path.dirname(os.path.abspath(config_path))
    fd, tmp_path = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(stream.getvalue())
            f.flush()
            os.fsync(f.fileno())
        if _revision(_read_bytes(config_path)) != revision:
            raise ConfigConflict(f"{os.path.basename(config_path)} changed while saving")
        try:
            os.replace(tmp_path, config_path)
        except OSError as e:
            raise ConfigError(f"Could not save {os.path.basename(config_path)}: {e}")
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    return resolved


Reload = namedtuple("Reload", "config changed")


def _signature(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class ConfigWatcher:
    """Detects config file edits and builds a validated replacement config.

    Secrets are not re-read; they keep their startup values.
    """

    def __init__(self, config_path=None):
        self.path = config_path or DEFAULT_CONFIG_PATH
        self._applied = _signature(self.path)
        self._candidate = None
        self._last_error = None

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
        except ConfigValidationError as e:
            message = "; ".join(_format_validation_errors(e.errors, os.path.basename(self.path)))
            return self._report(message)
        except ConfigError as e:
            return self._report(str(e))
        self._last_error = None
        return result

    def _report(self, message):
        if message != self._last_error:
            self._last_error = message
            _warn(f"Ignoring {os.path.basename(self.path)} edit, keeping previous settings: {message}")
        return None

    def _reload(self, running):
        yaml_data = _read_yaml(self.path)
        _check_yaml_keys(yaml_data, self.path)
        secrets = {"api_id": running.get("api_id"), "api_token": running.get("api_token")}
        resolved = resolve_config(yaml_data, secrets)
        changed = [opt.key for opt in OPTIONS if running.get(opt.key) != resolved[opt.key]]
        if not changed:
            return None
        return Reload({**running, **resolved}, changed)
