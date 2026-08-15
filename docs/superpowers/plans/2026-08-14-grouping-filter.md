# Grouping-Level Filtering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter API result groups to show only Overall and Category tiers, with configurable toggles per tier.

**Architecture:** Add group classification logic to `data_processing.py` that tags each API result group as `overall`, `category`, or skipped. Two new config flags control which tiers appear as dashboard pages. Groups are ordered by distance (overall first, then categories within each distance).

**Tech Stack:** Python/Flask backend, vanilla JS frontend

## Global Constraints

- Config vars: `SHOW_OVERALL_RESULTS` (default `true`), `SHOW_CATEGORY_RESULTS` (default `true`)
- Replaces `SHOW_CATEGORIES` config in all layers (config, app, frontend, tests)
- Summary page totals still counted from `Overall: true` groups only — no change to counting logic
- Group title: overall tier uses `Distance` (fallback "Overall"); category tier uses `Category` + " " + `Gender`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `config.py` | Modify | Replace `show_categories` with `show_overall_results`, `show_category_results` |
| `data_processing.py` | Modify | Add `_classify_group`, `_group_name`; update `process_race_data` to filter/order groups |
| `app.py` | Modify | Pass grouping config to `process_race_data`; remove `show_categories` from API response |
| `static/dashboard.js` | Modify | Remove `showCategories` from config and `buildPageList` filter |
| `tests/test_config.py` | Modify | Update for new config keys |
| `tests/test_data_processing.py` | Modify | Update multi-distance test; add filtering/ordering tests |
| `tests/test_app.py` | Modify | Replace `show_categories` in mock config |

---

### Task 1: Config and data processing — classification, filtering, ordering

**Files:**
- Modify: `config.py`
- Modify: `data_processing.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_data_processing.py`

**Interfaces:**
- Consumes: raw API response dict, two boolean flags
- Produces: `process_race_data(api_response, show_overall_results=True, show_category_results=True) -> dict` — same return shape, but `categories` list is filtered and ordered by distance

- [ ] **Step 1: Write failing tests for group classification and filtering**

Add to `tests/test_data_processing.py`:

```python
from data_processing import _classify_group, _group_name


def test_classify_group_overall():
    assert _classify_group({"Distance": "Long", "Overall": True}) == "overall"
    assert _classify_group({"Category": "Overall", "Overall": True}) == "overall"


def test_classify_group_category():
    assert _classify_group({"Category": "Masters Men", "Gender": "Male"}) == "category"
    assert _classify_group({"Category": "Male 20-29"}) == "category"


def test_classify_group_skipped():
    assert _classify_group({"Distance": "Long", "Gender": "Male"}) is None
    assert _classify_group({"Gender": "Female"}) is None


def test_group_name_overall():
    assert _group_name({"Distance": "Long Course (88 miles)", "Overall": True}, "overall") == "Long Course (88 miles)"
    assert _group_name({"Category": "Overall", "Overall": True}, "overall") == "Overall"


def test_group_name_category_with_gender():
    g = {"Distance": "Long", "Category": "Adult Long Course (age 18-44)", "Gender": "Male"}
    assert _group_name(g, "category") == "Adult Long Course (age 18-44) Male"


def test_group_name_category_without_gender():
    assert _group_name({"Category": "Male 20-29"}, "category") == "Male 20-29"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_processing.py -k "classify_group or group_name" -v`
Expected: FAIL — `_classify_group` and `_group_name` don't exist yet

- [ ] **Step 3: Implement `_classify_group` and `_group_name` in data_processing.py**

Add before `process_race_data`:

```python
def _classify_group(grouping):
    if grouping.get("Overall"):
        return "overall"
    if grouping.get("Category"):
        return "category"
    return None


def _group_name(grouping, tier):
    if tier == "overall":
        return grouping.get("Distance") or "Overall"
    parts = [grouping.get("Category", "")]
    gender = grouping.get("Gender")
    if gender:
        parts.append(gender)
    return " ".join(parts)
```

- [ ] **Step 4: Run classification tests to verify they pass**

Run: `pytest tests/test_data_processing.py -k "classify_group or group_name" -v`
Expected: PASS

- [ ] **Step 5: Write failing test for multi-distance filtering and ordering**

Update the existing `test_process_race_data_multi_distance` and add a new comprehensive test. Replace `test_process_race_data_multi_distance` with:

```python
def test_process_race_data_multi_distance():
    response = {
        "RaceInfo": {"RaceId": 200, "Name": "Trail Race", "Date": "2026-08-13", "Sport": "Cycling"},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                    {"Place": "", "Bib": "2", "Name": "B", "Time": "DNS"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "3", "Name": "C", "Time": "00:30:00"},
                    {"Place": 2, "Bib": "4", "Name": "D", "Time": "00:35:00"},
                    {"Place": "", "Bib": "5", "Name": "E", "Time": "DNF"},
                ],
            },
        ],
    }
    result = process_race_data(response)
    # Totals unchanged (from Overall groups)
    assert result["total_racers"] == 5
    assert result["total_finished"] == 3
    assert result["total_dns"] == 1
    assert result["total_dnf"] == 1
    # Distance+Gender group skipped; only 2 Overall groups remain
    assert len(result["categories"]) == 2
    assert result["categories"][0]["name"] == "Long"
    assert result["categories"][1]["name"] == "Short"


def test_process_race_data_multi_distance_with_categories():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Big Race", "Date": "2026-08-14", "Sport": "Cycling"},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                    {"Place": 2, "Bib": "2", "Name": "B", "Time": "01:10:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [
                    {"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Overall": True},
                "Racers": [
                    {"Place": 1, "Bib": "3", "Name": "C", "Time": "00:30:00"},
                ],
            },
            {
                "Grouping": {"Distance": "Short", "Category": "Adult", "Gender": "Female"},
                "Racers": [
                    {"Place": 1, "Bib": "4", "Name": "D", "Time": "00:35:00"},
                ],
            },
        ],
    }
    result = process_race_data(response)
    # Ordered: Long Overall, Long categories, Short Overall, Short categories
    assert len(result["categories"]) == 4
    assert result["categories"][0]["name"] == "Long"
    assert result["categories"][1]["name"] == "Masters Male"
    assert result["categories"][2]["name"] == "Short"
    assert result["categories"][3]["name"] == "Adult Female"


def test_process_race_data_filter_overall_off():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Race", "Date": "", "Sport": ""},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
        ],
    }
    result = process_race_data(response, show_overall_results=False)
    assert len(result["categories"]) == 1
    assert result["categories"][0]["name"] == "Masters Male"
    # Totals still counted from Overall groups
    assert result["total_racers"] == 1


def test_process_race_data_filter_category_off():
    response = {
        "RaceInfo": {"RaceId": 300, "Name": "Race", "Date": "", "Sport": ""},
        "Results": [
            {
                "Grouping": {"Distance": "Long", "Overall": True},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
            {
                "Grouping": {"Distance": "Long", "Category": "Masters", "Gender": "Male"},
                "Racers": [{"Place": 1, "Bib": "1", "Name": "A", "Time": "01:00:00"}],
            },
        ],
    }
    result = process_race_data(response, show_category_results=False)
    assert len(result["categories"]) == 1
    assert result["categories"][0]["name"] == "Long"
```

- [ ] **Step 6: Run all data processing tests to see which fail**

Run: `pytest tests/test_data_processing.py -v`
Expected: New tests fail; existing tests should still pass (classification is additive)

- [ ] **Step 7: Update `process_race_data` to classify, filter, and order groups**

Replace the loop and category-building logic in `process_race_data`. The full updated function:

```python
def process_race_data(api_response, show_overall_results=True, show_category_results=True):
    if "Error" in api_response:
        return {
            "race_name": "",
            "race_date": "",
            "race_sport": "",
            "total_racers": 0,
            "total_finished": 0,
            "total_dns": 0,
            "total_dnf": 0,
            "total_dsq": 0,
            "categories": [],
            "error": api_response["Error"],
        }

    info = api_response.get("RaceInfo", {})
    results = api_response.get("Results", [])

    total_racers = 0
    total_finished = 0
    total_dns = 0
    total_dnf = 0
    total_dsq = 0

    # Collect groups by distance, preserving API order
    distance_order = []
    distance_buckets = {}

    for group in results:
        grouping = group.get("Grouping", {})
        racers = group.get("Racers", [])

        if grouping.get("Overall"):
            total_racers += len(racers)
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

        tier = _classify_group(grouping)
        if tier is None:
            continue
        if tier == "overall" and not show_overall_results:
            continue
        if tier == "category" and not show_category_results:
            continue

        distance = grouping.get("Distance", "")
        if distance not in distance_buckets:
            distance_order.append(distance)
            distance_buckets[distance] = {"overall": [], "category": []}

        name = _group_name(grouping, tier)
        distance_buckets[distance][tier].append({
            "name": name,
            "racers": racers,
            "leaders": racers[:3],
        })

    categories = []
    for dist in distance_order:
        bucket = distance_buckets[dist]
        categories.extend(bucket["overall"])
        categories.extend(bucket["category"])

    return {
        "race_name": info.get("Name", ""),
        "race_date": info.get("Date", ""),
        "race_sport": info.get("Sport", ""),
        "total_racers": total_racers,
        "total_finished": total_finished,
        "total_dns": total_dns,
        "total_dnf": total_dnf,
        "total_dsq": total_dsq,
        "categories": categories,
        "error": None,
    }
```

- [ ] **Step 8: Run all data processing tests**

Run: `pytest tests/test_data_processing.py -v`
Expected: All tests PASS

- [ ] **Step 9: Update config.py — replace `show_categories` with new flags**

In `config.py`, replace:
```python
        "show_categories": os.environ.get("SHOW_CATEGORIES", "true").lower() == "true",
```

With:
```python
        "show_overall_results": os.environ.get("SHOW_OVERALL_RESULTS", "true").lower() == "true",
        "show_category_results": os.environ.get("SHOW_CATEGORY_RESULTS", "true").lower() == "true",
```

- [ ] **Step 10: Update config tests**

In `tests/test_config.py`, update `test_load_config_defaults` to also clear the new env vars and verify defaults:

Add to the `monkeypatch.delenv` block:
```python
    monkeypatch.delenv("SHOW_OVERALL_RESULTS", raising=False)
    monkeypatch.delenv("SHOW_CATEGORY_RESULTS", raising=False)
```

Add assertions:
```python
    assert cfg["show_overall_results"] is True
    assert cfg["show_category_results"] is True
```

Remove any `show_categories` assertions if present.

- [ ] **Step 11: Run config tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add config.py data_processing.py tests/test_config.py tests/test_data_processing.py
git commit -m "feat: filter result groups by tier (overall/category)"
```

---

### Task 2: App and frontend — wire config through, remove `showCategories`

**Files:**
- Modify: `app.py`
- Modify: `static/dashboard.js`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `process_race_data(api_response, show_overall_results, show_category_results)` from Task 1
- Consumes: config dict with `show_overall_results`, `show_category_results` keys from Task 1
- Produces: `/api/data` response no longer includes `show_categories`; result pages are pre-filtered server-side

- [ ] **Step 1: Update `app.py` — pass grouping config to `process_race_data`**

In `poll_once`, change:
```python
        data = process_race_data(raw)
```

To:
```python
        data = process_race_data(
            raw,
            show_overall_results=cfg.get("show_overall_results", True),
            show_category_results=cfg.get("show_category_results", True),
        )
```

- [ ] **Step 2: Update `app.py` — remove `show_categories` from API response**

In the `api_data` route, remove the `show_categories` line from the `jsonify` dict:
```python
                "show_categories": app.config["dashboard"].get("show_categories", True),
```

- [ ] **Step 3: Update `dashboard.js` — remove `showCategories` handling**

In `fetchData`, remove `showCategories` from the config object:
```javascript
          showCategories: data.show_categories !== false
```

In `buildPageList`, change the category filter from:
```javascript
      } else if (page.type === "category" && config.showCategories) {
```

To:
```javascript
      } else if (page.type === "category") {
```

- [ ] **Step 4: Update test_app.py — replace `show_categories` in mock config**

In the `app` fixture, replace:
```python
        "show_categories": True,
```

With:
```python
        "show_overall_results": True,
        "show_category_results": True,
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Update `.env` — replace `SHOW_CATEGORIES` with new vars**

Replace:
```
SHOW_CATEGORIES=true
```

With:
```
SHOW_OVERALL_RESULTS=true
SHOW_CATEGORY_RESULTS=true
```

- [ ] **Step 7: Manual verification**

Run the app with `.\start.ps1` and verify:
1. Dashboard shows Overall groups per distance (e.g., "Long Course (88 miles)")
2. Dashboard shows Category groups (e.g., "Adult Long Course (age 18-44) Male")
3. Mid-level Distance+Gender groups (e.g., "Long Course (88 miles) Female") are skipped
4. Groups are ordered by distance: all Long Course pages, then Mid Course, then Short Course
5. Summary page totals are unchanged
6. Progress dots reflect the correct number of filtered pages

- [ ] **Step 8: Commit**

```bash
git add app.py static/dashboard.js tests/test_app.py .env
git commit -m "feat: wire grouping config through app and remove showCategories"
```

---

## Self-Review

**Spec coverage:**
- ✅ Group classification: overall (Overall: true), category (has Category), skip everything else
- ✅ Title format: overall uses Distance, category uses Category + Gender
- ✅ Config: `SHOW_OVERALL_RESULTS`, `SHOW_CATEGORY_RESULTS` replace `SHOW_CATEGORIES`
- ✅ Ordering: by distance, overall first within each distance
- ✅ Totals: unchanged, from Overall groups only
- ✅ Frontend: `showCategories` removed, pages pre-filtered server-side
- ✅ Backward compatibility: simple races (Category-only groups) still work
- ✅ Edge cases: both flags false = no result pages; Gender-only groups skipped

**Placeholder scan:** No TBDs, TODOs, or vague steps found.

**Type consistency:** `_classify_group`, `_group_name`, `process_race_data` signatures consistent across all tasks. Config keys `show_overall_results` and `show_category_results` used consistently.
