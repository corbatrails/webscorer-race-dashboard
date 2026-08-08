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

2. Configure credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your WebScorer API ID and Token
   ```

3. (Optional) Add your organization logo as `static/logo.png`

4. Run:
   ```bash
   ./start-app.sh          # Development: server only
   ./start-app.sh --kiosk  # Raspberry Pi: server + fullscreen Chromium
   ```

5. If `WEBSCORER_RACE_ID` is not set, select a race from the list when prompted.

6. Open http://localhost:5000 (or view the TV in kiosk mode).

## Configuration

Set these in your `.env` file:

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEBSCORER_API_ID` | Yes | — | Your JSON API ID |
| `WEBSCORER_API_TOKEN` | Yes | — | Your JSON API Token |
| `WEBSCORER_RACE_ID` | No | — | Race ID (prompts if omitted) |
| `REFRESH_INTERVAL` | No | 60 | Seconds between API polls |
| `PAGE_ROTATION_INTERVAL` | No | 20 | Seconds per dashboard page |

## Requirements

- Python 3.9+
- For kiosk mode: Chromium browser (included with Raspberry Pi OS)
