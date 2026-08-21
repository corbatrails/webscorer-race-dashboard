# Demographics Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rotating "Demographics" dashboard page showing age distribution, gender split, distance popularity, and team participation, computed from all registrants.

**Architecture:** A new `build_demographics_data()` function in `data_processing.py` computes the breakdown from the raw API response (Overall groupings only, all registrants). `build_pages()` is extended to insert a `"demographics"` page into the existing server-side pages list (same mechanism as summary/category pages), gated client-side by a new `SHOW_DEMOGRAPHICS` config flag (default `false`), exactly like the existing `show_summary` gating. The frontend renders it as a static (non-scrolling) 2x2 grid of 3 Chart.js charts (age histogram, gender doughnut, distance bar) plus a team-stats panel, reusing the finish-chart's render/destroy lifecycle and CSS theming conventions.

**Tech Stack:** Python (Flask), vanilla JS, Chart.js (already vendored), pytest.

## Global Constraints

- Demographics computed from **Overall groupings only** — never Category groupings (avoids double-counting racers).
- Includes **all registrants** regardless of finish status (DNS/DNF/DSQ/finished all count).
- Age buckets are fixed decades: `<20`, `20-29`, `30-39`, `40-49`, `50-59`, `60-69`, `70+`.
- Missing `Age` → excluded from age stats only, still counted in `total_registrants`.
- Missing/blank `Gender` → bucketed as `"Unknown"`.
- Missing/blank `TeamName` → counted as solo, never in `top_teams`.
- `top_teams` = top 5 teams by headcount, ties broken alphabetically by name.
- No racers at all → `build_demographics_data` returns `None`, page omitted from rotation.
- New env var `SHOW_DEMOGRAPHICS`, default `false`.

---

## Task 1: `build_demographics_data()` in `data_processing.py`

**Files:**
- Modify: `data_processing.py` (add new function + helpers near `build_finish_chart_data`)
- Test: `tests/test_data_processing.py`

**Interfaces:**
- Consumes: nothing new (same raw API response shape used by `build_finish_chart_data`)
- Produces: `build_demographics_data(api_response)` → `dict | None`, importable as `from data_processing import build_demographics_data`. Return shape:
  ```python
  {
      "total_registrants": int,
      "age": {"average": float | None, "median": float | None, "min": int | None, "max": int | None,
              "labels": list[str], "counts": list[int]},
      "gender": {"labels": list[str], "counts": list[int]},
      "distance": {"labels": list[str], "counts": list[int]},
      "teams": {"solo_count": int, "team_count": int, "top_teams": [{"name": str, "count": int}]},
  }
  ```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_data_processing.py` (near the finish-chart tests):

```python
from data_processing import build_demographics_data


DEMOGRAPHICS_API_RESPONSE = {
    "RaceInfo": {"Name": "Test Race"},
    "Results": [
        {
            "Grouping": {"Distance": "Short (5K)", "Overall": True},
            "Racers": [
                {"Bib": "1", "Name": "A", "Age": 25, "Gender": "Male", "TeamName": "Team X", "Distance": "Short (5K)"},
                {"Bib": "2", "Name": "B", "Age": 34, "Gender": "Female", "TeamName": "Team X", "Distance": "Short (5K)"},
                {"Bib": "3", "Name": "C", "Age": 45, "Gender": "Male", "TeamName": None, "Distance": "Short (5K)"},
            ],
        },
        {
            "Grouping": {"Distance": "Long (10K)", "Overall": True},
            "Racers": [
                {"Bib": "4", "Name": "D", "Age": 62, "Gender": "Female", "TeamName": None, "Distance": "Long (10K)"},
                {"Bib": "5", "Name": "E", "Age": 19, "Gender": "Male", "TeamName": "Team Y", "Distance": "Long (10K)"},
            ],
        },
    ],
}


def test_build_demographics_normal_data():
    result = build_demographics_data(DEMOGRAPHICS_API_RESPONSE)
    assert result["total_registrants"] == 5

    age = result["age"]
    assert age["average"] == 37.0
    assert age["median"] == 34
    assert age["min"] == 19
    assert age["max"] == 62
    assert age["labels"] == ["<20", "20-29", "30-39", "40-49", "50-59", "60-69", "70+"]
    assert age["counts"] == [1, 1, 1, 1, 0, 1, 0]

    gender = result["gender"]
    assert gender["labels"] == ["Male", "Female"]
    assert gender["counts"] == [3, 2]

    distance = result["distance"]
    assert distance["labels"] == ["Short (5K)", "Long (10K)"]
    assert distance["counts"] == [3, 2]

    teams = result["teams"]
    assert teams["solo_count"] == 2
    assert teams["team_count"] == 3
    assert teams["top_teams"] == [
        {"name": "Team X", "count": 2},
        {"name": "Team Y", "count": 1},
    ]


def test_build_demographics_missing_age_excluded_from_age_stats():
    response = {
        "RaceInfo": {"Name": "Test"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Bib": "1", "Name": "A", "Age": 30, "Gender": "Male", "TeamName": None, "Distance": "5K"},
                    {"Bib": "2", "Name": "B", "Gender": "Male", "TeamName": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_demographics_data(response)
    assert result["total_registrants"] == 2
    assert result["age"]["average"] == 30.0
    assert sum(result["age"]["counts"]) == 1


def test_build_demographics_missing_gender_bucketed_as_unknown():
    response = {
        "RaceInfo": {"Name": "Test"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Bib": "1", "Name": "A", "Age": 30, "TeamName": None, "Distance": "5K"},
                    {"Bib": "2", "Name": "B", "Age": 31, "Gender": "", "TeamName": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_demographics_data(response)
    assert result["gender"]["labels"] == ["Unknown"]
    assert result["gender"]["counts"] == [2]


def test_build_demographics_no_teams():
    response = {
        "RaceInfo": {"Name": "Test"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Bib": "1", "Name": "A", "Age": 30, "Gender": "Male", "TeamName": None, "Distance": "5K"},
                    {"Bib": "2", "Name": "B", "Age": 31, "Gender": "Female", "TeamName": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_demographics_data(response)
    assert result["teams"]["solo_count"] == 2
    assert result["teams"]["team_count"] == 0
    assert result["teams"]["top_teams"] == []


def test_build_demographics_skips_category_groups():
    response = {
        "RaceInfo": {"Name": "Test"},
        "Results": [
            {
                "Grouping": {"Distance": "5K", "Overall": True},
                "Racers": [
                    {"Bib": "1", "Name": "A", "Age": 30, "Gender": "Male", "TeamName": None, "Distance": "5K"},
                ],
            },
            {
                "Grouping": {"Distance": "5K", "Category": "Male"},
                "Racers": [
                    {"Bib": "1", "Name": "A", "Age": 30, "Gender": "Male", "TeamName": None, "Distance": "5K"},
                ],
            },
        ],
    }
    result = build_demographics_data(response)
    assert result["total_registrants"] == 1


def test_build_demographics_no_racers_returns_none():
    assert build_demographics_data({"RaceInfo": {"Name": "Test"}, "Results": []}) is None


def test_build_demographics_error_response_returns_none():
    assert build_demographics_data({"Error": "PRO Results subscription required"}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_data_processing.py -k demographics -v`
Expected: FAIL with `ImportError: cannot import name 'build_demographics_data'`

- [ ] **Step 3: Implement `build_demographics_data()` and helpers**

Add to `data_processing.py` after `build_finish_chart_data`:

```python
_AGE_BUCKETS = [
    (0, 19, "<20"),
    (20, 29, "20-29"),
    (30, 39, "30-39"),
    (40, 49, "40-49"),
    (50, 59, "50-59"),
    (60, 69, "60-69"),
    (70, 999, "70+"),
]


def _as_age_int(age):
    if isinstance(age, bool):
        return None
    if isinstance(age, int):
        return age
    if isinstance(age, float):
        return int(age)
    if isinstance(age, str) and age.strip().isdigit():
        return int(age.strip())
    return None


def _build_age_stats(ages):
    labels = [label for _, _, label in _AGE_BUCKETS]
    if not ages:
        return {
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "labels": labels,
            "counts": [0] * len(labels),
        }

    counts = [0] * len(_AGE_BUCKETS)
    for age in ages:
        for i, (low, high, _) in enumerate(_AGE_BUCKETS):
            if low <= age <= high:
                counts[i] += 1
                break

    sorted_ages = sorted(ages)
    n = len(sorted_ages)
    if n % 2 == 1:
        median = sorted_ages[n // 2]
    else:
        median = (sorted_ages[n // 2 - 1] + sorted_ages[n // 2]) / 2

    return {
        "average": round(sum(ages) / len(ages), 1),
        "median": median,
        "min": min(ages),
        "max": max(ages),
        "labels": labels,
        "counts": counts,
    }


def _build_gender_stats(gender_counts):
    ordered = sorted(gender_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "labels": [label for label, _ in ordered],
        "counts": [count for _, count in ordered],
    }


def _build_team_stats(solo_count, team_counts):
    ordered = sorted(team_counts.items(), key=lambda item: (-item[1], item[0]))
    top_teams = [{"name": name, "count": count} for name, count in ordered[:5]]
    return {
        "solo_count": solo_count,
        "team_count": sum(team_counts.values()),
        "top_teams": top_teams,
    }


def build_demographics_data(api_response):
    if "Error" in api_response:
        return None

    results = api_response.get("Results", [])

    total_registrants = 0
    ages = []
    gender_counts = {}
    distance_order = []
    distance_counts = {}
    solo_count = 0
    team_counts = {}

    for group in results:
        grouping = group.get("Grouping", {})
        if not grouping.get("Overall"):
            continue

        distance = grouping.get("Distance") or "Overall"
        if distance not in distance_counts:
            distance_order.append(distance)
            distance_counts[distance] = 0

        for racer in group.get("Racers", []):
            total_registrants += 1
            distance_counts[distance] += 1

            age = _as_age_int(racer.get("Age"))
            if age is not None:
                ages.append(age)

            gender = (racer.get("Gender") or "").strip() or "Unknown"
            gender_counts[gender] = gender_counts.get(gender, 0) + 1

            team = (racer.get("TeamName") or "").strip()
            if team:
                team_counts[team] = team_counts.get(team, 0) + 1
            else:
                solo_count += 1

    if total_registrants == 0:
        return None

    return {
        "total_registrants": total_registrants,
        "age": _build_age_stats(ages),
        "gender": _build_gender_stats(gender_counts),
        "distance": {
            "labels": distance_order,
            "counts": [distance_counts[d] for d in distance_order],
        },
        "teams": _build_team_stats(solo_count, team_counts),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_processing.py -k demographics -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add data_processing.py tests/test_data_processing.py
git commit -m "feat: add build_demographics_data for race demographics"
```

---

## Task 2: Wire demographics into `build_pages()`

**Files:**
- Modify: `data_processing.py:` `build_pages()` function
- Test: `tests/test_data_processing.py`

**Interfaces:**
- Consumes: `build_demographics_data()` return shape from Task 1.
- Produces: `build_pages(dashboard_data, demographics=None, max_rows=18)` — when `demographics` is truthy, the returned list contains a page `{"type": "demographics", "title": "Demographics", "data": demographics}` immediately after the summary page (index 1) and before any category pages.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_data_processing.py`:

```python
def test_build_pages_includes_demographics_page_when_provided():
    dashboard_data = process_race_data(MOCK_API_RESPONSE)
    demographics = {"total_registrants": 5}
    pages = build_pages(dashboard_data, demographics=demographics)
    assert pages[0]["type"] == "summary"
    assert pages[1]["type"] == "demographics"
    assert pages[1]["data"] == demographics
    assert pages[1]["title"] == "Demographics"


def test_build_pages_omits_demographics_page_when_none():
    dashboard_data = process_race_data(MOCK_API_RESPONSE)
    pages = build_pages(dashboard_data, demographics=None)
    assert all(p["type"] != "demographics" for p in pages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_data_processing.py -k build_pages_includes_demographics -v`
Expected: FAIL — `pages[1]["type"]` is a category type, not `"demographics"` (no `TypeError` since `demographics` kwarg doesn't exist yet, so this will actually fail with `TypeError: build_pages() got an unexpected keyword argument 'demographics'`)

- [ ] **Step 3: Update `build_pages()`**

In `data_processing.py`, replace:

```python
def build_pages(dashboard_data, max_rows=18):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    for category in dashboard_data.get("categories", []):
```

with:

```python
def build_pages(dashboard_data, demographics=None, max_rows=18):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    if demographics:
        pages.append({"type": "demographics", "title": "Demographics", "data": demographics})

    for category in dashboard_data.get("categories", []):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_data_processing.py -v`
Expected: PASS (all tests, including full existing suite — confirms no regression)

- [ ] **Step 5: Commit**

```bash
git add data_processing.py tests/test_data_processing.py
git commit -m "feat: insert demographics page into build_pages output"
```

---

## Task 3: `SHOW_DEMOGRAPHICS` config flag

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `load_config()["show_demographics"]` → `bool`, default `False`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
@patch("config.load_dotenv")
def test_load_config_show_demographics_default_false(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("SHOW_DEMOGRAPHICS", raising=False)
    cfg = load_config()
    assert cfg["show_demographics"] is False


@patch("config.load_dotenv")
def test_load_config_show_demographics_true(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("SHOW_DEMOGRAPHICS", "true")
    cfg = load_config()
    assert cfg["show_demographics"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -k show_demographics -v`
Expected: FAIL with `KeyError: 'show_demographics'`

- [ ] **Step 3: Add the config value**

In `config.py`, add this line inside the returned dict, next to `show_category_results`:

```python
        "show_category_results": os.environ.get("SHOW_CATEGORY_RESULTS", "true").lower() == "true",
        "show_demographics": os.environ.get("SHOW_DEMOGRAPHICS", "false").lower() == "true",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add SHOW_DEMOGRAPHICS config flag"
```

---

## Task 4: Wire demographics computation and flag into `app.py`

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `build_demographics_data(raw)` (Task 1), `build_pages(data, demographics)` (Task 2), `cfg["show_demographics"]` (Task 3).
- Produces: `/api/data` response includes `"show_demographics": bool`. `pages` list includes the demographics page (when applicable) via `build_pages`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py`:

```python
@patch("app.fetch_race_results")
def test_api_data_includes_show_demographics_default_false(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["show_demographics"] is False


def test_api_data_show_demographics_true_when_configured():
    application = create_app({"show_demographics": True}, start_polling=False)
    application.config["TESTING"] = True
    client = application.test_client()
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["show_demographics"] is True


@patch("app.fetch_race_results")
def test_poll_once_includes_demographics_page(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    types = [p["type"] for p in data["pages"]]
    assert "demographics" in types
```

Also update `test_format_config_lines_includes_all_config_options`: add `"show_demographics": False,` to the `config` dict (next to `"show_summary": True,`), and add `"Show demographics:"` to the `expected_labels` list (next to `"Show summary:"`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL — `show_demographics` missing from `/api/data` response (`KeyError`/`assert False is None`-style failures), and `"demographics"` not in page types.

- [ ] **Step 3: Wire it up in `app.py`**

Update the import line:

```python
from data_processing import process_race_data, build_pages, build_finish_chart_data
```
to:
```python
from data_processing import process_race_data, build_pages, build_finish_chart_data, build_demographics_data
```

In `poll_once`, replace:

```python
        data = process_race_data(
            raw,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
        pages = build_pages(data)
        finish_chart = build_finish_chart_data(raw, cfg.get("chart_bucket_minutes", 15))
```

with:

```python
        data = process_race_data(
            raw,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
        demographics = build_demographics_data(raw)
        pages = build_pages(data, demographics)
        finish_chart = build_finish_chart_data(raw, cfg.get("chart_bucket_minutes", 15))
```

In `api_data()`, add `show_demographics` next to `show_summary`:

```python
                "show_summary": app.config["dashboard"].get("show_summary", True),
```
becomes:
```python
                "show_summary": app.config["dashboard"].get("show_summary", True),
                "show_demographics": app.config["dashboard"].get("show_demographics", False),
```

In `_format_config_lines`, add a line next to `Show summary`:

```python
        f"  Show summary:                   {config['show_summary']}",
```
becomes:
```python
        f"  Show summary:                   {config['show_summary']}",
        f"  Show demographics:              {config.get('show_demographics', False)}",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS (no regressions across the whole suite)

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: wire demographics computation into app and API response"
```

---

## Task 5: Frontend rendering — page rotation and charts

**Files:**
- Modify: `static/dashboard.js`

**Interfaces:**
- Consumes: `data.pages` entries with `type: "demographics"` and `data.show_demographics` boolean from `/api/data` (Task 4). Page `data` field shape matches Task 1's `build_demographics_data()` return value.
- Produces: a new page in the on-screen rotation between the summary page and category pages.

- [ ] **Step 1: Track config flag and page variable**

In `static/dashboard.js`, near the top module vars:

```js
  var currentIndex = 0;
  var categories = [];
  var summaryPage = null;
  var config = {};
```

add `demographicsPage` and chart-instance vars:

```js
  var currentIndex = 0;
  var categories = [];
  var summaryPage = null;
  var demographicsPage = null;
  var config = {};
```

and near `var finishChart = null;` add:

```js
  var finishChart = null;
  var ageChart = null;
  var genderChart = null;
  var distanceChart = null;
```

In `fetchData()`, add `showDemographics` to the `config` object next to `showSummary`:

```js
        config = {
          summaryDisplayTime: data.summary_display_time,
          scrollSpeed: data.scroll_speed,
          scrollPauseTime: data.scroll_pause_time,
          pinnedLeaders: data.pinned_leaders,
          showSummary: data.show_summary !== false,
```
becomes:
```js
        config = {
          summaryDisplayTime: data.summary_display_time,
          scrollSpeed: data.scroll_speed,
          scrollPauseTime: data.scroll_pause_time,
          pinnedLeaders: data.pinned_leaders,
          showSummary: data.show_summary !== false,
          showDemographics: data.show_demographics === true,
```

- [ ] **Step 2: Update `buildPageList` to recognize the demographics page**

Replace:

```js
  function buildPageList(data) {
    if (data.waiting && data.pages.length === 0) {
      summaryPage = null;
      categories = [];
      return;
    }

    summaryPage = null;
    categories = [];
    for (var i = 0; i < data.pages.length; i++) {
      var page = data.pages[i];
      if (page.type === "summary" && config.showSummary) {
        summaryPage = page;
      } else if (page.type === "category" && pageHasResults(page)) {
        categories.push(page);
      }
    }
  }
```

with:

```js
  function buildPageList(data) {
    if (data.waiting && data.pages.length === 0) {
      summaryPage = null;
      demographicsPage = null;
      categories = [];
      return;
    }

    summaryPage = null;
    demographicsPage = null;
    categories = [];
    for (var i = 0; i < data.pages.length; i++) {
      var page = data.pages[i];
      if (page.type === "summary" && config.showSummary) {
        summaryPage = page;
      } else if (page.type === "demographics" && config.showDemographics) {
        demographicsPage = page;
      } else if (page.type === "category" && pageHasResults(page)) {
        categories.push(page);
      }
    }
  }
```

- [ ] **Step 3: Update `getTotalPages` and `renderCurrentPage` for the new page slot**

Replace:

```js
  function getTotalPages() {
    return (summaryPage ? 1 : 0) + categories.length;
  }
```

with:

```js
  function getTotalPages() {
    return (summaryPage ? 1 : 0) + (demographicsPage ? 1 : 0) + categories.length;
  }
```

Replace the body of `renderCurrentPage`:

```js
  function renderCurrentPage() {
    stopAnimations();
    var container = document.getElementById("dashboard");
    hasRenderedPage = true;

    if (!summaryPage && categories.length === 0) {
      container.innerHTML = renderWaiting(lastData);
      return;
    }

    var totalPages = getTotalPages();
    if (currentIndex >= totalPages) currentIndex = 0;

    var html;
    if (summaryPage && currentIndex === 0) {
      html = renderSummary(summaryPage, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
      if (lastData.finish_chart) {
        renderFinishChart(lastData.finish_chart);
      }
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
    } else {
      var catIndex = summaryPage ? currentIndex - 1 : currentIndex;
      var category = categories[catIndex];
      html = renderCategory(category, catIndex, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
```

with:

```js
  function renderCurrentPage() {
    stopAnimations();
    var container = document.getElementById("dashboard");
    hasRenderedPage = true;

    if (!summaryPage && !demographicsPage && categories.length === 0) {
      container.innerHTML = renderWaiting(lastData);
      return;
    }

    var totalPages = getTotalPages();
    if (currentIndex >= totalPages) currentIndex = 0;

    var summaryOffset = summaryPage ? 1 : 0;
    var demographicsIndex = summaryOffset;

    var html;
    if (summaryPage && currentIndex === 0) {
      html = renderSummary(summaryPage, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
      if (lastData.finish_chart) {
        renderFinishChart(lastData.finish_chart);
      }
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
    } else if (demographicsPage && currentIndex === demographicsIndex) {
      html = renderDemographics(demographicsPage);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
      renderDemographicsCharts(demographicsPage.data);
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
    } else {
      var catIndex = currentIndex - summaryOffset - (demographicsPage ? 1 : 0);
      var category = categories[catIndex];
      html = renderCategory(category, catIndex, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
```

(The remainder of the function — the `startScroll();` call and closing braces — stays unchanged.)

- [ ] **Step 4: Add `renderDemographics()` and `renderDemographicsCharts()`**

Add these new functions near `renderFinishChart` (after `renderProgressBars`, before `renderFinishChart`):

```js
  function renderDemographics(page) {
    var d = page.data;
    var age = d.age;
    var html = '<div class="page active demographics-page">';

    html += renderEventHeader(lastData);

    html += '<div class="summary-stats-row">';
    html += '<div class="stat-card stat-card-primary"><div class="stat-value">' + d.total_registrants + '</div><div class="stat-label">Total Registrants</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + (age.average != null ? age.average : "\u2014") + '</div><div class="stat-label">Avg Age</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + (age.median != null ? age.median : "\u2014") + '</div><div class="stat-label">Median Age</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + (age.min != null ? age.min + "\u2013" + age.max : "\u2014") + '</div><div class="stat-label">Age Range</div></div>';
    html += "</div>";

    html += '<div class="demographics-grid">';
    html += '<div class="demographics-panel"><canvas id="demographics-age-chart"></canvas></div>';
    html += '<div class="demographics-panel"><canvas id="demographics-gender-chart"></canvas></div>';
    html += '<div class="demographics-panel"><canvas id="demographics-distance-chart"></canvas></div>';
    html += '<div class="demographics-panel demographics-teams-panel">';
    html += '<div class="demographics-teams-summary">' + d.teams.solo_count + ' solo &middot; ' + d.teams.team_count + ' on teams</div>';
    if (d.teams.top_teams.length > 0) {
      html += '<ol class="demographics-teams-list">';
      for (var i = 0; i < d.teams.top_teams.length; i++) {
        var t = d.teams.top_teams[i];
        html += '<li><span class="team-name">' + escapeHtml(t.name) + '</span><span class="team-count">' + t.count + '</span></li>';
      }
      html += '</ol>';
    } else {
      html += '<div class="chart-placeholder">No teams registered</div>';
    }
    html += '</div>';
    html += '</div>';

    html += '</div>';
    return html;
  }

  function renderDemographicsCharts(demographics) {
    if (!demographics) return;

    if (ageChart) { ageChart.destroy(); ageChart = null; }
    if (genderChart) { genderChart.destroy(); genderChart = null; }
    if (distanceChart) { distanceChart.destroy(); distanceChart = null; }

    var style = getComputedStyle(document.body);
    var textMuted = style.getPropertyValue('--text-muted').trim();

    var ageCanvas = document.getElementById("demographics-age-chart");
    if (ageCanvas) {
      ageChart = new Chart(ageCanvas, {
        type: "bar",
        data: {
          labels: demographics.age.labels,
          datasets: [{ data: demographics.age.counts, backgroundColor: generateChartColors(1)[0] }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { display: false }, title: { display: true, text: "Age", color: textMuted } },
          scales: {
            x: { ticks: { color: textMuted }, grid: { color: textMuted + "33" } },
            y: { beginAtZero: true, ticks: { color: textMuted, stepSize: 1 }, grid: { color: textMuted + "33" } },
          },
        },
      });
    }

    var genderCanvas = document.getElementById("demographics-gender-chart");
    if (genderCanvas) {
      var genderColors = generateChartColors(demographics.gender.labels.length);
      genderChart = new Chart(genderCanvas, {
        type: "doughnut",
        data: {
          labels: demographics.gender.labels,
          datasets: [{ data: demographics.gender.counts, backgroundColor: genderColors }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: { position: "bottom", labels: { color: textMuted } },
            title: { display: true, text: "Gender", color: textMuted },
          },
        },
      });
    }

    var distanceCanvas = document.getElementById("demographics-distance-chart");
    if (distanceCanvas) {
      distanceChart = new Chart(distanceCanvas, {
        type: "bar",
        data: {
          labels: demographics.distance.labels,
          datasets: [{ data: demographics.distance.counts, backgroundColor: generateChartColors(demographics.distance.labels.length) }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { display: false }, title: { display: true, text: "Distance", color: textMuted } },
          scales: {
            x: { beginAtZero: true, ticks: { color: textMuted, stepSize: 1 }, grid: { color: textMuted + "33" } },
            y: { ticks: { color: textMuted }, grid: { color: textMuted + "33" } },
          },
        },
      });
    }
  }
```

- [ ] **Step 5: Manual verification**

Run the app locally against a data file with demographic fields (e.g. `api_dump_443486_finished.json`), with `.env` containing `SHOW_DEMOGRAPHICS=true`:

```powershell
$env:DATA_FILE = "api_dump_443486_finished.json"
$env:SHOW_DEMOGRAPHICS = "true"
python app.py
```

Open `http://localhost:5000` and confirm:
- The demographics page appears in rotation after the summary page.
- Age histogram, gender doughnut, and distance bar chart render with correct-looking data.
- Team panel shows solo/team counts and a top-5 team list (or "No teams registered" placeholder if the fixture has no teams).
- Charts don't visually break when the page re-renders on the next poll cycle (no duplicate/leaked canvases).

- [ ] **Step 6: Commit**

```bash
git add static/dashboard.js
git commit -m "feat: render demographics page with age/gender/distance/team charts"
```

---

## Task 6: CSS for the demographics page

**Files:**
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `.demographics-page`, `.demographics-grid`, `.demographics-panel`, `.demographics-teams-panel`, `.demographics-teams-summary`, `.demographics-teams-list` class names used in `renderDemographics()` (Task 5).
- Produces: visual styling only, no new interfaces for other tasks.

- [ ] **Step 1: Add styles**

Add after the existing `.summary-chart-area canvas` rule block in `static/style.css` (see `.summary-chart-area canvas { ... }` around line 154):

```css
.demographics-page {
  display: flex;
  flex-direction: column;
}

.demographics-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 2vh;
  min-height: 0;
}

.demographics-panel {
  background: var(--bg-card);
  border-radius: 1vh;
  padding: 1.5vh 1.5vw;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.demographics-panel canvas {
  width: 100% !important;
  height: 100% !important;
}

.demographics-teams-panel {
  justify-content: flex-start;
}

.demographics-teams-summary {
  font-size: 2.2vh;
  color: var(--text-muted);
  margin-bottom: 1vh;
}

.demographics-teams-list {
  list-style: none;
  font-size: 2.2vh;
  overflow: hidden;
}

.demographics-teams-list li {
  display: flex;
  justify-content: space-between;
  padding: 0.5vh 0;
  border-bottom: 1px solid var(--border-color);
}

.demographics-teams-list .team-count {
  color: var(--accent-primary);
  font-weight: bold;
}
```

- [ ] **Step 2: Manual verification**

Reload the dashboard from Task 5's manual test in both `COLOR_SCHEME=dark` and `COLOR_SCHEME=light` and confirm the grid, panels, and team list are legible and consistent with the rest of the dashboard's styling.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "style: add demographics page grid and panel styles"
```

---

## Task 7: Documentation

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- None — documentation only.

- [ ] **Step 1: Add `SHOW_DEMOGRAPHICS` to the config table in `README.md`**

In the `## Configuration` table (the one with rows for `WEBSCORER_API_ID`, `REFRESH_INTERVAL`, etc.), add a row:

```markdown
| `SHOW_DEMOGRAPHICS` | No | false | Show the demographics page (age/gender/distance/team breakdown) |
```

- [ ] **Step 2: Add `SHOW_DEMOGRAPHICS` to `.env.example`**

Add next to the existing `SHOW_SUMMARY` / `SHOW_OVERALL_RESULTS` / `SHOW_CATEGORY_RESULTS` block:

```
# Optional: show demographics page (age/gender/distance/team breakdown, default false)
SHOW_DEMOGRAPHICS=false
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: document SHOW_DEMOGRAPHICS config option"
```
