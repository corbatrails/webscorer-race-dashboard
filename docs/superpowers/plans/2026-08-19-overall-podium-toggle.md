# Overall Podium Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `PINNED_LEADERS_ON_OVERALL_RESULTS` config toggle (default `false`) that suppresses medal coloring and the pinned-leaders row on Overall-tier result pages, so races without a real Overall podium don't visually imply one.

**Architecture:** Pure rendering-layer change. A new boolean flows from env var → `config.py` → `/api/data` JSON → `dashboard.js` frontend config. The frontend already tags each category page with `tier` ("overall" | "category"); the flag is combined with that tag to decide whether to pin leaders and color places 1-3.

**Tech Stack:** Python (Flask), vanilla JavaScript (no build step, no JS test framework — verify JS changes manually).

## Global Constraints

- Env var name: `PINNED_LEADERS_ON_OVERALL_RESULTS`, default `"false"`, parsed as `.lower() == "true"` (matches existing `SHOW_*` boolean pattern in `config.py`).
- Category-tier pages must be completely unaffected — always keep current pinning + medal-coloring behavior regardless of this flag.
- Place numbers must always be shown in the table; only the `place-1`/`place-2`/`place-3` CSS classes (medal coloring) and the pinned-leaders row are conditional.
- `.env.example` must stay in sync with `.env` variables per repo convention — add the new var there.

---

### Task 1: Add `pinned_leaders_on_overall_results` to config.py

**Files:**
- Modify: `config.py:37-42`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `load_config()` return dict gains key `"pinned_leaders_on_overall_results"` (bool).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
@patch("config.load_dotenv")
def test_load_config_pinned_leaders_on_overall_results_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.delenv("PINNED_LEADERS_ON_OVERALL_RESULTS", raising=False)
    cfg = load_config()
    assert cfg["pinned_leaders_on_overall_results"] is False


@patch("config.load_dotenv")
def test_load_config_pinned_leaders_on_overall_results_enabled(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("PINNED_LEADERS_ON_OVERALL_RESULTS", "true")
    cfg = load_config()
    assert cfg["pinned_leaders_on_overall_results"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -k pinned_leaders_on_overall_results -v`
Expected: FAIL with `KeyError: 'pinned_leaders_on_overall_results'`

- [ ] **Step 3: Implement the config key**

In `config.py`, add the new key next to the other `SHOW_*` toggles (after `show_category_results`):

```python
        "show_category_results": os.environ.get("SHOW_CATEGORY_RESULTS", "true").lower() == "true",
        "pinned_leaders_on_overall_results": os.environ.get("PINNED_LEADERS_ON_OVERALL_RESULTS", "false").lower() == "true",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all tests, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add PINNED_LEADERS_ON_OVERALL_RESULTS config toggle"
```

---

### Task 2: Expose the flag on `/api/data`

**Files:**
- Modify: `app.py:35-53`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `app.config["dashboard"]["pinned_leaders_on_overall_results"]` (bool, from Task 1's config dict).
- Produces: `/api/data` JSON response gains key `"pinned_leaders_on_overall_results"` (bool).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_app.py` (near `test_api_data_returns_json`):

```python
@patch("app.fetch_race_results")
def test_api_data_includes_pinned_leaders_on_overall_results(mock_fetch, app, client):
    mock_fetch.return_value = MOCK_RACE_RESULTS
    with app.app_context():
        from app import poll_once
        poll_once(app)
    response = client.get("/api/data")
    data = json.loads(response.data)
    assert data["pinned_leaders_on_overall_results"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app.py -k pinned_leaders_on_overall_results -v`
Expected: FAIL with `KeyError: 'pinned_leaders_on_overall_results'`

- [ ] **Step 3: Implement**

In `app.py`, inside `api_data()`, add the key to the JSON response (after `show_toasts`):

```python
                "show_toasts": app.config["dashboard"].get("show_toasts", True),
                "pinned_leaders_on_overall_results": app.config["dashboard"].get(
                    "pinned_leaders_on_overall_results", False
                ),
            })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: expose pinned_leaders_on_overall_results on /api/data"
```

---

### Task 3: Suppress pinning and medal coloring on Overall pages in dashboard.js

**Files:**
- Modify: `static/dashboard.js` (config object in `fetchData`, `renderCategory`, `renderRacerRow`)

**Interfaces:**
- Consumes: `data.pinned_leaders_on_overall_results` (bool, from Task 2's `/api/data` response); `category.tier` (`"overall"` | `"category"`, already present on page objects).
- Produces: `renderRacerRow(r, showPodiumStyling)` — new second parameter, `showPodiumStyling: boolean`.

There is no JS test framework in this repo, so this task is verified manually using the local `DATA_FILE` sample dumps already checked into the repo root (`api_dump_412060.json`, `api_dump_443486_finished.json`, `api_dump_443486.json`).

- [ ] **Step 1: Add the flag to the frontend config object**

In `static/dashboard.js`, in `fetchData()`, extend the `config` assignment:

```javascript
        config = {
          summaryDisplayTime: data.summary_display_time,
          scrollSpeed: data.scroll_speed,
          scrollPauseTime: data.scroll_pause_time,
          pinnedLeaders: data.pinned_leaders,
          showSummary: data.show_summary !== false,
          pinnedLeadersOnOverallResults: data.pinned_leaders_on_overall_results === true
        };
```

- [ ] **Step 2: Gate pinning in `renderCategory` on tier + flag**

Replace the pinned-count calculation in `renderCategory`:

```javascript
    var racers = category.racers || [];
    var pinnedCount = 0;
    for (var i = 0; i < Math.min(config.pinnedLeaders, racers.length); i++) {
      if (isFinished(racers[i])) pinnedCount++;
      else break;
    }
    var pinned = racers.slice(0, pinnedCount);
    var scrolling = racers.slice(pinnedCount);
```

with:

```javascript
    var racers = category.racers || [];
    var showPodiumStyling = category.tier !== "overall" || config.pinnedLeadersOnOverallResults;
    var pinnedCount = 0;
    if (showPodiumStyling) {
      for (var i = 0; i < Math.min(config.pinnedLeaders, racers.length); i++) {
        if (isFinished(racers[i])) pinnedCount++;
        else break;
      }
    }
    var pinned = racers.slice(0, pinnedCount);
    var scrolling = racers.slice(pinnedCount);
```

- [ ] **Step 3: Pass `showPodiumStyling` through to `renderRacerRow` calls**

In the same `renderCategory` function, update both loops that call `renderRacerRow`:

```javascript
      for (var i = 0; i < pinned.length; i++) {
        html += renderRacerRow(pinned[i], showPodiumStyling);
      }
```

and:

```javascript
      for (var j = 0; j < scrolling.length; j++) {
        html += renderRacerRow(scrolling[j], showPodiumStyling);
      }
```

- [ ] **Step 4: Gate medal coloring in `renderRacerRow`**

Replace:

```javascript
  function renderRacerRow(r) {
    var placeClass = "";
    var place = parseInt(r.Place) || 0;
    if (place === 1) placeClass = " place-1";
    else if (place === 2) placeClass = " place-2";
    else if (place === 3) placeClass = " place-3";
```

with:

```javascript
  function renderRacerRow(r, showPodiumStyling) {
    var placeClass = "";
    if (showPodiumStyling) {
      var place = parseInt(r.Place) || 0;
      if (place === 1) placeClass = " place-1";
      else if (place === 2) placeClass = " place-2";
      else if (place === 3) placeClass = " place-3";
    }
```

- [ ] **Step 5: Manual verification — default (flag off) suppresses styling on Overall pages**

Run: `$env:DATA_FILE = "api_dump_443486_finished.json"; python app.py` (stop any other instance first), then open `http://localhost:5000` (or configured port) in a browser and cycle to an Overall-tier page.
Expected: no pinned-leader row above the scroll area on the Overall page; place numbers show in the default text color (no gold/silver/bronze) for places 1-3; a Category-tier page still shows the pinned row and medal coloring as before.

- [ ] **Step 6: Manual verification — flag on restores current behavior**

Run: `$env:PINNED_LEADERS_ON_OVERALL_RESULTS = "true"; python app.py`, reload the browser, cycle to an Overall-tier page.
Expected: Overall page now shows the pinned-leaders row and gold/silver/bronze coloring for places 1-3, same as a Category-tier page.
Afterward, run `Remove-Item Env:\PINNED_LEADERS_ON_OVERALL_RESULTS` to clear the override.

- [ ] **Step 7: Commit**

```bash
git add static/dashboard.js
git commit -m "feat: suppress podium styling on overall pages by default"
```

---

### Task 4: Document the new env var in .env.example

**Files:**
- Modify: `.env.example:18-20`

- [ ] **Step 1: Add the new var next to the other display toggles**

```dotenv
# Which pages to display (true/false)
SHOW_SUMMARY=true
SHOW_OVERALL_RESULTS=true
SHOW_CATEGORY_RESULTS=true
# Optional: show pinned leaders row + medal coloring on Overall-tier pages (default false)
PINNED_LEADERS_ON_OVERALL_RESULTS=false
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: document PINNED_LEADERS_ON_OVERALL_RESULTS in .env.example"
```

---

## Final Verification

- [ ] Run the full test suite: `python -m pytest -v`
- [ ] Expected: all tests pass, including the new tests from Tasks 1 and 2
- [ ] Confirm `.env.example` and any local `.env` stay in sync (per repo project rules)
