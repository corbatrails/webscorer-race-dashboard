"""Password-protected admin pages: shared-password login, sessions and CSRF.

The admin is registered only when ``ADMIN_PASSWORD`` is set; otherwise every
``/admin`` route is a 404. The deployment is plain HTTP on a LAN, so the
session cookie is not marked Secure and no HSTS header is sent.
"""
import functools
import hmac
import secrets

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

ADMIN_CSP = (
    "default-src 'self'; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ADMIN_CSP,
}


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = session["csrf_token"] = secrets.token_urlsafe(32)
    return token


def _csrf_valid():
    expected = session.get("csrf_token")
    submitted = request.form.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


def _authenticated():
    return session.get("authenticated") is True


def admin_write(view):
    """Guard a state-changing admin route: login (401) then CSRF (403)."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not _authenticated():
            abort(401)
        if not _csrf_valid():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def admin_page(view):
    """Guard an admin page: logged-out browsers are sent to the login form."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not _authenticated():
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


def _password_matches(submitted):
    expected = current_app.extensions["admin_password"]
    return hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


def _build_blueprint():
    bp = Blueprint("admin", __name__, url_prefix="/admin")

    @bp.after_request
    def security_headers(response):
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("admin_login.html", csrf_token=csrf_token(), error=None)
        if not _csrf_valid():
            abort(403)
        if not _password_matches(request.form.get("password", "")):
            return render_template("admin_login.html", csrf_token=csrf_token(), error="Incorrect password."), 401
        session.clear()
        session["authenticated"] = True
        csrf_token()
        return redirect(url_for("admin.settings"), code=303)

    @bp.route("/logout", methods=["POST"])
    @admin_write
    def logout():
        session.clear()
        return redirect(url_for("admin.login"), code=303)

    @bp.route("", methods=["GET"])
    @admin_page
    def settings():
        return render_template("admin.html", csrf_token=csrf_token())

    return bp


def register_admin(app, password, save_settings):
    """Enable ``/admin`` when ``password`` is non-empty.

    ``save_settings(updates, expected_revision)`` validates, saves and applies
    settings; it is the only write path the admin pages use.
    """
    app.config["admin_enabled"] = bool(password)
    if not password:
        return
    app.secret_key = secrets.token_bytes(32)
    app.config.update(
        SESSION_COOKIE_NAME="dashboard_admin",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
    )
    app.extensions["admin_password"] = password
    app.extensions["admin_save_settings"] = save_settings
    app.register_blueprint(_build_blueprint())
