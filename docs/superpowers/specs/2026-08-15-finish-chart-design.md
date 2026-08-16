# Stacked Bar Chart — Finishers per Bucket by Distance

## Problem

The summary page has a placeholder chart area. Spectators and organizers want a visual showing the flow of finishers over time, broken down by distance.

## Solution

A stacked bar chart rendered with Chart.js showing finisher counts in configurable time buckets (default 15 minutes), with one color per distance. Bucket computation happens server-side; the frontend just renders pre-computed data.

## Vendor Dependency Management

New file `static/vendor/vendor.json`:

```json
{
  "chart.js": {
    "version": "4.4.7",
    "url": "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
    "file": "chart.umd.min.js"
  }
}
```

- Start scripts (`start.sh`, `start.ps1`) read this file after `pip install` and download missing files to `static/vendor/`
- `static/vendor/*.js` is `.gitignore`'d
- `dashboard.html` loads `<script src="/static/vendor/chart.umd.min.js">`

## Configuration

New optional env var:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHART_BUCKET_MINUTES` | `15` | Width of each time bucket in minutes |

Added to `config.py` and passed through `/api/data` response.

## Server-Side Bucket Computation

New function in `data_processing.py`:

```python
def build_finish_chart_data(api_response, bucket_minutes=15):
```

Logic:
1. Iterate Overall groupings only (avoids double-counting category groups)
2. For each finisher: parse `StartTime` (HH:MM:SS.d) + `Time` (elapsed) → finish clock time
3. Floor to nearest bucket boundary (e.g. 15:08 → 15:00)
4. Group counts by (distance, bucket)
5. Return structured data or `None` if no finishers

Return format:

```json
{
  "labels": ["14:00", "14:15", "14:30", "14:45", "15:00"],
  "datasets": [
    {"label": "Short Course (28 miles)", "data": [0, 2, 5, 3, 1]},
    {"label": "Mid Course (45 miles)", "data": [0, 0, 1, 4, 2]},
    {"label": "Long Course (88 miles)", "data": [0, 0, 0, 0, 1]}
  ]
}
```

- Labels start at the floor hour of the race start time (e.g. start at 14:08 → first bucket is 14:00) and continue through the last-finish-bucket, gaps filled with zeros
- Dataset order matches distance order from the API (preserves natural ordering)

### Time Parsing

- `StartTime` format: `"HH:MM:SS.d"` (e.g. `"14:08:22.9"`)
- `Time` (elapsed) format: `"H:MM:SS.d"` or `"M:SS.d"` (e.g. `"10:06:16.5"`, `"0:22.4"`)
- Finish clock = StartTime + Time (both parsed to total seconds, summed, converted back)

## API Response

Add `"finish_chart"` key to `/api/data`:
- Computed in the poll cycle alongside `process_race_data`
- Stored in `_cache`
- Value is the dict above, or `null` when no finishers

## Frontend Rendering

In `renderSummary()` in `dashboard.js`:

- If `finish_chart` is null → show "No finishers yet" placeholder text
- Otherwise → insert a `<canvas>` element and create a Chart.js stacked bar chart:
  - Dark theme: transparent background, `#a0a0c0` grid lines, white axis labels
  - One distinct color per distance (consistent palette)
  - X-axis: time bucket labels (HH:MM format)
  - Y-axis: integer finisher count
  - Stacked bars
  - No animation (page rotates, instant render preferred)
  - Chart instance destroyed/recreated on each render cycle

## Edge Cases

- No finishers yet → placeholder text "No finishers yet"
- Only one bucket has finishers → single bar rendered (still useful)
- Racer has valid `Time` but missing `StartTime` → skip that racer

## Files Changed

| File | Change |
|------|--------|
| `static/vendor/vendor.json` | New — dependency manifest |
| `.gitignore` | Add `static/vendor/*.js` |
| `start.sh` | Download vendor deps step |
| `start.ps1` | Download vendor deps step |
| `templates/dashboard.html` | Add Chart.js script tag |
| `config.py` | Add `CHART_BUCKET_MINUTES` |
| `data_processing.py` | Add `build_finish_chart_data()` |
| `app.py` | Wire chart data into cache and `/api/data` response |
| `static/dashboard.js` | Render chart in `renderSummary()` |
| `static/style.css` | Remove `.chart-placeholder` rule (no longer needed) |
| `tests/test_data_processing.py` | Tests for `build_finish_chart_data()` |
