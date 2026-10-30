# WebScorer Race Dashboard

A TV-mounted dashboard that displays live race results from WebScorer. Designed to run on a Raspberry Pi connected to a TV at race events.

## Features

- Polls WebScorer API for live race results, or reads a CSV spreadsheet (see [Sources](#sources))
- Auto-rotating dashboard pages: summary overview + per-category results
- Large, high-contrast dark theme optimized for TV readability
- Configurable refresh and rotation intervals
- Interactive race selection or pre-configured race ID

## Quick Start

1. Clone the repo:
   ```bash
   git clone https://github.com/corbatrails/webscorer-race-dashboard.git
   cd webscorer-race-dashboard
   ```

2. Configure credentials (secrets only):
   ```bash
   cp .env.example .env
   # Edit .env with your WebScorer API ID and Token
   ```
   All other options live in the committed `config.yaml` (see [Configuration](#configuration)).

3. (Optional) Add your organization logo as `static/logo.png`

4. Run:
   ```bash
   # Linux / Raspberry Pi
   ./start.sh              # Development: server only
   ./start.sh --kiosk      # Server + fullscreen Chromium

   # Windows (PowerShell)
   .\start.ps1             # Development: server only
   .\start.ps1 --kiosk     # Server + fullscreen Chromium
   ```

5. If `race_id` is not set in `config.yaml`, select a race from the list when prompted.

6. Open http://localhost:5000 (or view the TV in kiosk mode).

## Configuration

Options are split by sensitivity:

- **`.env` (secrets only, never committed):** `WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`, and optionally `ADMIN_PASSWORD`.
- **`config.yaml` (committed):** every other option. Edit it to change intervals, which pages show, layout, colors, etc.

### Choosing a config file

The app reads `config.yaml` next to `app.py` by default. Pass `--config` to use another file, for example a throwaway test setup:

```bash
python app.py --config /tmp/demo.yaml
```

Environment variables never override non-secret options; only the secrets above are read from the environment (a real environment variable wins over `.env`). Options missing from the file use the built-in default.

### Options

| `config.yaml` key | Default | Description |
|---|---|---|
| `source` | `webscorer` | Ingestion provider: `webscorer` or `csv` |
| `race_id` | `null` | Race ID (prompts at startup if omitted) |
| `data_file` | `null` | File the provider reads instead of the network: a WebScorer JSON dump, or the CSV for `source: csv` (no credentials needed) |
| `refresh_interval` | 60 | Seconds between API polls (at least 1) |
| `summary_display_time` | 20 | Seconds the summary page displays (at least 1) |
| `scroll_speed` | 100 | Scroll speed in pixels per second (at least 1) |
| `scroll_pause_time` | 2 | Seconds to pause before and after scrolling (0 or more) |
| `pinned_leaders` | 3 | Leader rows pinned at the top (0 or more) |
| `show_summary` | true | Show the summary page |
| `show_overall_results` | true | Show Overall result pages |
| `show_category_results` | true | Show category result pages |
| `show_demographics` | false | Show the demographics page (age/gender/distance/team breakdown) |
| `pinned_leaders_on_overall_results` | false | Pinned leaders row + medal coloring on Overall pages |
| `overall_results_layout` | standard | Overall table layout: `standard` or `detailed` |
| `display_unfinished_in_category` | false | Show in-progress category pages before racers finish |
| `display_unfinished_in_overall` | false | Show in-progress Overall pages before racers finish |
| `chart_bucket_minutes` | 15 | Minutes per bucket in the finish chart (at least 1) |
| `color_scheme` | dark | `dark` or `light` |
| `show_toasts` | true | Toast notifications when racers finish |

The full set of effective options is printed at startup. Booleans must be `true` or `false`, and choice options must use one of the listed values; an invalid value stops startup with a message naming the option. Unknown keys in `config.yaml` and secrets placed in it are ignored with a warning.

### Changing settings while running

The app watches its config file (`config.yaml`, or the `--config` path) and applies edits to every option without a restart. This is the intended way to adjust the TV during an event.

- **Latency:** a saved edit is picked up in about 2 seconds. The browser follows on its next fetch. The theme and page layout update without a page reload, and the fetch cadence follows `refresh_interval`.
- **Applied at the next poll:** `show_overall_results`, `show_category_results`, and `chart_bucket_minutes` shape the cached pages, so they take effect on the next API poll (within one `refresh_interval`).
- **Secrets are not reloaded.** `.env`, the API credentials and `ADMIN_PASSWORD` keep their startup values; restart to change them.
- **Bad edits are rejected whole.** If the file has invalid YAML or an invalid value (including `refresh_interval` below 1), the last good settings keep running and a warning is printed to the console once per distinct error. Fix the file and it is picked up automatically.
- **Switching races:** changing `source`, `race_id`, or `data_file` clears the current race from the TV right away, shows a waiting screen, and polls the new race immediately. Results from the old race that arrive afterward are discarded. If the new race cannot be fetched yet, the selection is kept and the app retries every `refresh_interval`.
- **`/api/data` fields:** `config_version` starts at 1 and increments each time an option changes. `race_generation` changes each time the race (`source`, `race_id`, `data_file`) changes. `race_selection_required` is true while a live WebScorer setup has no race chosen. `color_scheme` and `refresh_interval` report the active values. `admin_enabled` says whether the admin page is on (never the password).

### Migrating from an `.env`-only setup

Non-secret values in `.env` or the process environment (for example `REFRESH_INTERVAL` or `WEBSCORER_RACE_ID`) are ignored. Move them into `config.yaml` (lowercase keys, see the table) and leave only `WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN` and (optionally) `ADMIN_PASSWORD` in `.env`.

### Admin page

Set `ADMIN_PASSWORD` in `.env` and restart to enable `http://<host>:5000/admin`. Leave it empty and the admin page is disabled (every `/admin` URL returns 404). Startup prints whether the admin page is enabled, never the password.

The page edits every option in `config.yaml`, grouped by purpose. Saving validates the values, writes `config.yaml` (keeping its comments), and applies them to the running dashboard within one poll; no restart is needed. Invalid values are listed next to their fields and nothing is written.

- **Race picker:** with `source: webscorer` and API credentials in `.env`, the page lists your WebScorer races; choosing one fills in the race ID. You can also type an ID. Picking a race here while the terminal is still asking for one answers the terminal prompt too.
- **Conflicts:** if `config.yaml` changed after you opened the page (a hand edit, or a race picked in the terminal), saving is refused and nothing is written. Reload the page to see the current values, then make your change again.
- If `config.yaml` itself has errors, the page shows the running settings instead; saving replaces the file's values with the form's.
- Secrets never appear on the page and can't be set from it; they stay in `.env`.
- One shared password; no user accounts. Logging in gives a browser session that lasts until you log out or the app restarts.
- Forms are protected against cross-site requests, and admin pages send no-cache and anti-framing headers.
- **The dashboard serves plain HTTP.** The password and session cookie cross the network unencrypted, so only run the admin page on a network you trust (the race LAN), and use a password you don't use elsewhere.

## Sources

The `source` option selects where results come from. It can be changed while the app runs.

| `source` | Reads | Credentials |
|---|---|---|
| `webscorer` (default) | The WebScorer API, or a saved JSON dump when `data_file` is set | `WEBSCORER_API_ID` and `WEBSCORER_API_TOKEN` in `.env`, unless `data_file` is set |
| `csv` | The CSV file named by `data_file`, re-read on every poll | None |

With `source: csv`, `data_file` is required. Save the spreadsheet and the TV updates within one `refresh_interval`. If the file is invalid, the last good pages stay on screen and the error is shown until the file is fixed.

### Offline demo

The repo ships a sample file, [`docs/sample-results.csv`](docs/sample-results.csv), and a matching config, [`docs/demo-config.yaml`](docs/demo-config.yaml). No credentials are needed. From the repo root, after `./start.sh` or `.\start.ps1` has created the virtual environment:

```bash
source venv/bin/activate
python app.py --config docs/demo-config.yaml
```

```powershell
.\venv\Scripts\Activate.ps1
python app.py --config docs/demo-config.yaml
```

Or set `source: csv` and `data_file: docs/sample-results.csv` in `config.yaml`.

### CSV format

UTF-8, comma-separated, with a header row. A byte-order mark from Excel is accepted. Places are computed by the dashboard, so the sheet needs no place column and row order does not matter.

**Race details (optional)** go in `# key: value` comment lines before the header:

```
# name: 2026 Coon Fork 40
# date: Aug 13, 2026
# sport: Cycling - gravel
# start: 14:08
```

| Key | Meaning | Default |
|---|---|---|
| `name` | Race name shown in the header | File name without extension |
| `date` | Date text, shown as given | empty |
| `sport` | Sport text, shown as given | empty |
| `start` | Race start, 24-hour `H:MM` or `H:MM:SS` | Earliest racer `start time`, else `0` |

**Columns.** Names are case-insensitive, and `_` equals a space (`start_time` is `start time`). Other columns are ignored.

| Column | Required | Rules |
|---|---|---|
| `bib` | yes | Text. May be blank. A bib must be unique within its distance. |
| `name` | yes | Must not be blank. |
| `time` | yes | See below. |
| `team` | no | Text. |
| `distance` | no | Text. Each distinct value gets its own Overall page. Blank rows share one "Overall" page. |
| `category` | no | Text. Each distinct distance and category pair gets a category page. Blank means no category page. For gender-split pages, put the split in the text (`Women 40-49`). |
| `gender` | no | Text, any value. |
| `age` | no | Whole number 0-120, or blank. |
| `start time` | no | 24-hour `H:MM` or `H:MM:SS`. Needed for the finish chart. |

**`time` values:**

| Value | Meaning |
|---|---|
| `H:MM:SS`, `H:MM:SS.ff`, `M:SS`, `M:SS.ff` | Finished. Hours may exceed 23. |
| `DNS`, `DNF`, `DSQ` (any case) | Did not start, did not finish, disqualified |
| blank or `-` | Still racing |

Anything else is an error. An invalid file is rejected as a whole, and each problem is reported as `row N, column 'x': ...` (up to 10, then a count), where `N` is the line number a spreadsheet shows.

## Requirements

- Python 3.9+
- For kiosk mode: Chromium browser (included with Raspberry Pi OS)
