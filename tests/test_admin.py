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
