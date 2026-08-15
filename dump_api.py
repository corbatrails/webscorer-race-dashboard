"""Dump raw WebScorer API response to a JSON file for inspection."""

import json
import sys
from dotenv import load_dotenv
import os

from webscorer_client import fetch_race_results, fetch_race_list

load_dotenv()

api_id = os.environ.get("WEBSCORER_API_ID")
api_token = os.environ.get("WEBSCORER_API_TOKEN")
race_id = os.environ.get("WEBSCORER_RACE_ID")

if not api_id or not api_token:
    print("ERROR: WEBSCORER_API_ID and WEBSCORER_API_TOKEN must be set in .env")
    sys.exit(1)

if not race_id:
    print("No WEBSCORER_RACE_ID set, fetching race list to pick one...")
    races = fetch_race_list(api_id, api_token)
    if not races:
        print("No races found.")
        sys.exit(1)
    for i, race in enumerate(races):
        print(f"  [{i}] {race.get('Name', '?')} (ID: {race.get('RaceId')})")
    choice = input("Enter number: ")
    race_id = races[int(choice)]["RaceId"]

print(f"Fetching results for race {race_id}...")
data = fetch_race_results(race_id, api_id, api_token)

output_file = f"api_dump_{race_id}.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Saved to {output_file}")
