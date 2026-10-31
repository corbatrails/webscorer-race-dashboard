# Race Control Results Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Unfinished filter and an All distance view to Race control Results.

**Architecture:** Keep aggregation in `static/race_control.js`, combining only the existing per-distance Overall groups and preserving each row's distance-specific place. Keep the backend contract unchanged; reveal a Distance column only for All, and retain the existing default selection of the first concrete distance.

**Tech Stack:** Vanilla JavaScript, HTML, Node.js built-in test runner.

**Spec:** `docs/superpowers/specs/2026-10-31-race-control-results-filters-design.md`

## Global Constraints

- Unfinished means status `On course` or `Not started` only.
- All combines each distance's Overall racers and excludes category entries.
- Preserve distance-specific places; do not create a cross-distance ranking.
- Keep the existing distance rail and filter-button layout.
- Do not change server data or the race-control data contract.

## Review Focus

- Other non-finish statuses (DNF, DNS, DSQ) must not appear under Unfinished; test in `tests/race_control.test.cjs`.
- All must not duplicate racers through category groups; test a mixed Overall/category payload in `tests/race_control.test.cjs`.
- Distances with no Overall group must not break All or expose category rows; test in `tests/race_control.test.cjs`.
- An actual null/Overall distance must remain distinct from the All sentinel; test the rail choices and selection in `tests/race_control.test.cjs`.
- The conditional Distance column must not change per-distance split-detail column spans; test both distance modes in `tests/race_control.test.cjs`.

---

### Task 1: Add unfinished filtering and an all-distances Overall view

**Files:**
- Modify: `static/race_control.js`
- Modify: `templates/race_control.html`
- Test: `tests/race_control.test.cjs`

**Interfaces:**
- Consumes: `race_control.groups`, whose entries have `tier`, `distance`, `key`, `title`, and `racers`; racer rows include `Status`, `Place`, and other rendered result fields.
- Produces: the existing `filteredRows(racers, filter)` behavior for `"all"` and `"finished"`, plus `"unfinished"` for exactly `"On course"` and `"Not started"`; distance choices with a distinct All key; a combined synthetic Overall group whose racer rows retain their existing `Place` and carry their source distance for rendering.

- [ ] **Step 1: Write failing tests** in `tests/race_control.test.cjs`.

Add assertions that:
- `filteredRows` returns only On course and Not started for `"unfinished"` and continues to include only verified finishers for `"finished"`.
- All appears in the distance rail and selector; selecting it exposes one Overall grouping containing Overall racers from multiple distances, excludes category-only duplicates, preserves each row's `Place`, and displays its source distance.
- All is distinct from an actual null distance, keeps the first concrete distance as the initial selection, and remains selected across a same-race refresh.
- The Distance header is hidden for a concrete distance and visible for All, with split-detail cells spanning the visible columns in both modes.

- [ ] **Step 2: Run the targeted tests and verify they fail for the missing behavior.**

Run: `node --test tests/race_control.test.cjs`
Expected: failures for the new unfinished filter and All-distance behavior; existing tests continue to pass.

- [ ] **Step 3: Implement the minimum UI behavior.**

In `static/race_control.js`, add the All choice with a dedicated sentinel key, preserve the current default concrete-distance selection, synthesize one Overall group from source groups with `tier === "overall"` when All is selected, and carry the source distance on each combined row. Add the Unfinished predicate. Render the source distance only in All mode and keep expanded split details aligned to the visible column count.

In `templates/race_control.html`, add the Unfinished filter button and a Distance table heading hidden by default. Keep the existing rail and button layout.

- [ ] **Step 4: Run the targeted tests and verify they pass.**

Run: `node --test tests/race_control.test.cjs`
Expected: PASS, including existing race-control tests and the new filter, aggregation, selection, and column-span assertions.

- [ ] **Step 5: Commit the single logical change.**

```bash
git add static/race_control.js templates/race_control.html tests/race_control.test.cjs
git commit -m "fix: add unfinished and all-distance race control filters"
```

Include the required `Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>` trailer.
