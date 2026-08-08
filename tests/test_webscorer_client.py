import pytest
from unittest.mock import patch, Mock
from webscorer_client import fetch_race_list, fetch_race_results


MOCK_RACE_LIST_RESPONSE = {
    "OrganizerInfo": {"OrganizerPage": "https://www.webscorer.com/org/12345"},
    "ResultList": [
        {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running", "DisplayURL": "https://example.com/100"},
        {"RaceId": 200, "Name": "Trail 10K", "Date": "2026-08-07", "Sport": "Running", "DisplayURL": "https://example.com/200"},
    ],
}

MOCK_RACE_RESULTS_RESPONSE = {
    "RaceInfo": {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
    "Results": [
        {
            "Grouping": {"Category": "Male 20-29"},
            "Racers": [
                {"Place": 1, "Bib": "101", "Name": "Alice", "Time": "00:18:30"},
                {"Place": 2, "Bib": "102", "Name": "Bob", "Time": "00:19:15"},
            ],
        }
    ],
}


@patch("webscorer_client.requests.get")
def test_fetch_race_list(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = MOCK_RACE_LIST_RESPONSE
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    races = fetch_race_list("12345", "abc123de")

    mock_get.assert_called_once_with(
        "https://www.webscorer.com/json/mypostedraces",
        params={"apiid": "12345", "apipriv": "abc123de"},
        headers={"User-Agent": "WebScorerDashboard/1.0"},
        timeout=30,
    )
    assert len(races) == 2
    assert races[0]["Name"] == "Morning 5K"
    assert races[1]["RaceId"] == 200


@patch("webscorer_client.requests.get")
def test_fetch_race_results(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = MOCK_RACE_RESULTS_RESPONSE
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    data = fetch_race_results("100", "12345", "abc123de")

    mock_get.assert_called_once_with(
        "https://www.webscorer.com/json/race",
        params={"raceid": "100", "apiid": "12345", "apipriv": "abc123de"},
        headers={"User-Agent": "WebScorerDashboard/1.0"},
        timeout=30,
    )
    assert data["RaceInfo"]["Name"] == "Morning 5K"
    assert len(data["Results"]) == 1
    assert len(data["Results"][0]["Racers"]) == 2


@patch("webscorer_client.requests.get")
def test_fetch_race_list_error(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    with pytest.raises(Exception, match="Connection refused"):
        fetch_race_list("12345", "abc123de")


@patch("webscorer_client.requests.get")
def test_fetch_race_results_api_error(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"Error": "PRO Results subscription required"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    data = fetch_race_results("100", "12345", "abc123de")
    assert "Error" in data
