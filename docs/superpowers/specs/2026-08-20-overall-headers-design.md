# Overall Result Table Headers - Design

## Problem

Issue #51 reports that Overall result pages do not consistently show the result-table
headers in a fixed, non-scrolling location. In the current frontend, the table header is
rendered inside `#scroll-container` whenever no leaders are pinned, so it scrolls away
with the racer rows. When leaders are pinned, the header is incidentally kept visible by
the separate pinned table.

The result columns need to remain identifiable throughout the page rotation and scrolling
experience for both Overall and category result pages.

## Goals

- Always display `Place`, `Bib`, `Name`, `Team`, and `Time` on result pages.
- Keep the result headers outside the scrolling results region.
- Use the same column alignment and styling for Overall and category pages.
- Preserve category-page behavior, including pinned leaders and medal styling.
- Keep the change limited to the frontend result-page rendering and layout.

## Proposed design

### DOM structure

`renderCategory` will render a dedicated header-only table between the category metadata
and the result rows:

```text
page
|- event header
|- category header
|- fixed results header table
|- pinned leaders table, when applicable
`- scrolling results table
```

The fixed header table will contain one `<thead>` with the five required labels. The
pinned-leaders table will continue to render its rows in the non-scrolling area when
podium styling is enabled. The scrolling table will contain only a `<tbody>`; its rows
will never carry a second header that can scroll away.

This structure applies uniformly to Overall and category-tier pages. The existing tier
logic remains responsible for deciding whether leaders are pinned and whether medal
classes are applied; it does not affect header visibility.

### Layout and styling

The header-only table, pinned-leaders table, and scrolling results table will all use the
existing `results-table` class and the existing fixed five-column width rules. This keeps
the header labels aligned with the cells below them without introducing a second set of
column measurements.

The fixed header table remains outside `#scroll-container`. The scroll container retains
its current `flex: 1` and `overflow: hidden` behavior, so page sizing and automatic
scrolling continue to work as they do today. Existing typography, colors, borders, and
row styling remain unchanged unless a small selector adjustment is required to support
the shared table structure.

### Rendering flow

1. Render the event and category headers.
2. Render the fixed five-column table header.
3. Calculate and render pinned leaders using the existing tier/configuration rules.
4. Render remaining racers inside `#scroll-container` without a `<thead>`.
5. Start the existing scroll animation against `#scroll-container`.

When a category has no racers, the fixed table header remains visible and the existing
`No results yet` message is shown below it. This satisfies the requirement that result
pages visibly identify their columns even before rows arrive.

## Error handling and compatibility

No new API data or configuration is required. The change consumes the existing page data
and rendering configuration only. Empty pages, in-progress racers, DNS/DNF/DSQ rows,
pinned leaders, and automatic page rotation retain their current behavior.

The existing `renderRacerRow` and podium styling logic should not be changed unless the
new table structure exposes a necessary local adjustment. The fixed header is purely a
presentation concern and must not alter place calculations or racer ordering.

## Testing and verification

There is no JavaScript test framework in the repository, so verification will combine
backend regression tests with focused frontend checks:

- Run the full Python test suite and confirm the existing 55 tests remain green.
- Exercise the dashboard with the checked-in API dump data and inspect an Overall page
  with enough rows to scroll.
- Confirm the fixed header is outside `#scroll-container` and remains visible while rows
  scroll.
- Confirm all five labels are present and align with the corresponding result columns.
- Confirm category pages still show pinned leaders and retain their current medal styling.
- Confirm pages with no racers still show the header and the existing empty-state message.
- Run `git diff --check` before committing the spec and implementation changes.

## Scope boundaries

Included:

- `static/dashboard.js` result-page markup changes.
- `static/style.css` selector/layout adjustments only if required for shared alignment.
- Focused documentation or test updates needed to describe or verify the structure.

Excluded:

- Changes to WebScorer API processing or page data contracts.
- Changes to Overall/category visibility configuration.
- Changes to scroll speed, pause timing, page rotation, podium configuration, or toast
  notifications.
- A new JavaScript test framework.
