import json
import pytest
from unittest.mock import patch, MagicMock
from app import create_app


MOCK_RACE_RESULTS = {
    "RaceInfo": {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
    "Results": [
        {
            "Grouping": {"Category": "Open"},
            "Racers": [
                {"Place": 1, "Bib": "101", "Name": "Alice", "Time": "00:18:30"},
            ],
        }
    ],
}


@pytest.fixture(autouse=True)
def reset_cache():
    import app as app_module
    with app_module._cache_lock:
        app_module._cache.update({
            "pages": [],
            "last_refresh": None,
            "is_stale": False,
            "waiting": True,
            "error": None,
            "race_name": "",
            "race_date": "",
            "race_sport": "",
            "finish_chart": None,
        })


@pytest.fixture
def app():
    test_config = {
        "api_id": "12345",
        "api_token": "abc123de",
        "race_id": "100",
        "refresh_interval": 60,
        "summary_display_time": 20,
        "scroll_speed": 100,
        "scroll_pause_time": 3,
        "pinned_leaders": 3,
        "show_summary": True,
        "show_overall_results": True,
        "show_category_results": True,
        "color_scheme": "dark",
        "overall_results_layout": "detailed",
    }
    application = create_app(test_config, start_polling=False)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_index_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_index_includes_data_theme(client):
    response = client.get("/")
    assert b'data-theme="dark"' in response.data


@patch("app.fetch_race_results")
def test_api_data_returns_json(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    # Simulate a successful poll
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "pages" in data
    assert "scroll_speed" in data
    assert data["pages"][0]["type"] == "summary"


@patch("app.fetch_race_results")
def test_api_data_before_first_poll(mock_fetch, client):
    response = client.get("/api/data")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["pages"] == []
    assert data["waiting"] is True


@patch("app.fetch_race_list")
def test_select_race_interactive(mock_fetch_list):
    mock_fetch_list.return_value = [
        {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
        {"RaceId": 200, "Name": "Trail 10K", "Date": "2026-08-07", "Sport": "Running"},
    ]
    from app import select_race
    with patch("builtins.input", return_value="1"):
        race_id = select_race("12345", "abc123de")
    assert race_id == "100"


@patch("app.fetch_race_results")
def test_api_data_includes_finish_chart(mock_fetch, app, client):
    """finish_chart key is present in /api/data response."""
    mock_fetch.return_value = MOCK_RACE_RESULTS
    # Simulate a successful poll
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "finish_chart" in data


@patch("app.fetch_race_results")
def test_api_data_includes_pinned_leaders_on_overall_results(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["pinned_leaders_on_overall_results"] is False


@patch("app.fetch_race_results")
def test_api_data_includes_overall_results_layout(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["overall_results_layout"] == "detailed"


def test_api_data_defaults_overall_results_layout_to_standard():
    application = create_app({}, start_polling=False)
    application.config["TESTING"] = True
    client = application.test_client()

    response = client.get("/api/data")

    data = json.loads(response.data)
    assert data["overall_results_layout"] == "standard"


def test_api_data_includes_display_unfinished_result_page_toggles():
    application = create_app({
        "display_unfinished_in_category": True,
        "display_unfinished_in_overall": True,
    }, start_polling=False)
    application.config["TESTING"] = True
    client = application.test_client()

    response = client.get("/api/data")

    data = json.loads(response.data)
    assert data["display_unfinished_in_category"] is True
    assert data["display_unfinished_in_overall"] is True


def test_format_config_lines_includes_all_config_options():
    from app import _format_config_lines

    config = {
        "data_file": "api_dump.json",
        "api_id": "12345",
        "api_token": "abc123de",
        "race_id": "999",
        "refresh_interval": 60,
        "summary_display_time": 20,
        "scroll_speed": 100,
        "scroll_pause_time": 2,
        "pinned_leaders": 3,
        "show_summary": True,
        "show_overall_results": True,
        "show_category_results": True,
        "pinned_leaders_on_overall_results": False,
        "overall_results_layout": "detailed",
        "display_unfinished_in_category": True,
        "display_unfinished_in_overall": False,
        "chart_bucket_minutes": 15,
        "color_scheme": "dark",
        "show_toasts": True,
    }

    output = "\n".join(_format_config_lines(config, "Race Name", "Race Date"))

    expected_labels = [
        "Data file:",
        "API ID:",
        "API Token:",
        "Race ID:",
        "Race Name:",
        "Race Date:",
        "Refresh:",
        "Summary time:",
        "Scroll speed:",
        "Scroll pause:",
        "Pinned leaders:",
        "Show summary:",
        "Show Overall results:",
        "Show category results:",
        "Pinned leaders on Overall:",
        "Overall results layout:",
        "Display unfinished in category:",
        "Display unfinished in Overall:",
        "Chart bucket minutes:",
        "Color scheme:",
        "Show toasts:",
    ]
    for label in expected_labels:
        assert label in output
    assert "abc123de" not in output
    assert "abc*****" in output
