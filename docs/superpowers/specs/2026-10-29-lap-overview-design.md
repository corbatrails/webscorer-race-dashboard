# Lap Overview Dashboard Design

**Status:** Approved; revised after merging the admin UI (#81)  
**Related concept:** Lap bucket grid, concept 1 v2 (all distances, per-lap DNF notes, DNS separated)

## Intent

Give race spectators and organizers a quick, readable view of where the field is across every distance. The Lap Overview is a new screen in the existing rotating TV dashboard. It shows one row per overall distance and one cell per lap, with the current on-course count in each cell. It also shows Finished, DNS, Not Started, DNF, and DSQ counts so the roster is accounted for without treating non-starters or finishers as currently on course.

The inspiration is concept 1 v2, generated from the CORBA Fall Back Blast 2025 result dump. The lap grid is a timing-data view, not a GPS or exact physical-position display.

## Goals

- Add a dedicated Lap Overview screen to the existing page rotation without replacing or crowding the Summary screen.
- Show every overall distance, including one-lap events and distances with no current racers.
- Show each distance's lap count and a current on-course count in each applicable lap cell.
- Show a concise DNF count in the lap cell corresponding to the racer's last recorded crossing; include no-crossing DNFs in the Lap 1 note.
- Count DNS separately and exclude DNS racers from all lap and finish counts, even if stray lap-time data is present.
- Distinguish registered racers who have not yet started from those already on course.
- Reconcile status totals per distance and for the event.
- Preserve the provider-neutral snapshot boundary and avoid exposing raw timing-provider payloads to the browser.
- Update the display with each successful poll, using the existing stale-data behavior after a failed poll.
- Let the operator turn the page on or off with a new `show_lap_overview` option (default `false`), editable in `config.yaml` and on the admin page like the other `show_*` page toggles.
- Work with live race switching from the admin page: a race change must never show the previous race's lap counts.

## Non-goals

- GPS tracking, live location estimates, or claims about a racer's physical position on a lap.
- Per-racer search or a detailed racer table on this page.
- Changes to finish-chart, results-page ranking, demographics, or current page rotation timing.
- Configuration beyond the single `show_lap_overview` toggle (for example a separate dwell time or per-distance filtering).
- New admin page controls beyond the standard toggle field.
- Inferring a DNF's exact drop-out time or the lap on which the racer physically stopped when the source does not report it.

## Anti-goals

- Do not count DNS, DNF, DSQ, or finished racers as currently on course.
- Do not let a racer's missing or malformed lap splits make the race poll fail or silently remove that racer from registration totals.
- Do not display DNF placement as an exact DNF lap when the source only establishes the last completed crossing.
- Do not render a separate row for gender or category groupings; each distance appears once.

## Current Architecture and Constraints

- `app.py::poll_once` fetches and normalizes provider data, builds summary data and pages, then caches them for `/api/data`.
- `normalizer.py` is the canonical boundary for converting a provider payload into the provider-neutral `RaceSnapshot`. It currently preserves status, start time, elapsed time, and distance group descriptors, but not lap count or lap splits.
- `providers/base.py` requires every provider to return the same snapshot shape. Both WebScorer and CSV providers have contract tests. WebScorer supplies `Grouping.LapCount` and `LapTimes`; CSV currently has no lap-split input and must remain valid.
- `data_processing.py::build_pages` creates the summary, optional demographics, and results pages. `static/dashboard.js` rotates among those page types and renders them into the TV view. `/api/data` exposes cached pages.
- Overall groups preserve event distance order and include distances with no racers. The Lap Overview must use those groups, not category rows, to avoid duplicate distances.
- Non-secret options live only in `config.yaml` (environment variables never override them). Adding one means updating `OPTIONS` in `config.py`, `config.yaml`, the README options table, and `_format_config_lines` in `app.py`; tests enforce the first, second, and last. The admin page (`admin.py`) lists every `OPTIONS` key; options missing from its field-group table land in an "Other" group, so the new toggle belongs next to the other page toggles.
- Page toggles follow the demographics pattern: the server always builds the page, `/api/data` exposes the `show_*` flag, and `static/dashboard.js` decides whether the page is in the rotation. Toggling therefore takes effect through the existing `config_version` refresh without waiting for a new poll. Summary and Demographics both dwell for `summary_display_time`.
- Since #81, `source`, `race_id`, and `data_file` change at runtime. `_apply_config` clears the race cache and increments `race_generation`; `poll_once` drops results whose generation is out of date; the browser's `resetRaceState` resets the page index, finisher tracking, and charts. With no race selected, the poller does not fetch and `/api/data` returns a waiting state with no pages.
- `tests/dashboard.test.cjs` runs `static/dashboard.js` in a stub DOM with `node --test`, and CI runs it on Linux and Windows alongside `pytest`.
- UI checks run `python app.py --config <temp.yaml>`, where a temporary YAML outside the repository sets `data_file` to local fixture data. Do not overwrite `config.yaml` or use live credentials when fixtures suffice.

## Approaches Considered

### A. Dedicated Lap Overview page in the existing rotation — selected

Add a new `lap_overview` page type to the page payload and render it as its own screen. This keeps the current Summary layout intact, supports the requested multi-row grid, and uses the existing rotation and page indicators. It requires a new projection, a small extension to normalized lap data, and a frontend renderer.

### B. Put the lap grid on the Summary page

This would keep the information constantly visible, but competes with the current summary statistics, distance progress bars, and finish chart for the same 1080p screen area. It is less suitable for the six-distance, four-lap example and risks making the Summary difficult to read.

### C. Add a separate lap-only route or display mode

This gives the grid a dedicated full-screen view but introduces another URL or operating mode, alongside the existing page rotation. It is unnecessary for the requested TV use and would require operators to choose or switch displays.

**Decision:** The user selected approach A. The grid belongs on a new rotating page; it should not replace or be embedded in the current Summary.

## Data and State Semantics

### Lap metadata

- Each overall distance has a lap count. WebScorer's `Grouping.LapCount` is parsed as a positive integer when supplied; absent lap count means one lap.
- Each racer retains normalized, cumulative elapsed-time lap crossings derived from valid `LapTimes` entries: WebScorer provides `LapNumber` and cumulative race elapsed `RaceTime` for each crossing. Use `RaceTime` as the crossing time; do not sum `LapTime`, which is the duration of a single lap. The raw `LapTimes` objects are not passed through to the frontend.
- The CSV provider remains supported. CSV rows have a one-lap distance by default and no lap splits unless a future CSV format explicitly adds them. Existing one-lap status counts still work.
- Invalid or missing lap data is treated as unavailable, not as a failed race snapshot. Such a racer remains in the appropriate registration/status totals; when an in-progress racer has no valid crossings, they appear on Lap 1 with no crossing yet.

### Mutually exclusive racer states

Each overall racer contributes to exactly one state for a distance:

1. **DNS:** provider status is `DNS`. This takes precedence over any lap splits.
2. **Not Started:** status is in progress and a known scheduled start is later than the snapshot's observation time.
3. **Finished:** provider status is `FINISHED`.
4. **DNF:** provider status is `DNF`.
5. **DSQ:** provider status is `DSQ`.
6. **On Course:** otherwise in progress and not known to be waiting for a future start.

If start time is absent, do not infer Not Started; retain the provider's in-progress state and place the racer on Lap 1 or the lap after their valid recorded crossings. The implementation must compare the scheduled start and observation time on a consistent event-local time basis; it must not use the browser's arbitrary local clock. Use the event-local time and offset parsed from WebScorer race metadata when available. When no event offset is available (such as CSV input), use the dashboard machine's local time; the dashboard is intended to run at the event. Capture observation time at the application poll boundary and pass it explicitly to the lap projection; provider normalizers remain pure and must not read the system clock.

Per-distance invariant:

```text
registered = DNS + Not Started + On Course + Finished + DNF + DSQ
started    = On Course + Finished + DNF + DSQ
```

Event totals are the sums of the corresponding per-distance values. One-lap distances are included in these equations and rendered like every other distance.

### Lap bucket assignment and DNF notes

- For an on-course racer, `completed_crossings` is the count of valid cumulative lap crossings at or before the snapshot observation time. Their active lap is `min(completed_crossings + 1, lap_count)`.
- A racer who completes all laps is counted only in Finished, never in an on-course lap cell.
- DNF racers are excluded from on-course and finish counts. Their DNF note is placed in the cell for their last valid recorded crossing. That note is additive: the large cell count continues to mean racers currently on course.
- When a DNF has no valid crossing, include it in the Lap 1 DNF note, not as a claim that the racer reached Lap 1.
- Label every subnote with only the count and **“DNF”** (for example **“2 DNF”**). Combine no-crossing and Lap 1-attributed DNFs into one Lap 1 note. Do not label it “DNF on lap N.”
- If the source status is DNF but its last crossing is not available in the snapshot, count it in the DNF total and use the no-crossing note.

The dashboard cannot determine when a racer actually stopped unless the timing source reports that time. A DNF count appears after the provider reports DNF; in a replay, the state is reconstructed from each racer's status and recorded splits at the selected observation time.

### DNS accounting

- DNS is a separate state and is never placed in an on-course, finished, or DNF lap count.
- A DNS status remains authoritative even if a stray lap time is present (the sample event includes this case).
- Each distance row shows `registered`, `DNS`, and `started`; the event header shows the corresponding global totals.
- The UI displays the count reconciliation so the meaning of totals is clear:
  `registered = DNS + Not Started + On Course + Finished + DNF + DSQ`.

## User Interface

- When `show_lap_overview` is true, add a Lap Overview page after Summary and before optional Demographics/results pages. Keep the existing Summary screen and its current content unchanged. It dwells for `summary_display_time`, like Summary and Demographics.
- When `show_lap_overview` is false (the default), the rotation, page indicators, and arrow-key navigation are exactly as before.
- Show event name, date, and last successful refresh using the existing event header pattern.
- Show event-level totals for Registered, DNS, Not Started, On Course, Finished, DNF, and DSQ.
- Render one row per overall distance in the same order as the rest of the dashboard (Webscorer's API order), including empty and one-lap distances. The row label shows only the distance name.
- Render one column per lap up to the maximum lap count in the event, plus Finished. Cells for laps a distance does not have are subdued and marked “no lap N.”
- Each applicable lap cell shows the number currently on course on that lap. A thin indicator may show that count as a share of the distance's starters; label or style it so it cannot be mistaken for an individual racer's progress.
- DNF subnotes appear within their attributed lap cell, visually distinct from the on-course count. A lap can have both active racers and DNF notes.
- Finished has a distinct color and count. DNS and Not Started appear in event totals, not added to a lap cell. Distance blocks show only the distance name, with no metadata.
- Use the existing dark/light theme variables, typography scale, layout conventions, and progress indicators. The page must remain legible at the dashboard's 1080p TV target. If the event has more distance rows than fit vertically, use the existing page's controlled scrolling behavior or another consistent fit-to-screen treatment without omitting any distance.
- Do not show a reconciliation equation, legend, or explanatory paragraph on the page; timing attribution is documented here instead.
- The server builds the page whenever the snapshot has at least one overall distance group; the browser shows it only when `show_lap_overview` is true.
- When no race is selected or the new race's first poll hasn't completed, there is no Lap Overview page; the existing waiting screen applies.

## Data Flow and Implementation Boundaries

1. Extend the normalized snapshot with provider-neutral lap count and valid cumulative lap crossing data. At the application poll boundary, capture an observation timestamp and pass it explicitly to the lap projection, converted to event-local time when an event offset is available and otherwise using the machine's local clock.
2. Keep provider-specific parsing in the provider normalizer. WebScorer maps `LapCount` and valid `LapTimes`; CSV supplies one lap and an empty crossing list.
3. Add a pure projection in `data_processing.py` that builds the `lap_overview` page data from overall groups and racers. The projection owns state partitioning, reconciliation, and lap attribution.
4. Add the page to `build_pages` in the selected order. No separate Flask route or endpoint is needed; it travels through cached `pages` and `/api/data`. Because the page is built inside `poll_once`, the existing `race_generation` guard and cache reset cover it: results for a superseded race are discarded and a race switch empties the cached pages.
5. Add `show_lap_overview` to `OPTIONS`, `config.yaml`, the README options table, `_format_config_lines`, the `/api/data` payload, and the admin field groups next to `show_demographics`.
6. Add frontend handling for the new page type in `static/dashboard.js`, plus styles in `static/style.css`. Clear the remembered Lap Overview page in `resetRaceState` along with the other race-specific state.
7. Do not include raw API rows or unneeded racer fields in the projected page data.

## Testing and Validation

### Data/projection tests

- All provider snapshots preserve the documented shape and remain JSON serializable.
- Lap count defaults to one; valid positive counts and `LapNumber`/cumulative `RaceTime` values normalize correctly without summing per-lap `LapTime`.
- Invalid/missing split entries do not fail normalization and do not remove racers from counts.
- WebScorer and CSV provider contract tests include the new fields; CSV remains a valid one-lap provider.
- DNS overrides stray splits and is counted once in DNS, never in a lap or other terminal state.
- Future scheduled starts are Not Started; missing start times do not cause false Not Started classification.
- On-course assignment uses completed crossings plus one and never exceeds the distance lap count.
- Finished racers appear only in Finished.
- DNF with zero, one, or multiple valid crossings is counted exactly once and gets the appropriate lap note; DNF does not inflate on-course counts.
- DSQ is a separate terminal state.
- Per-distance and event reconciliation invariants hold for mixed status fixtures, empty distance groups, and one-lap events.
- `lap_overview` page ordering and inclusion are correct; all overall distances occur once, including empty groups.
- Existing page payloads and dashboard behavior remain unchanged apart from the new page.
- `show_lap_overview` defaults to `false`, parses like the other booleans, appears in `config.yaml`, `_format_config_lines`, and `/api/data`, and is saved through the admin form.
- After a race switch, cached pages are empty until the new race polls, and a poll result from the previous race generation never stores a Lap Overview page.

### Dashboard script tests (`tests/dashboard.test.cjs`)

- With `show_lap_overview` false, the Lap Overview page is not counted or rendered, and existing rotation tests pass unchanged.
- With it true, the page sits after Summary and before Demographics/results, dwells for `summary_display_time`, and arrow-key navigation reaches it.
- Changing the toggle via a new `config_version` adds or removes the page without a new poll.
- A `race_generation` change clears the previous race's Lap Overview before the new race's data renders.
- Provider-sourced distance names are escaped.

### UI validation

- Run `python app.py --config <temp.yaml>` with a temporary YAML outside the repository that sets `show_lap_overview: true` and points `data_file` at local anonymized or synthetic fixtures, including a one-lap distance, multi-lap distances, DNS with a stray split, future starts, and DNFs at different crossing counts.
- Run the dashboard with a temporary configuration, inspect the Lap Overview in a browser at the 1080p target, and check dark and light themes.
- Verify the counts shown in the browser against the fixture and the per-distance reconciliation formula.
- With `ADMIN_PASSWORD` set, toggle Show lap overview on the admin page and confirm the TV rotation updates. Switch `data_file` to a second fixture and confirm the first race's lap counts never appear on the new race.
- Do not use live credentials or overwrite the committed `config.yaml`.

## Acceptance Criteria

- With `show_lap_overview: true`, a new Lap Overview screen appears in the page rotation after Summary and leaves Summary unchanged. With the default `false`, the rotation is unchanged.
- The toggle is editable on the admin page and applies to the running TV without a restart.
- After a live race switch, the TV never shows the previous race's lap counts.
- The screen has one row for every overall distance, including one-lap and empty distances, with cells for applicable laps and a Finished cell.
- On-course counts show each active racer in exactly one lap cell, determined by valid completed crossings.
- DNF subnotes show only the count and “DNF” on the last recorded crossing's lap without being included in the on-course number; no-crossing DNFs are included in the Lap 1 note.
- DNS racers are counted separately and excluded from every lap and finish cell, even when split data is present.
- Future scheduled starters appear in Not Started rather than on Lap 1.
- Registered, DNS, Not Started, On Course, Finished, DNF, and DSQ totals reconcile for every distance and event.
- The page updates from each successful poll and continues to show cached stale data under existing failure behavior.
- Existing CSV, WebScorer, summary, demographics, chart, results-page, admin, config, and dashboard-script tests continue to pass.

## Decisions and Builder Calls

### Decisions from the user

- Use the bucket-grid concept.
- Include all distances, even when a distance has only one lap.
- Add DNF as a subnote in the lap cell where the racer was last recorded; do not imply an exact DNF lap.
- Count DNS racers separately and make all counts reconcile.
- Put the grid on a dedicated page in the existing rotation, not on Summary or a separate route.
- Show racers with known future scheduled starts in a distinct Not Started count.
- Show the Lap Overview from the start of the race, even before the first finisher.
- WebScorer `LapTimes` uses `LapNumber` plus cumulative `RaceTime`; `LapTime` is an individual lap duration and is not cumulative.
- For future-start classification, use WebScorer's event-local offset when available and the dashboard machine's local clock when it is not; capture the time at the poll boundary, not in provider normalization or browser code.
- After the admin UI merge: add a `show_lap_overview` toggle, default off, editable from the admin page like the other page toggles.

### Left to the builder

- Exact normalized field names and types, provided they remain provider-neutral and preserve the snapshot contract.
- Safely parse malformed, duplicate, or non-monotonic lap splits; keep the racer in totals and make conservative state assignments.
- The precise encoding of provider-neutral lap counts/crossings and event-local observation time, consistent with the existing start-time and midnight handling.
- Exact grid breakpoints, typography, compacting, and controlled-scroll details needed to keep every distance visible and readable at 1080p.
- Whether a distance with no racers still shows an explicit zero state or a concise empty label; it must remain visible and reconcile to zero.
- Any code-level mechanism for stale pages, provided it follows existing cache and error behavior.

## Files Likely to Change

| File | Expected change |
|---|---|
| `normalizer.py` | Add provider-neutral lap metadata and normalized crossing times. |
| `providers/csv_provider.py` | Supply default one-lap metadata and no crossings. |
| `providers/base.py` | Document any snapshot invariant changes. |
| `data_processing.py` | Add the lap overview projection and page. |
| `app.py` | Capture/pass observation time; expose `show_lap_overview` in `/api/data` and `_format_config_lines`. |
| `config.py`, `config.yaml`, `README.md` | Add the `show_lap_overview` option, default `false`. |
| `admin.py` | Place the toggle in the page-visibility field group. |
| `static/dashboard.js` | Include, filter, render, and reset the new rotating page type. |
| `static/style.css` | Style the responsive lap grid and DNF notes. |
| `tests/test_normalizer.py`, `tests/test_provider_contract.py`, `tests/test_data_processing.py`, `tests/test_app.py` | Add unit, provider-contract, page-flow, race-switch, and reconciliation coverage. |
| `tests/test_config.py`, `tests/test_admin.py` | Cover the new option's default, parsing, and admin save. |
| `tests/dashboard.test.cjs` | Cover toggle filtering, rotation order, and race-switch reset. |
