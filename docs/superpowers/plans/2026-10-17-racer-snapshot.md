# Racer Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `RaceSnapshot` (a flat `Racer` list) and route `process_race_data`, `build_finish_chart_data` and `build_demographics_data` through it with no visible change on the TV. Issue #68.

**Architecture:** New `normalizer.py` owns the only parse of the raw WebScorer payload (`normalize_webscorer`). Views in `data_processing.py` become pure projections over `snapshot["racers"]`, deriving place per view. `app.py` normalizes once per poll. Spec: `docs/superpowers/specs/2026-10-17-racer-snapshot-design.md`.

**Tech Stack:** Python, Flask, pytest. No new dependencies.

## Global Constraints

- One conventional commit per task, in order; the full suite (`python -m pytest`) is green after every task.
- Characterization (Task 1) lands with **no production code change**.
- Golden files must stay green through Tasks 3-6. The only golden diffs allowed are the ones listed under "Intentional output differences" in the spec; regenerate with `UPDATE_GOLDEN=1` and review the diff.
- Never commit real racer data: fixtures are anonymized subsets; `api_dump_*.json` stays gitignored.
- Do not touch `config.py`, `.env.example`, start scripts, or add config options (Phase 2 work).
- No provider abstraction, no frontend changes.

---

## Task 1: Golden-file characterization tests

**Files:**
- Create: `tests/test_golden.py`, `tests/fixtures/*.json`, `tests/golden/*.json`

- [ ] **Step 1:** Derive three anonymized fixtures from the real dumps (stratified subset, synthetic names/teams, no emails/lap data, places renumbered).
- [ ] **Step 2:** Write `test_golden.py`: run `poll_once` + `/api/data` per fixture/config variant, compare racer rows on the frontend contract fields.
- [ ] **Step 3:** Generate goldens with `UPDATE_GOLDEN=1` against the unchanged code; run the full suite.
- [ ] **Step 4:** Commit `test: add golden-file characterization tests for /api/data`.

## Task 2: Normalizer and schema (not wired in)

**Files:**
- Create: `normalizer.py`, `tests/test_normalizer.py`

**Interfaces:**
- Produces: `normalize_webscorer(api_response) -> RaceSnapshot`; `Racer`, `RaceSnapshot`, `GroupInfo`, `RaceMeta`, `CategoryMembership` TypedDicts; `classify_group`, `classify_time`, `parse_time_seconds`, `extract_race_start_seconds`.

- [ ] **Step 1:** Write failing tests: error response, race meta, overall racer fields, #34 fallback, statuses, elapsed/start/finish parsing, midnight rollover, unparseable time, category attachment (match, blank gender, different distance, blank bib, category-only), group list (order, gender-only skipped, dedup, empty groups).
- [ ] **Step 2:** Implement `normalizer.py` until green.
- [ ] **Step 3:** Commit `feat: add normalize_webscorer and RaceSnapshot schema`.

## Task 3: Migrate `process_race_data`

**Files:**
- Modify: `data_processing.py`, `app.py`, `tests/test_data_processing.py`
- Test: `tests/test_normalizer.py` (projection + reconciliation tests)

- [ ] **Step 1:** In `tests/test_data_processing.py` add a local adapter so `process_race_data(raw)` normalizes first. Rewrite the tests whose fixtures contradict their own times (category-place and place-sort tests) with consistent data and the `"-"` expectation.
- [ ] **Step 2:** Add projection tests that build a `RaceSnapshot` by hand: place derivation with ties, non-finishers last, `CategoryPlace`, totals, `distance_stats`, filters.
- [ ] **Step 3:** Implement place derivation and rewrite `process_race_data` over `snapshot`; emit slim rows. `_group_name` takes snapshot group keys.
- [ ] **Step 4:** Add reconciliation test: derived places equal `source_place` for every group in every fixture.
- [ ] **Step 5:** `app.py`: normalize once in `poll_once` and `main`; pass the snapshot to `process_race_data` (other builders still take raw until Tasks 4-5).
- [ ] **Step 6:** Regenerate goldens; the only diff is race B (#34) and the relay `CategoryPlace`. Commit `refactor: build process_race_data from the racer snapshot`.

## Task 4: Migrate `build_finish_chart_data`

- [ ] **Step 1:** Add tests: past-midnight finish keeps buckets in order, next-day wave start counted, unparseable time skipped.
- [ ] **Step 2:** Rewrite over `snapshot["racers"]` reading `finish_tod_seconds` and `snapshot["race"]["start_seconds"]`; adapter in tests; `app.py` passes the snapshot.
- [ ] **Step 3:** Goldens unchanged. Commit `refactor: build finish chart from the racer snapshot`.

## Task 5: Migrate `build_demographics_data`

- [ ] **Step 1:** Add tests: `Name`/`TeamName` fallback counts solo; category-only racers excluded.
- [ ] **Step 2:** Rewrite over `snapshot["racers"]`; adapter in tests; `app.py` passes the snapshot.
- [ ] **Step 3:** Race B golden demographics diff only (#34). Commit `refactor: build demographics from the racer snapshot`.

## Task 6: Remove old `Results` walking

- [ ] **Step 1:** Delete `_add_category_places`, `_result_match_key`, `_place_sort_key`, `_match_value` users and raw helpers left in `data_processing.py`; move test imports of `_classify_racer`/`_classify_group` to `normalizer`.
- [ ] **Step 2:** Assert (test) that `data_processing.py` no longer references `"Results"`.
- [ ] **Step 3:** The schema stays documented in the `normalizer.py` docstring and the spec (README is Phase 2's surface); full suite green; commit `refactor: remove raw Results walking from data_processing`.

## Verification

- `python -m pytest` green after every task.
- Local-only: run the legacy implementation (pre-refactor copy) and the new pipeline over the three full real dumps and diff the contract fields; only the intentional differences may appear.
