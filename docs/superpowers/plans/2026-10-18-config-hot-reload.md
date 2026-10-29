# Config Hot-Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editing `config.yaml` while the app runs updates live options within one refresh cycle, keeps the last good config on a bad edit, and tells the frontend when settings changed.

**Architecture:** `config.py` gains `ConfigWatcher` (stat-based change detection with debounce, re-resolution of options, validation, restart-key tracking). `app.py` runs the watcher in a daemon thread and swaps `app.config["dashboard"]` plus a small state dict under `_cache_lock`. The poll loop reads `refresh_interval` each cycle. `/api/data` gains `config_version`, `config_restart_required`, `color_scheme`, `refresh_interval`. The frontend applies the theme, re-renders on a version change, and follows the server's refresh interval.

**Tech Stack:** Python, Flask, PyYAML, pytest, vanilla JS

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-18-config-hot-reload-design.md`
- Do not touch fetch/normalize code paths or create a `providers/` package (Phase 3 is in flight in another worktree).
- Loaded config dict keys and types do not change; `load_config()` behavior and messages do not change.
- No secrets in logs or `/api/data`; log key names only.
- Full suite green before every commit: `python -m pytest -q` from the worktree (baseline: 192 passing).
- One logical change per commit, conventional commit subjects.
- Code comments: one short line, only where the code cannot show intent.

---

### Task 1: Loaders raise `ConfigError` instead of exiting

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `ConfigError`; `_read_yaml` and `_resolve_option` raise it; `load_config` converts it to `_fail` (same output and exit code).

- [ ] **Step 1: Write failing tests** that `config._read_yaml` raises `ConfigError` on malformed and non-mapping YAML, and `config._resolve_option` raises it on an invalid value; existing exit-path tests stay as the regression guard.
- [ ] **Step 2: Run** `python -m pytest tests/test_config.py -q`; confirm the new tests fail.
- [ ] **Step 3: Implement** `class ConfigError(Exception)`, replace `_fail(...)` calls inside `_read_yaml` and `_resolve_option` with `raise ConfigError(...)`, and in `load_config` catch `ConfigError` and call `_fail(str(e))`.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`refactor: raise ConfigError from config loaders`).

### Task 2: Reject `refresh_interval` below 1

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**: `refresh_interval: 0` and `-5` in `config.yaml` exit with a message naming `refresh_interval`; `1` is accepted.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** `_parse_refresh_interval` (reuses `_parse_int`, raises `ValueError("expected a whole number of at least 1")`) and use it for the `refresh_interval` option.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: reject refresh_interval below 1`).

### Task 3: `ConfigWatcher` detection, debounce, live reload

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `ConfigWatcher(config_path=None)`, `check(running) -> Reload | None`, `Reload(config, changed, restart_required)`; `restart_required` is an empty list until Task 4.

- [ ] **Step 1: Write failing tests** using a temp `config.yaml` and a `clean_env`-style fixture: unchanged file returns `None`; a changed file returns `None` on the first tick (not settled) and a `Reload` on the second; `changed` lists the changed live keys and `config` has the new values with secrets and untouched keys carried from `running`; a second identical tick returns `None`; env overrides still win and an edit to an env-overridden key produces no change; a file removed mid-run returns `None`; unknown keys warn.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** the signature `(st_mtime_ns, st_size)` via `os.stat`, the two-tick debounce, re-resolution through `_read_yaml`/`_resolve_option` (no credential checks, no `.env` reload), and the `Reload` result.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: add ConfigWatcher to detect and re-read config.yaml`).

### Task 4: Keep last good config on bad edits

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**: malformed YAML, a non-mapping file, and an invalid value each return `None` and leave the running config usable; the warning goes to stderr once per distinct message (a second tick with the same file does not repeat it, a different error does); fixing the file afterwards returns a `Reload`; a failed file is not retried until its signature changes.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** catching `ConfigError` in `check`, recording the signature as applied, and tracking the last error message for once-per-message logging via `_warn`.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: keep last good config on invalid edits`).

### Task 5: Track restart-only keys

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**: changing `data_file`/`race_id` in the file leaves the running values unchanged, returns a `Reload` whose `restart_required` is the sorted key names, and logs `requires restart` once; reverting the file to its startup value clears the list; a running `race_id` that differs from the file (chosen interactively) is not reported while the file is unchanged; a restart-only change alone leaves `changed` empty.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** a startup baseline of the file-resolved restart-key values in `ConfigWatcher.__init__` (quiet read; falls back to the running values if the file cannot be read), the pending comparison in `check`, and the once-per-change warning.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: report restart-only config changes without applying them`).

### Task 6: Atomic config swap and `/api/data` fields

**Files:**
- Modify: `app.py`, `tests/golden/*.json` (regenerated)
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `app.config["dashboard_state"]` (`config_version`, `restart_required`), `apply_config_reload(app, reload)`; `/api/data` fields `config_version`, `config_restart_required`, `color_scheme`, `refresh_interval`.

- [ ] **Step 1: Write failing tests**: `/api/data` returns `config_version` 1, an empty `config_restart_required`, `color_scheme` (default `dark`), and `refresh_interval`; after `apply_config_reload` with changed live keys, the next `/api/data` shows the new values and `config_version` 2; a reload with no live change leaves the version and updates `config_restart_required`; `index` reflects a changed `color_scheme`; the old config dict object is not mutated.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** `dashboard_state` in `create_app`, take one `cfg` snapshot in `index` and `api_data`, add the four fields, and `apply_config_reload` that swaps config and state under `_cache_lock` and sets the module-level `_config_changed` event when `refresh_interval` changed (the poll loop consumes it in Task 8). Add a test that the event is set only when `refresh_interval` changes.
- [ ] **Step 4: Regenerate** goldens with `UPDATE_GOLDEN=1 python -m pytest tests/test_golden.py -q`; review that the diff only adds the four fields.
- [ ] **Step 5: Run** the full suite; all green.
- [ ] **Step 6: Commit** (`feat: swap config atomically and expose config_version in /api/data`).

### Task 7: Watcher thread in `main()`

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing tests**: `_watch_config_once(app, watcher)` applies a `Reload` and returns; an unexpected exception from `check` is printed and does not propagate; `main()` starts two daemon threads (poll and watcher) and prints the live-reload line.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** `_watch_config_once`, `_watch_config` (loop with a 1 second sleep), `_start_config_watcher(app)`, call it from `main()` after `_start_polling`, and print `Config: live options reload from config.yaml; changes to race_id/data_file need a restart.`. Update the existing `main` test's thread-start assertion from once to twice.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: run config watcher thread alongside the poll loop`).

### Task 8: Live `refresh_interval`

**Files:**
- Modify: `app.py`, `config.py`
- Test: `tests/test_app.py`, `tests/test_config.py`

- [ ] **Step 1: Write failing tests**: `_wait_for_next_poll` returns after the current interval and returns early when `_config_changed` is set and the new interval has elapsed; `_poll_loop` calls it before the first poll when `sleep_first` is true and after every poll; `refresh_interval` is tagged `live` (update the reload-tag test to expect only `race_id` and `data_file` as `restart`).
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** `_wait_for_next_poll(app, since)`, simplify `_poll_loop` to `(app, sleep_first=False)`, update `_start_polling`, retag `refresh_interval` to `live` in `OPTIONS`, and update the existing poll-loop test for the new signature.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat: make refresh_interval live`).

### Task 9: Frontend reacts to config changes

**Files:**
- Modify: `static/dashboard.js`

- [ ] **Step 1: Implement** applying `data.color_scheme` to `document.body.dataset.theme`; tracking `config_version` and calling `renderCurrentPage()` when it changes after the first fetch; making `fetchData` return its promise and replacing the fixed 60 second `setInterval` with a `setTimeout` chain that waits `data.refresh_interval` seconds (default 60).
- [ ] **Step 2: Verify manually** in the end-to-end run (Task 12): theme flips without reload, a layout change re-renders, cadence follows `refresh_interval`.
- [ ] **Step 3: Run** the full suite; all green.
- [ ] **Step 4: Commit** (`feat: apply live config changes in the dashboard frontend`).

### Task 10: Docs for operators

**Files:**
- Modify: `README.md`, `config.yaml`

- [ ] **Step 1:** README: add a Reload column (`live`/`restart`) to the options table, retag `refresh_interval`, and add a "Changing settings while running" section covering what is watched, the roughly 2 second latency, apply-at-next-poll keys, that env overrides keep winning and `.env`/secrets are not reloaded, invalid edits keep the last good config (check the console), restart-only keys, and the `config_version` / `config_restart_required` fields.
- [ ] **Step 2:** `config.yaml`: header comment noting live reload and the two restart-only keys, and a one-line `restart required` note on `race_id` and `data_file`. Values unchanged (the defaults test still passes).
- [ ] **Step 3: Run** the full suite; all green.
- [ ] **Step 4: Commit** (`docs: document live config reload`).

### Task 11: Roadmap status

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1:** Mark Phase 4 shipped with a link to the spec, update the header status line and date, and strike the `refresh_interval` follow-up.
- [ ] **Step 2: Commit** (`docs: mark roadmap phase 4 shipped`).

### Task 12: End-to-end verification

- [ ] Run the full suite.
- [ ] Start the app on a spare port with a temp `config.yaml` and `data_file` pointing at `tests/fixtures/race_a_finished.json` (script wires `create_app`, the poll thread, and the watcher the same way `main()` does).
- [ ] Edit the temp file and confirm via `/api/data` within a few seconds: a live key changes and `config_version` increments; invalid YAML keeps the old values and logs one warning; fixing it recovers; a `data_file` change appears in `config_restart_required` while the running value is unchanged; lowering `refresh_interval` shortens the poll cycle.
- [ ] Open the page in a browser, flip `color_scheme` and `overall_results_layout`, and confirm the page updates without a reload.
- [ ] Fix anything found as its own commit; push; `gh pr ready`.
