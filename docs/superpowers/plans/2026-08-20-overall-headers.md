# Overall Result Table Headers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the five result-table column headers visible and aligned above scrolling results on both Overall and category pages.

**Architecture:** Change `renderCategory` in `static/dashboard.js` to render one dedicated header-only table outside `#scroll-container`, then render pinned and scrolling racer rows beneath it. Reuse the existing `results-table` class and column-width selectors so Overall and category pages share identical alignment and styling; no API or data-processing changes are needed.

**Tech Stack:** Vanilla JavaScript, CSS, Flask-served static assets, Python/pytest regression tests.

## Global Constraints

- Always display `Place`, `Bib`, `Name`, `Team`, and `Time` on result pages.
- Keep result headers outside `#scroll-container`.
- Category pages retain pinned leaders and medal styling behavior.
- Do not change WebScorer API processing or page data contracts.
- Do not add a JavaScript test framework.
- Use the existing `results-table` class and five-column width rules for alignment.

---

### Task 1: Add a shared fixed header to result-page rendering

**Files:**
- Modify: `static/dashboard.js:renderCategory`
- Test: manual structural check against dashboard output and checked-in API dump data

**Interfaces:**
- Consumes: existing `category.tier`, `category.racers`, and frontend rendering configuration.
- Produces: result-page HTML with a five-column `<thead>` outside `#scroll-container`; pinned and scrolling racer rows remain rendered through `renderRacerRow`.

- [ ] **Step 1: Capture the current rendering branches**

  In `renderCategory`, identify the two existing table branches:

  - The pinned table, which currently includes the header and pinned rows.
  - The scrolling table, which currently includes its own header only when `pinned.length === 0`.

  The replacement must preserve the existing `showPodiumStyling`, `pinnedCount`, `pinned`, and `scrolling` calculations.

- [ ] **Step 2: Render one fixed header table before result rows**

  Immediately after the category header, append:

  ```javascript
    html += '<table class="results-table results-header-table">';
    html += '<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Team</th><th>Time</th></tr></thead>';
    html += '</table>';
  ```

  This table must be rendered before the pinned table and before `#scroll-container`, so it remains fixed while the result rows scroll.

- [ ] **Step 3: Remove duplicate scrolling and pinned table headers**

  Remove the `<thead>` from the pinned-leaders table and remove the conditional `<thead>` from the scrolling table. Leave both tables with their existing `<tbody>` rows and preserve their existing classes and row-rendering calls.

- [ ] **Step 4: Handle empty categories without hiding the header**

  Move the fixed header rendering before the `racers.length === 0` early return. Keep the existing empty-state message and page closing markup unchanged, so a category with no racers still displays the five labels followed by `No results yet`.

- [ ] **Step 5: Run a focused static check**

  Run:

  ```powershell
  Select-String -Path static/dashboard.js -Pattern 'results-header-table|scroll-container|<thead>'
  ```

  Expected result: `results-header-table` appears before `scroll-container` in `renderCategory`; there is one result-page `<thead>` and no `<thead>` inside the scrolling-table branch.

- [ ] **Step 6: Commit the rendering change**

  ```powershell
  git add static/dashboard.js
  git commit -m "fix: keep result headers fixed while scrolling"
  ```

### Task 2: Align shared header and result tables

**Files:**
- Modify: `static/style.css:results-table selectors`
- Test: browser/manual visual check

**Interfaces:**
- Consumes: the new `results-header-table` class and the existing `results-table` column selectors.
- Produces: identical widths, typography, borders, and horizontal alignment for the fixed header and racer rows.

- [ ] **Step 1: Inspect computed layout after Task 1**

  Start the dashboard with a checked-in API dump and inspect an Overall page and a category page. Confirm whether the existing `.results-table` selectors already align the header-only table with row tables.

- [ ] **Step 2: Add only the necessary CSS adjustment**

  If the shared selectors already provide alignment, make no CSS change. If the fixed header needs a local layout rule, add it next to the existing result-table rules without changing colors, font sizes, row heights, or column percentages. The fixed header must remain in normal flow above the scrolling container.

- [ ] **Step 3: Verify the no-finishers category case**

  Use data where a category has racers but none have a finished time. Confirm that:

  - The five header labels are visible.
  - The header is outside `#scroll-container`.
  - The existing rows remain scrollable when they exceed the viewport.
  - No pinned-leader table is created until the existing finish-status rules allow it.

- [ ] **Step 4: Commit any required CSS adjustment**

  ```powershell
  git add static/style.css
  git commit -m "fix: align fixed result table headers"
  ```

  Skip this commit when no CSS change is needed.

### Task 3: Run regression and final verification

**Files:**
- Verify: `static/dashboard.js`
- Verify: `static/style.css`
- Verify: `tests/`

**Interfaces:**
- Consumes: the completed fixed-header rendering and any required CSS alignment adjustment.
- Produces: verified behavior with no backend regressions.

- [ ] **Step 1: Run the Python regression suite**

  ```powershell
  python -m pytest
  ```

  Expected result: all existing tests pass.

- [ ] **Step 2: Run whitespace and diff checks**

  ```powershell
  git diff --check
  git status --short
  ```

  Expected result: no whitespace errors and no unexpected files.

- [ ] **Step 3: Perform the browser acceptance check**

  Inspect a long Overall result page and a long category page. Confirm:

  - The fixed header displays all five labels.
  - Headers remain visible while results scroll.
  - Header labels align with `Place`, `Bib`, `Name`, `Team`, and `Time` cells.
  - Category pinned leaders and medal styling remain unchanged.
  - A category with no placed racers still shows its fixed header.
  - Empty categories retain the existing `No results yet` message.

- [ ] **Step 4: Review the final diff**

  ```powershell
  git diff HEAD~2..HEAD -- static/dashboard.js static/style.css
  ```

  Confirm the implementation is limited to result-page markup/layout and contains no API, configuration, or data-processing changes.
