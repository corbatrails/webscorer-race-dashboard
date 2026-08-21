# Demographics Page

## Problem

Spectators and organizers have no way to see the participant makeup of a race — age spread, gender balance, distance popularity, or team participation. The API provides this data per racer, but nothing surfaces it today.

## Solution

A new rotating page, `demographics`, computed from all registrants (including DNS/DNF, not just finishers) and shown as a single 2x2 grid of charts/stats, following the existing page-rotation and Chart.js patterns established by the finish chart.

## Data Source & Scope

New function in `data_processing.py`:

```python
def build_demographics_data(api_response):
```

- Iterates **Overall groupings only** in `Results` (avoids double-counting racers who also appear in Category groupings).
- Includes **all registrants** regardless of finish status (DNS/DNF/DSQ/finished all count).
- Returns `None` if there are no racers at all (e.g. `Error` in response, or empty `Results`) — the page is then omitted from rotation, same as a category page with no results.

## Computed Breakdowns

Return format:

```json
{
  "total_registrants": 87,
  "age": {
    "average": 41.2,
    "median": 40,
    "min": 19,
    "max": 71,
    "labels": ["<20", "20-29", "30-39", "40-49", "50-59", "60-69", "70+"],
    "counts": [1, 15, 22, 24, 15, 8, 2]
  },
  "gender": {
    "labels": ["Male", "Female", "Unknown"],
    "counts": [58, 27, 2]
  },
  "distance": {
    "labels": ["Short Course (28 miles)", "Long Course (88 miles)"],
    "counts": [40, 47]
  },
  "teams": {
    "solo_count": 50,
    "team_count": 37,
    "top_teams": [
      {"name": "Team X", "count": 6},
      {"name": "Team Y", "count": 4}
    ]
  }
}
```

Rules:
- **Age**: bucketed into fixed decade bins (`<20`, `20-29`, `30-39`, `40-49`, `50-59`, `60-69`, `70+`). Racers with missing/non-numeric `Age` are excluded from `age` stats (average/median/min/max/histogram) but still counted in `total_registrants`. `average` rounded to 1 decimal; `median` is the statistical median of ages with valid data.
- **Gender**: grouped by the exact string value of `Gender` as returned by the API. Missing/blank/null → bucketed as `"Unknown"`. Labels ordered by descending count.
- **Distance**: count of registrants per `Distance` value (registration choice — reflects the Overall grouping's `Distance`, not finish status). Labels preserve the natural order from the API (same convention as the finish chart).
- **Teams**: `solo_count` = racers with no `TeamName` (null/blank); `team_count` = racers with a non-blank `TeamName`. `top_teams` = top 5 distinct team names by headcount, ties broken alphabetically by name. Teams with only 1 member are still eligible to appear if they happen to be in the top 5 (no minimum team size filter).

## Configuration

New optional env var in `config.py`, following the existing `show_*` pattern:

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOW_DEMOGRAPHICS` | `false` | Whether to include the demographics page in rotation |

## Server Wiring

`app.py`:
- Call `build_demographics_data(raw)` alongside `process_race_data` / `build_finish_chart_data` in the poll cycle.
- Store result in `_cache["demographics"]`.
- Include `"demographics"` in the `/api/data` response.
- Include `show_demographics` in the `/api/data` response (config passthrough, same as `show_summary`).
- Add `Show demographics: <bool>` line to the startup config printout.

## Frontend Rendering

`static/dashboard.js`:
- `buildPageList`: when `config.showDemographics` is true and `data.demographics` is non-null, insert a `demographics` page into the rotation immediately after the summary page (before categories).
- New `renderDemographics(data)` function producing a `.page.active.demographics-page` container with:
  - A top stat strip: total registrants, average age, median age, age range (min–max) — reusing existing summary-stat text styling.
  - A 2x2 CSS grid of panels:
    - **Top-left**: age histogram — Chart.js bar chart, x-axis = age bucket labels, y-axis = count.
    - **Top-right**: gender breakdown — Chart.js doughnut chart.
    - **Bottom-left**: distance popularity — Chart.js horizontal bar chart, one bar per distance.
    - **Bottom-right**: team participation — solo vs. team counts as text, plus a simple ranked list of the top 5 teams (name + count). No chart needed here.
  - Chart instances (age, gender, distance) are tracked in module-level variables, destroyed and recreated each render cycle — same lifecycle as `finishChart`.
  - Colors/theme follow the existing dark/light `data-theme` conventions used by the finish chart (`#a0a0c0` gridlines, theme-aware text color, consistent color palette per series).

`static/style.css`:
- New `.demographics-page` grid layout (2x2, responsive to viewport) and stat-strip styling, reusing existing page/panel conventions where possible.

## Error Handling / Edge Cases

- No racers at all → `build_demographics_data` returns `None` → page omitted from rotation entirely (mirrors how a category page with no results is skipped).
- Missing `Age` → excluded from age stats only, still counted in `total_registrants`.
- Missing/blank `Gender` → bucketed as `"Unknown"`.
- Missing/blank `TeamName` → counted as solo, never appears in `top_teams`.
- Fewer than 5 distinct teams → `top_teams` simply has fewer entries.

## Testing

`tests/test_data_processing.py`:
- Normal race data (mixed ages/genders/teams/distances) → correct totals, buckets, and top teams.
- Missing `Age` on some racers → excluded from age stats, included in `total_registrants`.
- Missing `Gender` on some racers → bucketed as `Unknown`.
- No `TeamName` anywhere → `team_count` is 0, `top_teams` is empty.
- Empty `Results` / `Error` response → returns `None`.

## Files Changed

| File | Change |
|------|--------|
| `config.py` | Add `SHOW_DEMOGRAPHICS` |
| `data_processing.py` | Add `build_demographics_data()` |
| `app.py` | Wire demographics into cache, `/api/data` response, and startup printout |
| `static/dashboard.js` | Add `demographics` page to rotation, `renderDemographics()` |
| `static/style.css` | Add `.demographics-page` grid + stat-strip styles |
| `tests/test_data_processing.py` | Tests for `build_demographics_data()` |
