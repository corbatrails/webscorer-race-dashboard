# Show Event Name at the Top of All Screens

**Issue**: #12
**Date**: 2026-08-14

## Problem

The race/event name is only visible on the summary page. Category pages and the waiting screen don't show it.

## Approach

Extract a shared `renderEventHeader(data)` function that renders the full summary-style header (logo, race name, date/sport subtitle, last-updated timestamp). Call it from all three render functions.

## Layout

### Summary page (unchanged visually)

The existing `.summary-header` HTML is replaced by the shared `renderEventHeader()` call. Output is identical.

### Category pages

```
[Event header: logo + race name + date/sport + last updated]
[Category header: category name + "Category X of Y"]
[Pinned results table]
[Scrolling results table]
```

"Last updated" moves from `.category-meta` to the event header (already shown there). `.category-meta` retains only the category counter.

### Waiting screen

When `data.race_name` is available (after first successful poll), the event header is shown above the waiting message. Before any data arrives, the waiting screen remains unchanged.

## Changes

### dashboard.js

- New function `renderEventHeader(data)` returning the header HTML
- `renderSummary()`: replace inline header HTML with `renderEventHeader(data)` call
- `renderCategory()`: prepend `renderEventHeader(data)` before category header; remove "Last updated" from `.category-meta`
- `renderWaiting()`: prepend `renderEventHeader(data)` when `data.race_name` is truthy

### style.css

No structural CSS changes needed — category pages will reuse the existing `.summary-header`, `.race-title`, `.race-subtitle`, `.summary-meta` classes.

### Backend

No changes needed. `race_name`, `race_date`, `race_sport`, and `last_refresh` are already in the API response on every poll.

## Testing

- Existing JS rendering tests should be updated to verify the event header appears in category and waiting page output
- Manual verification: summary page looks identical, category pages show event header above category name, waiting screen shows header after first data fetch
