# Bootstrap Woodland Theme Implementation Plan

> **Historical plan:** This records the initial Woodland rollout. The [configuration reference](../../../README.md#configuration) lists the current theme choices and default.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply Bootstrap 5.3.8 and the high-contrast Woodland theme to every staff and TV dashboard page, with light mode as the new-install default.

**Architecture:** Vendor Bootstrap's compiled CSS locally and use it with the existing server-rendered templates. Keep `data-theme` for current app CSS and Chart.js behavior, add matching `data-bs-theme` for Bootstrap, and update both when the API reports a config change. Retain custom CSS for the TV dashboard's fixed viewport, dynamic grids, and rotation-specific elements.

**Tech Stack:** Flask/Jinja, Bootstrap 5.3.8 CSS, existing CSS custom properties, vanilla JavaScript, pytest, Node.js built-in test runner.

**Spec:** `docs/superpowers/specs/2026-11-08-woodland-high-contrast-theme-design.md`

## Global Constraints

- Pin Bootstrap CSS to version 5.3.8 and store the distributed stylesheet under `static/vendor/`.
- Do not use a CDN or add Bootstrap JavaScript. Self-host the Bootstrap CSS so the Admin Content Security Policy remains effective.
- Default new installations to light and preserve an explicit dark selection.
- In the light palette, target at least 7:1 contrast for meaningful text and at least 3:1 for meaningful dividers and progress indicators.
- Keep cards compact and flat; avoid decorative colored edge stripes, pill-shaped controls, and oversized rounded panels.
- Preserve the user's existing uncommitted `config.yaml` changes by stashing that path before implementation and restoring it after the planned commits.
- Confirm readability on the installed TV at the venue, from the expected viewing distance and under the actual glare conditions.

## Review Focus

- A live `color_scheme` update must keep `body[data-theme]`, `body[data-bs-theme]`, and chart colors synchronized; test the dashboard, Race Control, and announcements pollers.
- Admin pages must load only same-origin assets under the existing CSP; test the generated login and settings pages and their response headers.
- Bootstrap's `.toast` and `.visible` utilities must not break finish notifications or the pause indicator; test the generated dashboard markup and state changes.
- Unequal distances and large lap counts must stay inside the fixed TV viewport; exercise lap-grid and demographics layouts in fixture-backed browser checks.
- Semantic colors, dividers, keyboard focus, and narrow staff-page layouts must remain distinguishable; test contrast tokens and inspect both modes at TV and phone viewport sizes.

---

### Task 1: Vendor Bootstrap and establish the Woodland theme

**Files:**
- Create: `static/vendor/bootstrap.min.css`
- Modify: `static/vendor/vendor.json`
- Modify: `static/theme.css`
- Modify: `config.py:108` (`OPTIONS` default for `color_scheme`)
- Modify: `app.py:135-202` (template-context fallbacks for `color_scheme`)
- Modify: `config.yaml` (`color_scheme` default for new installations)
- Modify: `README.md:126` (configuration option table)
- Modify: `docs/superpowers/specs/2026-11-08-woodland-high-contrast-theme-design.md`
- Test: `tests/test_config.py`
- Test: `tests/test_app.py`
- Create: `tests/test_theme.py`

**Interfaces:**
- Produces `/static/vendor/bootstrap.min.css`, pinned to 5.3.8 and recorded with its license and source URL in `static/vendor/vendor.json`.
- Produces light/dark custom properties in `static/theme.css`; keep the existing token names used by current CSS and add Bootstrap variable mappings.
- Provides the configured theme value and Bootstrap mappings that later page tasks use to render synchronized `data-theme` and `data-bs-theme` attributes.

**Approved palette starting values:**

| Token | Light | Dark |
|---|---|---|
| Page background | `#F2F0E5` | `#171D18` |
| Card background | `#FFFDF6` | `#252E25` |
| Navigation background | `#E6EADC` | `#202820` |
| Main text | `#20281F` | `#F3F0E5` |
| Muted text | `#424C3E` | `#B0B6A7` |
| Primary forest/sage accent | `#374F2D` | `#9AAF78` |
| Divider | `#7B8474` | `#39443A` |
| Progress track | `#D0D8C4` | `#3B4637` |

These are starting colors, not permission to skip contrast checks. In light mode, target at least 7:1 for meaningful text and 3:1 for meaningful dividers and progress indicators. In dark mode, target at least 4.5:1 for text and 3:1 for meaningful boundaries. Verify the actual CSS declarations.

- [ ] **Step 1: Write failing default and contrast tests**

Update all config-default assertions to expect `color_scheme == "light"`. Keep `test_index_includes_data_theme` unchanged because its shared app fixture explicitly selects dark; add a separate test that creates an app without `color_scheme` and verifies the light fallback in rendered pages and `/api/data`. In `tests/test_theme.py`, read the actual CSS tokens and add `contrast_ratio(foreground: str, background: str) -> float` plus tests for:
  - meaningful light text pairs at least 7:1;
  - light dividers and progress fill at least 3:1;
  - dark text at least 4.5:1 and meaningful boundaries at least 3:1.

Keep explicit dark-mode tests unchanged and verify that an omitted setting uses light.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest tests/test_config.py tests/test_app.py tests/test_theme.py -q`

Expected: FAIL because the configured default and Woodland tokens have not been updated.

- [ ] **Step 3: Add the Bootstrap asset, theme tokens, and light default**

Store the official Bootstrap 5.3.8 compiled CSS, preserving its license header. Record `version`, `url`, `file`, and `license` in `static/vendor/vendor.json`. Map the approved palette to existing app tokens and Bootstrap color variables. Set the `OPTIONS` default, the `app.py` template-context fallbacks, and the committed `config.yaml` default to `light`, then update the README default. The user's `config.yaml` changes are stashed before implementation and restored after all planned commits. Keep `_format_config_lines` behavior unchanged; it reports the active value from config.

- [ ] **Step 4: Run focused tests and verify they pass**

Run: `pytest tests/test_config.py tests/test_app.py tests/test_theme.py -q`

Expected: PASS, including contrast checks against the actual CSS declarations.

- [ ] **Step 5: Commit the foundation**

```bash
git add static/vendor/bootstrap.min.css static/vendor/vendor.json static/theme.css config.py config.yaml README.md tests/test_config.py tests/test_app.py tests/test_theme.py docs/superpowers/specs/2026-11-08-woodland-high-contrast-theme-design.md
git commit -m "feat: add Bootstrap Woodland theme foundation"
```

### Task 2: Migrate Race Progress, Detailed Results, and Winner Announcements

**Files:**
- Modify: `templates/operator_nav.html`
- Modify: `templates/race_control.html`
- Modify: `templates/results.html`
- Modify: `static/operator.css`
- Modify: `static/race_control.css`
- Modify: `static/results.css`
- Modify: `static/race_control.js`
- Modify: `static/results.js`
- Test: `tests/test_app.py`
- Test: `tests/test_race_control.py`
- Test: `tests/race_control.test.cjs`
- Test: `tests/results.test.cjs`

**Interfaces:**
- Consume Task 1's local Bootstrap stylesheet, Woodland variables, and synchronized body theme attributes.
- Preserve current IDs, data attributes, `aria-*` states, and generated DOM contracts consumed by `race_control.js` and `results.js`.

- [ ] **Step 1: Add failing template and live-theme tests**

Extend `test_operator_pages_include_shared_styles`, `test_results_page_renders_theme_and_assets`, and `test_race_control_route_renders_configured_theme` to require the local Bootstrap asset and matching `data-theme`/`data-bs-theme` values for both modes. Add Node tests that an API response changing `color_scheme` updates both body attributes in Race Control and announcements.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest tests/test_app.py tests/test_race_control.py -q`

Run: `node --test tests/race_control.test.cjs tests/results.test.cjs`

Expected: FAIL because the operator templates and runtime theme updates do not yet include Bootstrap's color-mode attribute.

- [ ] **Step 3: Migrate the shared navigation and operator-page components**

Load the local Bootstrap stylesheet in the Race Progress and results templates. Apply Bootstrap navigation, grid, table, form, button, status, and spacing classes where they replace existing shared presentation. Update `operator.css`, `race_control.css`, and `results.css` for the Woodland Paddock appearance and retain page-specific layouts, scroll behavior, filters, and responsive breakpoints. When the pollers receive a valid `color_scheme`, update both `document.body.dataset.theme` and `document.body.dataset.bsTheme` to that value.

- [ ] **Step 4: Run operator tests and verify they pass**

Run: `pytest tests/test_app.py tests/test_race_control.py -q`

Run: `node --test tests/race_control.test.cjs tests/results.test.cjs`

Expected: PASS with unchanged route and data behavior and synchronized mode updates.

- [ ] **Step 5: Commit operator pages**

```bash
git add templates/operator_nav.html templates/race_control.html templates/results.html static/operator.css static/race_control.css static/results.css static/race_control.js static/results.js tests/test_app.py tests/test_race_control.py tests/race_control.test.cjs tests/results.test.cjs
git commit -m "feat: apply Woodland Bootstrap to operator pages"
```

### Task 3: Migrate Admin and Admin login under the existing CSP

**Files:**
- Modify: `templates/admin.html`
- Modify: `templates/admin_login.html`
- Modify: `static/admin.css`
- Modify: `admin.py` (fallback theme for Admin context)
- Test: `tests/test_admin.py`
- Test: `tests/admin.test.cjs`

**Interfaces:**
- Consume Task 1's local Bootstrap asset and Woodland tokens.
- Consume Task 2's shared Bootstrap operator navigation; preserve Admin form names, CSRF fields, revision fields, status roles, and JavaScript selectors.

- [ ] **Step 1: Add failing Admin theme, asset, and CSP assertions**

Update `test_admin_pages_use_active_dashboard_theme` and `test_admin_defaults_to_dark_theme` (rename the latter to reflect light) to check both theme attributes and the local Bootstrap stylesheet. The Admin test app omits `color_scheme`, so this also covers the Admin fallback. Assert the Admin response retains `default-src 'self'` and no stylesheet URL points off-origin. Keep explicit dark selection coverage.

- [ ] **Step 2: Run Admin tests and verify they fail**

Run: `pytest tests/test_admin.py -q`

Expected: FAIL because Admin templates do not yet load Bootstrap or set `data-bs-theme`, and the default assertion still expects dark.

- [ ] **Step 3: Migrate Admin and login presentation**

Use Bootstrap form, card, button, alert, and spacing classes while preserving existing fields, labels, validation messages, login flow, and Admin behavior. Set the Admin context fallback to light, matching the new-install default. Load Bootstrap only from `/static/vendor/bootstrap.min.css`; do not add inline styles, scripts, or remote assets. Retain compact Woodland cards and the existing top navigation.

- [ ] **Step 4: Run Admin tests and verify they pass**

Run: `pytest tests/test_admin.py -q`

Run: `node --test tests/admin.test.cjs`

Expected: PASS with existing CSP headers and Admin interactions intact.

- [ ] **Step 5: Commit Admin pages**

```bash
git add templates/admin.html templates/admin_login.html static/admin.css admin.py tests/test_admin.py tests/admin.test.cjs
git commit -m "feat: apply Woodland Bootstrap to admin pages"
```

### Task 4: Migrate the rotating TV dashboards and verify the full theme

**Files:**
- Modify: `templates/dashboard.html`
- Modify: `static/dashboard.js`
- Modify: `static/style.css`
- Test: `tests/dashboard.test.cjs`
- Test: `tests/test_app.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Consume Task 1's local Bootstrap asset, Woodland tokens, and body theme contract.
- Preserve dashboard data payloads, page builder inputs, chart variables, page rotation, scroll behavior, and DOM IDs.

- [ ] **Step 1: Add failing TV theme and class-collision tests**

Extend the dashboard Node harness so a payload changing `color_scheme` asserts matching `body.dataset.theme` and `body.dataset.bsTheme`. Add assertions that rendered summary, lap, demographics, and category pages use Bootstrap components, use `tv-toast` for notifications, and use `is-visible` for the pause state.

- [ ] **Step 2: Run dashboard tests and verify they fail**

Run: `node --test tests/dashboard.test.cjs`

Expected: FAIL because the current builders use only custom component classes and update only `data-theme`.

- [ ] **Step 3: Migrate dashboard components while retaining TV-specific CSS**

Load Bootstrap locally in `dashboard.html`. Update dashboard builders in `dashboard.js` to use Bootstrap cards, progress bars, tables, badges, lists, and utilities without changing payload semantics. Set both body theme attributes on each API update. Rename the dashboard toast class to `tv-toast` and the pause-indicator state class to `is-visible`. In `style.css`, retain the no-scroll `100vh` viewport, `vh` typography, dynamic lap columns/scaling, demographics 2-by-2 grid, fixed table widths, chart sizing, waiting screen, page dots, toast placement, and pause indicator.

- [ ] **Step 4: Run dashboard tests and verify they pass**

Run: `node --test tests/dashboard.test.cjs`

Expected: PASS for live theme changes, all page builders, and toast/pause states.

- [ ] **Step 5: Run the full automated suites**

Run: `pytest`

Run: `node --test tests/dashboard.test.cjs tests/results.test.cjs tests/race_control.test.cjs tests/admin.test.cjs`

Expected: both commands exit 0.

- [ ] **Step 6: Inspect fixture-backed pages in a browser**

Create a temporary YAML file outside the repository with `color_scheme: light` and `data_file` pointing to `tests/fixtures/race_a_finished.json`. Start the app with `python app.py --config <temp.yaml>` and a preview-only `ADMIN_PASSWORD`. Inspect all four rotating dashboard views plus Race Progress, Detailed Results, Winner Announcements, Admin, and Admin login in both light and dark modes. Check TV layouts at 1920×1080 and staff pages at desktop and phone widths; verify there is no clipping, horizontal overflow, CSP violation, or external stylesheet request. Do not modify `config.yaml` or use live credentials.

- [ ] **Step 7: Commit the TV migration**

```bash
git add templates/dashboard.html static/dashboard.js static/style.css tests/dashboard.test.cjs tests/test_app.py tests/test_theme.py
git commit -m "feat: migrate TV dashboards to Bootstrap Woodland"
```

Record venue TV readability as outstanding until the installed display is checked under the tent in actual event conditions.
