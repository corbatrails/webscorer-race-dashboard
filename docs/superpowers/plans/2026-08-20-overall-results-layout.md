# Overall Results Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable detailed Overall results layout that shows category placement and category context while reordering the shared standard result columns to `Place | Bib | Name | Time | Team`.

**Architecture:** Add an `OVERALL_RESULTS_LAYOUT` config value and expose it through `/api/data`. Enrich Overall-tier racer rows in `data_processing.py` with `CategoryPlace` by matching them to category-tier result rows, then refactor the frontend result table rendering to use page-specific column definitions and matching CSS width classes.

**Tech Stack:** Python, Flask, pytest, vanilla JavaScript, CSS, WebScorer JSON API data.

## Global Constraints

- `OVERALL_RESULTS_LAYOUT` supports exactly `standard` and `detailed`.
- `OVERALL_RESULTS_LAYOUT` defaults to `standard`.
- Unknown `OVERALL_RESULTS_LAYOUT` values fall back to `standard`.
- `.env` and `.env.example` must contain the same property names.
- Category pages always use `Place | Bib | Name | Time | Team`.
- Overall pages in standard mode use `Place | Bib | Name | Time | Team`.
- Overall pages in detailed mode use `Overall | Bib | Name | Time | Cat Place | Category | Gender | Team`.
- Display API-provided `Gender` values verbatim, including `X`, blank, or future values.
- Do not normalize, map, or switch on gender for display.
- Missing category-placement data renders as a blank cell and must not hide a row or break a page.
- Overall pages remain sorted by Overall placement; detailed mode must not sort by `Cat Place`, category, gender, or team.
- Category pages remain sorted by category placement.
- Sort each result group by numeric `Place` before pages are built because WebScorer API rows can arrive in bib order.
- Detailed Overall pages apply medal icons and podium colors to `Cat Place` for category places 1-3, not to the `Overall` column.
- `PINNED_LEADERS_ON_OVERALL_RESULTS` controls Overall leader pinning, but detailed Overall category-place medal styling does not depend on that setting.
- Existing pinned-leader and podium-styling rules remain unchanged.
- Do not change result ordering beyond sorting each result group by its own numeric `Place`.
- Do not change time calculation, status classification, page visibility behavior, or toast behavior.
- Do not add a JavaScript test framework.

---

## File Structure

- `config.py`: parse and validate `OVERALL_RESULTS_LAYOUT`.
- `.env`: add `OVERALL_RESULTS_LAYOUT=standard` using the same property set as `.env.example` while preserving local secret values.
- `.env.example`: document `OVERALL_RESULTS_LAYOUT=standard` with the other display toggles.
- `app.py`: include `overall_results_layout` in `/api/data`.
- `data_processing.py`: add category-placement enrichment helpers and call them from `process_race_data`.
- `static/dashboard.js`: add `overallResultsLayout` to frontend config and render result tables from column definitions.
- `static/style.css`: add layout-specific width rules for five-column standard tables and eight-column detailed Overall tables.
- `tests/test_config.py`: cover default, detailed override, and invalid fallback.
- `tests/test_app.py`: cover API exposure for `overall_results_layout`.
- `tests/test_data_processing.py`: cover category-place enrichment, gender pass-through, blank/missing gender, distance-aware matching, and missing-match behavior.

---

### Task 1: Add Overall results layout configuration

**Files:**
- Modify: `config.py`
- Modify: `.env`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `load_config()["overall_results_layout"] -> str`, returning either `"standard"` or `"detailed"`.
- Produces: `_normalize_overall_results_layout(value: str | None) -> str`.
- Consumes: environment variable `OVERALL_RESULTS_LAYOUT`.

- [ ] **Step 1: Write failing config tests**

  Add these tests near the existing display/config tests in `tests/test_config.py`:

  ```python
  @patch("config.load_dotenv")
  def test_load_config_overall_results_layout_default(mock_dotenv, monkeypatch):
      monkeypatch.setenv("WEBSCORER_API_ID", "12345")
      monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
      monkeypatch.delenv("OVERALL_RESULTS_LAYOUT", raising=False)
      cfg = load_config()
      assert cfg["overall_results_layout"] == "standard"


  @patch("config.load_dotenv")
  def test_load_config_overall_results_layout_detailed(mock_dotenv, monkeypatch):
      monkeypatch.setenv("WEBSCORER_API_ID", "12345")
      monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
      monkeypatch.setenv("OVERALL_RESULTS_LAYOUT", "detailed")
      cfg = load_config()
      assert cfg["overall_results_layout"] == "detailed"


  @patch("config.load_dotenv")
  def test_load_config_overall_results_layout_invalid_falls_back_to_standard(mock_dotenv, monkeypatch):
      monkeypatch.setenv("WEBSCORER_API_ID", "12345")
      monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc123de")
      monkeypatch.setenv("OVERALL_RESULTS_LAYOUT", "wide")
      cfg = load_config()
      assert cfg["overall_results_layout"] == "standard"
  ```

- [ ] **Step 2: Run the new config tests and verify they fail**

  Run:

  ```powershell
  python -m pytest tests/test_config.py -k overall_results_layout -v
  ```

  Expected result: fail with `KeyError: 'overall_results_layout'`.

- [ ] **Step 3: Implement config normalization**

  In `config.py`, add this helper after the imports:

  ```python
  _OVERALL_RESULTS_LAYOUTS = {"standard", "detailed"}


  def _normalize_overall_results_layout(value):
      value = (value or "standard").strip().lower()
      if value in _OVERALL_RESULTS_LAYOUTS:
          return value
      return "standard"
  ```

  Then add this key to the `load_config()` return dict near the display toggles:

  ```python
          "overall_results_layout": _normalize_overall_results_layout(
              os.environ.get("OVERALL_RESULTS_LAYOUT", "standard")
          ),
  ```

- [ ] **Step 4: Update env files**

  Add this block to `.env.example` after `PINNED_LEADERS_ON_OVERALL_RESULTS=false`:

  ```text
  # Optional: Overall result table layout (standard or detailed, default standard)
  OVERALL_RESULTS_LAYOUT=standard
  ```

  Add `OVERALL_RESULTS_LAYOUT=standard` to `.env` in the same relative location. Preserve existing local values and secrets in `.env`.

- [ ] **Step 5: Verify env property names stay in sync**

  Run this PowerShell check:

  ```powershell
  $envKeys = Select-String -Path .env -Pattern '^[A-Za-z_][A-Za-z0-9_]*=' | ForEach-Object { $_.Matches.Value.Split('=')[0] } | Sort-Object
  $exampleKeys = Select-String -Path .env.example -Pattern '^[A-Za-z_][A-Za-z0-9_]*=' | ForEach-Object { $_.Matches.Value.Split('=')[0] } | Sort-Object
  Compare-Object $envKeys $exampleKeys
  ```

  Expected result: no output.

- [ ] **Step 6: Run config tests and commit**

  Run:

  ```powershell
  python -m pytest tests/test_config.py -v
  git diff --check -- config.py tests/test_config.py .env.example
  git status --short
  ```

  Expected result: config tests pass, no whitespace errors, only intended files changed.

  Commit tracked files only. `.env` is a local ignored file in this repository; update it for
  local parity, but do not force-add it.

  ```powershell
  git add config.py tests/test_config.py .env.example
  git commit -m "feat: add overall results layout config"
  ```

---

### Task 2: Expose the layout through the API

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `app.config["dashboard"]["overall_results_layout"] -> str` from Task 1.
- Produces: `/api/data` JSON key `overall_results_layout -> str`.

- [ ] **Step 1: Write the failing API test**

  In the `app` fixture in `tests/test_app.py`, add this config entry:

  ```python
          "overall_results_layout": "detailed",
  ```

  Add this test near the existing `/api/data` config exposure tests:

  ```python
  @patch("app.fetch_race_results")
  def test_api_data_includes_overall_results_layout(mock_fetch, app, client):
      mock_fetch.return_value = MOCK_RACE_RESULTS
      with app.app_context():
          from app import poll_once
          poll_once(app)
      response = client.get("/api/data")
      data = json.loads(response.data)
      assert data["overall_results_layout"] == "detailed"
  ```

- [ ] **Step 2: Run the new API test and verify it fails**

  Run:

  ```powershell
  python -m pytest tests/test_app.py -k overall_results_layout -v
  ```

  Expected result: fail with `KeyError: 'overall_results_layout'`.

- [ ] **Step 3: Add the API field**

  In `app.py`, add this key to the `jsonify` dict in `api_data()`, near the other display settings:

  ```python
                  "overall_results_layout": app.config["dashboard"].get("overall_results_layout", "standard"),
  ```

- [ ] **Step 4: Run API tests and commit**

  Run:

  ```powershell
  python -m pytest tests/test_app.py -v
  git diff --check -- app.py tests/test_app.py
  git status --short
  ```

  Expected result: app tests pass, no whitespace errors, only intended files changed.

  Commit:

  ```powershell
  git add app.py tests/test_app.py
  git commit -m "feat: expose overall results layout"
  ```

---

### Task 3: Enrich Overall racers with category placement

**Files:**
- Modify: `data_processing.py`
- Test: `tests/test_data_processing.py`

**Interfaces:**
- Produces: `_result_match_key(distance, category, gender, bib) -> tuple[str, str, str, str]`.
- Produces: `_add_category_places(results: list[dict]) -> None`, mutating Overall racer dictionaries to add `CategoryPlace` when a matching category row exists.
- Consumes: WebScorer group dictionaries from `api_response["Results"]`.
- Produces: Overall page racer rows may include `CategoryPlace` while preserving all existing API row fields.

- [ ] **Step 1: Write failing enrichment tests**

  Add these tests to `tests/test_data_processing.py` after `test_process_race_data_categories`:

  ```python
  def test_process_race_data_adds_category_place_to_overall_racers():
      response = {
          "RaceInfo": {"RaceId": 400, "Name": "Race", "Date": "", "Sport": "Cycling"},
          "Results": [
              {
                  "Grouping": {"Distance": "Long", "Overall": True},
                  "Racers": [
                      {"Place": "7", "Bib": "10", "Name": "Alex", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:00:00"},
                  ],
              },
              {
                  "Grouping": {"Distance": "Long", "Category": "Open", "Gender": "X"},
                  "Racers": [
                      {"Place": "2", "Bib": "10", "Name": "Alex", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:00:00"},
                  ],
              },
          ],
      }

      result = process_race_data(response)

      overall = result["categories"][0]
      assert overall["tier"] == "overall"
      assert overall["racers"][0]["CategoryPlace"] == "2"
      assert overall["racers"][0]["Gender"] == "X"
  ```

  Add a distance-aware matching test:

  ```python
  def test_process_race_data_category_place_does_not_cross_match_distances():
      response = {
          "RaceInfo": {"RaceId": 401, "Name": "Race", "Date": "", "Sport": "Cycling"},
          "Results": [
              {
                  "Grouping": {"Distance": "Long", "Overall": True},
                  "Racers": [
                      {"Place": "5", "Bib": "10", "Name": "Alex", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:00:00"},
                  ],
              },
              {
                  "Grouping": {"Distance": "Short", "Category": "Open", "Gender": "X"},
                  "Racers": [
                      {"Place": "1", "Bib": "10", "Name": "Alex", "Distance": "Short", "Category": "Open", "Gender": "X", "Time": "0:30:00"},
                  ],
              },
          ],
      }

      result = process_race_data(response)

      assert "CategoryPlace" not in result["categories"][0]["racers"][0]
  ```

  Add a blank-gender matching test:

  ```python
  def test_process_race_data_category_place_matches_blank_gender():
      response = {
          "RaceInfo": {"RaceId": 402, "Name": "Race", "Date": "", "Sport": "Cycling"},
          "Results": [
              {
                  "Grouping": {"Distance": "Long", "Overall": True},
                  "Racers": [
                      {"Place": "9", "Bib": "11", "Name": "Sam", "Distance": "Long", "Category": "Open", "Gender": "", "Time": "1:05:00"},
                  ],
              },
              {
                  "Grouping": {"Distance": "Long", "Category": "Open", "Gender": ""},
                  "Racers": [
                      {"Place": "3", "Bib": "11", "Name": "Sam", "Distance": "Long", "Category": "Open", "Gender": "", "Time": "1:05:00"},
                  ],
              },
          ],
      }

      result = process_race_data(response)

      assert result["categories"][0]["racers"][0]["CategoryPlace"] == "3"
      assert result["categories"][0]["racers"][0]["Gender"] == ""
  ```

  Add a missing-gender matching test:

  ```python
  def test_process_race_data_category_place_matches_missing_gender_as_blank():
      response = {
          "RaceInfo": {"RaceId": 403, "Name": "Race", "Date": "", "Sport": "Cycling"},
          "Results": [
              {
                  "Grouping": {"Distance": "Long", "Overall": True},
                  "Racers": [
                      {"Place": "12", "Bib": "12", "Name": "Riley", "Distance": "Long", "Category": "Open", "Time": "1:10:00"},
                  ],
              },
              {
                  "Grouping": {"Distance": "Long", "Category": "Open"},
                  "Racers": [
                      {"Place": "4", "Bib": "12", "Name": "Riley", "Distance": "Long", "Category": "Open", "Time": "1:10:00"},
                  ],
              },
          ],
      }

      result = process_race_data(response)

      assert result["categories"][0]["racers"][0]["CategoryPlace"] == "4"
      assert "Gender" not in result["categories"][0]["racers"][0]
  ```

    Add an Overall placement sorting test:

  ```python
    def test_process_race_data_sorts_overall_racers_by_place_after_category_place_enrichment():
      response = {
          "RaceInfo": {"RaceId": 404, "Name": "Race", "Date": "", "Sport": "Cycling"},
          "Results": [
              {
                  "Grouping": {"Distance": "Long", "Overall": True},
                  "Racers": [
              {"Place": "44", "Bib": "8001", "Name": "Bib Sorted", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:10:00"},
              {"Place": "2", "Bib": "8002", "Name": "Second Overall", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:01:00"},
                  ],
              },
              {
                  "Grouping": {"Distance": "Long", "Category": "Open", "Gender": "X"},
                  "Racers": [
              {"Place": "31", "Bib": "8001", "Name": "Bib Sorted", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:10:00"},
              {"Place": "1", "Bib": "8002", "Name": "Second Overall", "Distance": "Long", "Category": "Open", "Gender": "X", "Time": "1:01:00"},
                  ],
              },
          ],
      }

      result = process_race_data(response)

      overall_racers = result["categories"][0]["racers"]
        assert [racer["Bib"] for racer in overall_racers] == ["8002", "8001"]
        assert [racer["Place"] for racer in overall_racers] == ["2", "44"]
        assert [racer["CategoryPlace"] for racer in overall_racers] == ["1", "31"]
  ```

- [ ] **Step 2: Run the new enrichment tests and verify they fail**

  Run:

  ```powershell
  python -m pytest tests/test_data_processing.py -k "category_place" -v
  ```

  Expected result: fail because `CategoryPlace` is not added yet.

- [ ] **Step 3: Implement matching helpers**

  In `data_processing.py`, add these helpers after `_group_name`:

  ```python
  def _match_value(value):
      if value is None:
        return ""
      return str(value).strip()


  def _result_match_key(distance, category, gender, bib):
      return (
          _match_value(distance),
          _match_value(category),
          _match_value(gender),
          _match_value(bib),
      )


      def _place_sort_key(racer):
        place = _match_value(racer.get("Place"))
        if place.isdigit():
          return (0, int(place))
        return (1, 0)


  def _add_category_places(results):
      category_places = {}

      for group in results:
          grouping = group.get("Grouping", {})
          if _classify_group(grouping) != "category":
              continue

          for racer in group.get("Racers", []):
              distance = grouping.get("Distance") or racer.get("Distance")
              category = grouping.get("Category") or racer.get("Category")
              gender = grouping.get("Gender") if grouping.get("Gender") is not None else racer.get("Gender")
              key = _result_match_key(distance, category, gender, racer.get("Bib"))
              category_places[key] = _match_value(racer.get("Place"))

      for group in results:
          grouping = group.get("Grouping", {})
          if _classify_group(grouping) != "overall":
              continue

          for racer in group.get("Racers", []):
              key = _result_match_key(
                  racer.get("Distance"),
                  racer.get("Category"),
                  racer.get("Gender"),
                  racer.get("Bib"),
              )
              if key in category_places:
                  racer["CategoryPlace"] = category_places[key]
  ```

- [ ] **Step 4: Call enrichment from `process_race_data`**

  In `process_race_data`, immediately after this line:

  ```python
      results = api_response.get("Results", [])
  ```

  add:

  ```python
      _add_category_places(results)
  ```

        In the main group loop, replace:

        ```python
          racers = group.get("Racers", [])
        ```

        with:

        ```python
          racers = sorted(group.get("Racers", []), key=_place_sort_key)
        ```

- [ ] **Step 5: Run data-processing tests and commit**

  Run:

  ```powershell
  python -m pytest tests/test_data_processing.py -v
  git diff --check -- data_processing.py tests/test_data_processing.py
  git status --short
  ```

  Expected result: data-processing tests pass, no whitespace errors, only intended files changed.

  Commit:

  ```powershell
  git add data_processing.py tests/test_data_processing.py
  git commit -m "feat: add category placement to overall rows"
  ```

---

### Task 4: Render result tables from column definitions

**Files:**
- Modify: `static/dashboard.js`

**Interfaces:**
- Consumes: `/api/data` key `overall_results_layout -> str` from Task 2.
- Consumes: Overall racer field `CategoryPlace` from Task 3.
- Produces: `getResultColumns(category) -> Array<{ header: string, className: string, value: function }>`.
- Produces: `renderResultHeader(columns, layoutClass) -> string`.
- Produces: `renderRacerRow(racer, showPodiumStyling, columns) -> string`.

- [ ] **Step 1: Add frontend config field**

  In `static/dashboard.js`, extend the `config = { ... }` assignment in `fetchData()`:

  ```javascript
          overallResultsLayout: data.overall_results_layout || "standard",
  ```

  Keep the existing `pinnedLeadersOnOverallResults` entry unchanged.

- [ ] **Step 2: Add standard column definitions**

  Add this helper near `renderRacerRow`:

  ```javascript
  function getStandardResultColumns() {
    return [
      { header: "Place", className: "col-place", value: function (r) { return r.Place || ""; } },
      { header: "Bib", className: "col-bib", value: function (r) { return r.Bib || ""; } },
      { header: "Name", className: "col-name", value: function (r) { return r.Name || ""; } },
      { header: "Time", className: "col-time", value: function (r) { return r.Time || ""; } },
      { header: "Team", className: "col-team", value: function (r) { return r.TeamName || ""; } },
    ];
  }
  ```

- [ ] **Step 3: Add detailed Overall column definitions**

  Add this helper below `getStandardResultColumns()`:

  ```javascript
  function getDetailedOverallResultColumns() {
    return [
      { header: "Overall", className: "col-overall", value: function (r) { return r.Place || ""; } },
      { header: "Bib", className: "col-bib", value: function (r) { return r.Bib || ""; } },
      { header: "Name", className: "col-name", value: function (r) { return r.Name || ""; } },
      { header: "Time", className: "col-time", value: function (r) { return r.Time || ""; } },
      { header: "Cat Place", className: "col-category-place", value: function (r) { return r.CategoryPlace || ""; } },
      { header: "Category", className: "col-category", value: function (r) { return r.Category || ""; } },
      { header: "Gender", className: "col-gender", value: function (r) { return r.Gender || ""; } },
      { header: "Team", className: "col-team", value: function (r) { return r.TeamName || ""; } },
    ];
  }
  ```

- [ ] **Step 4: Add page-level column selection**

  Add this helper below `getDetailedOverallResultColumns()`:

  ```javascript
  function getResultColumns(category) {
    if (category.tier === "overall" && config.overallResultsLayout === "detailed") {
      return {
        columns: getDetailedOverallResultColumns(),
        layoutClass: "results-table-overall-detail"
      };
    }

    return {
      columns: getStandardResultColumns(),
      layoutClass: "results-table-standard"
    };
  }
  ```

- [ ] **Step 5: Add header rendering helper**

  Add this helper below `getResultColumns()`:

  ```javascript
  function renderResultHeader(columns, layoutClass) {
    var html = '<table class="results-table results-header-table ' + layoutClass + '">';
    html += "<thead><tr>";
    for (var i = 0; i < columns.length; i++) {
      html += '<th class="' + columns[i].className + '">' + escapeHtml(columns[i].header) + "</th>";
    }
    html += "</tr></thead>";
    html += "</table>";
    return html;
  }
  ```

- [ ] **Step 6: Use selected columns in `renderCategory`**

  In `renderCategory`, after `var scrolling = racers.slice(pinnedCount).filter(hasResult);`, add:

  ```javascript
    var resultLayout = getResultColumns(category);
    var columns = resultLayout.columns;
    var layoutClass = resultLayout.layoutClass;
  ```

  In the empty-page branch, add the fixed header before the `No results yet` paragraph:

  ```javascript
      emptyHtml += renderResultHeader(columns, layoutClass);
  ```

  Replace the current hardcoded header table:

  ```javascript
    html += '<table class="results-table results-header-table">';
    html += '<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Team</th><th>Time</th></tr></thead>';
    html += '</table>';
  ```

  with:

  ```javascript
    html += renderResultHeader(columns, layoutClass);
  ```

  Add `layoutClass` to the pinned and scrolling table class lists:

  ```javascript
      html += '<table class="results-table pinned-table ' + layoutClass + '">';
  ```

  ```javascript
      html += '<table class="results-table scroll-table ' + layoutClass + '">';
  ```

- [ ] **Step 7: Update row rendering**

  Change the pinned and scrolling row calls:

  ```javascript
        html += renderRacerRow(pinned[i], showPodiumStyling, columns);
  ```

  ```javascript
        html += renderRacerRow(scrolling[j], showPodiumStyling, columns);
  ```

  Replace `renderRacerRow` with this implementation:

  ```javascript
  function renderRacerRow(r, showPodiumStyling, columns) {
    var placeClass = "";
    var medal = "";
    if (showPodiumStyling) {
      var place = parseInt(r.Place) || 0;
      if (place === 1) {
        placeClass = " place-1";
        medal = " \uD83E\uDD47";
      } else if (place === 2) {
        placeClass = " place-2";
        medal = " \uD83E\uDD48";
      } else if (place === 3) {
        placeClass = " place-3";
        medal = " \uD83E\uDD49";
      }
    }

    var html = "<tr>";
    for (var i = 0; i < columns.length; i++) {
      var column = columns[i];
      var cellClass = column.className;
      var value = column.value(r);
      if (i === 0) {
        cellClass += placeClass;
        value = value + medal;
      }
      html += '<td class="' + cellClass + '">' + escapeHtml(value) + "</td>";
    }
    html += "</tr>";
    return html;
  }
  ```

- [ ] **Step 8: Run a focused static check and commit**

  Run:

  ```powershell
  Select-String -Path static/dashboard.js -Pattern 'overallResultsLayout|getResultColumns|renderResultHeader|results-table-overall-detail|results-table-standard|<th>Place</th>'
  git diff --check -- static/dashboard.js
  git status --short
  ```

  Expected result: helpers and layout classes appear; the old hardcoded `<th>Place</th>` header does not appear; no whitespace errors.

  Commit:

  ```powershell
  git add static/dashboard.js
  git commit -m "feat: render configurable result columns"
  ```

---

### Task 5: Add layout-specific result table widths

**Files:**
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `results-table-standard` and `results-table-overall-detail` classes from Task 4.
- Produces: stable column widths for standard and detailed result layouts.

- [ ] **Step 1: Replace generic nth-child widths with standard layout widths**

  In `static/style.css`, replace the existing `.results-table th:nth-child(...)` and
  `.results-table td:nth-child(...)` width block with:

  ```css
  .results-table-standard .col-place {
    width: 7%;
  }

  .results-table-standard .col-bib {
    width: 8%;
  }

  .results-table-standard .col-name {
    width: 35%;
  }

  .results-table-standard .col-time {
    width: 20%;
  }

  .results-table-standard .col-team {
    width: 30%;
  }
  ```

- [ ] **Step 2: Add detailed Overall layout widths**

  Immediately after the standard widths, add:

  ```css
  .results-table-overall-detail .col-overall {
    width: 8%;
  }

  .results-table-overall-detail .col-bib {
    width: 7%;
  }

  .results-table-overall-detail .col-name {
    width: 24%;
  }

  .results-table-overall-detail .col-time {
    width: 14%;
  }

  .results-table-overall-detail .col-category-place {
    width: 9%;
  }

  .results-table-overall-detail .col-category {
    width: 22%;
  }

  .results-table-overall-detail .col-gender {
    width: 6%;
  }

  .results-table-overall-detail .col-team {
    width: 10%;
  }
  ```

- [ ] **Step 3: Run CSS static checks and commit**

  Run:

  ```powershell
  Select-String -Path static/style.css -Pattern 'results-table-standard|results-table-overall-detail|nth-child'
  git diff --check -- static/style.css
  git status --short
  ```

  Expected result: new layout classes appear; the old result-table column `nth-child` width rules are gone; no whitespace errors.

  Commit:

  ```powershell
  git add static/style.css
  git commit -m "feat: add result table layout widths"
  ```

---

### Task 6: Run regression and browser verification

**Files:**
- Verify: `config.py`
- Verify: `.env`
- Verify: `.env.example`
- Verify: `app.py`
- Verify: `data_processing.py`
- Verify: `static/dashboard.js`
- Verify: `static/style.css`
- Verify: `tests/`

**Interfaces:**
- Consumes: all implementation from Tasks 1-5.
- Produces: verified feature branch ready for review.

- [ ] **Step 1: Run the full Python regression suite**

  Run:

  ```powershell
  python -m pytest
  ```

  Expected result: all tests pass.

- [ ] **Step 2: Run final whitespace and status checks**

  Run:

  ```powershell
  git diff --check
  git status --short --branch
  ```

  Expected result: no whitespace errors and no uncommitted implementation changes.

- [ ] **Step 3: Start the dashboard with detailed Overall layout**

  Set local env values in `.env` for manual verification:

  ```text
  DATA_FILE=api_dump_443486_finished.json
  OVERALL_RESULTS_LAYOUT=detailed
  SHOW_SUMMARY=false
  SHOW_OVERALL_RESULTS=true
  SHOW_CATEGORY_RESULTS=true
  ```

  Start the app:

  ```powershell
  .\start.ps1
  ```

  Expected result: app starts and serves the dashboard locally.

- [ ] **Step 4: Manually verify detailed Overall pages**

  In the browser, inspect an Overall page and confirm:

  - Header shows `Overall | Bib | Name | Time | Cat Place | Category | Gender | Team`.
  - `Cat Place` cells are populated for racers that match category result rows.
  - `Gender` displays the API row value directly.
  - Header remains fixed above the scroll container.
  - Pinned leaders and medal coloring still follow `PINNED_LEADERS_ON_OVERALL_RESULTS`.
  - Team truncates before core identity, time, category, or placement information becomes unreadable.

- [ ] **Step 5: Manually verify standard and category pages**

  Change `.env` to:

  ```text
  OVERALL_RESULTS_LAYOUT=standard
  ```

  Restart the app:

  ```powershell
  .\start.ps1
  ```

  Confirm:

  - Overall pages show `Place | Bib | Name | Time | Team`.
  - Category pages show `Place | Bib | Name | Time | Team` in both standard and detailed modes.
  - Existing empty result pages still show the fixed header and `No results yet` message.

- [ ] **Step 6: Restore local `.env` defaults used for development**

  Restore any local `.env` values changed during manual verification while keeping the new `OVERALL_RESULTS_LAYOUT` property present.

- [ ] **Step 7: Review final branch diff**

  Run:

  ```powershell
  git log --oneline --decorate main..HEAD
  git diff main...HEAD --stat
  ```

  Expected result: commits are conventional and changed files match this plan's scope.