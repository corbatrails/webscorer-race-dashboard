import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from webscorer_client import fetch_race_list, fetch_race_results
from data_processing import process_race_data, build_pages
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
}
_cache_lock = threading.Lock()


def create_app(config=None, start_polling=True):
    app = Flask(__name__)
    app.config["dashboard"] = config or {}

    @app.route("/")
    def index():
        cfg = app.config["dashboard"]
        return render_template("dashboard.html", page_rotation_interval=cfg.get("page_rotation_interval", 20))

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
                "page_rotation_interval": app.config["dashboard"].get("page_rotation_interval", 20),
                "results_per_page": app.config["dashboard"].get("results_per_page", 0),
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
        data = process_race_data(raw)
        pages = build_pages(data)
        with _cache_lock:
            _cache["pages"] = pages
            _cache["last_refresh"] = datetime.now().strftime("%H:%M:%S")
            _cache["is_stale"] = False
            _cache["waiting"] = False
            _cache["error"] = data.get("error")
            _cache["race_name"] = data.get("race_name", "")
            _cache["race_date"] = data.get("race_date", "")
            _cache["race_sport"] = data.get("race_sport", "")
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

    app = create_app(config, start_polling=True)
    token = config["api_token"]
    race_name = ""
    race_date = ""
    try:
        raw = fetch_race_results(config["race_id"], config["api_id"], config["api_token"])
        race_name = raw.get("RaceInfo", {}).get("Name", "")
        race_date = raw.get("RaceInfo", {}).get("Date", "")
    except Exception:
        pass
    print(f"\n--- Configuration ---")
    print(f"  API ID:          {config['api_id']}")
    print(f"  API Token:       {token[:3]}{'*' * (len(token) - 3)}")
    print(f"  Race ID:         {config['race_id']}")
    print(f"  Race Name:       {race_name}")
    print(f"  Race Date:       {race_date}")
    print(f"  Refresh:         {config['refresh_interval']}s")
    print(f"  Page rotation:   {config['page_rotation_interval']}s")
    print(f"\nDashboard running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
