# Finish Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stacked bar chart to the summary page showing finisher counts per time bucket, grouped by distance.

**Architecture:** Server-side Python computes finish-time buckets from raw API data, passes pre-aggregated chart data through `/api/data`. Frontend renders it with Chart.js (downloaded by start scripts from a pinned version in `vendor.json`).

**Tech Stack:** Python/Flask (backend), Chart.js 4.4.7 (frontend charting), vanilla JS

## Global Constraints

- Chart.js version pinned in `static/vendor/vendor.json`; `.js` files in that dir are `.gitignore`'d
- `start.sh` and `start.ps1` must stay in sync (same behavior, same commit)
- Conventional commit messages
- TDD: tests before implementation

---

### Task 1: Vendor dependency infrastructure

**Files:**
- Create: `static/vendor/vendor.json`
- Modify: `.gitignore`
- Modify: `start.sh`
- Modify: `start.ps1`
- Modify: `templates/dashboard.html`

**Interfaces:**
- Consumes: nothing
- Produces: Chart.js available at `/static/vendor/chart.umd.min.js` at runtime

- [ ] **Step 1: Create `static/vendor/vendor.json`**

```json
{
  "chart.js": {
    "version": "4.4.7",
    "url": "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
    "file": "chart.umd.min.js"
  }
}
```

- [ ] **Step 2: Add vendor JS files to `.gitignore`**

Append to `.gitignore`:

```
static/vendor/*.js
```

- [ ] **Step 3: Add vendor download step to `start.sh`**

After the `pip install` line and before the `.env` check, add:

```bash
# Download pinned JS vendor dependencies
VENDOR_DIR="static/vendor"
if command -v python3 &>/dev/null; then PY=python3; else PY=python; fi
$PY -c "
import json, urllib.request, os
vendor_dir = '$VENDOR_DIR'
with open(os.path.join(vendor_dir, 'vendor.json')) as f:
    deps = json.load(f)
for name, info in deps.items():
    dest = os.path.join(vendor_dir, info['file'])
    if not os.path.exists(dest):
        print(f'Downloading {name} v{info[\"version\"]}...')
        urllib.request.urlretrieve(info['url'], dest)
"
```

- [ ] **Step 4: Add vendor download step to `start.ps1`**

After the `pip install` line and before the `.env` check, add:

```powershell
# Download pinned JS vendor dependencies
$vendorJson = Get-Content "static/vendor/vendor.json" | ConvertFrom-Json
foreach ($dep in $vendorJson.PSObject.Properties) {
    $info = $dep.Value
    $dest = Join-Path "static/vendor" $info.file
    if (-not (Test-Path $dest)) {
        Write-Host "Downloading $($dep.Name) v$($info.version)..."
        Invoke-WebRequest -Uri $info.url -OutFile $dest -UseBasicParsing
    }
}
```

- [ ] **Step 5: Add Chart.js script tag to `templates/dashboard.html`**

Add before the `dashboard.js` script tag:

```html
<script src="/static/vendor/chart.umd.min.js?v={{ cache_bust }}"></script>
```

- [ ] **Step 6: Run start script to verify download works**

Run: `pwsh start.ps1` (Ctrl+C after it starts) or manually run the download snippet.
Expected: `static/vendor/chart.umd.min.js` exists and is ~200KB.

- [ ] **Step 7: Commit**

```bash
git add static/vendor/vendor.json .gitignore start.sh start.ps1 templates/dashboard.html
git commit -m "feat: add vendor dependency infrastructure with Chart.js 4.4.7"
```

---

### Task 2: Configuration — `CHART_BUCKET_MINUTES`

**Files:**
- Modify: `config.py`
- Modify: `app.py` (pass to `/api/data`)
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `config["chart_bucket_minutes"]` (int, default 15) available in app config and `/api/data` response

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, add:

```python
def test_chart_bucket_minutes_default(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.delenv("CHART_BUCKET_MINUTES", raising=False)
    from config import load_config
    cfg = load_config()
    assert cfg["chart_bucket_minutes"] == 15


def test_chart_bucket_minutes_custom(monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("CHART_BUCKET_MINUTES", "30")
    from config import load_config
    cfg = load_config()
    assert cfg["chart_bucket_minutes"] == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v -k chart_bucket`
Expected: KeyError — `chart_bucket_minutes` not in config dict.

- [ ] **Step 3: Implement in `config.py`**

Add to the return dict in `load_config()`:

```python
"chart_bucket_minutes": int(os.environ.get("CHART_BUCKET_MINUTES", "15")),
```

- [ ] **Step 4: Pass through in `app.py` `/api/data` response**

Add to the `jsonify()` call in `api_data()`:

```python
"chart_bucket_minutes": app.config["dashboard"].get("chart_bucket_minutes", 15),
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add config.py app.py tests/test_config.py
git commit -m "feat: add CHART_BUCKET_MINUTES config option"
```

---

### Task 3: Server-side bucket computation

**Files:**
- Modify: `data_processing.py`
- Modify: `tests/test_data_processing.py`

**Interfaces:**
- Consumes: raw API response dict (same shape as `process_race_data` input), `bucket_minutes` int
- Produces: `build_finish_chart_data(api_response, bucket_minutes=15)` → dict `{"labels": [...], "datasets": [...]}` or `None`

- [ ] **Step 1: Write test for no finishers returns None**

In `tests/test_data_processing.py`:

```python
from data_processing import build_finish_chart_data


CHART_API_RESPONSE = {
    "RaceInfo": {
        "Name": "Test Race",
        "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)",
    },
    "Results": [
        {
            "Grouping": {"Distance": "Short (5K)", "Overall": True},
            "Racers": [
                {"Name": "Alice", "Time": "-", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "Bob", "Time": "DNS", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
            ],
        },
    ],
}


def test_build_finish_chart_no_finishers():
    result = build_finish_chart_data(CHART_API_RESPONSE)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_processing.py::test_build_finish_chart_no_finishers -v`
Expected: ImportError — `build_finish_chart_data` not defined.

- [ ] **Step 3: Write test for basic bucketing**

```python
CHART_API_FINISHERS = {
    "RaceInfo": {
        "Name": "Test Race",
        "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)",
    },
    "Results": [
        {
            "Grouping": {"Distance": "Short (5K)", "Overall": True},
            "Racers": [
                {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "B", "Time": "0:25:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
                {"Name": "C", "Time": "0:40:00.0", "StartTime": "14:00:00.0", "Distance": "Short (5K)"},
            ],
        },
        {
            "Grouping": {"Distance": "Long (10K)", "Overall": True},
            "Racers": [
                {"Name": "D", "Time": "0:50:00.0", "StartTime": "14:00:00.0", "Distance": "Long (10K)"},
                {"Name": "E", "Time": "1:05:00.0", "StartTime": "14:00:00.0", "Distance": "Long (10K)"},
            ],
        },
    ],
}


def test_build_finish_chart_basic():
    result = build_finish_chart_data(CHART_API_FINISHERS, bucket_minutes=15)
    assert result is not None
    # Start hour floor is 14:00, finishers at 14:20, 14:25, 14:40, 14:50, 15:05
    # Buckets: 14:00, 14:15, 14:30, 14:45, 15:00
    assert result["labels"] == ["14:00", "14:15", "14:30", "14:45", "15:00"]
    assert len(result["datasets"]) == 2
    # Short: 0 in 14:00, 2 in 14:15, 0 in 14:30, 1 in 14:45 (14:40), 0 in 15:00
    short_ds = next(ds for ds in result["datasets"] if ds["label"] == "Short (5K)")
    assert short_ds["data"] == [0, 2, 0, 1, 0]
    # Long: 0, 0, 0, 1 in 14:45 (14:50), 1 in 15:00 (15:05)
    long_ds = next(ds for ds in result["datasets"] if ds["label"] == "Long (10K)")
    assert long_ds["data"] == [0, 0, 0, 1, 1]
```

- [ ] **Step 4: Write test for missing StartTime skips racer**

```python
def test_build_finish_chart_missing_start_time():
    response = {
        "RaceInfo": {"Name": "Test", "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                    {"Name": "B", "Time": "0:25:00.0", "StartTime": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_finish_chart_data(response, bucket_minutes=15)
    assert result is not None
    assert result["labels"] == ["14:00", "14:15"]
    assert result["datasets"][0]["data"] == [0, 1]
```

- [ ] **Step 5: Write test for category groups are skipped (no double-counting)**

```python
def test_build_finish_chart_skips_category_groups():
    response = {
        "RaceInfo": {"Name": "Test", "StartTime": "Saturday, August 9, 2026 2:00 PM (GMT-5)"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                ],
            },
            {
                "Grouping": {"Distance": "5K", "Category": "Male"},
                "Racers": [
                    {"Name": "A", "Time": "0:20:00.0", "StartTime": "14:00:00.0", "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_finish_chart_data(response, bucket_minutes=15)
    # Only 1 finisher counted (from Overall), not 2
    total = sum(result["datasets"][0]["data"])
    assert total == 1
```

- [ ] **Step 6: Implement `build_finish_chart_data`**

Add to `data_processing.py`:

```python
def _parse_time_seconds(time_str):
    """Parse 'H:MM:SS.d' or 'M:SS.d' to total seconds."""
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def build_finish_chart_data(api_response, bucket_minutes=15):
    if "Error" in api_response:
        return None

    results = api_response.get("Results", [])
    race_info = api_response.get("RaceInfo", {})

    # Parse race start time to get the floor hour for bucket start
    start_time_str = race_info.get("StartTime", "")
    # Extract HH:MM from "Thursday, August 13, 2026 2:08 PM (GMT-5)"
    race_start_seconds = _extract_race_start_seconds(start_time_str)
    floor_hour = (race_start_seconds // 3600) * 3600

    # Collect finishers: (distance, finish_clock_seconds)
    distance_order = []
    finishers_by_distance = {}

    for group in results:
        grouping = group.get("Grouping", {})
        if not grouping.get("Overall"):
            continue
        distance = grouping.get("Distance", "")
        if distance not in finishers_by_distance:
            distance_order.append(distance)
            finishers_by_distance[distance] = []

        for racer in group.get("Racers", []):
            if _classify_racer(racer) != "FINISHED":
                continue
            start_str = racer.get("StartTime")
            if not start_str:
                continue
            start_secs = _parse_time_seconds(start_str)
            elapsed_secs = _parse_time_seconds(racer["Time"])
            finish_secs = start_secs + elapsed_secs
            finishers_by_distance[distance].append(finish_secs)

    # If no finishers at all, return None
    all_finishes = [s for fins in finishers_by_distance.values() for s in fins]
    if not all_finishes:
        return None

    # Build bucket boundaries from floor hour to last finisher
    bucket_secs = bucket_minutes * 60
    last_finish = max(all_finishes)
    labels = []
    bucket_starts = []
    t = floor_hour
    while t <= last_finish:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        labels.append(f"{h}:{m:02d}")
        bucket_starts.append(t)
        t += bucket_secs

    # Count finishers per bucket per distance
    datasets = []
    for distance in distance_order:
        counts = [0] * len(bucket_starts)
        for finish_secs in finishers_by_distance[distance]:
            idx = int((finish_secs - floor_hour) // bucket_secs)
            if 0 <= idx < len(counts):
                counts[idx] = counts[idx] + 1
        datasets.append({"label": distance, "data": counts})

    return {"labels": labels, "datasets": datasets}


def _extract_race_start_seconds(start_time_str):
    """Extract seconds-since-midnight from RaceInfo StartTime string.
    Format: 'Thursday, August 13, 2026 2:08 PM (GMT-5)'
    """
    import re
    match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', start_time_str, re.IGNORECASE)
    if not match:
        return 0
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return hour * 3600 + minute * 60
```

- [ ] **Step 7: Run all tests**

Run: `pytest tests/test_data_processing.py -v`
Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add data_processing.py tests/test_data_processing.py
git commit -m "feat: add build_finish_chart_data for time-bucket aggregation"
```

---

### Task 4: Wire chart data into API response

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `build_finish_chart_data(api_response, bucket_minutes)` from `data_processing.py`
- Produces: `finish_chart` key in `/api/data` JSON response (dict or null)

- [ ] **Step 1: Write test for finish_chart in API response**

Check existing test patterns in `tests/test_app.py`, then add:

```python
def test_api_data_includes_finish_chart(client, mock_api):
    """finish_chart key is present in /api/data response."""
    from app import poll_once, create_app
    app = create_app(config=mock_config(), start_polling=False)
    with app.test_client() as c:
        poll_once(app)
        resp = c.get("/api/data")
        data = resp.get_json()
        assert "finish_chart" in data
```

(Adapt to match existing test_app.py patterns — use existing fixtures if available.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -v -k finish_chart`
Expected: KeyError — `finish_chart` not in response.

- [ ] **Step 3: Implement — import and call in `app.py`**

Update import:

```python
from data_processing import process_race_data, build_pages, build_finish_chart_data
```

In `poll_once()`, after the `pages = build_pages(data)` line, add:

```python
finish_chart = build_finish_chart_data(raw, cfg.get("chart_bucket_minutes", 15))
```

In the `_cache` dict initialization at module top, add:

```python
"finish_chart": None,
```

In the `with _cache_lock:` block inside `poll_once()`, add:

```python
_cache["finish_chart"] = finish_chart
```

In the `api_data()` route's `jsonify()`, add:

```python
"finish_chart": _cache["finish_chart"],
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_app.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: include finish_chart in /api/data response"
```

---

### Task 5: Frontend chart rendering

**Files:**
- Modify: `static/dashboard.js`
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `data.finish_chart` from `/api/data` (dict with `labels` and `datasets`, or null)
- Produces: Stacked bar chart rendered in the summary page's `.summary-chart-area`

- [ ] **Step 1: Update `renderSummary()` in `dashboard.js`**

Replace the chart placeholder block:

```javascript
html += '<div class="summary-chart-area">';
html += '<div class="chart-placeholder">Chart coming soon</div>';
html += "</div>";
```

With:

```javascript
html += '<div class="summary-chart-area">';
if (data.finish_chart && data.finish_chart.labels && data.finish_chart.labels.length > 0) {
  html += '<canvas id="finish-chart"></canvas>';
} else {
  html += '<div class="chart-placeholder">No finishers yet</div>';
}
html += "</div>";
```

- [ ] **Step 2: Add chart rendering after DOM update**

After `container.innerHTML = html;` in the summary branch of `renderCurrentPage()`, add chart creation. Insert a `renderFinishChart` function:

```javascript
var CHART_COLORS = [
  "rgba(54, 162, 235, 0.8)",
  "rgba(255, 159, 64, 0.8)",
  "rgba(75, 192, 192, 0.8)",
  "rgba(153, 102, 255, 0.8)",
  "rgba(255, 99, 132, 0.8)",
];

function renderFinishChart(chartData) {
  var canvas = document.getElementById("finish-chart");
  if (!canvas || !chartData) return;

  var datasets = [];
  for (var i = 0; i < chartData.datasets.length; i++) {
    datasets.push({
      label: chartData.datasets[i].label,
      data: chartData.datasets[i].data,
      backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
    });
  }

  new Chart(canvas, {
    type: "bar",
    data: {
      labels: chartData.labels,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          stacked: true,
          ticks: { color: "#a0a0c0", font: { size: 14 } },
          grid: { color: "rgba(160,160,192,0.2)" },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: { color: "#a0a0c0", font: { size: 14 }, stepSize: 1 },
          grid: { color: "rgba(160,160,192,0.2)" },
        },
      },
      plugins: {
        legend: {
          labels: { color: "#e0e0e0", font: { size: 14 } },
        },
      },
    },
  });
}
```

- [ ] **Step 3: Call `renderFinishChart` after setting innerHTML**

In the summary branch of `renderCurrentPage()`, after `container.innerHTML = html;`:

```javascript
if (data.finish_chart) {
  renderFinishChart(data.finish_chart);
}
```

(Note: need to pass `lastData` to have access to `finish_chart`. The `data` variable in the summary rendering path should be `lastData`.)

- [ ] **Step 4: Update CSS — remove placeholder reference if desired, ensure canvas sizing**

In `static/style.css`, keep `.summary-chart-area` as-is (flex:1, etc.). Add:

```css
.summary-chart-area canvas {
  width: 100% !important;
  height: 100% !important;
}
```

- [ ] **Step 5: Manual test**

Run the app with the test data (`api_dump_443486.json` has some Short Course finishers). Verify:
- Chart renders with bars for Short Course
- When no finishers, "No finishers yet" text shows
- Dark theme colors look correct on the page

- [ ] **Step 6: Commit**

```bash
git add static/dashboard.js static/style.css
git commit -m "feat: render stacked bar finish chart on summary page"
```
