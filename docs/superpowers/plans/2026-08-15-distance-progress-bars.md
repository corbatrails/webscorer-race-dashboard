# Distance Completion Progress Bars — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-distance completion progress bars below the finish chart on the summary page.

**Architecture:** Backend adds `distance_stats` (list of {name, total, finished}) to `process_race_data` return. Frontend renders a horizontal row of colored progress bars using the same HSL color generator as the chart.

**Tech Stack:** Python/Flask backend, vanilla JS frontend, CSS for bar styling.

## Global Constraints

- Colors must match the finish chart exactly — use the chart's dataset count as `n` in `generateChartColors(n)` so HSL spacing is identical
- Distance order must match `distance_order` (API order preserved)
- Readable at ~20 feet on a TV (minimum 2-3vh font sizes, 5vh bar height)
- No new dependencies

---

## Task 1: Add `distance_stats` to `process_race_data`

**Files:**
- Modify: `data_processing.py:57-105` (inside `process_race_data`)
- Test: `tests/test_data_processing.py`

**Interfaces:**
- Consumes: existing `distance_order`, `distance_buckets`, `_classify_racer`
- Produces: `distance_stats` key in return dict — `list[dict]` with keys `name` (str), `total` (int), `finished` (int)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_data_processing.py`:

```python
def test_distance_stats_multi_distance():
    response = {
        "RaceInfo": {"RaceId": 200, "Name": "Trail Race", "Date": "2026-08-13", "Sport": "Cycling"},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                    {"Place": "", "Bib": "2", "Name": "B", "Time": "DNS"},
                    {"Place": "-", "Bib": "3", "Name": "C", "Time": "-"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "4", "Name": "D", "Time": "00:30:00"},
                    {"Place": 2, "Bib": "5", "Name": "E", "Time": "00:35:00"},
                ],
            },
        ],
    }
    result = process_race_data(response)
    assert result["distance_stats"] == [
        {"name": "Long", "total": 3, "finished": 1},
        {"name": "Short", "total": 2, "finished": 2},
    ]


def test_distance_stats_single_distance():
    result = process_race_data(MOCK_API_RESPONSE)
    # Single-distance race (no Distance field) — uses "Overall" as name
    assert result["distance_stats"] == [
        {"name": "Overall", "total": 11, "finished": 6},
    ]


def test_distance_stats_empty_results():
    response = {
        "RaceInfo": {"RaceId": 100, "Name": "Empty", "Date": "", "Sport": ""},
        "Results": [],
    }
    result = process_race_data(response)
    assert result["distance_stats"] == []


def test_distance_stats_error_response():
    response = {"Error": "PRO Results subscription required"}
    result = process_race_data(response)
    assert result["distance_stats"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_processing.py::test_distance_stats_multi_distance tests/test_data_processing.py::test_distance_stats_single_distance tests/test_data_processing.py::test_distance_stats_empty_results tests/test_data_processing.py::test_distance_stats_error_response -v`

Expected: FAIL with `KeyError: 'distance_stats'`

- [ ] **Step 3: Implement `distance_stats` in `process_race_data`**

In `data_processing.py`, inside the existing Overall-grouping loop (where `total_racers` and `total_finished` are computed), track per-distance counts. After the loop, build the list.

Add tracking dict near line 60 (alongside `distance_order`):

```python
distance_stats_map = {}
```

Inside the `if grouping.get("Overall"):` block, accumulate per-distance:

```python
        if grouping.get("Overall"):
            dist_name = grouping.get("Distance") or "Overall"
            if dist_name not in distance_stats_map:
                distance_stats_map[dist_name] = {"name": dist_name, "total": 0, "finished": 0}
            total_racers += len(racers)
            distance_stats_map[dist_name]["total"] += len(racers)
            for racer in racers:
                status = _classify_racer(racer)
                if status == "DNS":
                    total_dns += 1
                elif status == "DNF":
                    total_dnf += 1
                elif status == "DSQ":
                    total_dsq += 1
                elif status == "FINISHED":
                    total_finished += 1
                    distance_stats_map[dist_name]["finished"] += 1
```

Add to the return dict:

```python
"distance_stats": [distance_stats_map[d] for d in distance_order if d in distance_stats_map],
```

Add `"distance_stats": []` to the error return at the top of the function.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_processing.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add data_processing.py tests/test_data_processing.py
git commit -m "feat: compute per-distance stats in process_race_data"
```

---

## Task 2: Render progress bars in frontend

**Files:**
- Modify: `static/dashboard.js` (inside `renderSummary` function)
- Modify: `static/style.css` (add progress bar styles)

**Interfaces:**
- Consumes: `d.distance_stats` array from summary page data (from Task 1), `generateChartColors(n)` (existing)
- Produces: rendered `.progress-bars-row` DOM below the chart area

- [ ] **Step 1: Add CSS for progress bars**

Append to `static/style.css`:

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

- [ ] **Step 2: Add `renderProgressBars` function in `dashboard.js`**

Add after the `renderFinishChart` function. The `colorCount` parameter ensures the same `n` is passed to `generateChartColors` as the chart uses, so colors are identical:

```javascript
function renderProgressBars(distanceStats, colorCount) {
  if (!distanceStats || distanceStats.length === 0) return "";
  var colors = generateChartColors(colorCount || distanceStats.length);
  var html = '<div class="progress-bars-row">';
  for (var i = 0; i < distanceStats.length; i++) {
    var stat = distanceStats[i];
    var pct = stat.total > 0 ? Math.round((stat.finished / stat.total) * 100) : 0;
    html += '<div class="progress-bar-item">';
    html += '<div class="progress-bar-label">' + escapeHtml(stat.name) + '</div>';
    html += '<div class="progress-bar-track">';
    html += '<div class="progress-bar-fill" style="width:' + pct + '%;background:' + colors[i] + '"></div>';
    html += '<div class="progress-bar-count">' + stat.finished + '/' + stat.total + '</div>';
    html += '</div>';
    html += '</div>';
  }
  html += '</div>';
  return html;
}
```

- [ ] **Step 3: Call `renderProgressBars` in `renderSummary`**

In `renderSummary`, after the chart area closing `</div>` (the line `html += "</div>";` that closes `.summary-chart-area`), add:

```javascript
var chartColorCount = (data.finish_chart && data.finish_chart.datasets) ? data.finish_chart.datasets.length : 0;
html += renderProgressBars(d.distance_stats, chartColorCount);
```

- [ ] **Step 4: Manual verification**

Run the app with a multi-distance race and verify:
- Progress bars appear below the chart
- Colors match the chart dataset colors
- Counts are correct
- Layout fits on screen without overflow

Run: `python app.py` (with test data or API dump)

- [ ] **Step 5: Commit**

```bash
git add static/dashboard.js static/style.css
git commit -m "feat: render distance completion progress bars on summary page"
```
