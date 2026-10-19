# Config Split: Secrets in `.env`, Everything Else in `config.yaml`

Roadmap: Phase 2 of `docs/ROADMAP.md` (issue #69, part of epic #67).

## Problem

Every option lives in `.env`, including non-secret settings (intervals, toggles, layout, colors). That forces `.env` / `.env.example` to be kept in sync by hand, makes settings impossible to commit or review, and gives later phases (hot-reload, admin UI) nothing to watch or edit. `SHOW_TOASTS` already drifted: it is read by `config.py` but missing from `.env.example`.

## Solution

Add a committed `config.yaml` that holds every non-secret option. `.env` keeps only secrets (`WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`). `load_config()` builds the final config from layered sources with a documented, tested precedence. Existing `.env`-only setups keep working unchanged.

## Design Decisions

These were resolved without a reviewer, choosing the simplest option consistent with the issue.

| Question | Decision | Rationale |
|---|---|---|
| Auto-generate `config.yaml` on first run, or ship one? | **Ship a committed `config.yaml` with the defaults.** No auto-generation. | Nothing to write at runtime, nothing to go wrong on a read-only Pi image, and the file doubles as the documented list of every option. A missing file is tolerated (built-in defaults), so there is no required manual step. |
| Schema shape | **Flat top-level keys**, lowercase, identical to the internal config dict keys (`refresh_interval`, `show_summary`, ...). Grouped by comments only. | Matches Phase 3's `source: webscorer` top-level key and keeps the Phase 5 editor a simple key/value form. Nesting adds mapping code with no present benefit. |
| Source of truth for options | A single **option registry** in `config.py` (`OPTIONS`): key, env var name, default, parser, `reload` mode. | One place defines defaults, env names, and validation; `config.yaml` and the startup printout are tested against it so they cannot drift. |
| Phase 4 hot vs. restart | Each option carries `reload: "live"` or `"restart"` metadata in the registry. Not acted on in this phase. | Lets Phase 4 surface which is which without a schema change. `race_id`, `data_file`, `refresh_interval` are `restart` (consumed once at startup / by the poll thread); display options are `live`. |
| Phase 3 `source:` | Not implemented. Unknown yaml keys produce a warning and are ignored; Phase 3 adds `source` to the registry. | Keeps this change surface small. |
| Secrets in `config.yaml` | `api_id` / `api_token` (any case, or `WEBSCORER_API_*`) in the yaml are **ignored with a warning**. | Prevents secrets drifting into a committed file. |
| Legacy `.env`-only setups | Keep working with no action. Non-secret keys found in `.env` still apply (as environment overrides) and print a **deprecation warning** naming the keys and pointing at `config.yaml`. | Zero-break upgrade; the warning drives migration. Real process environment variables never warn because they are the documented override mechanism. |
| Blank env values | `KEY=` (empty) is treated as unset. | Old `.env.example` shipped `WEBSCORER_RACE_ID=` blank; it must not blank out a yaml value. |
| Invalid values | Print `ERROR: ...` naming the option and source, `sys.exit(1)`. Enum options (`overall_results_layout`, `color_scheme`) keep their existing fallback-to-default behavior. | Matches existing fail-fast handling for missing credentials; avoids a raw `ValueError` traceback on the TV. |
| Config file path | `config.yaml` next to `config.py`; `load_config(config_path=None)` accepts an override (used by tests). | Independent of the current working directory, so the app starts the same from any launch location. |
| Startup printout | `_format_config_lines` is unchanged and still prints the full universe of options; a test asserts every registry option appears in it. | Satisfies the "configuration output must include every option" project rule. |

## Precedence

Lowest to highest; a later source overrides an earlier one per key:

1. **Built-in defaults** (registry; identical to the previous hard-coded defaults)
2. **`config.yaml`**
3. **`.env`** (loaded by `python-dotenv`; also supplies the secrets)
4. **Real process environment variables** (`python-dotenv` never overrides these)

`.env` and the process environment both surface as `os.environ`, so for non-secret options layers 3 and 4 behave as one "environment" layer where the real environment wins over `.env`. Secrets come only from that environment layer.

## Schema

`config.yaml` (flat):

| Key | Env override | Default | Reload |
|---|---|---|---|
| `race_id` | `WEBSCORER_RACE_ID` | `null` (prompt at startup) | restart |
| `data_file` | `DATA_FILE` | `null` | restart |
| `refresh_interval` | `REFRESH_INTERVAL` | `60` | restart |
| `summary_display_time` | `SUMMARY_DISPLAY_TIME` | `20` | live |
| `scroll_speed` | `SCROLL_SPEED` | `100` | live |
| `scroll_pause_time` | `SCROLL_PAUSE_TIME` | `2` | live |
| `pinned_leaders` | `PINNED_LEADERS` | `3` | live |
| `show_summary` | `SHOW_SUMMARY` | `true` | live |
| `show_overall_results` | `SHOW_OVERALL_RESULTS` | `true` | live |
| `show_category_results` | `SHOW_CATEGORY_RESULTS` | `true` | live |
| `show_demographics` | `SHOW_DEMOGRAPHICS` | `false` | live |
| `pinned_leaders_on_overall_results` | `PINNED_LEADERS_ON_OVERALL_RESULTS` | `false` | live |
| `overall_results_layout` | `OVERALL_RESULTS_LAYOUT` | `standard` (`standard`/`detailed`) | live |
| `display_unfinished_in_category` | `DISPLAY_UNFINISHED_IN_CATEGORY` | `false` | live |
| `display_unfinished_in_overall` | `DISPLAY_UNFINISHED_IN_OVERALL` | `false` | live |
| `chart_bucket_minutes` | `CHART_BUCKET_MINUTES` | `15` | live |
| `color_scheme` | `COLOR_SCHEME` | `dark` (`dark`/`light`) | live |
| `show_toasts` | `SHOW_TOASTS` | `true` | live |

Secrets (environment only): `WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`.

Type rules: booleans accept YAML booleans, or the strings `true`/`false` (case-insensitive) from the environment; integers accept YAML ints or numeric strings. `null` or blank means unset.

## Behavior

- The returned config dict has the same keys and types as before; `app.py`, `data_processing.py`, and templates are untouched.
- Credentials are required unless a `data_file` is set, as before; error messages still point to `.env`.
- `.env.example` shrinks to the two secrets. `start.sh` / `start.ps1` keep their `.env` existence check; only the message text changes (kept identical in both).

## Testing

- Defaults with no `config.yaml`; every option read from `config.yaml`.
- Precedence: yaml beats default; env beats yaml; real env beats `.env` value.
- Blank env values do not override yaml.
- Secrets in yaml are ignored with a warning; unknown yaml keys warn.
- Legacy `.env`-only: values apply and a deprecation warning lists the keys; no warning for a secrets-only `.env`.
- Malformed yaml / invalid values exit with a clear message.
- The committed `config.yaml` has exactly the registry keys and loads to the registry defaults.
- `_format_config_lines` shows every registry option.

## Non-Goals

Hot-reload (Phase 4), provider `source` selection (Phase 3), admin UI and yaml writing (Phase 5), nested schema, auto-generating `config.yaml`.

## Project rule change

The rule "`.env.example` must always list the same properties as `.env`" is replaced: `.env.example` lists only secrets, and `config.yaml` must list every supported non-secret option (enforced by a test).
