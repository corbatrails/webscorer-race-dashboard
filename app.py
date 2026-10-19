import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from webscorer_client import fetch_race_list, fetch_race_results
from data_processing import process_race_data, build_pages, build_finish_chart_data, build_demographics_data
from normalizer import normalize_webscorer
from config import load_config

_cache = {
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
_cache_lock = threading.Lock()
# Set when refresh_interval changes so the poll loop re-reads it.
_config_changed = threading.Event()


def apply_config_reload(app, reload):
    """Swap in a reloaded config and its state; neither dict is ever mutated in place."""
    with _cache_lock:
        old = app.config["dashboard"]
        state = app.config["dashboard_state"]
        app.config["dashboard"] = reload.config
        app.config["dashboard_state"] = {
            "config_version": state["config_version"] + (1 if reload.changed else 0),
            "restart_required": list(reload.restart_required),
        }
        if old.get("refresh_interval") != reload.config.get("refresh_interval"):
            _config_changed.set()


def create_app(config=None, start_polling=True):
    app = Flask(__name__)
    app.config["dashboard"] = config or {}
    app.config["dashboard_state"] = {"config_version": 1, "restart_required": []}
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
                "config_restart_required": state["restart_required"],
            })

    if start_polling:
        _start_polling(app)

    return app


def _start_polling(app, sleep_first=False):
    race_id = app.config["dashboard"]["race_id"]
    interval = app.config["dashboard"]["refresh_interval"]
    t = threading.Thread(target=_poll_loop, args=(app, race_id, interval, sleep_first), daemon=True)
    t.start()


def poll_once(app):
    cfg = app.config["dashboard"]
    try:
        if cfg.get("data_file"):
            print(f"Loading data from local file: {cfg['data_file']}")
            with open(cfg["data_file"], "r", encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = fetch_race_results(cfg["race_id"], cfg["api_id"], cfg["api_token"])
        snapshot = normalize_webscorer(raw)
        data = process_race_data(
            snapshot,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
        demographics = build_demographics_data(snapshot)
        pages = build_pages(data, demographics)
        finish_chart = build_finish_chart_data(snapshot, cfg.get("chart_bucket_minutes", 15))
        with _cache_lock:
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
            _cache["is_stale"] = True
            error_msg = str(e)
            # Strip URL params to avoid leaking API credentials to the frontend
            if "apipriv=" in error_msg:
                error_msg = error_msg.split("?")[0] if "?" in error_msg else "API request failed"
            _cache["error"] = error_msg


def _poll_loop(app, race_id, interval, sleep_first=False):
    if sleep_first:
        time.sleep(interval)
    while True:
        with app.app_context():
            poll_once(app)
        time.sleep(interval)


def select_race(api_id, api_token):
    try:
        races = fetch_race_list(api_id, api_token)
    except Exception as e:
        print(f"\nERROR: Failed to fetch race list: {e}")
        print("Set WEBSCORER_RACE_ID in your .env file to skip race selection.")
        raise SystemExit(1)

    if not races:
        print("No posted races found.")
        raise SystemExit(1)

    print("\nAvailable races:")
    for i, race in enumerate(races, 1):
        print(f"  {i}. [{race['RaceId']}] {race['Name']} ({race.get('Date', 'N/A')}) - {race.get('Sport', '')}")

    while True:
        try:
            choice = int(input(f"\nSelect race [1-{len(races)}]: "))
            if 1 <= choice <= len(races):
                selected = races[choice - 1]
                print(f"Selected: {selected['Name']}")
                return str(selected["RaceId"])
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


def main():
    config = load_config()

    if not config.get("data_file") and not config["race_id"]:
        config["race_id"] = select_race(config["api_id"], config["api_token"])
        print("Waiting 5s to prevent API rate limit...")
        time.sleep(5)

    # Fetch initial data before starting the server to avoid rate-limit conflicts
    app = create_app(config, start_polling=False)
    poll_once(app)
    with _cache_lock:
        race_name = _cache["race_name"]
        race_date = _cache["race_date"]

    # Priming poll already fetched, so the loop waits one interval before its first poll
    _start_polling(app, sleep_first=True)
    for line in _format_config_lines(config, race_name, race_date):
        print(line)
    print(f"\nDashboard running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
