import os
import sys
from dotenv import load_dotenv


def load_config():
    load_dotenv()

    api_id = os.environ.get("WEBSCORER_API_ID")
    api_token = os.environ.get("WEBSCORER_API_TOKEN")

    if not api_id:
        print("ERROR: WEBSCORER_API_ID is required. Set it in .env file.")
        sys.exit(1)
    if not api_token:
        print("ERROR: WEBSCORER_API_TOKEN is required. Set it in .env file.")
        sys.exit(1)

    return {
        "api_id": api_id,
        "api_token": api_token,
        "race_id": os.environ.get("WEBSCORER_RACE_ID") or None,
        "refresh_interval": int(os.environ.get("REFRESH_INTERVAL", "60")),
        "page_rotation_interval": int(os.environ.get("PAGE_ROTATION_INTERVAL", "20")),
    }
