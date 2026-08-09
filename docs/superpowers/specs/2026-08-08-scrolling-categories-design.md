# Scrolling Category Results — Design Spec

## Problem

The current page-splitting approach for large categories creates many sub-pages that rotate quickly, making it hard to find your name. A smooth-scrolling ticker with pinned leaders is more natural for passive TV viewing.

## Solution

Replace page-based category display with a continuous scroll. Each category has pinned leader rows at the top and remaining results scroll upward at a configurable speed. The dashboard advances to the next category after the scroll completes.

## Behavior

1. Summary page displays statically for `SUMMARY_DISPLAY_TIME` seconds
2. Category page appears: top N rows (leaders) pinned, pause for `SCROLL_PAUSE_TIME` seconds, then begin scrolling upward at `SCROLL_SPEED` px/s
3. When the last row is fully visible, pause for `SCROLL_PAUSE_TIME` seconds
4. Advance to next category (or back to summary)
5. If a category fits entirely on screen (no overflow beyond pinned + visible area), display statically for `SUMMARY_DISPLAY_TIME` then advance

## Configuration

Replaces `PAGE_ROTATION_INTERVAL` and `RESULTS_PER_PAGE`.

| Variable | Default | Description |
|---|---|---|
| `SUMMARY_DISPLAY_TIME` | `20` | Seconds the summary page displays |
| `SCROLL_SPEED` | `100` | Pixels per second for category result scrolling |
| `SCROLL_PAUSE_TIME` | `3` | Seconds to pause before and after scroll |
| `PINNED_LEADERS` | `3` | Number of rows frozen at top of each category |
| `SHOW_SUMMARY` | `true` | Whether to show the summary page |
| `SHOW_CATEGORIES` | `true` | Whether to show category pages |

Removed:
- `PAGE_ROTATION_INTERVAL` — replaced by `SUMMARY_DISPLAY_TIME` and scroll duration
- `RESULTS_PER_PAGE` — no longer relevant with scrolling

## Layout (Category Page)

```
┌─────────────────────────────────────────────────┐
│ Category Title • Page 3 of 17   Last updated: X │  ← header (fixed)
├─────────────────────────────────────────────────┤
│ Place │ Bib │ Name            │ Time            │  ← table header (fixed)
│   1   │ 112 │ Eli Kotz        │ 4:10:00.0       │  ← pinned leader
│   2   │ 108 │ John Smith      │ 4:15:30.0       │  ← pinned leader
│   3   │ 115 │ Jane Doe        │ 4:18:00.0       │  ← pinned leader
├─────────────────────────────────────────────────┤  ← visual separator
│   4   │ 120 │ ...             │ ...             │  ↑
│   5   │ 131 │ ...             │ ...             │  │ scrolling area
│  ...  │ ... │ ...             │ ...             │  │
│  42   │ 199 │ ...             │ ...             │  ↓
├─────────────────────────────────────────────────┤
│              ● ● ● ○ ● ● ●                     │  ← progress dots (fixed)
└─────────────────────────────────────────────────┘
```

## Scroll Mechanics

- Scroll is CSS-driven (`transform: translateY()` or `scrollTop` animation via `requestAnimationFrame`)
- Scroll distance = total height of non-pinned rows - visible scroll area height
- If scroll distance ≤ 0 (all results fit), no scroll needed — static display
- Scroll starts after `SCROLL_PAUSE_TIME` pause when category page becomes active
- On completion (last row visible): pause `SCROLL_PAUSE_TIME`, then fire advance

## Rotation Flow

```
Summary (20s) → Category 1 (scroll + 3s pause) → Category 2 (scroll + 3s pause) → ... → Summary → ...
```

- "Page X of Y" in the header now means category position (e.g., "Page 3 of 17 categories"), not sub-pages
- Progress dots represent categories, not sub-pages

## Timing Examples (1080p)

Row height: ~49px (4.5vh). Visible scroll area: ~600px (~12 rows visible at once).

| Category size | Pinned | Scrolling rows | Scroll distance | At 100px/s | Total time |
|---|---|---|---|---|---|
| 10 racers | 3 | 7 | Fits on screen | 0s scroll | 20s (static) |
| 42 racers | 3 | 39 | ~1310px | 13s | 16s |
| 123 racers | 3 | 120 | ~5290px | 53s | 56s |
| 300 racers | 3 | 297 | ~13960px | 140s | 143s |

## Data Model

No changes to `process_race_data`. The `build_pages` function already sends full racer lists per category (no splitting). The frontend receives all racers and handles scroll rendering.

API response adds new fields:
```json
{
  "summary_display_time": 20,
  "scroll_speed": 100,
  "scroll_pause_time": 3,
  "pinned_leaders": 3
}
```

## Files Changed

- `config.py` — replace `page_rotation_interval` and `results_per_page` with new config values
- `.env.example` — update config template
- `app.py` — pass new config values through `/api/data`, remove old ones
- `static/dashboard.js` — rewrite rotation logic: summary timer, scroll animation, category advance
- `static/style.css` — pinned row styles, scroll container with overflow hidden
- `tests/test_config.py` — update for new config keys
- `tests/test_app.py` — update mock config and API response assertions

## Edge Cases

- Category with ≤ screen-full of results: static display for `SUMMARY_DISPLAY_TIME`, then advance
- Category with 0 results: show "No results yet" statically for `SUMMARY_DISPLAY_TIME`
- Data refresh during scroll: update content in-place, don't reset scroll position (new results appear at correct sorted position)
- Both `SHOW_SUMMARY` and `SHOW_CATEGORIES` false: show waiting screen
