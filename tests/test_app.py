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


@patch("app.fetch_race_results")
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


@patch("app.fetch_race_results")
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
@patch("app.fetch_race_results")
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
    out = capsys.readouterr().out
    assert "Race Name:                      -" not in out
    assert mock_thread.return_value.start.call_count == 2
    assert "live options reload from config.yaml" in out
    mock_run.assert_called_once()


@patch("app._wait_for_next_poll")
@patch("app.poll_once")
def test_poll_loop_sleep_first_waits_before_first_poll(mock_poll, mock_wait):
    from app import _poll_loop

    order = []

    def wait(*args):
        order.append("wait")
        if len(order) > 2:
            raise StopIteration

    mock_wait.side_effect = wait
    mock_poll.side_effect = lambda *args: order.append("poll")
    with pytest.raises(StopIteration):
        _poll_loop(create_app({}, start_polling=False), sleep_first=True)

    assert order == ["wait", "poll", "wait"]


@patch("app._wait_for_next_poll")
@patch("app.poll_once")
def test_poll_loop_polls_immediately_by_default(mock_poll, mock_wait):
    from app import _poll_loop

    mock_wait.side_effect = StopIteration
    with pytest.raises(StopIteration):
        _poll_loop(create_app({}, start_polling=False))

    assert mock_poll.call_count == 1


def _run_wait(app, since):
    import time
    from app import _wait_for_next_poll

    done = {}

    def target():
        start = time.monotonic()
        _wait_for_next_poll(app, since)
        done["elapsed"] = time.monotonic() - start

    import threading
    t = threading.Thread(target=target, daemon=True)
    t.start()
    return t, done


def test_wait_for_next_poll_returns_after_current_interval():
    import time
    import app as app_module

    app = create_app({"refresh_interval": 0.2}, start_polling=False)
    start = time.monotonic()
    app_module._wait_for_next_poll(app, time.monotonic())
    assert 0.15 <= time.monotonic() - start < 2


def test_wait_for_next_poll_returns_early_when_interval_is_lowered():
    import time
    import app as app_module

    app = create_app({"refresh_interval": 60}, start_polling=False)
    t, done = _run_wait(app, time.monotonic() - 5)
    app_module.apply_config_reload(app, _reload(app, refresh_interval=1))
    t.join(timeout=3)

    assert not t.is_alive()
    assert done["elapsed"] < 3


def test_wait_for_next_poll_keeps_waiting_if_new_interval_has_not_elapsed():
    import time
    import app as app_module

    app = create_app({"refresh_interval": 60}, start_polling=False)
    t, done = _run_wait(app, time.monotonic())
    app_module.apply_config_reload(app, _reload(app, refresh_interval=0.4))
    t.join(timeout=3)

    assert not t.is_alive()
    assert done["elapsed"] >= 0.3

# --- Live config swap (Phase 4) ----------------------------------------------


def _reload(app, changed=None, restart_required=(), **values):
    from config import Reload

    new_config = {**app.config["dashboard"], **values}
    return Reload(new_config, list(changed if changed is not None else values), list(restart_required))


def test_api_data_includes_config_fields(client):
    data = client.get("/api/data").get_json()
    assert data["config_version"] == 1
    assert data["config_restart_required"] == []
    assert data["color_scheme"] == "dark"
    assert data["refresh_interval"] == 60


def test_apply_config_reload_swaps_values_and_bumps_version(app, client):
    from app import apply_config_reload

    apply_config_reload(app, _reload(app, scroll_speed=250, color_scheme="light", refresh_interval=30))

    data = client.get("/api/data").get_json()
    assert data["scroll_speed"] == 250
    assert data["color_scheme"] == "light"
    assert data["refresh_interval"] == 30
    assert data["config_version"] == 2
    assert b'data-theme="light"' in client.get("/").data


def test_apply_config_reload_does_not_mutate_old_config(app):
    from app import apply_config_reload

    old = app.config["dashboard"]
    apply_config_reload(app, _reload(app, scroll_speed=250))

    assert old["scroll_speed"] == 100
    assert app.config["dashboard"] is not old


def test_restart_only_reload_keeps_version_and_reports_keys(app, client):
    from app import apply_config_reload

    apply_config_reload(app, _reload(app, changed=[], restart_required=["race_id"]))

    data = client.get("/api/data").get_json()
    assert data["config_version"] == 1
    assert data["config_restart_required"] == ["race_id"]


def test_apply_config_reload_wakes_poll_loop_only_when_interval_changes(app):
    import app as app_module

    app_module._config_changed.clear()
    app_module.apply_config_reload(app, _reload(app, scroll_speed=250))
    assert not app_module._config_changed.is_set()

    app_module.apply_config_reload(app, _reload(app, refresh_interval=10))
    assert app_module._config_changed.is_set()


# --- Config watcher thread (Phase 4) -----------------------------------------


def test_watch_config_once_applies_reload(app, client, capsys):
    from app import _watch_config_once

    watcher = MagicMock()
    watcher.check.return_value = _reload(app, scroll_speed=250)

    _watch_config_once(app, watcher)

    watcher.check.assert_called_once()
    assert client.get("/api/data").get_json()["scroll_speed"] == 250
    assert "Config reloaded: scroll_speed" in capsys.readouterr().out


def test_watch_config_once_passes_running_config_and_ignores_none(app, client):
    from app import _watch_config_once

    running = app.config["dashboard"]
    watcher = MagicMock()
    watcher.check.return_value = None

    _watch_config_once(app, watcher)

    watcher.check.assert_called_once_with(running)
    assert client.get("/api/data").get_json()["config_version"] == 1


def test_watch_config_once_survives_unexpected_exception(app, capsys):
    from app import _watch_config_once

    watcher = MagicMock()
    watcher.check.side_effect = RuntimeError("boom")

    _watch_config_once(app, watcher)

    assert "boom" in capsys.readouterr().err


@patch("app.time.sleep")
@patch("app._watch_config_once")
def test_watch_config_loop_ticks_every_second(mock_once, mock_sleep):
    from app import _watch_config

    mock_sleep.side_effect = [None, StopIteration]
    with pytest.raises(StopIteration):
        _watch_config("app", "watcher")

    assert mock_once.call_count == 2
    mock_once.assert_called_with("app", "watcher")
    assert mock_sleep.call_args_list[0].args == (1,)
