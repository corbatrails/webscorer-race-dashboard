import hmac
import re

import pytest

import admin as admin_module
from app import create_app

PASSWORD = "pässwörd-SENTINEL-7731"
API_ID = "APIID-SENTINEL-4410"
API_TOKEN = "APITOKEN-SENTINEL-9902"
SENTINELS = (PASSWORD, API_ID, API_TOKEN)


def _app(tmp_path, password=PASSWORD):
    path = tmp_path / "config.yaml"
    path.write_text("race_id: '100'\n", encoding="utf-8")
    config = {"api_id": API_ID, "api_token": API_TOKEN, "race_id": "100"}
    return create_app(config, start_polling=False, config_path=str(path), admin_password=password)


def _csrf(client, url="/admin/login"):
    html = client.get(url).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, html
    return match.group(1)


def _login(client, password=PASSWORD):
    token = _csrf(client)
    return client.post("/admin/login", data={"password": password, "csrf_token": token})


def _session(client):
    with client.session_transaction() as sess:
        return dict(sess)


@pytest.fixture
def client(tmp_path):
    return _app(tmp_path).test_client()


def test_unset_password_disables_admin(tmp_path):
    for password in (None, ""):
        app = _app(tmp_path, password=password)
        c = app.test_client()
        assert c.get("/admin").status_code == 404
        assert c.get("/admin/login").status_code == 404
        assert c.post("/admin/login", data={"password": "x"}).status_code == 404
        assert c.post("/admin/logout").status_code == 404
        assert c.get("/api/data").get_json()["admin_enabled"] is False


def test_api_data_reports_admin_enabled_without_password(client):
    response = client.get("/api/data")
    assert response.get_json()["admin_enabled"] is True
    assert PASSWORD not in response.get_data(as_text=True)


def test_admin_redirects_to_login_when_logged_out(client):
    response = client.get("/admin")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/login")


def test_login_uses_constant_time_bytes_comparison(client, monkeypatch):
    calls = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((type(a), type(b)))
        return real(a, b)

    monkeypatch.setattr(admin_module.hmac, "compare_digest", spy)

    bad = _login(client, "wrong")
    assert bad.status_code == 401
    assert "Incorrect password" in bad.get_data(as_text=True)
    assert _session(client).get("authenticated") is not True
    assert (bytes, bytes) in calls

    good = _login(client)
    assert good.status_code == 303
    assert good.headers["Location"].endswith("/admin")
    assert _session(client).get("authenticated") is True
    assert client.get("/admin").status_code == 200


def test_csrf_required_for_login_and_logout(client):
    assert client.post("/admin/login", data={"password": PASSWORD}).status_code == 403
    _csrf(client)
    assert client.post("/admin/login", data={"password": PASSWORD, "csrf_token": "nope"}).status_code == 403
    assert _session(client).get("authenticated") is not True

    before = _session(client)["csrf_token"]
    assert _login(client).status_code == 303
    after = _session(client)["csrf_token"]
    assert after != before

    assert client.post("/admin/logout", data={}).status_code == 403
    assert client.post("/admin/logout", data={"csrf_token": before}).status_code == 403
    assert _session(client).get("authenticated") is True

    response = client.post("/admin/logout", data={"csrf_token": after})
    assert response.status_code == 303
    assert "authenticated" not in _session(client)
    assert client.get("/admin").status_code == 302


def test_login_discards_preexisting_session_values(client):
    _csrf(client)
    with client.session_transaction() as sess:
        sess["planted"] = "value"
    _login(client)
    assert "planted" not in _session(client)


def test_admin_headers_and_cookie(client):
    response = client.get("/admin/login")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    csp = response.headers["Content-Security-Policy"]
    for directive in ("default-src 'self'", "object-src 'none'", "base-uri 'none'",
                      "frame-ancestors 'none'", "form-action 'self'"):
        assert directive in csp
    assert "Strict-Transport-Security" not in response.headers

    _login(client)
    page = client.get("/admin")
    assert page.headers["Cache-Control"] == "no-store"
    assert "Content-Security-Policy" in page.headers


def test_dashboard_keeps_its_own_headers(client):
    assert "Content-Security-Policy" not in client.get("/").headers


def test_admin_responses_never_contain_secrets(client):
    pages = [
        client.get("/admin/login"),
        _login(client, "wrong"),
        _login(client),
        client.get("/admin"),
        client.get("/api/data"),
    ]
    for response in pages:
        body = response.get_data(as_text=True)
        headers = str(response.headers)
        for secret in SENTINELS:
            assert secret not in body and secret not in headers
    for secret in SENTINELS:
        assert secret not in str(_session(client))


def test_signing_key_is_random_per_app(tmp_path):
    a = _app(tmp_path)
    b = _app(tmp_path)
    assert a.secret_key and b.secret_key and a.secret_key != b.secret_key
    assert PASSWORD.encode() not in a.secret_key


def test_require_admin_post_guard(tmp_path):
    """Future settings writes share the login + CSRF guard."""
    app = _app(tmp_path)

    @app.route("/admin/_probe", methods=["POST"])
    @admin_module.admin_write
    def probe():
        return "ok"

    c = app.test_client()
    assert c.post("/admin/_probe").status_code == 401
    _login(c)
    assert c.post("/admin/_probe").status_code == 403
    token = _session(c)["csrf_token"]
    assert c.post("/admin/_probe", data={"csrf_token": token}).status_code == 200


# --- Settings form and race list (Task 6) --------------------------------------

import os
from html.parser import HTMLParser
from unittest.mock import patch

import yaml

from config import OPTIONS

REPO_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
SAMPLE_CSV = os.path.join(os.path.dirname(REPO_CONFIG), "docs", "sample-results.csv")
OPTION_KEYS = {opt.key for opt in OPTIONS}


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self._select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and "name" in a:
            if a.get("type") == "checkbox":
                self.fields[a["name"]] = "true" if "checked" in a else None
            else:
                self.fields[a["name"]] = a.get("value", "")
        elif tag == "select" and "name" in a:
            self._select = a["name"]
            self.fields.setdefault(self._select, None)
        elif tag == "option" and self._select and "selected" in a:
            self.fields[self._select] = a.get("value")

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None


def _form(client):
    response = client.get("/admin")
    assert response.status_code == 200
    parser = _FormParser()
    parser.feed(response.get_data(as_text=True))
    return parser.fields


def _post_form(client, fields, **changes):
    data = {k: v for k, v in fields.items() if v is not None}
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return client.post("/admin", data=data)


def _yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _settings_app(tmp_path, text="race_id: '100'\n", api=True):
    path = tmp_path / "admin config.yaml"
    path.write_text(text, encoding="utf-8")
    from config import resolve_config
    secrets = {"api_id": API_ID, "api_token": API_TOKEN} if api else {}
    config = resolve_config(yaml.safe_load(text) or {}, secrets)
    app = create_app(config, start_polling=False, config_path=str(path), admin_password=PASSWORD)
    c = app.test_client()
    _login(c)
    return app, c, path


def test_form_covers_option_registry(tmp_path):
    _, c, _ = _settings_app(tmp_path, "race_id: '100'\nshow_demographics: false\nscroll_speed: 140\n")
    fields = _form(c)
    assert set(fields) - {"csrf_token", "revision"} == OPTION_KEYS
    assert fields["revision"]
    assert fields["race_id"] == "100"
    assert fields["data_file"] == ""
    assert fields["scroll_speed"] == "140"
    assert fields["show_summary"] == "true"
    assert fields["show_demographics"] is None
    assert fields["source"] == "webscorer"
    assert fields["color_scheme"] == "dark"


def test_save_updates_only_selected_config(tmp_path):
    repo_before = open(REPO_CONFIG, "rb").read()
    app, c, path = _settings_app(tmp_path)
    fields = _form(c)

    response = _post_form(c, fields, scroll_speed="250", show_demographics="true", show_toasts=None)
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/admin?saved=1")

    saved = _yaml(path)
    assert saved["scroll_speed"] == 250
    assert saved["show_demographics"] is True
    assert saved["show_toasts"] is False
    assert saved["race_id"] == "100"
    assert app.config["dashboard"]["scroll_speed"] == 250
    assert app.config["dashboard"]["show_toasts"] is False
    assert open(REPO_CONFIG, "rb").read() == repo_before
    assert "Settings saved" in c.get("/admin?saved=1").get_data(as_text=True)


def test_validation_error_keeps_submitted_values(tmp_path):
    app, c, path = _settings_app(tmp_path)
    before_file, before_cfg = path.read_bytes(), app.config["dashboard"]
    fields = _form(c)

    response = _post_form(c, fields, scroll_speed="0", data_file="<script>x</script>")
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "at least 1" in body
    assert "<script>x</script>" not in body
    assert "&lt;script&gt;x&lt;/script&gt;" in body
    parser = _FormParser()
    parser.feed(body)
    assert parser.fields["scroll_speed"] == "0"
    assert path.read_bytes() == before_file
    assert app.config["dashboard"] is before_cfg


def test_unknown_and_secret_fields_are_rejected(tmp_path):
    _, c, path = _settings_app(tmp_path)
    before = path.read_bytes()
    fields = _form(c)
    assert _post_form(c, fields, mystery="1").status_code == 400
    response = _post_form(c, fields, api_token="LEAKED-VALUE-123")
    assert response.status_code == 400
    assert "LEAKED-VALUE-123" not in response.get_data(as_text=True)
    assert path.read_bytes() == before


def test_settings_post_requires_login_and_csrf(tmp_path):
    _, c, path = _settings_app(tmp_path)
    fields = _form(c)
    before = path.read_bytes()
    assert _post_form(c, fields, csrf_token="bad").status_code == 403
    c.post("/admin/logout", data={"csrf_token": fields["csrf_token"]})
    assert _post_form(c, fields).status_code == 401
    assert path.read_bytes() == before


def test_stale_startup_form_cannot_overwrite_cli(tmp_path):
    from app import update_dashboard

    app, c, path = _settings_app(tmp_path, "race_id: null\n")
    stale = _form(c)
    assert stale["race_id"] == ""

    assert update_dashboard(app, {"race_id": "100"}, startup_only=True) is True  # terminal wins

    response = _post_form(c, stale, race_id="200")
    assert response.status_code == 409
    assert "changed" in response.get_data(as_text=True)
    assert _yaml(path)["race_id"] == "100"

    fresh = _form(c)
    assert fresh["race_id"] == "100"
    assert _post_form(c, fresh, race_id="200").status_code == 303
    assert _yaml(path)["race_id"] == "200"
    assert app.config["dashboard"]["race_id"] == "200"


def test_missing_credentials_get_generic_error(tmp_path):
    _, c, path = _settings_app(tmp_path, f"source: csv\ndata_file: '{SAMPLE_CSV}'\n", api=False)
    fields = _form(c)
    response = _post_form(c, fields, source="webscorer", data_file="")
    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "credentials" in body
    assert "WEBSCORER_API" not in body
    assert _yaml(path)["source"] == "csv"


def test_invalid_file_still_renders_form(tmp_path):
    app, c, path = _settings_app(tmp_path)
    path.write_text("scroll_speed: fast\n", encoding="utf-8")
    fields = _form(c)
    assert set(fields) - {"csrf_token", "revision"} == OPTION_KEYS
    assert fields["scroll_speed"] == str(app.config["dashboard"]["scroll_speed"])
    assert "has errors" in c.get("/admin").get_data(as_text=True)
    assert _post_form(c, fields).status_code == 303
    assert _yaml(path)["scroll_speed"] == app.config["dashboard"]["scroll_speed"]


@patch("providers.webscorer.fetch_race_results")
def test_save_does_not_preflight_results(mock_results, tmp_path):
    _, c, _ = _settings_app(tmp_path)
    assert _post_form(c, _form(c), race_id="555").status_code == 303
    mock_results.assert_not_called()


@patch("providers.webscorer.fetch_race_list")
def test_authenticated_race_list_uses_selected_provider(mock_list, tmp_path):
    app, c, _ = _settings_app(tmp_path, f"source: csv\ndata_file: '{SAMPLE_CSV}'\n")
    mock_list.return_value = [
        {"RaceId": 7, "Name": "<img src=x onerror=alert(1)>", "Date": "2026-08-07", "Sport": "Running", "Extra": "x"},
    ]

    response = c.get("/admin/races?source=webscorer")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    races = response.get_json()["races"]
    assert races == [{"id": "7", "name": "<img src=x onerror=alert(1)>", "date": "2026-08-07", "sport": "Running"}]
    mock_list.assert_called_once_with(API_ID, API_TOKEN)

    assert c.get("/admin/races?source=csv").get_json() == {"races": [], "supported": False}
    assert c.get("/admin/races?source=nope").status_code == 400

    mock_list.side_effect = RuntimeError(f"401 https://x/?apiid={API_ID}&apipriv={API_TOKEN}")
    failed = c.get("/admin/races?source=webscorer")
    assert failed.status_code == 502
    for secret in SENTINELS:
        assert secret not in failed.get_data(as_text=True)

    logged_out = app.test_client()
    assert logged_out.get("/admin/races?source=webscorer").status_code == 401


def test_race_list_without_credentials_is_generic(tmp_path):
    _, c, _ = _settings_app(tmp_path, f"source: csv\ndata_file: '{SAMPLE_CSV}'\n", api=False)
    response = c.get("/admin/races?source=webscorer")
    assert response.status_code == 502
    body = response.get_data(as_text=True)
    assert "credentials" in body and "WEBSCORER_API" not in body


def test_form_loads_external_script_only(tmp_path):
    _, c, _ = _settings_app(tmp_path)
    body = c.get("/admin").get_data(as_text=True)
    assert 'src="/static/admin.js' in body
    assert "<script>" not in body


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
RACE_A = os.path.join(FIXTURES, "race_a_live.json")
RACE_B = os.path.join(FIXTURES, "race_b_teamname.json")
DISPLAY_KEYS = ("scroll_speed", "pinned_leaders", "refresh_interval", "show_toasts", "color_scheme")


@patch("providers.webscorer.fetch_race_results", side_effect=AssertionError("no network"))
@patch("providers.webscorer.fetch_race_list")
def test_fixture_admin_flow_persists_and_reloads(mock_list, _no_results, tmp_path):
    from app import apply_config_reload, poll_once
    from config import ConfigWatcher

    mock_list.return_value = [{"RaceId": 1, "Name": "Fake Race", "Date": "2026-10-30", "Sport": "Running"}]
    app, c, path = _settings_app(tmp_path, "refresh_interval: 30\n")
    api = lambda: c.get("/api/data").get_json()

    start = api()
    assert start["race_selection_required"] is True
    assert not app.extensions["startup_race_selected"].is_set()
    assert c.get("/admin/races?source=webscorer").get_json()["races"][0]["name"] == "Fake Race"

    # Initial selection through the admin form, then a poll reads the fixture
    assert _post_form(c, _form(c), data_file=RACE_A).status_code == 303
    assert app.extensions["startup_race_selected"].is_set()
    poll_once(app)
    first = api()
    assert first["race_selection_required"] is False
    assert first["race_generation"] == start["race_generation"] + 1
    assert first["race_name"] == "2026 Coon Fork 40 TEST"
    assert first["waiting"] is False and first["pages"]

    # A display setting keeps the race and its cached results
    assert _post_form(c, _form(c), scroll_speed="250", show_toasts=None).status_code == 303
    tuned = api()
    assert tuned["race_generation"] == first["race_generation"]
    assert tuned["config_version"] > first["config_version"]
    assert tuned["race_name"] == first["race_name"]

    # A hand edit is picked up by the watcher once it settles
    watcher = ConfigWatcher(str(path))
    text = path.read_text(encoding="utf-8")
    edited = re.sub(r"^pinned_leaders:.*$", "pinned_leaders: 10", text, flags=re.M)
    assert edited != text
    path.write_text(edited, encoding="utf-8")
    assert watcher.check(app.config["dashboard"]) is None
    reload = watcher.check(app.config["dashboard"])
    assert reload is not None
    apply_config_reload(app, reload)
    assert api()["pinned_leaders"] == 10
    assert _form(c)["pinned_leaders"] == "10"

    # A later switch replaces the old race entirely
    assert _post_form(c, _form(c), data_file=RACE_B).status_code == 303
    switched = api()
    assert switched["race_generation"] == first["race_generation"] + 1
    assert switched["waiting"] is True and switched["pages"] == [] and switched["race_name"] != first["race_name"]
    poll_once(app)
    final = api()
    assert final["race_name"] == "CORBA Fall Back Blast Trail Run 2025"

    saved = _yaml(path)
    assert saved["data_file"] == RACE_B
    for key in DISPLAY_KEYS:
        assert saved[key] == final[key], key
    assert final["scroll_speed"] == 250 and final["show_toasts"] is False
