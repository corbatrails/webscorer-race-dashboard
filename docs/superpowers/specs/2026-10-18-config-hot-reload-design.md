# Live Config Hot-Reload

Roadmap: Phase 4 of `docs/ROADMAP.md` (issue #71, part of epic #67). Depends on Phase 2 (`config.yaml`, the `OPTIONS` registry).

## Problem

Changing any setting means editing `config.yaml` and restarting the process, which blanks the TV during a race. Phase 2 tagged every option `live` or `restart` in `OPTIONS` but nothing acts on the tag. `refresh_interval` is also restart-only today because the poll thread captures it once.

## Solution

A small watcher thread polls `config.yaml` for changes, re-resolves the options with the same precedence as startup, validates the result, and atomically swaps the active config. Options tagged `live` take effect without a restart. Options tagged `restart` keep their running value; the app logs that a restart is needed and lists them in `/api/data`. A bad edit (invalid YAML, bad value) is rejected whole and the last good config keeps running. `/api/data` carries a `config_version` so the frontend can tell when settings changed.

## Design Decisions

These were resolved without a reviewer, choosing the simplest option consistent with the issue. Each is listed so a reviewer can overrule it.

| Question | Decision | Rationale |
|---|---|---|
| How is a change detected? | **Poll `os.stat` on `config.yaml`** every 1 second; the signature is `(st_mtime_ns, st_size)`. | Cross-platform, no new dependency (a `watchdog` dependency is not worth it on a Pi), and a stat is cheap. Size is included because some filesystems have coarse mtime granularity. |
| Who runs the watcher? | **A dedicated daemon thread**, separate from the poll thread. | The poll thread blocks on network calls and sleeps for `refresh_interval`; reusing it would delay a reload by up to a full cycle or a slow API call. A separate thread keeps reload latency at about 2 seconds regardless of the API. |
| Partial writes mid-edit | **Debounce:** a new signature is only loaded once it is seen unchanged on two consecutive ticks. | Editors that write in chunks can leave a truncated but valid YAML file, which would silently reset missing keys to defaults. Waiting for the file to settle avoids that at the cost of one extra second. |
| Invalid YAML or invalid value | **All-or-nothing.** Any parse or validation error rejects the whole file; the last good config stays active. A warning is logged **once per distinct error message**. | Matches the issue's mitigation. Applying the valid subset of a broken file would make behavior depend on which line the operator got wrong. Once-per-message logging stops a broken file from spamming the console, while a changed error message is still reported. |
| File missing or unreadable at a tick | **Treated as no change.** The last good config stays active. | Editors that save by delete-and-rename leave the file absent for a moment. A removed file is not a request to reset to defaults. |
| Env overrides and secrets on reload | **The environment layer is not re-read.** `.env` is not reloaded; process env vars and `.env` values loaded at startup keep winning over `config.yaml`. `api_id` / `api_token` are copied from the running config, never re-read. | Env overrides are the documented way to pin a value on race day, so they must keep winning. Re-reading `.env` mid-run adds a second watched file and a secrets-handling path for no stated need. Editing `config.yaml` for an env-overridden key is a documented no-op. |
| Atomic swap | **Replace `app.config["dashboard"]` with a new dict under `_cache_lock`; never mutate it in place.** Readers take one reference snapshot (`cfg = app.config["dashboard"]`) and read from that. | A reference swap is atomic, and a snapshot gives each request or poll a self-consistent config even if a swap lands mid-request. Reuses the existing `_cache_lock` pattern as the issue asks. |
| Where does version and restart info live? | **A separate `app.config["dashboard_state"]` dict** (`config_version`, `restart_required`), swapped in the same locked block as the config. | Keeps the loaded config dict identical in shape to Phase 2 (tests compare config dicts), and `/api/data`, which already holds the lock, sees the config and its version together. |
| Is `refresh_interval` live? | **Yes.** Retag it `live` in `OPTIONS`. The poll loop reads it each cycle and is woken early when it changes. | The roadmap lists this as a known follow-up. Without the early wake, lowering 600 to 10 would take up to 10 minutes to apply. |
| Guard against a bad interval | **`refresh_interval` must be at least 1.** Values below 1 are a validation error (startup and reload). | Live editing makes `0` or a negative typo a real way to hammer the WebScorer API in a tight loop. This also tightens startup validation, where `0` was accepted before. |
| Restart-only key changes in the file | **Keep the running value.** Log once that the key `requires restart`, and expose the pending key names (no values) as `config_restart_required` in `/api/data`. The comparison is against the value `config.yaml` resolved to at startup, not the running value. | The running `race_id` can differ from the file when it was chosen interactively at startup, so comparing against the running value would report a false pending change forever. |
| Does `config_version` bump on a restart-only change? | **No.** It bumps only when at least one live option value changed. | The version describes the config the app is actually running. |
| Options baked into cached pages (`show_overall_results`, `show_category_results`, `chart_bucket_minutes`) | **Apply on the next poll.** Reload does not trigger an extra API fetch. | These shape the data built by `poll_once`. Forcing a fetch would risk the rate limit the app already guards against and would touch the fetch path owned by Phase 3. They still apply within one refresh cycle, as the exit criteria require. |
| Frontend reaction | **No full page reload.** The frontend (1) applies `color_scheme` from `/api/data` to `<body data-theme>`, (2) re-renders the current page when `config_version` changes, and (3) schedules its next fetch from the server's `refresh_interval` instead of a fixed 60 seconds. | Everything else the frontend uses is already rebuilt from `/api/data` on each fetch. A reload would blank the TV and reset the rotation. Step 3 is needed for a live `refresh_interval` to matter on screen; with the default of 60 the cadence is unchanged. |
| Log content | **Key names only** (for example `Config reloaded: scroll_speed, color_scheme`). | No secret can reach the log, and the `data_file` path or other values are not echoed. |
| Where does the code live? | Detection, reload, and validation in `config.py` (`ConfigWatcher`); thread, swap, and wake in `app.py`. | Keeps config logic testable without Flask and keeps the `app.py` footprint small. |

## Hot vs restart keys

Defined by the `reload` column of `OPTIONS` in `config.py`:

| Reload | Keys |
|---|---|
| `restart` | `race_id`, `data_file` |
| `live` | `refresh_interval`, `summary_display_time`, `scroll_speed`, `scroll_pause_time`, `pinned_leaders`, `show_summary`, `show_overall_results`, `show_category_results`, `show_demographics`, `pinned_leaders_on_overall_results`, `overall_results_layout`, `display_unfinished_in_category`, `display_unfinished_in_overall`, `chart_bucket_minutes`, `color_scheme`, `show_toasts` |

Of the live keys, `show_overall_results`, `show_category_results`, and `chart_bucket_minutes` apply at the next poll; the rest apply on the next frontend fetch. Phase 3's `source` option will be `restart`.

## Design

### `config.py`

- `ConfigError`: raised by the internal loaders instead of exiting. `load_config` catches it and calls `_fail`, so startup behavior and messages are unchanged.
- `ConfigWatcher(config_path=None)`:
  - Remembers the last applied signature and the `config.yaml` restart-key values resolved at startup.
  - `check(running)` is one tick. It stats the file, applies the debounce, and on a settled new signature re-reads the YAML and resolves every option (env still wins). On success it returns a `Reload(config, changed, restart_required)` when a live option changed or the pending-restart list changed, else `None`. On `ConfigError` it logs once per distinct message and returns `None`.
  - The new config is `{**running, **live_values}`: restart keys and secrets come from `running`.
- The signature is recorded as seen even when the load fails, so a broken file is retried only after it changes again.

### `app.py`

- `_watch_config(app, watcher)`: loop that sleeps one tick, calls `watcher.check(app.config["dashboard"])`, and on a result swaps config and state under `_cache_lock`. If `refresh_interval` changed it sets a module-level `_config_changed` event.
- `_poll_loop` reads `refresh_interval` from the current config each cycle and waits on `_config_changed` with the remaining time, recomputing when woken.
- `api_data` and `index` read one config snapshot. `/api/data` gains `config_version`, `config_restart_required`, `color_scheme`, and `refresh_interval`.
- `main()` starts the watcher thread after the poll thread and prints one line saying live options reload automatically.

### Thread safety summary

- Writers: only the watcher thread, under `_cache_lock`, replacing two references.
- Readers: `api_data` (already holding the lock), `index`, and `poll_once` (each take a single reference; never mutate it).
- The poll thread's wait reads the current config reference without the lock; a stale or new reference are both valid values.

## `/api/data` additions

| Field | Meaning |
|---|---|
| `config_version` | Integer, starts at 1, increments on each applied live change |
| `config_restart_required` | Sorted list of restart-only keys whose `config.yaml` value changed since startup |
| `color_scheme` | Active scheme, so the frontend can switch theme without a reload |
| `refresh_interval` | Active poll interval in seconds, so the frontend can match its fetch cadence |

No secret and no value of a restart-only option is exposed.

## Testing

- `config.py` (pytest, temp files, no threads): `check` returns `None` when the file is unchanged; applies a live change after the file settles; ignores a changed file that has not settled; keeps the old config on malformed YAML and on an invalid value; logs a failure once per distinct message; recovers when the file is fixed; leaves restart keys and secrets untouched and reports pending restart keys against the startup baseline; env overrides still win; unknown keys warn; `refresh_interval < 1` is rejected at startup and on reload; a missing file is ignored.
- `app.py`: swap replaces config and bumps the version under the lock; `/api/data` returns the new fields and reflects a swap on the next request; restart-only change exposes `config_restart_required` without changing the running value; the poll loop uses the current interval and wakes early when it changes; the watcher loop applies a result and survives an unexpected exception.
- Existing tests stay green. The golden files compare the whole `/api/data` payload, so they are regenerated once (`UPDATE_GOLDEN=1`) for the four new fields, and the diff is only those fields. The `refresh_interval` reload tag test and the poll-loop and `main` thread tests are updated for the new behavior.
- End-to-end: run the app against `tests/fixtures` via `data_file` with a temp `config.yaml`, edit the file, and confirm `/api/data` changes within a few seconds.
- The frontend has no JS test harness; it is checked manually in the end-to-end run.

## Non-Goals

Admin UI and writing `config.yaml` (Phase 5), watching or reloading `.env` or secrets, `watchdog`/inotify, an immediate extra API fetch on config change, per-key change notifications to the frontend beyond the version, applying a `source` change (Phase 3 key, restart-only), and reloading the browser page.
