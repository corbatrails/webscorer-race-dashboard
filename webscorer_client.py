import requests

BASE_URL = "https://www.webscorer.com/json"


def fetch_race_list(api_id, api_token):
    response = requests.get(
        f"{BASE_URL}/mypostedraces",
        params={"apiid": api_id, "apipriv": api_token},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("ResultList", [])


def fetch_race_results(race_id, api_id, api_token):
    response = requests.get(
        f"{BASE_URL}/race",
        params={"raceid": race_id, "apiid": api_id, "apipriv": api_token},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
