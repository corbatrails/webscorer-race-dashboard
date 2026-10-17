# Racer Snapshot: Normalize to a Single Filterable Racer List

Phase 1 of the platform roadmap (`docs/ROADMAP.md`), issue #68, part of epic #67.

## Problem

Every view reaches into the raw WebScorer payload and re-derives what it needs:

- `process_race_data` walks `Results`, classifies each racer from the `Time` string, and stitches category places onto overall rows with `_add_category_places`.
- `build_finish_chart_data` re-parses `StartTime` and `Time` and re-adds them to get a finish time of day.
- `build_demographics_data` re-walks the Overall groupings and re-classifies age, gender and team.

The same facts (status, elapsed time, place, name) are computed three different ways, so a fix in one place does not reach the others. #34 (empty `Name`, name stored in `TeamName`) and every follow-on feature (#40 category details on overall pages, #14 lap races, filtering, search) would have to be patched into each walker.

## Solution

Add a normalizer, `normalize_webscorer(api_response) -> RaceSnapshot`, in a new `normalizer.py`. It is the only code that reads the raw payload. It produces one flat `racers` list in which every racer is parsed once. Views become pure projections over `snapshot["racers"]`:

```
raw API response --normalize_webscorer--> RaceSnapshot --process_race_data / build_finish_chart_data / build_demographics_data--> view dicts --build_pages--> pages
```

No visible behavior change on the TV. No provider abstraction (that is Phase 3); `normalize_webscorer` is simply the first adapter.

## Schema

`normalizer.py` defines these as `TypedDict`s and is the canonical documentation; this section mirrors it.

### `RaceSnapshot`

| Field | Type | Meaning |
|-------|------|---------|
| `error` | `str \| None` | The API `Error` message, otherwise `None`. When set, `racers` and `groups` are empty. |
| `race` | `RaceMeta` | Race-level facts (below). |
| `groups` | `list[GroupInfo]` | The API's overall and category groupings, in API order, de-duplicated. Carries page order and empty groups (a distance with no racers still gets a page and a progress bar). Gender-only groupings are not listed (neither tier). |
| `racers` | `list[Racer]` | Flat racer list. |

`RaceMeta`: `name`, `date`, `sport` (strings, `""` if missing) and `start_seconds` (float, seconds since midnight of the race start parsed from `RaceInfo.StartTime`; `0` if absent, as the finish chart already does).

`GroupInfo`: `tier` (`"overall"` or `"category"`), `distance` (`""` if the grouping has none), `category` and `gender` (`""` if none, and always `""` for the overall tier).

### `Racer`

| Field | Type | Meaning |
|-------|------|---------|
| `bib` | `str` | Stripped; `""` if missing. |
| `name` | `str` | Display name. `Name`, or `TeamName` when `Name` is empty (#34). |
| `team` | `str` | `TeamName`, or `""` when `TeamName` was used as the name. |
| `distance` | `str` | Distance of the grouping the racer was listed under. |
| `category` | `str` | The racer's own `Category`. |
| `gender` | `str` | The racer's own `Gender`, `""` if missing. |
| `age` | `int \| None` | Parsed with the existing lenient rules (int, float, digit string). |
| `status` | `str` | `FINISHED`, `IN_PROGRESS`, `DNS`, `DNF` or `DSQ`, classified from `Time` exactly as `_classify_racer` does today. |
| `time_display` | `str` | The API `Time` string as reported, stripped (what the TV prints). |
| `elapsed_seconds` | `float \| None` | Parsed `Time`; only set for `FINISHED` racers with a parseable time. |
| `start_seconds` | `float \| None` | Parsed racer `StartTime` as seconds of the race-start day (see Midnight). |
| `finish_tod_seconds` | `float \| None` | `start_seconds + elapsed_seconds` for finishers, else `None`. |
| `source_place` | `str` | The overall `Place` string exactly as the API sent it. Only for reconciliation. |
| `in_overall` | `bool` | Listed in an Overall grouping. Only these racers feed totals, the chart and demographics. |
| `category_groups` | `list[CategoryMembership]` | One entry per Category grouping the racer was listed in. |

`CategoryMembership`: `distance`, `category`, `gender` (the grouping's values) and `source_place` (the place the API gave inside that grouping; reconciliation only).

## Decisions

### One racer per overall listing, category listings attach to it

Overall groupings are the registration roster: each racer listed in an Overall grouping becomes one `Racer` (`in_overall=True`). Each racer listed in a Category grouping is attached to that racer as a `CategoryMembership`. This is why the old rule "count only Overall groups" survives without double counting.

Matching rule (dedup): a category listing attaches to the first overall `Racer` with the same `(distance, bib)`; when the bib is blank it falls back to `(distance, name)`. `distance` for the category listing is the grouping's `Distance`, else the racer's own `Distance`, else `""`. If nothing matches, the listing becomes a category-only `Racer` (`in_overall=False`, `source_place=""`) so category pages that exist without an Overall grouping keep working (an existing test relies on this).

Overall racers are never de-duplicated against each other: every overall listing counts, as today. If the API ever listed the same bib twice in one Overall grouping, both would count and the second would receive no category attachment.

This intentionally drops the old `(distance, category, gender, bib)` key. In dump 412060 the two relay racers have an empty `Gender` in the overall list but `Male` in the relay category grouping, so the old key never matched and their overall rows got no `CategoryPlace`. They now get one. See "Intentional output differences".

Limitation: one Overall grouping per distance is assumed (true for every WebScorer dump seen). Duplicate group descriptors are collapsed into one page, and Overall descriptors carry only a `distance` (`category` and `gender` are `""`).

**The overall listing is the source of truth for a racer.** A racer has one name, time and status in the snapshot; category listings only add membership and a place. In the real dumps the two agree, with one exception: every category listing in `api_dump_443486_finished.json` (402 of 402) carries a `Time` unrelated to the same racer's overall `Time` (for example 4:03:11 overall and 4:22:38 in the category), so its category pages ranked different times than its overall page. That file is not a result set WebScorer itself would produce, so the old behavior is not preserved: category pages now rank and show the overall time. The committed fixture for that dump copies the overall time into each category listing before places are renumbered, and the local comparison against the legacy code does the same.

### Place is derived per view

`source_place` is not displayed. Each view derives place from `status` and `elapsed_seconds` over exactly the racers it shows:

- Finishers (status `FINISHED`, elapsed known) are ordered by elapsed time; ties keep the order of `snapshot["racers"]`.
- Competition ranking: `place = 1 + count of racers in scope with a strictly smaller elapsed`, so tied racers share a place and the next place is skipped (`1, 2, 2, 4`).
- Everyone else (`IN_PROGRESS`, `DNS`, `DNF`, `DSQ`, finisher without a parseable time) has no place, is shown as `"-"`, and sorts after finishers in snapshot order. The API sends `"-"` for all of them in every dump, so the TV is unchanged. Old unit tests that fed `""` for non-placed racers now see `"-"`.
- Overall scope = overall racers of that distance. Category scope = racers holding a `CategoryMembership` for that `(distance, category, gender)`. `CategoryPlace` on an overall row = rank inside the membership that matches the racer's own category and gender, else the first membership.
- Places are emitted as strings (the API sends strings).

This is what makes filtering cheap later (rank any subset), at the cost of trusting that the platform orders by elapsed time. Reconciliation: tests assert derived place equals `source_place` / `CategoryMembership.source_place` for every group in every fixture, and the real dumps were checked the same way during development (0 mismatches across 1,794 placed rows in all three dumps; ties in the live dump share places the same way). A future race with a different `ResultsOrder` (laps, points, #14) needs a ranking strategy then; the reconciliation test is the tripwire.

### Finish past midnight

`finish_tod_seconds` is **not wrapped**: it is seconds since midnight of the race-start day and may exceed 86400. Reasons: the chart's bucket math is `(finish - floor_hour) // bucket`, which only works on a monotonic timeline; the existing code already adds raw seconds. Two details:

1. A racer `StartTime` is a time of day with no date. If it is more than 12 hours earlier than the race start time of day (a wave starting at `00:05` in a race that began at `23:50`), it belongs to the next day and 86400 is added at normalization. Before this, such racers silently fell outside every bucket and vanished from the chart.
2. Chart x-axis labels use `hour % 24`, so a bucket 25 hours after midnight reads `1:15`, not `25:15`.

Both only affect races that cross midnight, which none of the dumps do.

### Missing or unparseable times

Normalization never raises on a bad time string. A `FINISHED` racer whose `Time` cannot be parsed gets `elapsed_seconds=None` and is skipped by the chart and by place derivation (old behavior: the whole poll cycle failed with a `ValueError` and the TV went stale). A racer with no `StartTime` is skipped by the chart, as before.

### Empty `Name` with `TeamName` (#34)

When `Name` is blank and `TeamName` is not, `name = TeamName` and `team = ""`. Consequences, all intended by #34: names land in the Name column, the Team column is blank for them, and demographics counts them as solo instead of as one-person teams. This changes dump 412060's output and nothing else. (`SHOW_TEAM_COLUMN` from the same issue is separate config work, not part of this phase.)

### View racer rows

Views no longer hand the raw API dict to the frontend. Each row is a dict with only the fields `static/dashboard.js` reads: `Place`, `Bib`, `Name`, `Time`, `TeamName`, `Category`, `Gender`, plus `CategoryPlace` on overall rows that have one. Keys keep their API names so the frontend does not change. Side effect: `Email`, `LapTimes`, `ChipId` and the rest stop being served from `/api/data` (the 412060 dump carries racer emails).

### Where things live

- `normalizer.py`: schema, `normalize_webscorer`, `classify_group`, time parsing, race start parsing.
- `data_processing.py`: `process_race_data`, `build_finish_chart_data`, `build_demographics_data`, `build_pages`. They take a `RaceSnapshot`, not the raw payload. `build_pages` is unchanged.
- `app.py`: `poll_once` and `main` call `normalize_webscorer(raw)` once and pass the snapshot to all three builders.

## Testing

Characterization first, then equivalence:

1. `tests/test_golden.py` runs `poll_once` then `/api/data` over three anonymized fixtures in `tests/fixtures/` (race A finished, race A live with in-progress racers and a tie, race B with names in `TeamName` and a relay) under several config variants, and compares against `tests/golden/`. Written and committed with no production change. Racer rows are compared on the frontend contract fields so the golden files survive the row slimming above.
2. `tests/test_normalizer.py`: unit tests for every `Racer` field, #34, status, elapsed, midnight rollover, matching and dedup, category-only racers, error response, and the place reconciliation against the fixtures.
3. Existing `test_data_processing.py` tests keep their assertions. They call the views through a tiny local adapter that normalizes first. Tests whose fixtures contradicted their own times (a "place 44" racer faster than "place 2") are rewritten with consistent data, and `_group_name` tests use the snapshot group keys. Each is called out in the plan.
4. Projection tests that build `RaceSnapshot` dicts by hand, proving views read only the snapshot.

Fixtures are derived from the real dumps by keeping a small stratified subset (top finishers, every non-finish status, ties, every category), replacing names, team names, emails and chip ids with synthetic values, dropping lap data and organizer metadata, and renumbering places to stay consistent with the reduced field. Real dumps stay gitignored.

## Intentional output differences

| Difference | Why |
|------------|-----|
| Race B (412060): `Name` filled from `TeamName`, `TeamName` blank; demographics `solo_count`/`top_teams` change accordingly | #34, in scope for this phase. |
| Relay racers (412060) gain `CategoryPlace` on the overall page | Old key required equal gender between two sources that disagree; new match is by `(distance, bib)`. |
| Category pages for a dump whose category times contradict its overall times (only `api_dump_443486_finished.json`) | The overall listing is the source of truth, see above. |
| Rows contain only frontend fields | Stops leaking emails/lap data to the browser; frontend untouched. |
| Non-placed racers always show `Place` `"-"` | The API already sends `"-"`; only synthetic `""` inputs differ. |
| Races crossing midnight bucket correctly and label hours mod 24 | Previously dropped or labelled `24:xx`. |
| Unparseable times no longer abort the poll cycle | Previously `ValueError` made the data stale. |

Everything else (counts, page order and titles, leaders, progress-bar stats, chart labels and counts, demographics buckets) must match the golden files.

## Out of scope

Provider abstraction (Phase 3), config changes (Phase 2), frontend changes, filtering/search UI, lap-race ranking (#14).

## Files Changed

| File | Change |
|------|--------|
| `normalizer.py` | New: schema and `normalize_webscorer` |
| `data_processing.py` | Views rewritten as projections; `_add_category_places` and raw `Results` walking removed |
| `app.py` | Normalize once in `poll_once` and `main` |
| `tests/test_golden.py`, `tests/fixtures/`, `tests/golden/` | New characterization tests |
| `tests/test_normalizer.py` | New normalizer and projection tests |
| `tests/test_data_processing.py` | Adapter, rewritten contradictory fixtures |
| `docs/superpowers/specs/`, `docs/superpowers/plans/` | This spec and its plan |
