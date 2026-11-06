# Unified Operator Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared top navigation and visual conventions to the race-staff pages while keeping Progress and Results read-only, unauthenticated, and restricted by deployment to a staff-only network or location.

**Architecture:** Add one Jinja navigation partial to Race control, Race results, and Admin. Use URL state to open either Race control view directly, reuse the existing Admin session and CSRF-protected logout, and add shared operator styles without changing the TV dashboard or shared API.

**Tech Stack:** Python, Flask, Jinja, vanilla JavaScript and CSS, pytest, Node.js `node:test`.

**Spec:** `docs/superpowers/specs/2026-11-04-unified-operator-console-design.md`

## Global Constraints

- The app uses Flask, Jinja templates, vanilla JavaScript, and CSS. Prefer these existing tools and the shared theme variables in `static/theme.css`.
- `ADMIN_PASSWORD` is optional. When unset, the app disables Admin and Observability while continuing to serve Progress, Results, and the TV display at `/`.
- The app does not verify that a person viewing `/race-control` or `/results` belongs to race staff. The deployment must restrict those pages to a staff-only network or location.
- Admin writes remain authenticated and CSRF-protected. The shared navigation must not weaken that boundary.
- `race_control.html` combines progress and detailed results in separate views. `/results` is a distinct, read-only winner-announcement page. Keep their purposes clear rather than merging their data or behavior.
- The shared console shell must not change kiosk styling.
- Do not add configuration options, dependencies, users, roles, TLS, or password-management features.

## Review Focus

- `ADMIN_PASSWORD` unset: hide unavailable Admin navigation while keeping `/`, `/race-control`, and `/results` available; pin with `test_operator_pages_stay_public_when_admin_disabled` in `tests/test_app.py`.
- Logged-out visitor selects Admin: require the existing login and preserve the Admin destination; pin with `test_admin_nav_requires_login` in `tests/test_admin.py`.
- Unknown `view` query on `/race-control`: fall back to Progress; pin with `test_race_control_invalid_view_defaults_to_progress` in `tests/test_race_control.py` and `test_initial_view_falls_back_to_progress` in `tests/race_control.test.cjs`.
- Logout from a public result page with an authenticated session: require a valid CSRF token, clear the session, keep public pages available, and require login for Admin; pin with `test_logout_from_results_clears_admin_session` in `tests/test_admin.py`.
- Narrow viewport and either color scheme: keep every navigation destination reachable, preserve focus visibility, and prevent horizontal page overflow; verify in the browser with fixture data.

---

### Task 1: Add Shared Navigation and Direct Race Control Links

**Files:**
- Create: `templates/operator_nav.html`
- Modify: `app.py`
- Modify: `admin.py`
- Modify: `templates/race_control.html`
- Modify: `templates/results.html`
- Modify: `templates/admin.html`
- Modify: `static/race_control.js`
- Test: `tests/test_app.py`
- Test: `tests/test_admin.py`
- Test: `tests/test_race_control.py`
- Test: `tests/race_control.test.cjs`

**Interfaces:**
- Consumes: Flask's `config`, `session`, and `url_for`; the current Admin password-enabled flag; the existing session authentication and CSRF values.
- Produces: `templates/operator_nav.html`, which consumes `active_destination` and renders links for Race progress (`/race-control?view=progress`), detailed results (`/race-control?view=results`), Winner announcements (`/results`), and enabled Admin (`/admin`). It uses `.operator-nav`, `.operator-nav__link`, `.operator-nav__link.is-active`, and `.operator-nav__logout`.
- Produces: `race_control()` validates `request.args["view"]` against `progress` and `results`, defaults invalid or missing values to `progress`, and passes `initial_view` to the template.
- `race_control.html` exposes `initial_view` as `body[data-initial-view]`. `race_control.js` initializes `state.view` from that value and falls back to `progress`.
- Admin and Observability remain protected by their existing or future routes. Do not add an Observability link until #98 provides a page.

- [ ] **Step 1: Add failing route and navigation tests**

In `tests/test_app.py`, add `test_operator_pages_stay_public_when_admin_disabled`:

```python
assert client.get("/race-control").status_code == 200
assert client.get("/results").status_code == 200
assert 'href="/admin"' not in client.get("/results").get_data(as_text=True)
assert 'class="operator-nav"' not in client.get("/").get_data(as_text=True)
```

In `tests/test_admin.py`, add `test_operator_navigation_is_shared`,
`test_admin_nav_requires_login`, and
`test_logout_from_results_clears_admin_session`. Assert that Race control,
Results, and Admin render the same destination links; no Observability link
appears before #98; a logged-out `/admin` request redirects to `/admin/login`;
and logout from Results requires the session CSRF token, clears the session,
keeps Results public, and requires login for the next Admin request.

In `tests/test_race_control.py`, add
`test_race_control_invalid_view_defaults_to_progress`. Assert
`/race-control?view=results` renders `data-initial-view="results"` and an
unknown view renders `data-initial-view="progress"`.

Run: `pytest tests/test_app.py tests/test_admin.py tests/test_race_control.py -q`
Expected: FAIL on the new navigation and route-state assertions.

- [ ] **Step 2: Add failing JavaScript tests for initial Race control view**

Update the Node test harness so a test can set `document.body.dataset.initialView` before `Control.start(env)`. Add `test_initial_view_uses_results_query` and `test_initial_view_falls_back_to_progress`; assert the resulting `state.view` is `results` and `progress`, respectively.

Run: `node --test tests/race_control.test.cjs`
Expected: FAIL because `race_control.js` still starts on Progress for every URL.

- [ ] **Step 3: Implement the shared navigation partial**

Create `templates/operator_nav.html`. Use semantic `<nav>` markup with an accessible label and `aria-current="page"` for the active destination. Link Race progress and detailed results to `/race-control` with their respective `view` query values; link Winner announcements to `/results`; render Admin only when `config["admin_enabled"]` is true. Render the existing CSRF-protected logout form only for an authenticated session. Do not add an Observability placeholder.

- [ ] **Step 4: Include the navigation on director pages**

Include the partial in `race_control.html`, `results.html`, and `admin.html`.
Pass `active_destination="announcements"` from `results()`,
`active_destination="admin"` from `_render_settings()`, and either
`"progress"` or `"detailed-results"` from `race_control()` based on
`initial_view`. Keep `dashboard.html` and `admin_login.html` outside the shared
navigation. Remove the old duplicated Admin/Results links from page headers,
but retain page-specific race status, result tabs, and settings actions.

- [ ] **Step 5: Support direct Race control view selection**

In `app.py`, validate the `view` query value and pass `initial_view` to `race_control.html`. Set `body[data-initial-view]` in that template. Initialize the `state.view` field in `static/race_control.js` from the body data attribute, accepting only `progress` or `results`.

- [ ] **Step 6: Run targeted route and script tests**

Run:

```powershell
pytest tests/test_app.py tests/test_admin.py tests/test_race_control.py -q
node --test tests/race_control.test.cjs
```

Expected: PASS, including unchanged public access to Progress and Results, existing Admin authentication and CSRF coverage, hidden Admin navigation when disabled, direct Race control view selection, and no TV navigation.

- [ ] **Step 7: Commit the navigation change**

```powershell
git add app.py admin.py templates/operator_nav.html templates/race_control.html templates/results.html templates/admin.html static/race_control.js tests/test_app.py tests/test_admin.py tests/test_race_control.py tests/race_control.test.cjs
git commit -m "feat: add shared race director navigation" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Apply Shared Operator Styles and Document the Access Boundary

**Depends on:** Task 1.

**Files:**
- Create: `static/operator.css`
- Modify: `templates/race_control.html`
- Modify: `templates/results.html`
- Modify: `templates/admin.html`
- Modify: `README.md`
- Test: `tests/test_app.py`
- Test: `tests/test_admin.py`
- Test: `tests/test_race_control.py`

**Interfaces:**
- Consumes: the shared navigation classes `.operator-nav`, `.operator-nav__link`, `.operator-nav__link.is-active`, and `.operator-nav__logout` from Task 1.
- Produces: `static/operator.css`, which styles those classes and shared operator typography, controls, status treatments, focus, active state, and spacing using the existing theme variables.
- Page-specific stylesheets continue to own their data layouts. `dashboard.html` does not load `operator.css`.
- README states that Progress and Results have no app login and must run only on a staff-restricted network or at a staff-only location; Admin uses `ADMIN_PASSWORD`.

- [ ] **Step 1: Add failing shared-style asset assertions**

Add `test_operator_pages_include_shared_styles` in `tests/test_app.py` and
`tests/test_admin.py`, plus an assertion in the existing Race control asset
test. Assert that Race control, Results, and Admin include `/static/operator.css`
and the TV dashboard does not.

Run: `pytest tests/test_app.py tests/test_admin.py tests/test_race_control.py -q`
Expected: FAIL because the shared stylesheet does not exist or is not linked.

- [ ] **Step 2: Add the shared operator stylesheet**

Create `static/operator.css` with the top navigation and shared console primitives. Reuse variables from `theme.css`; keep the selectors scoped to operator pages. Include visible focus and active states. Add a narrow-screen treatment that keeps all destinations reachable without horizontal page overflow. Do not alter the TV stylesheet or its layout.

- [ ] **Step 3: Load shared styles without changing page-specific layouts**

Link `operator.css` on the Race control, Results, and Admin templates after `theme.css` and before each page-specific stylesheet. Add only the shared classes needed for consistent headers, navigation, controls, and status messages; keep the progress grid, tables, announcement layout, and Admin form intact.

- [ ] **Step 4: Update the README**

Update the Race control, Race results, and Admin sections to describe the shared navigation and access boundary. State that `/race-control` and `/results` remain unauthenticated and read-only, so operators must deploy them on a race-staff-restricted network or at a staff-only location. State that Admin uses `ADMIN_PASSWORD`, and keep the public TV display and shared API behavior distinct.

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
pytest tests/test_app.py tests/test_admin.py tests/test_race_control.py -q
node --test tests/race_control.test.cjs
```

Expected: PASS, including shared stylesheet inclusion on director pages and its absence from the TV dashboard.

- [ ] **Step 6: Verify the UI with fixture data**

Create a temporary YAML configuration outside the repository with `source: csv` and `data_file` pointing to an existing fixture. Run `python app.py --config <temp.yaml>` and inspect Race progress, detailed results, Winner announcements, and Admin in a browser. Check both dark and light themes, a desktop viewport, and a narrow viewport; confirm focus visibility, reachable links, and no horizontal overflow. Do not overwrite `config.yaml` or use live credentials.

- [ ] **Step 7: Commit the visual and documentation change**

```powershell
git add static/operator.css templates/race_control.html templates/results.html templates/admin.html README.md tests/test_app.py tests/test_admin.py tests/test_race_control.py
git commit -m "feat: align race director page styles" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```
