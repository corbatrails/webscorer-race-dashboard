import json
import os
import pytest
from unittest.mock import patch, MagicMock
from app import create_app


MOCK_RACE_RESULTS = {
    "RaceInfo": {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
    "Results": [
        {
            "Grouping": {"Overall": True, "Category": "Open", "Distance": "5K"},
            "Racers": [
                {
                    "Place": 1,
                    "Bib": "101",
                    "Name": "Alice",
                    "Time": "00:18:30",
                    "Age": "31",
                    "Gender": "F",
                    "TeamName": "Corba Trails",
                },
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


@patch("providers.webscorer.fetch_race_results")
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


@patch("providers.webscorer.fetch_race_results")
def test_api_data_before_first_poll(mock_fetch, client):
    response = client.get("/api/data")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["pages"] == []
    assert data["waiting"] is True


@patch("providers.webscorer.fetch_race_list")
def test_select_race_interactive(mock_fetch_list):
    mock_fetch_list.return_value = [
        {"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"},
        {"RaceId": 200, "Name": "Trail 10K", "Date": "2026-08-07", "Sport": "Running"},
    ]
    from app import select_race
    from providers import get_provider
    with patch("builtins.input", return_value="1"):
        race_id = select_race(get_provider("webscorer"), {"api_id": "12345", "api_token": "abc123de"})
    assert race_id == "100"


def _main_config(**overrides):
    from config import OPTIONS
    cfg = {"api_id": None, "api_token": None, **{opt.key: opt.default for opt in OPTIONS}}
    cfg.update(overrides)
    return cfg


def _stub_provider(**overrides):
    from normalizer import normalize_webscorer
    from providers.base import Provider
    fields = dict(
        name="stub",
        required_secrets={"api_token": "STUB_TOKEN"},
        requires_data_file=False,
        fetch=MagicMock(return_value=MOCK_RACE_RESULTS),
        normalize=normalize_webscorer,
    )
    fields.update(overrides)
    return Provider(**fields)


def test_poll_once_uses_provider_named_by_source(app, monkeypatch):
    import app as app_module
    import providers
    stub = _stub_provider()
    monkeypatch.setitem(providers._REGISTRY, "stub", stub)
    app.config["dashboard"]["source"] = "stub"
    with app.app_context():
        app_module.poll_once(app)
    stub.fetch.assert_called_once()
    config, secrets = stub.fetch.call_args.args
    assert config is app.config["dashboard"]
    assert secrets == {"api_token": "abc123de"}
    assert app_module._cache["race_name"] == "Morning 5K"


@patch("providers.webscorer.fetch_race_results")
def test_poll_once_defaults_source_to_webscorer(mock_fetch, app):
    import app as app_module
    mock_fetch.return_value = MOCK_RACE_RESULTS
    assert "source" not in app.config["dashboard"]
    with app.app_context():
        app_module.poll_once(app)
    mock_fetch.assert_called_once_with("100", "12345", "abc123de")


@patch("app.select_race")
@patch("app.threading.Thread")
@patch("app.Flask.run")
@patch("app.load_config")
def test_main_skips_race_prompt_without_list_races(
    mock_load_config, mock_run, mock_thread, mock_select, monkeypatch
):
    import app as app_module
    import providers
    stub = _stub_provider(list_races=None)
    monkeypatch.setitem(providers._REGISTRY, "stub", stub)
    mock_load_config.return_value = _main_config(source="stub", api_token="t")
    app_module.main()
    mock_select.assert_not_called()


@patch("app.time.sleep")
@patch("app.select_race", return_value="100")
@patch("app.threading.Thread")
@patch("app.Flask.run")
@patch("providers.webscorer.fetch_race_results")
@patch("app.load_config")
def test_main_prompts_for_webscorer_without_race_id_or_data_file(
    mock_load_config, mock_fetch, mock_run, mock_thread, mock_select, mock_sleep
):
    import app as app_module
    mock_fetch.return_value = MOCK_RACE_RESULTS
    mock_load_config.return_value = _main_config(api_id="1", api_token="t")
    app_module.main()
    mock_select.assert_called_once()


@patch("providers.webscorer.fetch_race_results")
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


@patch("providers.webscorer.fetch_race_results")
def test_api_data_includes_pinned_leaders_on_overall_results(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["pinned_leaders_on_overall_results"] is False


@patch("providers.webscorer.fetch_race_results")
def test_api_data_includes_overall_results_layout(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["overall_results_layout"] == "detailed"


@patch("providers.webscorer.fetch_race_results")
def test_api_data_includes_show_demographics_default_false(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["show_demographics"] is False


def test_api_data_show_demographics_true_when_configured():
    application = create_app({"show_demographics": True}, start_polling=False)
    application.config["TESTING"] = True
    client = application.test_client()
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["show_demographics"] is True


@patch("providers.webscorer.fetch_race_results")
def test_poll_once_includes_demographics_page(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    types = [p["type"] for p in data["pages"]]
    assert "demographics" in types


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
        "show_demographics": False,
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
        "Show demographics:",
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


def test_format_config_lines_covers_every_registry_option():
    from app import _format_config_lines
    from config import OPTIONS

    class Marker:
        def __init__(self, key):
            self.key = key

        def __str__(self):
            return f"<<{self.key}>>"

    config = {opt.key: Marker(opt.key) for opt in OPTIONS}
    config.update({"api_id": "12345", "api_token": "abc123de"})

    output = "\n".join(_format_config_lines(config, "Race Name", "Race Date"))

    for opt in OPTIONS:
        assert f"<<{opt.key}>>" in output, f"{opt.key} missing from startup config output"


@patch("app.threading.Thread")
@patch("app.Flask.run")
@patch("providers.webscorer.fetch_race_results")
@patch("app.load_config")
def test_main_initial_load_populates_demographics_and_finish_chart(
    mock_load_config, mock_fetch, mock_run, mock_thread, capsys
):
    import app as app_module
    from config import OPTIONS

    config = {opt.key: opt.default for opt in OPTIONS}
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "race_a_finished.json")
    config.update({"api_id": "12345", "api_token": "abc123de", "data_file": fixture})
    mock_load_config.return_value = config

    app_module.main()

    with app_module._cache_lock:
        types = [p["type"] for p in app_module._cache["pages"]]
        finish_chart = app_module._cache["finish_chart"]
    assert "demographics" in types
    assert finish_chart is not None
    mock_fetch.assert_not_called()
    assert "Race Name:                      -" not in capsys.readouterr().out
    mock_thread.return_value.start.assert_called_once()
    mock_run.assert_called_once()


@patch("app.time.sleep")
@patch("app.poll_once")
def test_poll_loop_sleep_first_skips_immediate_poll(mock_poll, mock_sleep):
    from app import _poll_loop

    mock_sleep.side_effect = [None, StopIteration]
    with pytest.raises(StopIteration):
        _poll_loop(create_app({}, start_polling=False), "100", 60, sleep_first=True)

    assert mock_sleep.call_args_list[0].args == (60,)
    assert mock_poll.call_count == 1
