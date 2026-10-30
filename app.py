import argparse
import os
import sys
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from data_processing import process_race_data, build_pages, build_finish_chart_data, build_demographics_data
from providers import get_provider
from config import (
    DEFAULT_CONFIG_PATH,
    OPTIONS,
    ConfigWatcher,
    load_config,
    read_config_snapshot,
    save_config,
)

_EMPTY_RACE = {
    "pages": [],
    "last_refresh": None,
    "is_stale": False,
    "waiting": True,
    "error": None,
    "race_name": "",
    "race_date": "",
    "race_sport": "",
    "finish_chart": None,
}
_cache = dict(_EMPTY_RACE)
_cache_lock = threading.Lock()
# Set when refresh_interval changes (or a race switch needs a poll) so the poll loop re-reads it.
_config_changed = threading.Event()


def _race_identity(cfg):
    return (cfg.get("source", "webscorer"), cfg.get("race_id"), cfg.get("data_file"))


def race_selection_required(cfg):
    """True when a live provider is configured but no race has been chosen yet."""
    try:
        provider = _provider_for(cfg)
    except Exception:
        return False
    return bool(provider.list_races) and not cfg.get("data_file") and not cfg.get("race_id")


def _apply_config(app, new_config, changed):
    """Swap in a new config; the caller holds the settings lock. Dicts are never mutated in place."""
    with _cache_lock:
        old = app.config["dashboard"]
        state = app.config["dashboard_state"]
        race_changed = _race_identity(old) != _race_identity(new_config)
        generation = state["race_generation"] + (1 if race_changed else 0)
        if race_changed:
            _cache.update(_EMPTY_RACE)
        app.config["dashboard"] = new_config
        app.config["dashboard_state"] = {
            "config_version": state["config_version"] + (1 if changed else 0),
            "race_generation": generation,
        }
    if race_changed:
        app.extensions["dashboard_poll_now"].set()
        _config_changed.set()
    elif old.get("refresh_interval") != new_config.get("refresh_interval"):
        _config_changed.set()
    if not race_selection_required(new_config):
        app.extensions["startup_race_selected"].set()


def apply_config_reload(app, reload):
    with app.extensions["dashboard_settings_lock"]:
        _apply_config(app, reload.config, reload.changed)


def update_dashboard(app, updates, *, expected_revision=None, startup_only=False):
    """Validate, save and apply settings in one serialized step.

    Returns False when ``startup_only`` and a race is already selected (in memory or
    in the file). Validation, conflict and write errors raise ConfigError subclasses.
    """
    with app.extensions["dashboard_settings_lock"]:
        active = app.config["dashboard"]
        secrets = {"api_id": active.get("api_id"), "api_token": active.get("api_token")}
        path = app.config["dashboard_config_path"]
        if startup_only:
            if app.extensions["startup_race_selected"].is_set() or not race_selection_required(active):
                return False
            persisted, _ = read_config_snapshot(path, secrets)
            if not race_selection_required(persisted):
                return False
        saved = save_config(path, updates, secrets, expected_revision=expected_revision)
        changed = [opt.key for opt in OPTIONS if active.get(opt.key) != saved[opt.key]]
        _apply_config(app, {**active, **saved}, changed)
        return True


def create_app(config=None, start_polling=True, *, config_path=None):
    app = Flask(__name__)
    app.config["dashboard"] = config or {}
    app.config["dashboard_config_path"] = os.path.abspath(config_path or DEFAULT_CONFIG_PATH)
    app.config["dashboard_state"] = {"config_version": 1, "race_generation": 1}
    app.extensions["dashboard_settings_lock"] = threading.RLock()
    app.extensions["dashboard_poll_now"] = threading.Event()
    app.extensions["startup_race_selected"] = threading.Event()
    if not race_selection_required(app.config["dashboard"]):
        app.extensions["startup_race_selected"].set()
    _start_time = int(time.time())

    @app.route("/")
    def index():
        color_scheme = app.config["dashboard"].get("color_scheme", "dark")
        return render_template("dashboard.html", cache_bust=_start_time, color_scheme=color_scheme)

    @app.route("/api/data")
    def api_data():
        with _cache_lock:
            cfg = app.config["dashboard"]
            state = app.config["dashboard_state"]
            return jsonify({
                "pages": _cache["pages"],
                "last_refresh": _cache["last_refresh"],
                "is_stale": _cache["is_stale"],
                "waiting": _cache["waiting"],
                "error": _cache["error"],
                "race_name": _cache["race_name"],
                "race_date": _cache["race_date"],
                "race_sport": _cache["race_sport"],
                "finish_chart": _cache["finish_chart"],
                "summary_display_time": cfg.get("summary_display_time", 20),
                "scroll_speed": cfg.get("scroll_speed", 100),
                "scroll_pause_time": cfg.get("scroll_pause_time", 2),
                "pinned_leaders": cfg.get("pinned_leaders", 3),
                "show_summary": cfg.get("show_summary", True),
                "show_demographics": cfg.get("show_demographics", False),
                "chart_bucket_minutes": cfg.get("chart_bucket_minutes", 15),
                "show_toasts": cfg.get("show_toasts", True),
                "overall_results_layout": cfg.get("overall_results_layout", "standard"),
                "display_unfinished_in_category": cfg.get("display_unfinished_in_category", False),
                "display_unfinished_in_overall": cfg.get("display_unfinished_in_overall", False),
                "pinned_leaders_on_overall_results": cfg.get("pinned_leaders_on_overall_results", False),
                "color_scheme": cfg.get("color_scheme", "dark"),
                "refresh_interval": cfg.get("refresh_interval", 60),
                "config_version": state["config_version"],
                "race_generation": state["race_generation"],
                "race_selection_required": race_selection_required(cfg),
            })

    if start_polling:
        _start_polling(app)

    return app


def _start_polling(app, sleep_first=False):
    t = threading.Thread(target=_poll_loop, args=(app, sleep_first), daemon=True)
    t.start()


def _provider_for(cfg):
    return get_provider(cfg.get("source", "webscorer"))


def _secrets_for(provider, cfg):
    return {key: cfg.get(key) for key in provider.required_secrets}


def poll_once(app):
    with _cache_lock:
        cfg = app.config["dashboard"]
        generation = app.config["dashboard_state"]["race_generation"]
    if race_selection_required(cfg):
        return
    try:
        provider = _provider_for(cfg)
        raw = provider.fetch(cfg, _secrets_for(provider, cfg))
        snapshot = provider.normalize(raw)
        data = process_race_data(
            snapshot,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
        demographics = build_demographics_data(snapshot)
        pages = build_pages(data, demographics)
        finish_chart = build_finish_chart_data(snapshot, cfg.get("chart_bucket_minutes", 15))
        with _cache_lock:
            if app.config["dashboard_state"]["race_generation"] != generation:
                return
            _cache["pages"] = pages
            _cache["last_refresh"] = datetime.now().strftime("%H:%M:%S")
            _cache["is_stale"] = False
            if not data.get("error"):
                _cache["waiting"] = False
            _cache["error"] = data.get("error")
            _cache["race_name"] = data.get("race_name", "")
            _cache["race_date"] = data.get("race_date", "")
            _cache["race_sport"] = data.get("race_sport", "")
            _cache["finish_chart"] = finish_chart
    except Exception as e:
        with _cache_lock:
            if app.config["dashboard_state"]["race_generation"] != generation:
                return
            _cache["is_stale"] = True
            error_msg = str(e)
            # Strip URL params to avoid leaking API credentials to the frontend
            if "apipriv=" in error_msg:
                error_msg = error_msg.split("?")[0] if "?" in error_msg else "API request failed"
            _cache["error"] = error_msg


def _wait_for_next_poll(app, since):
    """Block until refresh_interval seconds have passed since `since`, re-reading the interval if it changes.

    Returns early when a race switch requests an immediate poll.
    """
    poll_now = app.extensions["dashboard_poll_now"]
    while True:
        if poll_now.is_set():
            poll_now.clear()
            return
        interval = app.config["dashboard"].get("refresh_interval", 60)
        remaining = since + interval - time.monotonic()
        if remaining <= 0:
            return
        if _config_changed.wait(remaining):
            _config_changed.clear()


def _poll_loop(app, sleep_first=False):
    if sleep_first:
        _wait_for_next_poll(app, time.monotonic())
    while True:
        with app.app_context():
            poll_once(app)
        _wait_for_next_poll(app, time.monotonic())


def _watch_config_once(app, watcher):
    try:
        with app.extensions["dashboard_settings_lock"]:
            reload = watcher.check(app.config["dashboard"])
            if reload is not None:
                _apply_config(app, reload.config, reload.changed)
        if reload is not None:
            if reload.changed:
                print(f"Config reloaded: {', '.join(reload.changed)}")
    except Exception as e:
        print(f"WARNING: config watcher error: {e}", file=sys.stderr)


def _watch_config(app, watcher):
    while True:
        _watch_config_once(app, watcher)
        time.sleep(1)


def _start_config_watcher(app):
    watcher = ConfigWatcher(app.config["dashboard_config_path"])
    t = threading.Thread(target=_watch_config, args=(app, watcher), daemon=True)
    t.start()


def select_race(provider, config):
    try:
        races = provider.list_races(config, _secrets_for(provider, config))
    except Exception as e:
        print(f"\nERROR: Failed to fetch race list: {e}")
        print("Set race_id in config.yaml to skip race selection.")
        raise SystemExit(1)

    if not races:
        print("No posted races found.")
        raise SystemExit(1)

    print("\nAvailable races:")
    for i, race in enumerate(races, 1):
        print(f"  {i}. [{race['id']}] {race['name']} ({race['date']}) - {race['sport']}")

    while True:
        try:
            choice = int(input(f"\nSelect race [1-{len(races)}]: "))
            if 1 <= choice <= len(races):
                selected = races[choice - 1]
                print(f"Selected: {selected['name']}")
                return selected["id"]
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(races)}")


def _mask_token(token):
    if not token:
        return "-"
    return token[:3] + "*" * max(len(token) - 3, 0)


def _format_config_lines(config, race_name, race_date):
    return [
        "",
        "--- Configuration ---",
        f"  Source:                         {config.get('source', 'webscorer')}",
        f"  Data file:                      {config.get('data_file') or '-'}",
        f"  API ID:                         {config.get('api_id') or '-'}",
        f"  API Token:                      {_mask_token(config.get('api_token'))}",
        f"  Race ID:                        {config.get('race_id') or '-'}",
        f"  Race Name:                      {race_name}",
        f"  Race Date:                      {race_date}",
        f"  Refresh:                        {config['refresh_interval']}s",
        f"  Summary time:                   {config['summary_display_time']}s",
        f"  Scroll speed:                   {config['scroll_speed']}px/s",
        f"  Scroll pause:                   {config['scroll_pause_time']}s",
        f"  Pinned leaders:                 {config['pinned_leaders']}",
        f"  Show summary:                   {config['show_summary']}",
        f"  Show demographics:              {config.get('show_demographics', False)}",
        f"  Show Overall results:           {config['show_overall_results']}",
        f"  Show category results:          {config['show_category_results']}",
        f"  Pinned leaders on Overall:      {config['pinned_leaders_on_overall_results']}",
        f"  Overall results layout:         {config['overall_results_layout']}",
        f"  Display unfinished in category: {config['display_unfinished_in_category']}",
        f"  Display unfinished in Overall:  {config['display_unfinished_in_overall']}",
        f"  Chart bucket minutes:           {config['chart_bucket_minutes']}",
        f"  Color scheme:                   {config['color_scheme']}",
        f"  Show toasts:                    {config['show_toasts']}",
    ]


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Webscorer race results dashboard")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="path to the YAML configuration file (default: config.yaml next to app.py)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    config_path = os.path.abspath(args.config)
    config = load_config(config_path=config_path)
    provider = _provider_for(config)

    if provider.list_races and not config.get("data_file") and not config["race_id"]:
        config["race_id"] = select_race(provider, config)
        print("Waiting 5s to prevent API rate limit...")
        time.sleep(5)

    # Fetch initial data before starting the server to avoid rate-limit conflicts
    app = create_app(config, start_polling=False, config_path=config_path)
    poll_once(app)
    with _cache_lock:
        race_name = _cache["race_name"]
        race_date = _cache["race_date"]

    # Priming poll already fetched, so the loop waits one interval before its first poll
    _start_polling(app, sleep_first=True)
    _start_config_watcher(app)
    for line in _format_config_lines(config, race_name, race_date):
        print(line)
    print(f"\nConfig: edits to {os.path.basename(config_path)} apply while running, including source, race_id and data_file.")
    print(f"\nDashboard running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
