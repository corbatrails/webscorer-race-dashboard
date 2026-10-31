# Lap Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a timing-based Lap Overview screen to the rotating race dashboard that accounts for every racer across all distances.

**Architecture:** Extend the provider-neutral `RaceSnapshot` with distance lap counts, lap crossings, the event date, and WebScorer's UTC offset. Build a pure lap-overview projection from overall groups and racers, passing an event-local observation clock from `app.py`; add its page after Summary. Add a `show_lap_overview` option (default `false`) that the admin page edits, and render the page in the existing client-side rotation when the option is on.

**Tech Stack:** Python, Flask, pytest, vanilla JavaScript, CSS, `node --test`, local JSON/CSV fixtures via `python app.py --config <temp.yaml>`.

**Spec:** `docs/superpowers/specs/2026-10-29-lap-overview-design.md`

## Global Constraints

- The page must remain legible at the dashboard's 1080p TV target.
- One new option only: `show_lap_overview`, default `false`. Follow the project rule: `OPTIONS` in `config.py`, `config.yaml`, the README options table, and `_format_config_lines` in `app.py`; also expose it in `/api/data` and place it in `admin.py`'s field groups next to `show_demographics`.
- The server always builds the Lap Overview page when there are overall distances; `static/dashboard.js` includes it in the rotation only when `show_lap_overview` is true (the demographics pattern). It dwells for `summary_display_time`.
- DNS is a separate state and is never placed in an on-course, finished, or DNF lap count.
- `registered = DNS + Not Started + On Course + Finished + DNF + DSQ`.
- `started = On Course + Finished + DNF + DSQ`.
- Use the event-local time and offset parsed from WebScorer race metadata when available. When no event offset is available (such as CSV input), use the dashboard machine's local time; the dashboard is intended to run at the event.
- Capture observation time at the application poll boundary and pass it explicitly to the lap projection; provider normalizers remain pure and must not read the system clock.
- Live race switching (#81) must keep working: the page is built inside `poll_once`, so it inherits the `race_generation` guard and cache reset; the browser's `resetRaceState` must also drop the remembered Lap Overview page.
- For UI changes, run `python app.py --config <temp.yaml>` with a temporary YAML outside the repo that points `data_file` at local fixtures, then inspect in a browser; avoid live credentials and edits to the committed `config.yaml`.

## Review Focus

- **A malformed or missing `LapCount` or `LapTimes` record:** fall back safely without dropping the racer or failing normalization; pin with normalizer tests for absent, invalid, duplicate, and non-monotonic lap records.
- **A DNS racer carrying lap splits:** DNS remains authoritative and contributes only to DNS; pin with a projection test.
- **A DNF with no recorded crossing or with crossings on several laps:** count exactly once and display a no-crossing note or the latest valid crossing lap; pin both cases in projection tests.
- **A scheduled start near midnight or with no parseable event date/offset:** future-start classification uses the agreed event offset or machine-local fallback without false Not Started state; pin with clock-conversion tests.
- **A race with empty groups or mixed one-lap and multi-lap distances:** render all overall distances once, keep cells aligned to the event's maximum lap count, and reconcile zero/nonzero rows; pin with projection and page tests.
- **A live race switch while the Lap Overview is showing:** the previous race's counts must not render under the new race; pin with an app test for stale-generation polls and a dashboard script test for `resetRaceState`.
- **The toggle off (default):** rotation, page dots, and arrow keys match today's behavior exactly; pin with dashboard script tests.

---

## File Map

| File | Responsibility |
|---|---|
| `normalizer.py` | Provider-neutral `LapCrossing`, `GroupInfo.lap_count`, `Racer.lap_crossings`, `RaceMeta.event_date_iso`, and `RaceMeta.timezone_offset_minutes`; parse WebScorer lap, date, and offset data. |
| `providers/csv_provider.py` | Keep CSV snapshots contract-compatible with one lap, no crossings, and no known event offset. |
| `providers/base.py` | Document the additional provider-neutral snapshot requirements. |
| `data_processing.py` | Build per-distance lap state/totals and insert the `lap_overview` page in rotation order. |
| `app.py` | Capture the poll observation clock in event-local seconds, with machine-local fallback, and pass it to the lap projection; expose `show_lap_overview` in `/api/data` and `_format_config_lines`. |
| `config.py`, `config.yaml`, `README.md` | Add `show_lap_overview` (default `false`). |
| `admin.py` | Label the toggle "Show lap overview page" next to `show_demographics`. |
| `static/dashboard.js` | Include the new page type in page selection, rotation, page dots, and rendering when `show_lap_overview` is true; refresh its visible counts on poll without resetting the rotation timer; clear it in `resetRaceState`. |
| `static/style.css` | Style the grid with existing theme variables and a controlled scrolling/fit-to-screen layout. |
| `tests/test_normalizer.py` | Cover WebScorer lap and UTC-offset normalization. |
| `tests/test_provider_contract.py` | Enforce new snapshot keys for WebScorer and CSV. |
| `tests/test_lap_overview.py` | Cover state classification, per-lap counts, notes, totals, and page construction. |
| `tests/test_app.py` | Cover observation-clock conversion, lap page in cached `/api/data`, the new flag, and race-switch behavior. |
| `tests/test_config.py`, `tests/test_admin.py` | Cover the option default, parsing, YAML listing, and admin save. |
| `tests/dashboard.test.cjs` | Cover toggle filtering, rotation order, dwell time, race-switch reset, and escaping. |

## Task 1: Normalize Lap and Event-Clock Metadata

**Files:**
- Modify: `normalizer.py`
- Modify: `providers/csv_provider.py`
- Modify: `providers/base.py`
- Test: `tests/test_normalizer.py`
- Test: `tests/test_provider_contract.py`

**Interfaces:**
- Add `LapCrossing(TypedDict)` with `lap_number: int` and `elapsed_seconds: float`.
- Add `GroupInfo.lap_count: int`; use a positive value, defaulting to `1` when absent or invalid.
- Add `Racer.lap_crossings: List[LapCrossing]`; CSV racers use `[]`.
- Add `RaceMeta.event_date_iso: Optional[str]`; parse supported ISO and English month-name dates from provider metadata, otherwise use `None`.
- Add `RaceMeta.timezone_offset_minutes: Optional[int]`; parse WebScorer's `RaceInfo.StartTime` UTC offset when present, and set `None` for CSV.
- Preserve `normalize(raw) -> RaceSnapshot` as a pure function. Do not read the current time in either provider normalizer.

- [ ] **Step 1: Write failing normalizer tests** for the `LapCount` default/valid/invalid cases, cumulative `RaceTime` paired with `LapNumber`, ignoring invalid split values, parsing positive/negative/missing `GMT` offsets, and parsing supported/unsupported event dates. Assert `LapTime` is not used as a cumulative crossing.
- [ ] **Step 2: Run the targeted tests and confirm they fail** because the new fields and parsing behavior are absent.

Run: `pytest tests/test_normalizer.py -k "lap or timezone or event_date" -q`

Expected: FAIL on missing lap metadata, crossing fields, and offset parsing.

- [ ] **Step 3: Implement normalized metadata.** Parse each WebScorer `LapTimes` entry as `{lap_number, elapsed_seconds}` using integer `LapNumber` and cumulative `RaceTime`; skip invalid lap numbers, `"-"`/unparseable race times, and crossings outside `1..lap_count`. Keep entries ordered by lap number, discard duplicate lap numbers after the first valid crossing, and discard any later crossing whose cumulative time is not greater than the preceding retained crossing. Parse supported `RaceInfo.Date` values to ISO `event_date_iso`; parse `GMT±H[:MM]` from `RaceInfo.StartTime` into signed minutes; use `None` for an unparseable date or absent/malformed offset.
- [ ] **Step 4: Add CSV defaults and update provider contract expectations.** CSV `GroupInfo` entries use `lap_count=1`, racer entries use `lap_crossings=[]`, race metadata uses `timezone_offset_minutes=None`, and supported date metadata is normalized to `event_date_iso`. Update `providers/base.py` invariants and `SNAPSHOT_KEYS`/`RACE_KEYS`/`GROUP_KEYS`/`RACER_KEYS` in `tests/test_provider_contract.py`.
- [ ] **Step 5: Run normalizer and provider contract tests.**

Run: `pytest tests/test_normalizer.py tests/test_provider_contract.py -q`

Expected: PASS for both providers, including snapshot serialization and all shared invariants.

- [ ] **Step 6: Commit this logical change.**

```bash
git add normalizer.py providers/csv_provider.py providers/base.py tests/test_normalizer.py tests/test_provider_contract.py
git commit -m "feat: normalize lap timing data" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

## Task 2: Project Reconciled Lap State and Add the Page Payload

**Files:**
- Modify: `data_processing.py`
- Modify: `app.py`
- Test: `tests/test_lap_overview.py` (create)
- Test: `tests/test_data_processing.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Add `build_lap_overview_data(snapshot: RaceSnapshot, observation_seconds: float) -> Optional[dict]`; return `None` for provider errors or when there are no overall distance groups.
- `observation_seconds` is the current event-local time in seconds relative to the event date. `app.py` computes it from a timezone-aware local datetime, using `timezone_offset_minutes` when known and machine-local time otherwise. When event date is known, include whole-day offset so overnight events compare correctly; when the date is unknown, use the existing 12-hour rollover convention conservatively.
- Return `{"totals": ..., "distances": [...]}`. Each distance entry contains `name`, `lap_count`, `registered`, `dns`, `not_started`, `started`, `on_course_by_lap`, `dnf_by_lap`, `dnf_without_crossing`, `finished`, and `dsq`. Totals contain the corresponding event sums.
- Add `build_pages(dashboard_data, demographics=None, max_rows=18, lap_overview=None)`, preserving the existing positional `max_rows` argument; when `lap_overview` is present, insert `{"type": "lap_overview", "title": "Lap Overview", "data": lap_overview}` after Summary and before optional Demographics.
- `app.py` captures aware local `datetime.now()` once per successful poll. If `timezone_offset_minutes` is known, convert to that fixed offset; otherwise retain the machine-local time. Compute seconds relative to `event_date_iso`, including day offset for overnight races. If the event date is unknown, use the existing 12-hour rollover convention only when it unambiguously distinguishes same-day from next-day time.

- [ ] **Step 1: Create failing pure-projection tests** with synthetic `RaceSnapshot` fixtures for all statuses, future and missing starts, one-lap and multi-lap groups, empty overall groups, split crossings, DNS with stray crossings, and DNF with and without a valid crossing. Assert each racer belongs to exactly one status, each on-course racer belongs to one lap, DNF notes are attributed correctly, and both reconciliation equations hold.
- [ ] **Step 2: Run the new tests and confirm they fail** because the projection does not exist.

Run: `pytest tests/test_lap_overview.py -q`

Expected: FAIL with `build_lap_overview_data` unavailable.

- [ ] **Step 3: Implement `build_lap_overview_data`.** Use only `in_overall` racers and overall groups in source order. Classify DNS first; classify Not Started only when status is `IN_PROGRESS` and a known start is in the future; then classify Finished, DNF, DSQ, and remaining racers as On Course. For an active racer with a start time, count valid crossings whose elapsed time is no greater than `observation_seconds - start_seconds`; with no start time, count the valid crossings reported in the snapshot. Assign `min(crossings + 1, lap_count)`. Count DNF once and attribute it to the highest valid recorded lap at or before observation (or the highest valid lap when start time is absent); increment `dnf_without_crossing` when none exists. Assert or otherwise enforce per-distance reconciliation in tests, not by silently changing counts.
- [ ] **Step 4: Add page construction tests.** Verify page order is Summary, Lap Overview, optional Demographics, then results; no Lap Overview is emitted for provider errors or without an overall distance group; empty overall groups remain in the data with zero counts.
- [ ] **Step 5: Wire poll-time clock into `app.py`.** Add a small private helper for event-local observation seconds and test offset conversion, machine-local fallback, event-date rollover, and unknown-date fallback with an injected `datetime` so tests do not depend on wall-clock time. Call the lap projection in `poll_once` and pass its result to `build_pages`. Extend the stale-cache test to verify a failed poll preserves the last successful Lap Overview page and marks it stale. Add a race-switch test: a poll that finishes after `race_generation` changes does not store its Lap Overview page, and the cache has no pages until the new race polls.
- [ ] **Step 6: Verify cached API payload and existing backend behavior.**

Run: `pytest tests/test_lap_overview.py tests/test_data_processing.py tests/test_app.py tests/test_provider_contract.py -q`

Expected: PASS; `/api/data` JSON includes the `lap_overview` page for both providers without changing existing summary/category payloads.

- [ ] **Step 7: Commit the projection and data-flow change.**

```bash
git add data_processing.py app.py tests/test_lap_overview.py tests/test_data_processing.py tests/test_app.py
git commit -m "feat: project reconciled lap overview" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

## Task 3: Add the `show_lap_overview` Option

**Files:**
- Modify: `config.py`, `config.yaml`, `README.md`, `app.py`, `admin.py`
- Test: `tests/test_config.py`, `tests/test_app.py`, `tests/test_admin.py`

**Interfaces:**
- `Option("show_lap_overview", False, _parse_bool)` in `OPTIONS`, after `show_demographics`.
- `/api/data` includes `"show_lap_overview": cfg.get("show_lap_overview", False)`.
- `_format_config_lines` prints a `Show lap overview:` line.
- `admin.py` field group entry `("show_lap_overview", "Show lap overview page", None)` next to `show_demographics`.

- [ ] **Step 1: Write failing tests** for the default (`False`), YAML parsing (`true`/`false`, invalid values rejected like other booleans), presence in `config.yaml` with its default, the `/api/data` flag, the `_format_config_lines` line, and saving the checkbox through the admin form (mirror the existing `show_demographics` admin test).
- [ ] **Step 2: Run them and confirm they fail.**

Run: `pytest tests/test_config.py tests/test_app.py tests/test_admin.py -k "lap_overview or options or format_config" -q`

Expected: FAIL on the missing option.

- [ ] **Step 3: Implement the option** in `config.py`, `config.yaml` (with a one-line comment), the README options table, `_format_config_lines`, `/api/data`, and `admin.py`.
- [ ] **Step 4: Run the config, app, and admin tests.**

Run: `pytest tests/test_config.py tests/test_app.py tests/test_admin.py -q`

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add config.py config.yaml README.md app.py admin.py tests/test_config.py tests/test_app.py tests/test_admin.py
git commit -m "feat: add show_lap_overview option" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

## Task 4: Render Lap Overview in the TV Rotation

**Files:**
- Modify: `static/dashboard.js`
- Modify: `static/style.css`
- Test: `tests/dashboard.test.cjs`
- Validate: local dashboard in browser with fixture data

**Interfaces:**
- `dashboard.js` reads `page.data.totals` and `page.data.distances` from the `lap_overview` page, and `config.showLapOverview` from `data.show_lap_overview === true`.
- `renderLapOverview(page, data)` renders the existing event header, event totals, distance-name-only rows, lap cells, count-only DNF subnotes, and `renderProgressDots` output. No reconciliation hint or explanatory paragraph is displayed.
- Page order is supplied by the backend; the frontend must count and render `lap_overview` as one normal rotating page when the toggle is on, and skip it otherwise.

- [ ] **Step 1: Write failing dashboard script tests** in `tests/dashboard.test.cjs`: toggle off leaves the page out of the count and rotation; toggle on puts it after Summary and before Demographics/results with a `summary_display_time` dwell; a new `config_version` adds/removes it without a poll; a `race_generation` change clears it before the new race renders; distance names are escaped.

Run: `node --test tests/dashboard.test.cjs`

Expected: FAIL for the new lap overview cases; existing cases still pass.

- [ ] **Step 2: Implement page selection and rotation.** Track the Lap Overview page in `buildPageList` (only when `config.showLapOverview`), include it in `getTotalPages`, render it in `renderCurrentPage` at the backend-provided position with a `summaryDisplayTime` dwell, and clear it in `resetRaceState`. Keep the existing arrow-key behavior and page indicators working.
- [ ] **Step 3: Implement `renderLapOverview`.** Display all distances; show cells through the event-wide maximum lap count plus Finished; mark non-applicable lap cells; keep DNS and Not Started outside lap counts; render DNF notes inside the appropriate cell without changing its on-course number. Escape provider-sourced labels with `escapeHtml`.
- [ ] **Step 4: Add theme-aware layout styles.** Use existing CSS variables for background, text, border, and state accents. Make all rows visible at the 1080p target when practical; otherwise use a controlled, contained vertical scroll without omitting a distance. Distinguish active lap, finished, and DNF subnote states in both themes.
- [ ] **Step 5: Refresh an active Lap Overview on successful polling without resetting its page index or rotation timer.** Leave current refresh behavior for Summary, Demographics, and category pages unchanged.
- [ ] **Step 6: Run all tests and inspect the real UI with fixture data.**

Run: `pytest -q` and `node --test tests/dashboard.test.cjs`

Expected: PASS with no regressions in provider, projection, config, admin, app, or dashboard script behavior.

Validation: Write a temporary YAML outside the repo with `show_lap_overview: true` and `data_file` pointing at a local anonymized/synthetic fixture containing one-lap and multi-lap distances, DNS with a stray split, future starts, finishes, and DNFs on different recorded laps. Run `python app.py --config <temp.yaml>` and inspect the rotating page in a browser at 1920x1080 in dark and light themes; verify every distance appears, cell and event totals reconcile to the fixture, the page appears before the first finisher, and the active page refreshes without restarting its dwell timer. With `ADMIN_PASSWORD` set, turn the toggle off and on from `/admin` and confirm the rotation updates; switch `data_file` to a second fixture and confirm the first race's lap counts never appear.

- [ ] **Step 7: Commit the UI change.**

```bash
git add static/dashboard.js static/style.css tests/dashboard.test.cjs
git commit -m "feat: render rotating lap overview" -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```
