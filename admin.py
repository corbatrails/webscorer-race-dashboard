"""Password-protected admin pages: shared-password login, sessions and CSRF.

The admin is registered only when ``ADMIN_PASSWORD`` is set; otherwise every
``/admin`` route is a 404. The deployment is plain HTTP on a LAN, so the
session cookie is not marked Secure and no HSTS header is sent.
"""
import functools
import hmac
import secrets
import sys

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, session, url_for

from config import (
    OPTIONS,
    ConfigConflict,
    ConfigError,
    ConfigValidationError,
    config_revision,
    option_choices,
    option_minimum,
    read_config_snapshot,
)
from providers import get_provider, provider_names

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


_OPTION_KEYS = {opt.key for opt in OPTIONS}
_FORM_META_KEYS = {"csrf_token", "revision"}

# (group title, ((key, label, help), ...)). Options missing here land in "Other".
FIELD_GROUPS = (
    ("Race and data source", (
        ("source", "Source", "Where results come from."),
        ("race_id", "WebScorer race", "Leave empty to choose a race when the app starts."),
        ("data_file", "Data file", "Path on the server to a WebScorer JSON dump or a CSV export. "
                                   "When set it is read instead of the live race; CSV needs it."),
    )),
    ("Timing", (
        ("refresh_interval", "Refresh interval (seconds)", "How often results are fetched."),
        ("summary_display_time", "Summary display time (seconds)", None),
        ("scroll_speed", "Scroll speed (pixels per second)", None),
        ("scroll_pause_time", "Scroll pause (seconds)", "Pause before and after scrolling."),
    )),
    ("Pages", (
        ("show_summary", "Show summary page", None),
        ("show_overall_results", "Show Overall result pages", None),
        ("show_category_results", "Show category result pages", None),
        ("show_demographics", "Show demographics page", None),
        ("show_lap_overview", "Show lap overview page", None),
        ("display_unfinished_in_category", "Show category pages before racers finish", None),
        ("display_unfinished_in_overall", "Show Overall pages before racers finish", None),
    )),
    ("Layout", (
        ("overall_results_layout", "Overall results layout", None),
        ("pinned_leaders", "Pinned leader rows", None),
        ("pinned_leaders_on_overall_results", "Pinned leaders and medals on Overall pages", None),
        ("chart_bucket_minutes", "Finish chart bucket (minutes)", None),
    )),
    ("Appearance", (
        ("color_scheme", "Color scheme", None),
        ("show_toasts", "Finish notifications", "Pop-ups when racers finish."),
    )),
)

_CREDENTIALS_MESSAGE = (
    "The selected source needs API credentials that are not configured on the server. "
    "Set a data file instead, or ask whoever runs the server to add them."
)
_CONFLICT_MESSAGE = (
    "Settings changed since this page was loaded (for example a race was picked in the "
    "terminal or the config file was edited). Nothing was saved. Reload the page to see "
    "the current values."
)


def _kind(opt):
    if isinstance(opt.default, bool):
        return "bool"
    if option_choices(opt):
        return "choice"
    if option_minimum(opt) is not None or isinstance(opt.default, int):
        return "int"
    return "text"


def _display(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    return str(value)


def _field_groups(values, errors):
    options = {opt.key: opt for opt in OPTIONS}
    placed = set()
    groups = []

    def field(key, label, help_text):
        opt = options[key]
        placed.add(key)
        return {
            "key": key,
            "label": label,
            "help": help_text,
            "kind": _kind(opt),
            "choices": option_choices(opt) or (),
            "minimum": option_minimum(opt),
            "value": _display(values.get(key, opt.default)),
            "error": errors.get(key),
        }

    for title, entries in FIELD_GROUPS:
        fields = [field(key, label, help_text) for key, label, help_text in entries if key in options]
        if fields:
            groups.append({"title": title, "fields": fields})
    rest = [field(opt.key, opt.key, None) for opt in OPTIONS if opt.key not in placed]
    if rest:
        groups.append({"title": "Other", "fields": rest})
    return groups


def _active_secrets():
    cfg = current_app.config["dashboard"]
    return {"api_id": cfg.get("api_id"), "api_token": cfg.get("api_token")}


def _render_settings(values, revision, *, errors=None, form_error=None, notice=None, status=200):
    return render_template(
        "admin.html",
        csrf_token=csrf_token(),
        revision=revision,
        groups=_field_groups(values, errors or {}),
        form_error=form_error,
        notice=notice,
    ), status


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

    @bp.context_processor
    def theme_context():
        return {"color_scheme": current_app.config["dashboard"].get("color_scheme", "dark")}

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
        path = current_app.config["dashboard_config_path"]
        try:
            values, revision = read_config_snapshot(path, _active_secrets())
            form_error = None
        except ConfigError:
            values, revision = current_app.config["dashboard"], config_revision(path)
            form_error = ("The config file has errors, so the running settings are shown. "
                          "Saving this form replaces the file's values with these.")
        notice = "Settings saved." if request.args.get("saved") else None
        return _render_settings(values, revision, form_error=form_error, notice=notice)

    @bp.route("", methods=["POST"])
    @admin_write
    def save():
        form = request.form
        revision = form.get("revision", "")
        updates = {}
        for opt in OPTIONS:
            if _kind(opt) == "bool":
                updates[opt.key] = opt.key in form
            else:
                updates[opt.key] = form.get(opt.key, "").strip()
        if any(key not in _OPTION_KEYS | _FORM_META_KEYS for key in form):
            return _render_settings(updates, revision, status=400,
                                    form_error="The form contained unsupported fields. Nothing was saved.")
        if not revision:
            return _render_settings(updates, revision, form_error=_CONFLICT_MESSAGE, status=409)
        try:
            current_app.extensions["admin_save_settings"](updates, revision)
        except ConfigValidationError as e:
            errors = {k: v for k, v in e.errors.items() if k in _OPTION_KEYS}
            form_error = _CREDENTIALS_MESSAGE if len(errors) < len(e.errors) else "Fix the highlighted settings."
            return _render_settings(updates, revision, errors=errors, form_error=form_error, status=400)
        except ConfigConflict:
            return _render_settings(updates, revision, form_error=_CONFLICT_MESSAGE, status=409)
        except ConfigError as e:
            return _render_settings(updates, revision, form_error=f"Could not save settings: {e}", status=500)
        return redirect(url_for("admin.settings", saved=1), code=303)

    @bp.route("/races", methods=["GET"])
    def races():
        if not _authenticated():
            return jsonify(error="Log in first."), 401
        source = request.args.get("source", "")
        if source not in provider_names():
            return jsonify(error="Unknown source."), 400
        provider = get_provider(source)
        if not provider.list_races:
            return jsonify(races=[], supported=False)
        cfg = current_app.config["dashboard"]
        provider_secrets = {key: cfg.get(key) for key in provider.required_secrets}
        if not all(provider_secrets.values()):
            return jsonify(error="Race list unavailable: API credentials are not configured on the server."), 502
        try:
            choices = provider.list_races(cfg, provider_secrets)
        except Exception as e:
            print(f"WARNING: admin race list failed ({type(e).__name__})", file=sys.stderr)
            return jsonify(error="Could not load the race list. Check the server console and try again."), 502
        return jsonify(races=[
            {field: str(race[field]) for field in ("id", "name", "date", "sport")} for race in choices
        ])

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
