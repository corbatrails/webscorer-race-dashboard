# Distance Completion Progress Bars

## Problem

The summary page shows global totals (Total Racers, Finishers) but no per-distance breakdown of completion. Spectators and organizers want to see at a glance how each distance group is progressing.

## Solution

Horizontal progress bars in a single row below the stacked bar chart, one bar per distance group. Each bar shows the fill proportion (finished/total) with a numeric count overlay. Colors match the chart datasets for visual consistency.

## Data Layer

Add `distance_stats` to the return value of `process_race_data`:

```python
"distance_stats": [
    {"name": "Long Course (88 miles)", "total": 16, "finished": 12},
    {"name": "Short Course (28 miles)", "total": 24, "finished": 24},
]
```

Computed from the existing Overall-grouping loop. Order matches `distance_order` (same order as chart datasets) so color indices align.

Empty list when no distances exist or all totals are zero.

## API

No changes needed — `distance_stats` is inside `dashboard_data` which flows through `build_pages` → summary page `data` → `/api/data` automatically.

## Frontend Rendering

In `renderSummary`, after the chart area closing `</div>`, render a `.progress-bars-row` div when `d.distance_stats` has entries:

```
┌─────────────────────────────────────────────────────────┐
│  Long Course (88 miles)   │  Short Course (28 miles)    │
│  ████████████░░░░  12/16  │  ████████████████████ 24/24 │
└─────────────────────────────────────────────────────────┘
```

Each bar element:
- Distance name label above (2vh, light gray)
- Track background with filled portion colored via `generateChartColors(n)[i]`
- Count text "12/16" centered on the bar (3vh, bold white)

Colors use the same `generateChartColors` function and same index as the chart datasets.

## CSS

```css
.progress-bars-row {
  display: flex;
  gap: 1.5vw;
  padding: 1.5vh 0;
}

.progress-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.progress-bar-label {
  font-size: 2vh;
  color: #a0a0c0;
  margin-bottom: 0.5vh;
}

.progress-bar-track {
  height: 5vh;
  background: #0f3460;
  border-radius: 0.5vh;
  position: relative;
  overflow: hidden;
}

.progress-bar-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 0.5vh;
}

.progress-bar-count {
  position: absolute;
  width: 100%;
  text-align: center;
  line-height: 5vh;
  font-size: 3vh;
  font-weight: bold;
  color: #ffffff;
}
```

## Layout Impact

The `.summary-chart-area` keeps `flex: 1`. The progress bars row sits below it with fixed height (~8vh). The chart loses that small amount of vertical space.

## Testing

Unit test in `test_data_processing.py`:
- `distance_stats` present in output, ordered correctly
- Counts match expected (finished vs total per distance)
- Empty list when no Overall groupings exist
- Racers with DNS/DNF/DSQ/in-progress are counted in total but not finished

## Acceptance Criteria

- One progress bar per distance group displayed on the summary page
- Shows finished count / total count numerically
- Fill width proportional to completion percentage
- Updates on each data refresh (re-rendered from latest `/api/data`)
- Colors consistent with stacked bar chart
