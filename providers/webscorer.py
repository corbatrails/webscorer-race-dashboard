"""WebScorer provider: the WebScorer JSON API (or a saved dump) and `normalize_webscorer`."""
import json

from normalizer import normalize_webscorer
from providers.base import Provider
from webscorer_client import fetch_race_list, fetch_race_results


def fetch(config, secrets):
    if config.get("data_file"):
        print(f"Loading data from local file: {config['data_file']}")
        with open(config["data_file"], "r", encoding="utf-8") as f:
            return json.load(f)
    return fetch_race_results(config["race_id"], secrets["api_id"], secrets["api_token"])


def list_races(config, secrets):
    return [
        {
            "id": str(race["RaceId"]),
            "name": race["Name"],
            "date": race.get("Date", "N/A"),
            "sport": race.get("Sport", ""),
        }
        for race in fetch_race_list(secrets["api_id"], secrets["api_token"])
    ]


PROVIDER = Provider(
    name="webscorer",
    required_secrets={"api_id": "WEBSCORER_API_ID", "api_token": "WEBSCORER_API_TOKEN"},
    requires_data_file=False,
    fetch=fetch,
    normalize=normalize_webscorer,
    list_races=list_races,
)
