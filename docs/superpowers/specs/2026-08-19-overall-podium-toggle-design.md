# Overall Podium De-emphasis Toggle — Design

## Problem

(Issue #48) Some races don't award an "Overall" podium — only category-level awards. On the
dashboard's Overall-tier result pages, the top 3 places are currently visually treated like a
podium:

- Places 1-3 get gold/silver/bronze text coloring (`place-1`/`place-2`/`place-3` CSS classes).
- The top 3 finishers (that have finished) are pinned to a frozen header row above the scrolling
  list.

This implies a podium exists for Overall results even when the race doesn't award one. Category-tier
pages are unaffected — categories generally do have real awards, and podium toasts already only
fire for category placements (see `detectNewFinishers` in `dashboard.js`).

## Solution

Add a single new boolean env-driven config toggle: `PINNED_LEADERS_ON_OVERALL_RESULTS`, default
`false`.

- When `false` (new default): Overall-tier pages render with no pinned-leaders row (all racers
  scroll together as one list) and no medal coloring on places 1-3. Place numbers are still shown
  in the table — only the visual "podium" treatment is removed.
- When `true`: Overall-tier pages behave exactly as they do today (pinned top 3 + medal coloring).
- Category-tier pages are never affected by this toggle.

## Implementation touchpoints

1. **[config.py](../../../config.py)** — add:
   ```python
   "pinned_leaders_on_overall_results": os.environ.get("PINNED_LEADERS_ON_OVERALL_RESULTS", "false").lower() == "true",
   ```
2. **[app.py](../../../app.py)** — pass the flag through in the `/api/data` JSON response, same
   pattern as `show_summary` / `show_toasts`.
3. **[static/dashboard.js](../../../static/dashboard.js)**:
   - `renderCategory`: when `category.tier === "overall"` and the config flag is off, treat
     `pinnedCount` as `0` so nothing is pinned.
   - `renderRacerRow`: accept a parameter for whether podium coloring should be applied; omit the
     `place-1`/`place-2`/`place-3` classes when rendering an Overall-tier page with the flag off.
4. **[.env.example](../../../.env.example)** — add `PINNED_LEADERS_ON_OVERALL_RESULTS=false` next
   to the other display toggles.

No changes are needed in `data_processing.py` — this is purely a rendering concern, and page
`tier` ("overall" vs "category") is already threaded through to the frontend.

## Testing

- `tests/test_config.py`: default value and env var override for `pinned_leaders_on_overall_results`.
- Frontend behavior (pinning/coloring suppression) is manual/visual — no existing JS test
  infrastructure covers `dashboard.js` rendering.

## Out of scope

- Category-tier pages and their podium toasts are unchanged.
- No change to `SHOW_OVERALL_RESULTS` / `SHOW_CATEGORY_RESULTS` (whether pages are shown at all).
