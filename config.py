import os
import sys
from dotenv import load_dotenv


def load_config():
    load_dotenv()

    data_file = os.environ.get("DATA_FILE")
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

    color_scheme_raw = os.environ.get("COLOR_SCHEME", "dark").lower()

    return {
        "data_file": data_file,
        "api_id": api_id,
        "api_token": api_token,
        "race_id": os.environ.get("WEBSCORER_RACE_ID") or None,
        "refresh_interval": int(os.environ.get("REFRESH_INTERVAL", "60")),
        "summary_display_time": int(os.environ.get("SUMMARY_DISPLAY_TIME", "20")),
        "scroll_speed": int(os.environ.get("SCROLL_SPEED", "100")),
        "scroll_pause_time": int(os.environ.get("SCROLL_PAUSE_TIME", "2")),
        "pinned_leaders": int(os.environ.get("PINNED_LEADERS", "3")),
        "show_summary": os.environ.get("SHOW_SUMMARY", "true").lower() == "true",
        "show_overall_results": os.environ.get("SHOW_OVERALL_RESULTS", "true").lower() == "true",
        "show_category_results": os.environ.get("SHOW_CATEGORY_RESULTS", "true").lower() == "true",
        "chart_bucket_minutes": int(os.environ.get("CHART_BUCKET_MINUTES", "15")),
        "color_scheme": color_scheme_raw if color_scheme_raw in ("dark", "light") else "dark",
    }
