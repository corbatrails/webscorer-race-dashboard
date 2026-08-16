# Toast Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show toast notifications when new finishers are detected between polls, with individual podium toasts for category top-3 and a batch count for the rest.

**Architecture:** Frontend-only detection with minimal backend annotation. Backend adds a `tier` field to pages and passes `show_toasts` config. Frontend tracks finished Bibs across polls, diffs to find new finishers, and renders CSS-animated toasts at bottom-center.

**Tech Stack:** Vanilla JS, CSS transitions, Python/Flask backend

## Global Constraints

- No external dependencies (no toast libraries)
- All JS must be ES5-compatible (the codebase uses `var`, no arrow functions)
- CSS uses existing custom properties from `style.css`
- Config loaded from env vars via `config.py`

---

### Task 1: Backend — Add `tier` field to pages and `show_toasts` config

**Files:**
- Modify: `config.py` (add `show_toasts` option)
- Modify: `data_processing.py:217-228` (`build_pages` — add `tier` field)
- Modify: `app.py:37-52` (pass `show_toasts` in API response)
- Test: `tests/test_config.py`
- Test: `tests/test_data_processing.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: Each page dict in `build_pages()` output gains `"tier": "overall"` or `"tier": "category"` field
- Produces: `/api/data` JSON gains `"show_toasts": true/false`

- [ ] **Step 1: Write failing test for `build_pages` tier field**

In `tests/test_data_processing.py`, add:

```python
def test_build_pages_includes_tier():
    data = process_race_data(MOCK_API_RESPONSE)
    pages = build_pages(data)
    # Summary page has no tier
    assert "tier" not in pages[0]
    # Overall group
    assert pages[1]["tier"] == "overall"
    # Category groups
    assert pages[2]["tier"] == "category"
    assert pages[3]["tier"] == "category"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_processing.py::test_build_pages_includes_tier -v`
Expected: FAIL — `KeyError: 'tier'`

- [ ] **Step 3: Implement tier field in `build_pages`**

In `data_processing.py`, modify `process_race_data` to include tier in each category dict, then propagate in `build_pages`:

Change the category accumulation loop (around line 100) to include tier:

```python
        name = _group_name(grouping, tier)
        distance_buckets[distance][tier].append({
            "name": name,
            "tier": tier,
            "racers": racers,
            "leaders": racers[:3],
        })
```

Then in `build_pages`, propagate it:

```python
def build_pages(dashboard_data, max_rows=18):
    """Build page list. Categories are sent whole; the frontend splits by viewport size."""
    pages = [{"type": "summary", "title": "Summary", "data": dashboard_data}]

    for category in dashboard_data.get("categories", []):
        pages.append({
            "type": "category",
            "title": category["name"],
            "tier": category["tier"],
            "racers": category["racers"],
        })

    return pages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_processing.py::test_build_pages_includes_tier -v`
Expected: PASS

- [ ] **Step 5: Write failing test for `show_toasts` config**

In `tests/test_config.py`, add:

```python
@patch("config.load_dotenv")
def test_load_config_show_toasts_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    cfg = load_config()
    assert cfg["show_toasts"] is True


@patch("config.load_dotenv")
def test_load_config_show_toasts_disabled(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "12345")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
    monkeypatch.setenv("SHOW_TOASTS", "false")
    cfg = load_config()
    assert cfg["show_toasts"] is False
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_load_config_show_toasts_default tests/test_config.py::test_load_config_show_toasts_disabled -v`
Expected: FAIL — `KeyError: 'show_toasts'`

- [ ] **Step 7: Add `show_toasts` to config.py**

In `config.py`, add to the return dict:

```python
        "show_toasts": os.environ.get("SHOW_TOASTS", "true").lower() == "true",
```

- [ ] **Step 8: Run config tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 9: Add `show_toasts` to API response in app.py**

In `app.py`, inside the `api_data()` route's `jsonify()` call, add:

```python
                "show_toasts": app.config["dashboard"].get("show_toasts", True),
```

- [ ] **Step 10: Run all tests to confirm nothing breaks**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add config.py data_processing.py app.py tests/test_config.py tests/test_data_processing.py
git commit -m "feat: add page tier field and show_toasts config (#37)"
```

---

### Task 2: Frontend — Toast container, CSS, and rendering functions

**Files:**
- Modify: `templates/dashboard.html` (add toast container div)
- Modify: `static/style.css` (toast styles)
- Modify: `static/dashboard.js` (toast rendering functions)

**Interfaces:**
- Consumes: Nothing from Task 1 yet (this task builds the rendering layer)
- Produces: `showToasts(toasts)` function that accepts an array of `{text, type}` objects and renders them

- [ ] **Step 1: Add toast container to `dashboard.html`**

Add before the closing `</body>` tag, after the script tags:

```html
    <div id="toast-container"></div>
```

- [ ] **Step 2: Add toast CSS to `style.css`**

Append to `static/style.css`:

```css
#toast-container {
  position: fixed;
  bottom: 5vh;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  gap: 0.5vh;
  z-index: 1000;
  pointer-events: none;
}

.toast {
  background: rgba(0, 0, 0, 0.85);
  color: #fff;
  padding: 1vh 2vw;
  border-radius: 0.5vh;
  font-size: 2.5vh;
  opacity: 0;
  transition: opacity 0.3s ease;
  white-space: nowrap;
}

[data-theme="light"] .toast {
  background: rgba(30, 30, 30, 0.9);
}

.toast.toast-visible {
  opacity: 1;
}

.toast.toast-exit {
  opacity: 0;
}

.toast-place-1 {
  border-left: 0.4vh solid #ffd700;
  padding-left: 1.5vw;
}

.toast-place-2 {
  border-left: 0.4vh solid #c0c0c0;
  padding-left: 1.5vw;
}

.toast-place-3 {
  border-left: 0.4vh solid #cd7f32;
  padding-left: 1.5vw;
}
```

- [ ] **Step 3: Add toast rendering functions to `dashboard.js`**

Add inside the IIFE, before the `fetchData()` call at the bottom:

```javascript
  var TOAST_DURATION = 5000;
  var TOAST_FADE = 300;

  function showToasts(toasts) {
    var container = document.getElementById("toast-container");
    if (!container) return;
    for (var i = 0; i < toasts.length; i++) {
      createToast(container, toasts[i]);
    }
  }

  function createToast(container, toast) {
    var el = document.createElement("div");
    el.className = "toast" + (toast.placeClass ? " " + toast.placeClass : "");
    el.textContent = toast.text;
    container.appendChild(el);

    // Trigger reflow then fade in
    el.offsetHeight;
    el.classList.add("toast-visible");

    setTimeout(function () {
      el.classList.remove("toast-visible");
      el.classList.add("toast-exit");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, TOAST_FADE);
    }, TOAST_DURATION);
  }
```

- [ ] **Step 4: Verify visually — manual test**

Start the app with `DATA_FILE=api_dump_443486_finished.json` and confirm:
- Toast container exists in the DOM (inspect element)
- No visual artifacts on the page

- [ ] **Step 5: Commit**

```bash
git add templates/dashboard.html static/style.css static/dashboard.js
git commit -m "feat: add toast container, styles, and rendering (#37)"
```

---

### Task 3: Frontend — Finisher detection and toast triggering

**Files:**
- Modify: `static/dashboard.js` (detection logic in `fetchData`)

**Interfaces:**
- Consumes: `tier` field on pages from Task 1, `show_toasts` from API, `showToasts()` from Task 2
- Produces: Complete working feature

- [ ] **Step 1: Add finisher tracking state**

Add near the top of the IIFE, after the existing `var` declarations:

```javascript
  var knownFinishedBibs = null;
```

`null` means "first poll, establish baseline."

- [ ] **Step 2: Add detection function**

Add after the `showToasts`/`createToast` functions:

```javascript
  function detectNewFinishers(data) {
    if (!data.show_toasts) return;

    var currentFinished = {};
    var pages = data.pages || [];

    // Collect all currently finished bibs and their best category placement
    for (var i = 0; i < pages.length; i++) {
      var page = pages[i];
      if (page.type !== "category") continue;
      var racers = page.racers || [];
      for (var j = 0; j < racers.length; j++) {
        var r = racers[j];
        if (!isFinished(r)) continue;
        var bib = r.Bib;
        if (!bib) continue;

        if (!currentFinished[bib]) {
          currentFinished[bib] = { name: r.Name, bib: bib, catPlace: null, catName: "" };
        }

        // Track best category placement (lowest place number on a category tier page)
        if (page.tier === "category") {
          var place = parseInt(r.Place) || 0;
          if (place >= 1 && place <= 3) {
            var existing = currentFinished[bib].catPlace;
            if (!existing || place < existing) {
              currentFinished[bib].catPlace = place;
              currentFinished[bib].catName = page.title;
            }
          }
        }
      }
    }

    // First poll — establish baseline silently
    if (knownFinishedBibs === null) {
      knownFinishedBibs = {};
      for (var bib in currentFinished) {
        knownFinishedBibs[bib] = true;
      }
      return;
    }

    // Find new finishers
    var podiumToasts = [];
    var otherCount = 0;

    for (var bib in currentFinished) {
      if (knownFinishedBibs[bib]) continue;
      var f = currentFinished[bib];
      if (f.catPlace) {
        var medal = f.catPlace === 1 ? "\uD83E\uDD47" : f.catPlace === 2 ? "\uD83E\uDD48" : "\uD83E\uDD49";
        var ordinal = f.catPlace === 1 ? "1st" : f.catPlace === 2 ? "2nd" : "3rd";
        podiumToasts.push({
          text: medal + " " + f.name + " \u2014 " + ordinal + " " + f.catName,
          placeClass: "toast-place-" + f.catPlace
        });
      } else {
        otherCount++;
      }
    }

    // Build toast list: podium first, then batch
    var toasts = podiumToasts.slice();
    if (otherCount > 0) {
      var word = otherCount === 1 ? "racer" : "racers";
      toasts.push({ text: otherCount + " " + word + " finished since last update", placeClass: "" });
    }

    if (toasts.length > 0) {
      showToasts(toasts);
    }

    // Update known set
    knownFinishedBibs = {};
    for (var bib in currentFinished) {
      knownFinishedBibs[bib] = true;
    }
  }
```

- [ ] **Step 3: Call `detectNewFinishers` from `fetchData`**

In the `fetchData` success handler, after `buildPageList(data)` and before the `wasEmpty` check, add:

```javascript
        detectNewFinishers(data);
```

- [ ] **Step 4: Verify manually with simulated data**

Start with `DATA_FILE=api_dump_443486_finished.json`. On first load, no toasts appear (baseline). Then edit the JSON file to add a new finisher and wait for the next poll — toasts should appear.

Alternatively, temporarily set `knownFinishedBibs = {}` (empty instead of null) to force all current finishers to show as "new" on first load for visual testing.

- [ ] **Step 5: Commit**

```bash
git add static/dashboard.js
git commit -m "feat: detect new finishers and show toast notifications (#37)"
```

---
