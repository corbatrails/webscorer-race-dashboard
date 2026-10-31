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


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("app.load_config")
def test_main_skips_race_prompt_without_list_races(
    mock_load_config, mock_run, mock_thread, mock_prompt, monkeypatch
):
    import app as app_module
    import providers
    stub = _stub_provider(list_races=None)
    monkeypatch.setitem(providers._REGISTRY, "stub", stub)
    mock_load_config.return_value = _main_config(source="stub", api_token="t")
    app_module.main([])
    mock_prompt.assert_not_called()


class _Tty:
    def isatty(self):
        return True


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("providers.webscorer.fetch_race_results")
@patch("app.load_config")
def test_main_prompts_for_webscorer_without_race_id_or_data_file(
    mock_load_config, mock_fetch, mock_server, mock_thread, mock_prompt, monkeypatch, capsys
):
    import app as app_module
    monkeypatch.setattr(app_module.sys, "stdin", _Tty())
    mock_prompt.return_value = (MagicMock(), _threading_mod().Event())
    mock_load_config.return_value = _main_config(api_id="1", api_token="t")
    app_module.main([])
    mock_prompt.assert_called_once()
    mock_fetch.assert_not_called()  # no results request until a race is chosen
    mock_server.return_value.serve_forever.assert_called_once()
    out = capsys.readouterr().out
    assert "Dashboard running at" in out


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("providers.webscorer.fetch_race_results")
@patch("app.load_config")
def test_main_with_saved_race_skips_prompt(
    mock_load_config, mock_fetch, mock_server, mock_thread, mock_prompt, monkeypatch
):
    import app as app_module
    monkeypatch.setattr(app_module.sys, "stdin", _Tty())
    mock_fetch.return_value = MOCK_RACE_RESULTS
    mock_load_config.return_value = _main_config(api_id="1", api_token="t", race_id="100")
    app_module.main([])
    mock_prompt.assert_not_called()
    mock_fetch.assert_called_once()


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("app.load_config")
def test_main_noninteractive_stdin_leaves_server_waiting(
    mock_load_config, mock_server, mock_thread, mock_prompt, monkeypatch, capsys
):
    import io
    import app as app_module
    monkeypatch.setattr(app_module.sys, "stdin", io.StringIO(""))
    mock_load_config.return_value = _main_config(api_id="1", api_token="t")
    app_module.main([])
    mock_prompt.assert_not_called()
    mock_server.return_value.serve_forever.assert_called_once()
    assert "No interactive terminal" in capsys.readouterr().out


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("app.load_config")
def test_main_ctrl_c_stops_prompt_and_closes_server(
    mock_load_config, mock_server, mock_thread, mock_prompt, monkeypatch
):
    import app as app_module
    monkeypatch.setattr(app_module.sys, "stdin", _Tty())
    worker = MagicMock()
    mock_prompt.return_value = (worker, _threading_mod().Event())
    mock_server.return_value.serve_forever.side_effect = KeyboardInterrupt
    mock_load_config.return_value = _main_config(api_id="1", api_token="t")
    app_module.main([])
    stop = mock_prompt.return_value[1]
    assert stop.is_set()
    worker.join.assert_called_once()
    mock_server.return_value.server_close.assert_called_once()


def _threading_mod():
    import threading
    return threading


# --- source: csv end to end (no WebScorer credentials, no network) ----------

SAMPLE_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "sample-results.csv")


def _csv_config(tmp_path, data_file=SAMPLE_CSV):
    import yaml
    from config import load_config
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"source": "csv", "data_file": data_file}), encoding="utf-8")
    return load_config(config_path=str(config_path), env_path=str(tmp_path / ".env"))


@pytest.fixture
def no_credentials(monkeypatch):
    for name in ("WEBSCORER_API_ID", "WEBSCORER_API_TOKEN", "RACE_SOURCE", "DATA_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_csv_source_serves_pages_without_credentials(no_credentials, tmp_path):
    cfg = _csv_config(tmp_path)
    assert cfg["api_id"] is None and cfg["api_token"] is None
    application = create_app(cfg, start_polling=False)
    with patch("requests.get", side_effect=AssertionError("network used")):
        import app as app_module
        app_module.poll_once(application)
    data = json.loads(application.test_client().get("/api/data").data)
    assert data["waiting"] is False and data["is_stale"] is False and data["error"] is None
    assert data["race_name"] == "Sample Gravel Grinder"
    titles = [p["title"] for p in data["pages"]]
    assert titles[0] == "Summary"
    assert "Overall - 40 mile" in titles and "Men 40-49" in titles
    assert data["finish_chart"]["datasets"]


def test_bad_csv_marks_stale_and_keeps_previous_pages(no_credentials, tmp_path):
    import app as app_module
    data_file = tmp_path / "results.csv"
    data_file.write_text("bib,name,time\n1,Alice,1:00:00\n", encoding="utf-8")
    application = create_app(_csv_config(tmp_path, str(data_file)), start_polling=False)
    app_module.poll_once(application)
    good_pages = list(app_module._cache["pages"])
    assert good_pages

    data_file.write_text("bib,name,time\n1,Alice,soon\n", encoding="utf-8")
    app_module.poll_once(application)
    data = json.loads(application.test_client().get("/api/data").data)
    assert data["is_stale"] is True
    assert "row 2, column 'time'" in data["error"]
    assert data["pages"] == good_pages

    data_file.write_text("bib,name,time\n1,Alice,1:00:00\n", encoding="utf-8")
    app_module.poll_once(application)
    assert app_module._cache["is_stale"] is False and app_module._cache["error"] is None


@patch("app._start_race_prompt")
@patch("app.threading.Thread")
@patch("app.make_server")
@patch("providers.webscorer.fetch_race_results")
@patch("providers.webscorer.fetch_race_list")
@patch("app.load_config")
def test_main_with_csv_source_never_prompts_or_calls_webscorer(
    mock_load_config, mock_list, mock_fetch, mock_run, mock_thread, mock_select, monkeypatch
):
    import app as app_module
    monkeypatch.setattr(app_module.sys, "stdin", _Tty())
    mock_load_config.return_value = _main_config(source="csv", data_file=SAMPLE_CSV)
    app_module.main([])
    mock_select.assert_not_called()
    mock_list.assert_not_called()
    mock_fetch.assert_not_called()
    assert app_module._cache["race_name"] == "Sample Gravel Grinder"
    assert app_module._cache["pages"]


def test_webscorer_source_still_requires_credentials(no_credentials, tmp_path, capsys):
    import yaml
    from config import load_config
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"source": "webscorer"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_config(config_path=str(config_path), env_path=str(tmp_path / ".env"))
    assert "WEBSCORER_API_ID is required" in capsys.readouterr().out


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


@pytest.mark.parametrize("configured, expected", [({}, False), ({"show_lap_overview": True}, True)])
def test_api_data_includes_show_lap_overview(configured, expected):
    application = create_app(configured, start_polling=False)
    data = application.test_client().get("/api/data").get_json()
    assert data["show_lap_overview"] is expected


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
        "source": "webscorer",
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
        "show_lap_overview": False,
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
        "Source:",
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
        "Show lap overview:",
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
@patch("app.make_server")
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

    app_module.main([])

    with app_module._cache_lock:
        types = [p["type"] for p in app_module._cache["pages"]]
        finish_chart = app_module._cache["finish_chart"]
    assert "demographics" in types
    assert finish_chart is not None
    mock_fetch.assert_not_called()
    out = capsys.readouterr().out
    assert "Race Name:                      -" not in out
    assert mock_thread.return_value.start.call_count == 2
    assert "config.yaml apply while running" in out
    mock_run.return_value.serve_forever.assert_called_once()


@patch("app.threading.Thread")
@patch("app.make_server")
@patch("app.ConfigWatcher")
@patch("app.load_config")
def test_main_uses_selected_config_path(mock_load_config, mock_watcher, mock_run, mock_thread, tmp_path):
    import app as app_module

    path = tmp_path / "dir with spaces" / "demo.yaml"
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "race_a_finished.json")
    mock_load_config.return_value = _main_config(data_file=fixture)

    app_module.main(["--config", str(path)])

    assert mock_load_config.call_args.kwargs["config_path"] == os.path.abspath(str(path))
    mock_watcher.assert_called_once_with(os.path.abspath(str(path)))


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


def _reload(app, changed=None, **values):
    from config import Reload

    new_config = {**app.config["dashboard"], **values}
    return Reload(new_config, list(changed if changed is not None else values))


def test_api_data_includes_config_fields(client):
    data = client.get("/api/data").get_json()
    assert data["config_version"] == 1
    assert "config_restart_required" not in data
    assert data["race_selection_required"] is False
    assert isinstance(data["race_generation"], int)
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


# --- Live race switching (Phase 5) -------------------------------------------


import threading as _threading


def _poll(app):
    from app import poll_once

    with app.app_context():
        poll_once(app)


def _yaml_app(tmp_path, **values):
    import yaml
    from config import load_config

    path = tmp_path / "dashboard config.yaml"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    config = load_config(config_path=str(path), env_path=str(tmp_path / ".env"))
    return create_app(config, start_polling=False, config_path=str(path)), path


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")


@patch("providers.webscorer.fetch_race_list")
@patch("providers.webscorer.fetch_race_results")
def test_poll_skips_results_without_selected_live_race(mock_fetch, mock_list):
    app = create_app({"api_id": "1", "api_token": "t", "race_id": None}, start_polling=False)
    _poll(app)

    data = app.test_client().get("/api/data").get_json()
    assert data["race_selection_required"] is True
    assert data["pages"] == []
    assert data["waiting"] is True
    assert data["error"] is None
    mock_fetch.assert_not_called()


@patch("providers.webscorer.fetch_race_results")
def test_race_switch_clears_cache_and_wakes_poll(mock_fetch, app, client):
    from app import apply_config_reload

    mock_fetch.return_value = MOCK_RACE_RESULTS
    _poll(app)
    before = client.get("/api/data").get_json()
    assert before["pages"] and before["race_name"] == "Morning 5K"
    poll_now = app.extensions["dashboard_poll_now"]
    poll_now.clear()

    apply_config_reload(app, _reload(app, race_id="200"))

    data = client.get("/api/data").get_json()
    assert data["pages"] == []
    assert data["race_name"] == ""
    assert data["finish_chart"] is None
    assert data["waiting"] is True
    assert data["error"] is None
    assert data["race_generation"] != before["race_generation"]
    assert poll_now.is_set()


@patch("providers.webscorer.fetch_race_results")
def test_display_setting_change_keeps_race_generation_and_results(mock_fetch, app, client):
    from app import apply_config_reload

    mock_fetch.return_value = MOCK_RACE_RESULTS
    _poll(app)
    before = client.get("/api/data").get_json()
    app.extensions["dashboard_poll_now"].clear()

    apply_config_reload(app, _reload(app, scroll_speed=250))

    data = client.get("/api/data").get_json()
    assert data["race_generation"] == before["race_generation"]
    assert data["pages"] == before["pages"]
    assert not app.extensions["dashboard_poll_now"].is_set()


@pytest.mark.parametrize("outcome", ["results", "error"])
@patch("providers.webscorer.fetch_race_results")
def test_old_poll_cannot_publish_after_switch(mock_fetch, app, client, outcome):
    from app import apply_config_reload

    started, release = _threading.Event(), _threading.Event()

    def slow_fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        if outcome == "error":
            raise RuntimeError("old race failed")
        return MOCK_RACE_RESULTS

    mock_fetch.side_effect = slow_fetch
    worker = _threading.Thread(target=_poll, args=(app,))
    worker.start()
    assert started.wait(5)

    apply_config_reload(app, _reload(app, race_id="200"))
    release.set()
    worker.join(5)

    data = client.get("/api/data").get_json()
    assert data["pages"] == []
    assert data["race_name"] == ""
    assert data["error"] is None
    assert data["is_stale"] is False
    assert data["waiting"] is True


@patch("providers.webscorer.fetch_race_results")
def test_new_race_failure_stays_waiting_and_retries(mock_fetch, tmp_path, creds):
    import yaml
    from app import update_dashboard

    app, path = _yaml_app(tmp_path, race_id="100")
    client = app.test_client()

    assert update_dashboard(app, {"race_id": "200"}) is True
    mock_fetch.assert_not_called()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == "200"

    mock_fetch.side_effect = [RuntimeError("not posted yet"), MOCK_RACE_RESULTS]
    _poll(app)
    data = client.get("/api/data").get_json()
    assert data["waiting"] is True
    assert data["error"] == "not posted yet"
    assert app.config["dashboard"]["race_id"] == "200"

    _poll(app)
    data = client.get("/api/data").get_json()
    assert data["waiting"] is False
    assert data["error"] is None
    assert data["pages"]


def test_update_dashboard_rejects_invalid_values_without_changes(tmp_path, creds):
    from app import update_dashboard
    from config import ConfigValidationError

    app, path = _yaml_app(tmp_path, race_id="100")
    before_file, before_cfg = path.read_bytes(), app.config["dashboard"]

    with pytest.raises(ConfigValidationError):
        update_dashboard(app, {"scroll_speed": 0})

    assert path.read_bytes() == before_file
    assert app.config["dashboard"] is before_cfg


def test_startup_selection_has_one_winner(tmp_path, creds):
    import yaml
    from app import update_dashboard

    app, path = _yaml_app(tmp_path)
    assert app.config["dashboard"]["race_id"] is None
    assert not app.extensions["startup_race_selected"].is_set()

    barrier = _threading.Barrier(2)
    results = {}

    def submit(race_id):
        barrier.wait(5)
        results[race_id] = update_dashboard(app, {"race_id": race_id}, startup_only=True)

    threads = [_threading.Thread(target=submit, args=(rid,)) for rid in ("100", "200")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)

    winners = [rid for rid, ok in results.items() if ok]
    assert len(winners) == 1
    assert app.config["dashboard"]["race_id"] == winners[0]
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == winners[0]
    assert app.extensions["startup_race_selected"].is_set()


def test_startup_selection_loses_to_race_saved_in_file(tmp_path, creds):
    import yaml
    from app import update_dashboard

    app, path = _yaml_app(tmp_path)
    path.write_text(yaml.safe_dump({"race_id": "300"}), encoding="utf-8")

    assert update_dashboard(app, {"race_id": "100"}, startup_only=True) is False
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == "300"


def test_watcher_tick_after_internal_save_is_noop(tmp_path, creds):
    from app import _watch_config_once, update_dashboard
    from config import ConfigWatcher

    app, path = _yaml_app(tmp_path, race_id="100")
    watcher = ConfigWatcher(str(path))
    assert update_dashboard(app, {"scroll_speed": 250}) is True
    version = app.config["dashboard_state"]["config_version"]

    for _ in range(3):
        _watch_config_once(app, watcher)

    assert app.config["dashboard_state"]["config_version"] == version
    assert app.config["dashboard"]["scroll_speed"] == 250


# --- Terminal and web startup selection (Phase 5) ------------------------------


def _blocking_reader(started):
    def reader(stop, stdin, stdout):
        started.set()
        stop.wait(5)
        return None
    return reader


@patch("providers.webscorer.fetch_race_list")
def test_cli_selection_saves_race_and_ends_prompt(mock_list, tmp_path, creds, monkeypatch):
    import yaml
    import race_prompt
    from app import _start_race_prompt

    mock_list.return_value = [{"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"}]
    monkeypatch.setattr(race_prompt, "read_line_until", lambda stop, i, o: "1")
    app, path = _yaml_app(tmp_path)

    worker, stop = _start_race_prompt(app, _threading.Event())
    worker.join(5)

    assert not worker.is_alive()
    assert stop.is_set()
    assert app.config["dashboard"]["race_id"] == "100"
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == "100"
    assert app.extensions["dashboard_poll_now"].is_set()


@patch("providers.webscorer.fetch_race_list")
def test_ui_selection_cancels_terminal_prompt(mock_list, tmp_path, creds, monkeypatch):
    import yaml
    import race_prompt
    from app import _start_race_prompt, update_dashboard

    mock_list.return_value = [{"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"}]
    started = _threading.Event()
    monkeypatch.setattr(race_prompt, "read_line_until", _blocking_reader(started))
    app, path = _yaml_app(tmp_path)

    worker, stop = _start_race_prompt(app, _threading.Event())
    assert started.wait(5)
    assert update_dashboard(app, {"race_id": "200"}, startup_only=True) is True
    worker.join(5)

    assert not worker.is_alive()
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == "200"


@patch("providers.webscorer.fetch_race_list")
def test_late_cli_choice_loses_to_ui_selection(mock_list, tmp_path, creds, monkeypatch, capsys):
    import yaml
    import race_prompt
    from app import _start_race_prompt, update_dashboard

    mock_list.return_value = [{"RaceId": 100, "Name": "Morning 5K", "Date": "2026-08-07", "Sport": "Running"}]
    app, path = _yaml_app(tmp_path)

    def reader(stop, stdin, stdout):
        update_dashboard(app, {"race_id": "200"}, startup_only=True)  # UI wins first
        return "1"  # typed just before cancellation

    monkeypatch.setattr(race_prompt, "read_line_until", reader)
    worker, stop = _start_race_prompt(app, _threading.Event())
    worker.join(5)

    assert yaml.safe_load(path.read_text(encoding="utf-8"))["race_id"] == "200"
    assert app.config["dashboard"]["race_id"] == "200"


def test_access_log_buffer_holds_info_until_flush():
    import logging
    from app import _AccessLogBuffer

    logger = logging.getLogger("werkzeug")
    seen = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Collect(level=logging.DEBUG)
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        buffer = _AccessLogBuffer(logger)
        buffer.start()
        logger.info("GET /api/data 200")
        logger.warning("port busy")
        assert seen == ["port busy"]
        buffer.flush()
        assert seen == ["port busy", "GET /api/data 200"]
        logger.info("GET / 200")
        assert seen[-1] == "GET / 200"
        buffer.flush()  # idempotent
        assert len(seen) == 3
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


@patch("app.threading.Thread")
@patch("app.make_server")
@patch("app.load_config")
def test_main_reports_admin_status_without_password(mock_load_config, mock_server, mock_thread, monkeypatch, capsys):
    import app as app_module
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "race_a_finished.json")
    mock_load_config.return_value = _main_config(data_file=fixture)

    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    app_module.main([])
    assert "Admin page: disabled" in capsys.readouterr().out

    monkeypatch.setenv("ADMIN_PASSWORD", "SENTINEL-pw-123")
    app_module.main([])
    out = capsys.readouterr().out
    assert "Admin page: http://localhost:5000/admin" in out
    assert "SENTINEL-pw-123" not in out
    application = mock_server.call_args.args[2]
    assert application.config["admin_enabled"] is True


from datetime import datetime as _dt, timedelta as _td, timezone as _tz


def _race(date_iso=None, offset=None, start=8 * 3600):
    return {"event_date_iso": date_iso, "timezone_offset_minutes": offset, "start_seconds": start}


def test_observation_seconds_converts_to_event_offset():
    from app import _observation_seconds
    now = _dt(2025, 11, 1, 14, 0, 30, tzinfo=_tz.utc)
    assert _observation_seconds(_race("2025-11-01", -300), now) == 9 * 3600 + 30


def test_observation_seconds_adds_days_after_event_date():
    from app import _observation_seconds
    now = _dt(2025, 11, 2, 5, 30, tzinfo=_tz.utc)
    assert _observation_seconds(_race("2025-11-01", -300), now) == 86400 + 30 * 60


def test_observation_seconds_is_negative_before_event_date():
    from app import _observation_seconds
    now = _dt(2025, 10, 31, 20, 0, tzinfo=_tz.utc)
    assert _observation_seconds(_race("2025-11-01", 0), now) == 20 * 3600 - 86400


def test_observation_seconds_uses_machine_local_time_without_offset():
    from app import _observation_seconds
    now = _dt(2026, 6, 6, 10, 0, tzinfo=_tz(_td(hours=2)))
    assert _observation_seconds(_race("2026-06-06", None), now) == 10 * 3600


@pytest.mark.parametrize("hour, start, expected", [
    (10, 8 * 3600, 10 * 3600),
    (1, 23 * 3600, 86400 + 3600),
    (7, 8 * 3600, 7 * 3600),
])
def test_observation_seconds_without_event_date_uses_rollover(hour, start, expected):
    from app import _observation_seconds
    now = _dt(2026, 6, 6, hour, 0, tzinfo=_tz.utc)
    assert _observation_seconds(_race(None, 0, start), now) == expected


LAP_RACE_RESULTS = {
    "RaceInfo": {
        "RaceId": 100, "Name": "Lap Race", "Date": "Nov 1, 2025", "Sport": "Running",
        "StartTime": "Saturday, November 1, 2025 8:00 AM (GMT-5)",
    },
    "Results": [
        {
            "Grouping": {"Overall": True, "Distance": "25K", "LapCount": 2},
            "Racers": [
                {"Place": "1", "Bib": "1", "Name": "A", "Time": "2:00:00.0", "StartTime": "08:00:00.0",
                 "LapTimes": [{"LapNumber": 1, "RaceTime": "1:00:00.0"}, {"LapNumber": 2, "RaceTime": "2:00:00.0"}]},
                {"Place": "", "Bib": "2", "Name": "B", "Time": "DNS", "StartTime": ""},
                {"Place": "", "Bib": "3", "Name": "C", "Time": "DNF", "StartTime": "08:00:00.0",
                 "LapTimes": [{"LapNumber": 1, "RaceTime": "1:10:00.0"}]},
            ],
        },
        {"Grouping": {"Overall": True, "Distance": "5K", "LapCount": 1}, "Racers": []},
    ],
}


@patch("providers.webscorer.fetch_race_results")
def test_poll_once_adds_lap_overview_after_summary(mock_fetch, app, client):
    mock_fetch.return_value = LAP_RACE_RESULTS
    _poll(app)
    pages = client.get("/api/data").get_json()["pages"]
    assert [p["type"] for p in pages[:2]] == ["summary", "lap_overview"]
    lap = pages[1]["data"]
    assert [d["name"] for d in lap["distances"]] == ["5K", "25K"]
    assert lap["totals"]["registered"] == 3
    assert lap["totals"]["dns"] == 1 and lap["totals"]["finished"] == 1 and lap["totals"]["dnf"] == 1
    assert lap["distances"][1]["dnf_by_lap"] == [1, 0]


def test_csv_poll_includes_lap_overview(no_credentials, tmp_path):
    import app as app_module
    application = create_app(_csv_config(tmp_path), start_polling=False)
    app_module.poll_once(application)
    pages = application.test_client().get("/api/data").get_json()["pages"]
    assert pages[1]["type"] == "lap_overview"
    assert all(d["lap_count"] == 1 for d in pages[1]["data"]["distances"])


def test_failed_poll_keeps_last_lap_overview_and_marks_stale(no_credentials, tmp_path):
    import app as app_module
    data_file = tmp_path / "results.csv"
    data_file.write_text("bib,name,time\n1,Alice,1:00:00\n", encoding="utf-8")
    application = create_app(_csv_config(tmp_path, str(data_file)), start_polling=False)
    app_module.poll_once(application)
    lap_page = app_module._cache["pages"][1]
    assert lap_page["type"] == "lap_overview"

    data_file.write_text("bib,name,time\n1,Alice,soon\n", encoding="utf-8")
    app_module.poll_once(application)
    data = application.test_client().get("/api/data").get_json()
    assert data["is_stale"] is True
    assert data["pages"][1] == lap_page


@patch("providers.webscorer.fetch_race_results")
def test_race_switch_drops_lap_overview_until_new_race_polls(mock_fetch, app, client):
    from app import apply_config_reload

    mock_fetch.return_value = LAP_RACE_RESULTS
    _poll(app)
    assert any(p["type"] == "lap_overview" for p in client.get("/api/data").get_json()["pages"])

    started, release = _threading.Event(), _threading.Event()

    def slow_fetch(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return LAP_RACE_RESULTS

    mock_fetch.side_effect = slow_fetch
    worker = _threading.Thread(target=_poll, args=(app,))
    worker.start()
    assert started.wait(5)
    apply_config_reload(app, _reload(app, race_id="200"))
    release.set()
    worker.join(5)

    assert client.get("/api/data").get_json()["pages"] == []
