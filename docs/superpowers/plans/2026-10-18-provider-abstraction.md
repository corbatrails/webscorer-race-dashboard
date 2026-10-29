# Provider Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ingestion pluggable behind a small `Provider` contract selected by a `source` option, with WebScorer as the reference provider (no behavior change) and a CSV provider as the second, validating the contract.

**Architecture:** A `providers/` package holds the contract, a static registry, `webscorer` (wrapping the existing client and `normalize_webscorer`) and `csv_provider`. `poll_once` and `main` ask the selected provider to fetch and normalize; `config.py` validates `source` and the selected provider's credentials. Everything after `normalize` is untouched.

**Tech Stack:** Python, Flask, PyYAML, pytest (stdlib `csv` for the CSV provider; no new dependencies)

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-18-provider-abstraction-design.md` (decisions D1-D15).
- Zero behavior change for WebScorer: `tests/test_golden.py` and `tests/golden/` must not change; `normalizer.py` and `webscorer_client.py` are not modified (except the `normalizer.py` docstring pointer in Task 8).
- Existing tests may change only as listed in D14 (patch retargeting, `select_race` signature, reload-mode set).
- Adding `source` means updating `OPTIONS` in `config.py`, `config.yaml`, the README options table and `_format_config_lines` in `app.py`. `.env.example`, `start.sh`, `start.ps1` stay unchanged.
- Do not touch the poll-loop interval handling, config reload logic or the `/api/data` config fields (Phase 4 is changing them in parallel).
- Run `python -m pytest -q` (baseline 192 passing) before every commit. One logical change per commit, conventional commit subjects.
- Code comments: one short line, only where the code cannot show the intent.

---

### Task 1: Provider contract and registry

**Files:**
- Create: `providers/__init__.py`, `providers/base.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Produces: `Provider` (frozen dataclass: `name`, `required_secrets`, `requires_data_file`, `fetch`, `normalize`, `list_races=None`), `RaceChoice` (`TypedDict`), `get_provider(name)`, `provider_names()`, module-level `_REGISTRY` dict.

- [ ] **Step 1: Write failing tests** for: `Provider` is frozen and `list_races` defaults to `None`; `get_provider` returns the registered instance (registry patched with `monkeypatch.setitem`); `get_provider("nope")` raises `ValueError` listing the valid names; `provider_names()` is sorted.
- [ ] **Step 2: Run** `python -m pytest tests/test_providers.py -q`; confirm the failures are import errors / missing attributes.
- [ ] **Step 3: Implement** `providers/base.py` (contract, with the contract rules from the spec as a short module docstring) and `providers/__init__.py` (empty `_REGISTRY`, `get_provider`, `provider_names`).
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: add provider contract and registry`.

### Task 2: WebScorer provider

**Files:**
- Create: `providers/webscorer.py`
- Modify: `providers/__init__.py` (register `webscorer`)
- Test: `tests/test_providers.py`

**Interfaces:**
- Consumes: `webscorer_client.fetch_race_results` / `fetch_race_list`, `normalizer.normalize_webscorer`.
- Produces: `providers.webscorer.PROVIDER` with `name="webscorer"`, `required_secrets={"api_id": "WEBSCORER_API_ID", "api_token": "WEBSCORER_API_TOKEN"}`, `requires_data_file=False`.

- [ ] **Step 1: Write failing tests**: `fetch` with `config["data_file"]` returns the parsed JSON of that file and does not call `fetch_race_results` (patched at `providers.webscorer.fetch_race_results`); `fetch` without `data_file` calls `fetch_race_results(race_id, api_id, api_token)` with config/secrets values and returns its result; `normalize(raw)` equals `normalize_webscorer(raw)` for `tests/fixtures/race_a_finished.json`; `list_races` maps `fetch_race_list` output to `{"id": str(RaceId), "name", "date", "sport"}`; `get_provider("webscorer")` returns it.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** the module. `fetch` keeps the existing `print("Loading data from local file: ...")` line.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: add WebScorer provider`.

### Task 3: Route the poll loop and race selection through the provider

**Files:**
- Modify: `app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `get_provider`, `Provider` from Task 1/2.
- Produces: `poll_once` using `provider.fetch` / `provider.normalize`; `select_race(provider, config)`; `_secrets_for(provider, config)` helper.

- [ ] **Step 1: Retarget existing tests** (mechanical, D14): `@patch("app.fetch_race_results")` becomes `@patch("providers.webscorer.fetch_race_results")`; `@patch("app.fetch_race_list")` becomes `@patch("providers.webscorer.fetch_race_list")`; `test_select_race_interactive` calls `select_race(get_provider("webscorer"), {"api_id": "12345", "api_token": "abc123de"})`. Run: they fail (app still imports the client directly).
- [ ] **Step 2: Add failing tests**: `poll_once` uses the provider named by `config["source"]` (a stub provider registered via `monkeypatch.setitem`) and defaults to `webscorer` when `source` is absent; `main` does not call `select_race` when the provider has no `list_races`; `main` still prompts for a WebScorer run with no `race_id` and no `data_file`.
- [ ] **Step 3: Implement**: `poll_once` resolves the provider from `cfg.get("source", "webscorer")`, builds `secrets`, calls `fetch` then `normalize`; drop the direct `webscorer_client` / `normalize_webscorer` imports and the inline `data_file` read; make `select_race` iterate `provider.list_races(...)`; in `main`, prompt only when `provider.list_races` is set and neither `data_file` nor `race_id` is. Leave the `except` block, `_poll_loop`, `_start_polling`, `/api/data` and `_cache` alone.
- [ ] **Step 4: Run** the full suite; golden tests green with no golden file changes.
- [ ] **Step 5: Commit** `refactor: route ingestion through the provider contract`.

### Task 4: `source` option and per-provider credential checks

**Files:**
- Modify: `config.py`, `config.yaml`, `README.md` (options table row, `data_file` description), `app.py` (`_format_config_lines`)
- Test: `tests/test_config.py`, `tests/test_app.py`

**Interfaces:**
- Produces: `Option("source", "RACE_SOURCE", "webscorer", _parse_source, "restart")` first in `OPTIONS`; `load_config` checks `requires_data_file` and `required_secrets` of the selected provider; the returned dict still has `api_id` / `api_token`.

- [ ] **Step 1: Write failing tests**: default `source` is `webscorer`; yaml sets it; `RACE_SOURCE` env overrides yaml; value is case-insensitive; an unknown value exits with `ERROR:` naming `source` and the valid names; with a stub provider that has `requires_data_file=True`, a missing `data_file` exits with a `requires data_file` message and no credentials are required; with `required_secrets={}` no credentials are needed; WebScorer missing `WEBSCORER_API_ID` / `WEBSCORER_API_TOKEN` messages are unchanged; `test_every_option_declares_reload_mode` expects `source` in the restart set; `_format_config_lines` output has a `Source:` line (existing registry test covers the rest); committed `config.yaml` lists `source`.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** the option, parser (validates against `provider_names()`), provider-driven validation (secrets only when no `data_file`), `config.yaml` entry with comment, README row, and the printout line.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: add source option to select the ingestion provider`.

### Task 5: CSV provider, rows to racers

**Files:**
- Create: `providers/csv_provider.py`
- Test: `tests/test_csv_provider.py`

**Interfaces:**
- Produces: `CsvFormatError(ValueError)`; `_parse_rows(text) -> (meta, racers)` internal helper: header handling, per-row field parsing and validation, error collection (cap 10).

- [ ] **Step 1: Write failing tests** (one behavior each): minimal sheet (`bib,name,time`) yields racers; header matching (case, spaces, `start_time`), BOM, quoted commas, blank rows skipped; extra columns ignored; each time format and `elapsed_seconds`; DNS/DNF/DSQ any case; blank and `-` mean `IN_PROGRESS` with `time_display == "-"`; age parsing and rejection; start time parsing; `finish_tod_seconds`; blank name rejected; duplicate bib within a distance rejected; missing required column and duplicate header rejected; no racer rows rejected; several errors reported together as `row N, column 'x': ...`, capped at 10 with `and K more`.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** the parsing and validation. Reuse nothing lenient from `normalizer.py`; time parsing here is strict.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: parse CSV race results into racers`.

### Task 6: CSV provider, metadata, groups and snapshot

**Files:**
- Modify: `providers/csv_provider.py`
- Test: `tests/test_csv_provider.py`

**Interfaces:**
- Produces: `normalize(raw)` where `raw = {"name": <file stem>, "text": <file text>}`; `fetch(config, secrets)` reading `config["data_file"]` (UTF-8, BOM tolerated); `PROVIDER` with `name="csv"`, `required_secrets={}`, `requires_data_file=True`, `list_races=None`.

- [ ] **Step 1: Write failing tests**: `# name/date/sport/start` metadata; defaults (name from file stem, `start` from earliest racer start, else `0`); unknown metadata key and malformed comment line are errors; next-day rollover for starts more than 12 hours before the race start; Overall groups per distinct distance in first-appearance order (blank distance is one group); category groups per `(distance, category)` with blank gender; each racer's `category_groups` membership; `in_overall` is true and `source_place` is `""`; snapshot `error` is `None`; `fetch` reads the file named by `data_file` and returns the raw dict; a missing file raises `FileNotFoundError`.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** metadata parsing, group derivation, `normalize`, `fetch`, and `PROVIDER`.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: add CSV provider`.

### Task 7: Register CSV, sample file and pipeline tests

**Files:**
- Create: `docs/sample-results.csv`
- Modify: `providers/__init__.py` (register `csv`)
- Test: `tests/test_csv_provider.py`, `tests/test_app.py`, `tests/test_config.py`

- [ ] **Step 1: Write failing tests**: `get_provider("csv")` works and `provider_names()` is `["csv", "webscorer"]`; `load_config` with `source: csv` and a `data_file` needs no credentials, and without `data_file` exits naming `data_file`; `poll_once` with `source: csv` on `docs/sample-results.csv` fills the cache (summary, Overall and category pages, finish chart, demographics when enabled, race name from the metadata); a malformed CSV sets `is_stale` and an `error` containing `row` and the column name while keeping previous pages; `main` against the sample (patched `Flask.run` and `threading.Thread`, as the existing `main` test does) populates the cache and never prompts or calls the network.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Create** `docs/sample-results.csv` (about 20 racers, two distances, several categories, finishers with ties, DNF/DNS/DSQ and in-progress rows, start times, metadata lines) and register the provider.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `feat: register CSV provider with a sample results file`.

### Task 8: Contract tests across providers

**Files:**
- Create: `tests/test_provider_contract.py`
- Modify: `normalizer.py` (docstring pointer only)

- [ ] **Step 1: Write the tests**, parametrized over `[webscorer (fixture race_a_finished.json via data_file), csv (docs/sample-results.csv via data_file)]`: provider fields are well-typed and `name` matches its registry key; `fetch` with `data_file` returns a payload and makes no network call (patch `requests.get` to fail); `normalize` returns a snapshot with the Phase 1 keys; invariants hold (`FINISHED` iff `elapsed_seconds` set, finish time only when both parts are known, every `in_overall` racer's distance has an Overall group, every membership matches a category group, group tiers are valid); the snapshot flows through `process_race_data`, `build_demographics_data`, `build_finish_chart_data` and `build_pages` and produces a summary page with at least one Overall category; `poll_once` run for each source yields `is_stale is False`.
- [ ] **Step 2: Run** them. They should pass against the existing implementation; if any fail, fix the provider (not the test) and note it.
- [ ] **Step 3: Add** the docstring pointer in `normalizer.py` naming `providers/base.py` as the contract that produces snapshots.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** `test: add provider contract tests for webscorer and csv`.

### Task 9: Docs and roadmap

**Files:**
- Modify: `README.md`, `docs/ROADMAP.md`

- [ ] **Step 1:** README: add a Sources section (what `source` does, restart-only, the table from the spec for `data_file` behavior, credentials per source), the CSV format (metadata, columns, `time` values, groups, errors) and a link to `docs/sample-results.csv`; adjust the Features line that says the dashboard only polls WebScorer.
- [ ] **Step 2:** ROADMAP: set the Phase 3 status line to Shipped (link the spec), update the header status to Phases 1-3.
- [ ] **Step 3: Run** the full suite.
- [ ] **Step 4: Commit** `docs: document sources and the CSV format`.

### Task 10: Verification

- [ ] Run `python -m pytest -q` (all green, golden files unchanged: `git diff --stat origin/main -- tests/golden` is empty).
- [ ] Start the app with `RACE_SOURCE=csv DATA_FILE=docs/sample-results.csv` (empty `.env`), fetch `/api/data` and confirm pages, finish chart and race name.
- [ ] Break the sample copy (bad time, missing column) and confirm `is_stale` plus a row/column error; fix it and confirm recovery on the next poll.
- [ ] Run with `source: webscorer` and `DATA_FILE=tests/fixtures/race_a_finished.json` and confirm the same pages as before.
- [ ] Push, mark the PR ready (`gh pr ready`).
