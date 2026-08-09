# WebScorer Race Dashboard — Design Spec

## Problem

Race participants at events in remote locations (no public internet) can't see their results after finishing. The event infrastructure uses Starlink-backed wifi but can't share it publicly. A TV-mounted dashboard displaying live results solves this.

## Solution

A Python/Flask web application running on a Raspberry Pi, connected to a TV. The app polls the WebScorer JSON API over the event's private wifi, caches results in memory, and serves a rotating HTML dashboard via Chromium in kiosk mode.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Raspberry Pi                     │
│                                                  │
│  ┌──────────────┐        ┌───────────────────┐  │
│  │  Flask Server │◄──────│  Chromium (kiosk)  │  │
│  │  port 5000    │───────►  fullscreen browser│  │
│  └──────┬───────┘        └───────────────────┘  │
│         │                                        │
│         │ polls every 60s                        │
└─────────┼───────────────────────────────────────┘
          │ HTTPS
          ▼
   ┌──────────────┐
   │ WebScorer API │
   │ webscorer.com │
   └──────────────┘
```

### Components

- **Flask server** (`app.py`) — single process. A background thread fetches from WebScorer API at a configurable interval (default 60s), caches results in a Python dict in memory. Serves HTML pages via Jinja2 templates.
- **Chromium kiosk** — opens `http://localhost:5000` in fullscreen, no browser chrome. Minimal JS handles page rotation.
- **No database, no state files** — everything lives in memory, rebuilt from API on each poll.

## Configuration

Via `.env` file (`.env.example` template committed to repo, `.env` gitignored):

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEBSCORER_API_ID` | yes | — | JSON API ID from organizer settings |
| `WEBSCORER_API_TOKEN` | yes | — | JSON API Token (8-char) |
| `WEBSCORER_RACE_ID` | no | — | Race ID; if omitted, app prompts for selection at startup |
| `REFRESH_INTERVAL` | no | `60` | Seconds between API polls |
| `PAGE_ROTATION_INTERVAL` | no | `20` | Seconds each page is displayed |

## Race Selection

On startup:

1. If `WEBSCORER_RACE_ID` is set in `.env`, use it directly
2. Otherwise, call `GET /json/mypostedraces?apiid=n&apipriv=p` to fetch all posted races
3. Display a numbered list in the terminal (race name, date, sport)
4. User selects a race by number
5. Dashboard launches with the selected race ID

## Data Flow

1. Background thread calls `GET /json/race?raceid=r&apiid=n&apipriv=p` every `REFRESH_INTERVAL` seconds
2. Parses response: extracts `RaceInfo` (name, date, sport) and `Results` (grouped by category)
3. Computes summary stats: total participants, finished count, per-category top 3 leaders
4. Stores everything in a Python dict in memory with a fetch timestamp
5. Flask serves the cached data to the Jinja2 template on each page request

## Dashboard Pages

All pages rendered in a single HTML template. Client-side JS rotates between logical "pages" (sections) every `PAGE_ROTATION_INTERVAL` seconds.

### Page 1 — Summary/Overview (always shown as its own screen)

- Organization logo (from `static/logo.png`, drop-in replaceable)
- Race name, date, sport (from API `RaceInfo`)
- Total participants started vs. finished
- Top 3 leaders for each category (compact leaderboard)
- Last refresh timestamp

### Pages 2+ — Category Results (one page per category, rotated after summary)

- Category name as header
- Full results table: Place, Bib, Name, Time
- If a category exceeds ~15-20 visible rows (readable font size on 1080p TV), it splits into multiple pages automatically
- Last refresh timestamp in footer

### Rotation Behavior

- Cycle: Summary → Category 1 (page 1) → Category 1 (page 2 if split) → Category 2 → ... → Summary → repeat
- Summary page is always a distinct screen, never merged with category results
- On data refresh, page content updates in-place without resetting rotation position

## Visual Design

- Dark background, light text (reduces glare, readable outdoors/in tents)
- Large, high-contrast fonts optimized for 1080p TV readable from 10-20 feet
- Organization logo displayed from `static/logo.png` — replaceable by dropping in a different image
- Clean, minimal layout prioritizing readability at distance

## Error Handling

### API Failures
- If a fetch fails (network error, timeout, invalid credentials), the dashboard continues showing the last successful data with a visible "stale data" indicator and the last-successful-refresh timestamp
- On first startup with unreachable API, shows a "Waiting for data..." screen with the error message for race-day diagnosis

### Empty/In-Progress States
- Race with no results yet: Summary shows "0 finished", category pages show "No results yet"
- Category with no finishers: still displays the category page with an empty state (not skipped)

### Configuration Errors
- Missing `.env` or missing required values: app exits immediately with a clear error message identifying what's missing

## File Structure

```
├── app.py                  # Flask server + background poller
├── templates/
│   └── dashboard.html      # Jinja2 template (all pages, JS rotates)
├── static/
│   ├── style.css           # Dashboard styling
│   ├── dashboard.js        # Page rotation + refresh logic
│   └── logo.png            # Drop-in org logo
├── .env.example            # Config template
├── .gitignore
├── requirements.txt        # flask, requests, python-dotenv
├── start-app.sh            # Setup + launch script
├── docs/
│   └── webscorer-api-reference.md
└── README.md
```

## Dependencies

- `flask` — web server and templating
- `requests` — HTTP client for WebScorer API
- `python-dotenv` — `.env` file loading

## Deployment

### `start-app.sh`

1. Creates a Python venv if it doesn't exist
2. Installs/updates deps from `requirements.txt`
3. Validates `.env` exists and has required keys
4. Starts the Flask server
5. With `--kiosk` flag: also launches Chromium in fullscreen kiosk mode

```bash
./start-app.sh            # server only (for dev/testing)
./start-app.sh --kiosk    # server + Chromium fullscreen (for Pi)
```

### Pi Setup (one-time)

1. Clone repo from GitHub
2. Copy `.env.example` to `.env`, fill in API credentials
3. Drop org logo as `static/logo.png`
4. Run `./start-app.sh --kiosk`
5. Select race from the displayed list

### Dev Workflow

- Run `./start-app.sh` on any machine
- Open `http://localhost:5000` in any browser
- No Pi or TV required for development

## API Reference

See `docs/webscorer-api-reference.md` for full WebScorer JSON API documentation.

Primary endpoint used:
```
GET https://www.webscorer.com/json/race?raceid=r&apiid=n&apipriv=p
```
