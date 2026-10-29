# Provider Abstraction: Pluggable Ingestion

Roadmap: Phase 3 of `docs/ROADMAP.md` (issue #70, part of epic #67). Builds on Phase 1 (`RaceSnapshot`, `normalizer.py`) and Phase 2 (`config.yaml`, the `OPTIONS` registry).

## Problem

Phase 1 made everything downstream of `normalize_webscorer` provider-neutral, but the ingestion half is still hard-wired to WebScorer:

- `app.py` imports `fetch_race_results` / `fetch_race_list` and `normalize_webscorer` directly. `poll_once` is: read `data_file` JSON or call the WebScorer API, then normalize.
- `select_race` and its prompt text assume WebScorer's race list.
- `config.py` hard-codes `WEBSCORER_API_ID` / `WEBSCORER_API_TOKEN` as the only credentials, required whenever `data_file` is unset.

A second timing platform would mean touching all of these. The roadmap goal is that a new platform is one adapter, not a new pipeline.

## Solution

Add a `providers/` package. A provider is a small bundle of functions behind one contract; a static registry maps the new `source` option to a provider. The poll loop asks the selected provider to fetch and normalize, and everything after `normalize` (views, pages, `/api/data`, frontend) is unchanged.

```
config.source --registry--> Provider --fetch(config, secrets)--> raw --normalize(raw)--> RaceSnapshot --views--> /api/data
```

Two providers ship, and only two (the roadmap's guard against over-abstracting):

1. `webscorer`: the existing API client and `normalize_webscorer`, wrapped with no behavior change.
2. `csv`: reads a spreadsheet export from `data_file`. It needs no credentials and no network, so it is also the offline demo path.

## Decisions

These were resolved without a reviewer, choosing the simplest option consistent with the issue. Each can be overruled in review.

| # | Question | Decision | Rationale |
|---|---|---|---|
| D1 | Shape of the contract | A frozen `Provider` dataclass holding a `name`, a `required_secrets` mapping, a `requires_data_file` flag, and the functions `fetch`, `normalize` and an optional `list_races`. Each provider module exports one `PROVIDER` instance. | The issue specifies two functions; the rest is the minimum the existing code needs (credentials, race selection, `data_file`). Plain functions need no inheritance and are trivial to fake in tests. |
| D2 | Registry | A static dict in `providers/__init__.py` (`get_provider(name)`, `provider_names()`). No entry points, no directory scanning, no runtime registration. | Two known providers. Adding a third is one import and one dict entry in a reviewed PR. |
| D3 | Where WebScorer code lives | `providers/webscorer.py` is a thin wrapper. `webscorer_client.py` and `normalizer.py` (including `normalize_webscorer` and the snapshot `TypedDict`s) stay where they are. | Zero behavior change and a small diff: no file moves, `test_normalizer.py` and `test_webscorer_client.py` are untouched, git history of both modules is preserved. |
| D4 | `source` option | Key `source`, env override `RACE_SOURCE`, default `webscorer`, `reload: "restart"`. Value is lower-cased and must be a registered provider, else the usual `ERROR:` and exit. Listed first in `OPTIONS` and `config.yaml`. | Swapping the ingestion pipeline mid-run is not worth supporting, and Phase 4 already treats `source` as restart-only. A bare `SOURCE` env name is too collision-prone; `RACE_SOURCE` follows the `WEBSCORER_RACE_ID` naming spirit. |
| D5 | CSV input path | **Reuse `data_file`** for any provider's offline input. `source: csv` requires `data_file`. For `source: webscorer`, `data_file` keeps its meaning (a WebScorer JSON dump replaces the API call). | No second option to document, print and keep in sync. One rule: `data_file` is the file the active provider reads instead of the network. |
| D6 | Credentials | Each provider declares `required_secrets` as `{config_key: ENV_VAR}`. `load_config` checks only the selected provider's secrets, and only when no `data_file` is set (as today). `webscorer` declares `api_id` / `api_token`; `csv` declares none. | Keeps the existing rule and error text (`WEBSCORER_API_ID is required. Set it in .env file.`) while letting `source: csv` start with an empty `.env`. |
| D7 | How secrets reach `fetch` | `poll_once` passes `secrets = {key: cfg.get(key) for key in provider.required_secrets}`. The config dict keeps its top-level `api_id` / `api_token`. | No change to the `load_config` return shape that tests and the startup printout depend on. A future provider adds its env var to `SECRET_ENV_VARS` and its key to the returned dict (one line each). |
| D8 | Race selection | Optional `list_races(config, secrets) -> list[{"id","name","date","sport"}]`. `select_race` becomes generic over that list. `main` prompts only when the provider has `list_races`, there is no `data_file`, and `race_id` is unset. | `select_race` is WebScorer-specific today. A hook keeps the prompt and drops the WebScorer assumption without special-casing provider names in `main`. `csv` sets it to `None`, so it never prompts. |
| D9 | CSV race metadata | Optional leading `# key: value` comment lines in the CSV (`name`, `date`, `sport`, `start`). `name` defaults to the file name without extension; `start` defaults to the earliest racer start time, else `0`. | A CSV has no place for race-level facts, and adding `race_name` / `race_date` options would grow the config surface and the Phase 4 conflict area. The metadata travels with the file. |
| D10 | CSV groups | One Overall group per distinct `distance` value, in first-appearance order (a blank distance is the single "Overall" group). One category group per distinct `(distance, category)` with a non-blank category, gender left blank. | Gives every distance an Overall page and every category a page, with category place and `CategoryPlace` derived by the existing projections. Gender-split pages are expressed by putting the split in the `category` text (for example `Women 40-49`). |
| D11 | CSV strictness | Any invalid row or column fails the whole file with an error naming each problem as `row N, column 'x': ...` (all problems up to 10, then a count). Unknown columns are ignored. | A half-loaded results board on a TV is worse than a clear error. Reporting several problems at once avoids a fix-one-rerun loop on a 300-row sheet. Extra columns (email, notes) are normal in exports and are never served. |
| D12 | CSV vs. platform errors | CSV validation raises (`CsvFormatError`, a `ValueError`). `webscorer` keeps reporting API-level errors through `snapshot["error"]`. | Raising reuses the existing stale/error path, which keeps the last good pages on screen while the operator fixes the file. |
| D13 | `race.source` in the snapshot | Not added. | The roadmap sketch lists it, but the shipped Phase 1 schema omits it and nothing downstream reads it. Adding an unused field is over-abstracting. |
| D14 | Existing test edits | Only mechanical retargeting: tests that patch `app.fetch_race_results` / `app.fetch_race_list` patch `providers.webscorer.*` instead, the `select_race` test passes the provider, and the reload-mode test adds `source` to the restart set. No assertion about WebScorer output changes. | The call sites move, so the patch targets must too. Golden files and all normalizer/projection tests are untouched. |
| D15 | `dump_api.py` | Unchanged and WebScorer-only. | It is a developer tool for capturing raw WebScorer payloads, not part of the runtime pipeline. |

## Provider contract

Defined in `providers/base.py`:

```python
@dataclass(frozen=True)
class Provider:
    name: str                                   # value of the `source` option
    required_secrets: Mapping[str, str]         # config key -> env var, e.g. {"api_id": "WEBSCORER_API_ID"}
    requires_data_file: bool                    # True when `data_file` is the provider's only input
    fetch: Callable[[dict, dict], Any]          # (config, secrets) -> raw payload
    normalize: Callable[[Any], RaceSnapshot]    # raw payload -> RaceSnapshot
    list_races: Optional[Callable[[dict, dict], List[RaceChoice]]] = None
```

Rules every provider follows:

- `fetch` does all I/O and returns an opaque `raw` value. It honors `config["data_file"]` when the provider supports offline input. It may raise; it must never put secrets in an exception message.
- `normalize` is pure: `raw -> RaceSnapshot` as documented in the `normalizer.py` docstring. It does not read config, files or the network, so it can be tested with literals.
- The returned snapshot upholds the Phase 1 invariants: `status == "FINISHED"` iff `elapsed_seconds` is set; every `in_overall` racer's `distance` has an Overall entry in `groups`; every `CategoryMembership` matches a category entry in `groups`.
- A platform-level error may be returned as `error` with empty `racers` / `groups` (WebScorer does this). Anything else raises.
- `required_secrets` is consulted only by `load_config` (presence check, skipped when `data_file` is set) and `poll_once` (building the `secrets` argument).
- `RaceChoice` is `{"id": str, "name": str, "date": str, "sport": str}`.

`providers/__init__.py` exposes `get_provider(name)`, `provider_names()` and the `Provider` type. `normalizer.py` stays the home of the `RaceSnapshot` schema; its docstring gains a pointer to this contract.

## Changes to existing code

| File | Change |
|---|---|
| `config.py` | Add the `source` option (restart). `load_config` resolves the provider, then checks `requires_data_file` and the provider's `required_secrets` instead of the hard-coded two. Messages for WebScorer are unchanged. |
| `config.yaml`, `README.md` | Document `source`; README gains a Sources section and the CSV format. `data_file` description generalized. |
| `app.py` | `poll_once` calls `provider.fetch` / `provider.normalize` instead of reading the file and calling `fetch_race_results` / `normalize_webscorer`. `select_race` takes the provider. `main` resolves the provider and prompts via `list_races`. `_format_config_lines` adds a `Source:` line. The `/api/data` response, poll loop, interval handling and `_cache` are untouched. |
| `providers/` | New: `base.py`, `__init__.py`, `webscorer.py`, `csv_provider.py`. |

`.env.example` stays secrets-only and unchanged. `start.sh` / `start.ps1` are unchanged.

## `data_file` and offline behavior

| `source` | `data_file` unset | `data_file` set |
|---|---|---|
| `webscorer` | Calls the WebScorer API (credentials and race id required; the race is chosen interactively when `race_id` is unset). | Reads that JSON dump instead of the API. No credentials. Same as today. |
| `csv` | Startup error: `source 'csv' requires data_file`. | Reads that CSV on every poll, so editing and saving the file updates the TV within one refresh interval. |

`load_config` still fails with `DATA_FILE '...' not found.` for a missing file.

## CSV format

UTF-8 (a leading byte-order mark from Excel is accepted), comma-separated, RFC 4180 quoting via Python's `csv` module. Line endings may be `\n` or `\r\n`.

**Race metadata (optional)**: comment lines at the top of the file, before the header row. Blank lines there are ignored.

```
# name: 2026 Coon Fork 40
# date: Aug 13, 2026
# sport: Cycling - gravel
# start: 14:08
```

| Key | Meaning | Default |
|---|---|---|
| `name` | Race name shown in the header | File name without extension |
| `date` | Date text shown as given | empty |
| `sport` | Sport text shown as given | empty |
| `start` | Race start time of day, `H:MM`, `H:MM:SS` or `H:MM:SS.f`, 24-hour | Earliest racer `start time`, else `0` |

An unknown key or a comment line that is not `key: value` is an error.

**Header row (required)**: column names are matched case-insensitively, ignoring surrounding spaces; `_` and a space are equivalent (`start_time` = `start time`). Duplicate or missing required columns are errors. Other columns are ignored.

| Column | Required | Maps to | Rules |
|---|---|---|---|
| `bib` | yes | `bib` | Text. May be blank. A non-blank bib must be unique within its distance. |
| `name` | yes | `name` | Must not be blank. |
| `time` | yes | `status`, `time_display`, `elapsed_seconds` | See below. |
| `team` | no | `team` | Text. |
| `distance` | no | `distance`, Overall group | Text. Blank rows share the "Overall" group. |
| `category` | no | `category`, category group | Text. Blank means no category page membership. |
| `gender` | no | `gender` | Text, any value. |
| `age` | no | `age` | Whole number 0-120, or blank. |
| `start time` | no | `start_seconds`, `finish_tod_seconds` | Same format as `# start:`. Blank means unknown (racer is skipped by the finish chart). |

**`time` column and status** (the same convention WebScorer uses, so organizers can paste either):

| `time` value | `status` | `elapsed_seconds` | `time_display` |
|---|---|---|---|
| `H:MM:SS`, `H:MM:SS.ff`, `M:SS`, `M:SS.ff` | `FINISHED` | parsed, rounded to milliseconds | as written |
| `DNS`, `DNF`, `DSQ` (any case) | the same word, upper-cased | `None` | as written |
| blank or `-` | `IN_PROGRESS` | `None` | `-` |
| anything else | error: `row N, column 'time': ...` | | |

Hours may exceed 23 (a long ultra). Minutes and seconds must be below 60 when a larger unit is present.

**Derived fields**: `finish_tod_seconds = start_seconds + elapsed_seconds` for finishers with a start time, not wrapped at midnight. A racer start more than 12 hours before the race start is treated as the next day (+86400), as in `normalizer.py`. `source_place` is `""`; places are derived by the projections, so the sheet needs no place column and row order does not matter. `in_overall` is always `True`.

**Groups**: Overall and category groups are built as in D10, so Overall, category, summary, finish chart and demographics pages all work from one flat sheet.

**Errors**: a problem message is `row N, column 'x': <what is wrong>`, where `N` is the line number in the file (what a spreadsheet shows, since comment lines are rows too). Structural problems (missing required column, duplicate header, no racer rows, bad metadata line) name the line or column. Up to 10 problems are reported, followed by `and K more`.

A sample file lives at `docs/sample-results.csv` and is used by the tests.

## Error handling

- Provider exceptions, including `CsvFormatError`, a missing CSV file, and WebScorer HTTP errors, propagate to `poll_once`'s existing `except`: the cache is marked stale, the message is shown in `error`, and the previous pages stay on screen. The next successful poll clears it.
- The existing credential scrub stays in that `except` (an error containing `apipriv=` is cut at the `?`). `fetch` implementations must not embed secrets in messages; CSV has none.
- A bad CSV at startup does not abort `main`: it behaves like a failed first WebScorer poll (TV shows the error, retries each interval).
- WebScorer's in-payload `Error` still flows through `snapshot["error"]` and the views' `error` path unchanged.

## What stays WebScorer-specific

`webscorer_client.py`, `normalize_webscorer` and its `Place` / `Grouping` / `Time` handling, the `WEBSCORER_*` secrets and `race_id`, the race list prompt (via `list_races`), `dump_api.py`, and the API-key log scrub. Nothing in `data_processing.py`, `templates/` or `static/` knows a provider exists.

## Testing

1. **Golden tests unchanged**: `tests/test_golden.py` and `tests/golden/` must pass with zero diff; they go through `poll_once` and so exercise the WebScorer provider end to end.
2. **Registry tests**: `get_provider` returns each provider, an unknown name raises a clear error, names are listed.
3. **WebScorer provider tests**: `fetch` with `data_file` reads the dump without touching the network; without it calls `fetch_race_results` with the right arguments; `normalize` equals `normalize_webscorer`; `list_races` maps the API list into `RaceChoice`s.
4. **CSV provider unit tests** (TDD): every column, status cases, time formats, start/finish arithmetic and next-day rollover, metadata defaults, group derivation order, category membership, BOM, quoted commas, blank-row skipping, and each error message (row and column named, several reported at once, capped at 10).
5. **Contract tests parametrized over both providers** (`tests/test_provider_contract.py`): for a sample input each, `fetch` + `normalize` returns a snapshot satisfying the invariants in the contract section, and the snapshot flows through `process_race_data`, `build_demographics_data`, `build_finish_chart_data` and `build_pages` without error. Adding a provider means adding it to the parameter list.
6. **Config tests**: `source` default, yaml and env override, invalid value exits naming the option; `source: csv` needs no credentials but needs `data_file`; webscorer credential errors keep their text; `config.yaml` / README / printout cover `source` (existing registry-driven tests).
7. **App tests**: `poll_once` with `source: csv` fills the cache from a CSV; a malformed CSV marks the cache stale with the row/column message; `main` skips the race prompt for `csv`.
8. **End to end**: run the app against `docs/sample-results.csv` and confirm `/api/data` returns summary, Overall, category and finish chart data.

## Non-goals

Third-party platform adapters (RunSignup, RaceResult, ...), Excel (`.xlsx`) input, per-source options beyond `data_file`, changing `source` without a restart (Phase 4 treats it as restart-only), provider plugin discovery, any UI change, and a CSV writer or exporter.
