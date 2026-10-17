# WebScorer Race Dashboard

A TV-mounted dashboard that displays live race results from WebScorer. Designed to run on a Raspberry Pi connected to a TV at race events.

## Features

- Polls WebScorer API for live race results
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

- **`.env` (secrets only, never committed):** `WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`.
- **`config.yaml` (committed):** every other option. Edit it to change intervals, which pages show, layout, colors, etc.

### Precedence

Each option is resolved from these sources; a later one overrides an earlier one:

1. Built-in default
2. `config.yaml`
3. `.env`
4. Real environment variables (e.g. `REFRESH_INTERVAL=30 ./start.sh`)

A blank environment value (`KEY=`) counts as unset. Every `config.yaml` option can be overridden with the environment variable shown below, which is handy for one-off changes on race day without editing the file.

### Options

| `config.yaml` key | Environment override | Default | Description |
|---|---|---|---|
| `race_id` | `WEBSCORER_RACE_ID` | `null` | Race ID (prompts at startup if omitted) |
| `data_file` | `DATA_FILE` | `null` | Load results from a local JSON file instead of the API (no credentials needed) |
| `refresh_interval` | `REFRESH_INTERVAL` | 60 | Seconds between API polls |
| `summary_display_time` | `SUMMARY_DISPLAY_TIME` | 20 | Seconds the summary page displays |
| `scroll_speed` | `SCROLL_SPEED` | 100 | Scroll speed in pixels per second |
| `scroll_pause_time` | `SCROLL_PAUSE_TIME` | 2 | Seconds to pause before and after scrolling |
| `pinned_leaders` | `PINNED_LEADERS` | 3 | Leader rows pinned at the top |
| `show_summary` | `SHOW_SUMMARY` | true | Show the summary page |
| `show_overall_results` | `SHOW_OVERALL_RESULTS` | true | Show Overall result pages |
| `show_category_results` | `SHOW_CATEGORY_RESULTS` | true | Show category result pages |
| `show_demographics` | `SHOW_DEMOGRAPHICS` | false | Show the demographics page (age/gender/distance/team breakdown) |
| `pinned_leaders_on_overall_results` | `PINNED_LEADERS_ON_OVERALL_RESULTS` | false | Pinned leaders row + medal coloring on Overall pages |
| `overall_results_layout` | `OVERALL_RESULTS_LAYOUT` | standard | Overall table layout: `standard` or `detailed` |
| `display_unfinished_in_category` | `DISPLAY_UNFINISHED_IN_CATEGORY` | false | Show in-progress category pages before racers finish |
| `display_unfinished_in_overall` | `DISPLAY_UNFINISHED_IN_OVERALL` | false | Show in-progress Overall pages before racers finish |
| `chart_bucket_minutes` | `CHART_BUCKET_MINUTES` | 15 | Minutes per bucket in the finish chart |
| `color_scheme` | `COLOR_SCHEME` | dark | `dark` or `light` |
| `show_toasts` | `SHOW_TOASTS` | true | Toast notifications when racers finish |

The full set of effective options is printed at startup. Unknown keys in `config.yaml` and secrets placed in it are ignored with a warning.

### Migrating from an `.env`-only setup

Existing setups keep working with no changes: non-secret values in `.env` still apply (and override `config.yaml`), but the app prints a deprecation warning listing them. To migrate, move those values into `config.yaml` (lowercase keys, see the table) and leave only `WEBSCORER_API_ID` and `WEBSCORER_API_TOKEN` in `.env`.

## Requirements

- Python 3.9+
- For kiosk mode: Chromium browser (included with Raspberry Pi OS)
