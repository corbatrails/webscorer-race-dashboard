import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from webscorer_client import fetch_race_list, fetch_race_results
from data_processing import process_race_data, build_pages, build_finish_chart_data
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


def create_app(config=None, start_polling=True):
    app = Flask(__name__)
    app.config["dashboard"] = config or {}
    _start_time = int(time.time())

    @app.route("/")
    def index():
        color_scheme = app.config["dashboard"].get("color_scheme", "dark")
        return render_template("dashboard.html", cache_bust=_start_time, color_scheme=color_scheme)

    @app.route("/api/data")
    def api_data():
        with _cache_lock:
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
                "summary_display_time": app.config["dashboard"].get("summary_display_time", 20),
                "scroll_speed": app.config["dashboard"].get("scroll_speed", 100),
                "scroll_pause_time": app.config["dashboard"].get("scroll_pause_time", 2),
                "pinned_leaders": app.config["dashboard"].get("pinned_leaders", 3),
                "show_summary": app.config["dashboard"].get("show_summary", True),
                "chart_bucket_minutes": app.config["dashboard"].get("chart_bucket_minutes", 15),
                "show_toasts": app.config["dashboard"].get("show_toasts", True),
            })

    if start_polling:
        race_id = app.config["dashboard"]["race_id"]
        interval = app.config["dashboard"]["refresh_interval"]
        t = threading.Thread(target=_poll_loop, args=(app, race_id, interval), daemon=True)
        t.start()

    return app


def poll_once(app):
    cfg = app.config["dashboard"]
    try:
        raw = fetch_race_results(cfg["race_id"], cfg["api_id"], cfg["api_token"])
        data = process_race_data(
            raw,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
        pages = build_pages(data)
        finish_chart = build_finish_chart_data(raw, cfg.get("chart_bucket_minutes", 15))
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


def _poll_loop(app, race_id, interval):
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
        print(f"  {i}. {race['Name']} ({race.get('Date', 'N/A')}) - {race.get('Sport', '')}")

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


def main():
    config = load_config()

    if not config["race_id"]:
        config["race_id"] = select_race(config["api_id"], config["api_token"])
        print("Waiting 5s to prevent API rate limit...")
        time.sleep(5)

    # Fetch initial data before starting the server to avoid rate-limit conflicts
    race_name = ""
    race_date = ""
    try:
        raw = fetch_race_results(config["race_id"], config["api_id"], config["api_token"])
        data = process_race_data(
            raw,
            show_overall_results=config.get("show_overall_results", True),
            show_category_results=config.get("show_category_results", True),
        )
        pages = build_pages(data)
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
        race_name = data.get("race_name", "")
        race_date = data.get("race_date", "")
    except Exception:
        pass

    app = create_app(config, start_polling=True)
    token = config["api_token"]
    print(f"\n--- Configuration ---")
    print(f"  API ID:          {config['api_id']}")
    print(f"  API Token:       {token[:3]}{'*' * (len(token) - 3)}")
    print(f"  Race ID:         {config['race_id']}")
    print(f"  Race Name:       {race_name}")
    print(f"  Race Date:       {race_date}")
    print(f"  Refresh:         {config['refresh_interval']}s")
    print(f"  Summary time:    {config['summary_display_time']}s")
    print(f"  Scroll speed:    {config['scroll_speed']}px/s")
    print(f"  Scroll pause:    {config['scroll_pause_time']}s")
    print(f"  Pinned leaders:  {config['pinned_leaders']}")
    print(f"\nDashboard running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
