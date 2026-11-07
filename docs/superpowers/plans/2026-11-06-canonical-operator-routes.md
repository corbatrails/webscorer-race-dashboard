# Canonical Operator Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give staff pages canonical flat URLs and same-tab navigation without silently losing Admin edits.

**Architecture:** Keep Progress and detailed results in the shared Race control template, served by separate Flask endpoints. Redirect legacy URLs, synchronize in-page view changes with canonical paths, and add an independent Admin unsaved-settings guard.

**Tech Stack:** Flask, Jinja, vanilla JavaScript, pytest, Node.js `node:test`.

**Spec:** `docs/superpowers/specs/2026-11-06-canonical-operator-routes-design.md`

## Global Constraints

- Canonical paths are `/progress`, `/race-results`, `/announcements`, and `/admin`.
- Preserve existing Admin authentication/CSRF and the public TV/API behavior.
- Add no dependencies or configuration options; do not modify the user's `config.yaml`.
- Use the current isolated worktree and Native execution unless the user changes that choice.

## Review Focus

- Missing or unknown legacy views redirect to Progress; test in Task 1.
- Canonical paths ignore obsolete `view` queries; in-page switches preserve unrelated queries/fragments; test in Task 1.
- Explicit Ctrl-click keeps browser behavior while normal top-link clicks stay in-tab; test in Task 1.
- Programmatic race-picker changes count as unsaved settings; test in Task 2.
- Restored values, Save, and Discard avoid spurious leave-page warnings; test in Task 2.

---

### Task 1: Canonical Routes and Navigation

**Files:**
- Modify: `app.py`, `templates/operator_nav.html`, `static/race_control.js`
- Modify: `README.md`
- Test: `tests/test_app.py`, `tests/test_admin.py`, `tests/test_race_control.py`, `tests/race_control.test.cjs`

**Interfaces:**
- Produce Flask endpoints `race_progress()` for `/progress`, `race_results()` for
  `/race-results`, and existing `results()` for `/announcements`.
- Share rendering through `_render_race_control(initial_view)` inside `create_app`.
  Its view is `progress` or `results`, and it passes the existing template context.
- Keep `race_control()` as the legacy redirect endpoint; use permanent HTTP 301
  redirects for old GET URLs, including `/results`.
- Keep existing navigation IDs and `setView(view)` API. `syncViewLocation()`
  uses the selected link's canonical href to set the pathname and removes `view`,
  preserving unrelated query parameters and the fragment.
- Ordinary shared Race control link clicks call `setView`; modified clicks retain
  browser defaults. No top link includes `target="_blank"`.

- [ ] **Step 1: Write route/navigation regressions**

Add `test_canonical_operator_routes` and `test_legacy_operator_redirects` covering
200 responses, correct initial views, exact active links, and 301 locations:
`/race-control`, `?view=progress`, and `?view=unknown` -> `/progress`;
`?view=results` -> `/race-results`; `/results` -> `/announcements`.
Assert canonical paths determine the view even with contradictory `view` queries.
Update staff-page tests to request canonical pages and assert all four hrefs and
no new-tab target on any top link, including Admin.

Update the Node view-navigation test to expect `/race-results` and `/progress`.
Add cases preserving `?filter=finished#table` while removing `view`, retaining
selection/filter state, and not preventing a Ctrl-click.

- [ ] **Step 2: Verify RED**

Run `pytest tests/test_app.py tests/test_admin.py tests/test_race_control.py -q`
and `node --test tests/race_control.test.cjs`; confirm the new route and path
assertions fail because canonical behavior is missing.

- [ ] **Step 3: Implement routes and link behavior**

Wire the endpoints and redirects above; update `url_for` calls, path synchronization,
and normal-click interception. Remove conditional new-tab attributes.
Update README URLs and describe legacy redirects and same-tab navigation.

- [ ] **Step 4: Verify GREEN and commit**

Run the same targeted commands and `git diff --check`.
Commit only this logical change as `refactor: standardize operator page routes`,
with the required Copilot co-author trailer.

### Task 2: Protect Unsaved Admin Settings

**Files:**
- Modify: `static/admin.js`, `templates/admin.html`, `README.md`
- Create: `tests/admin.test.cjs`

**Interfaces:**
- Add private `initUnsavedChanges()` to `static/admin.js`, independent of race-picker
  initialization and its early returns. Use `.settings-form` and its named controls.
- Capture initial form values and compare live values on `beforeunload`; request
  the standard browser warning only for changed settings.
- Settings submission bypasses the guard. Mark the explicit Discard link with
  `data-discard-changes` and bypass for an ordinary activation of that link.
- Read live values so race-picker assignments to `race_id.value` count without
  requiring a synthetic input event.

- [ ] **Step 1: Write unsaved-settings tests**

Execute the real `admin.js` in a Node VM with a minimal DOM/window harness.
Cover clean forms; text, checkbox, and select changes; restoring original values;
programmatic race-ID changes; normal Save and Discard; and initialization when
race-picker controls are absent. Assert `beforeunload` prevention/return value
rather than internal flags.

- [ ] **Step 2: Verify RED**

Run `node --test tests/admin.test.cjs`; confirm changed-settings cases fail
because the guard is missing.

- [ ] **Step 3: Implement the guard and documentation**

Wire `initUnsavedChanges()`, the Discard marker, and README warning guidance.
Retain existing race-picker behavior and server validation.

- [ ] **Step 4: Verify and inspect the fixture-backed app**

Run `pytest -q`, `node --test`, and `git diff --check`.
Start the dashboard with temporary YAML outside the repo and local CSV fixtures.
Inspect all four destinations, redirects, active links, in-page view retention,
and Admin's dirty/clean navigation behavior. Stop the helper and remove its
temporary files afterward.

- [ ] **Step 5: Commit and review**

Commit as `fix: warn before leaving unsaved admin settings`, with the required
Copilot co-author trailer. Review the completed change against the approved
spec, preserve the worktree, and do not push, open a PR, or merge without a request.
