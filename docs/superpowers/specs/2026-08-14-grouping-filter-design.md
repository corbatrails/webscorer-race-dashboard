# Grouping-Level Filtering — Design Spec

## Problem

The dashboard creates a page for every result group from the WebScorer API. For a multi-distance event this produces 29 groups — including Overall, Distance+Gender, and Category+Gender tiers — showing the same racers multiple times across duplicate pages. The rotation also stalls with too many pages.

## Solution

Classify each API result group into one of three tiers and let the user configure which tiers to display. Replace the existing `SHOW_CATEGORIES` config with three granular flags.

## Group Classification

Each group in the API `Results` array is classified by its `Grouping` fields:

| Tier | Rule | Title format | Example |
|---|---|---|---|
| **overall** | `Overall: true` | `Distance` (or fallback to "Overall") | "Long Course (88 miles)" |
| **category** | Has `Category`, no `Overall` | `Category` + " " + `Gender` | "Adult Long Course (age 18-44) Male" |
| **distance** | Everything else | `Distance` + " " + `Gender` (or available fields) | "Long Course (88 miles) Female" |

## Configuration

Replaces `SHOW_CATEGORIES`.

| Variable | Default | Description |
|---|---|---|
| `SHOW_OVERALL_RESULTS` | `true` | Show Overall groups (one per distance) |
| `SHOW_CATEGORY_RESULTS` | `true` | Show Category+Gender leaf groups |
| `SHOW_DISTANCE_RESULTS` | `false` | Show Distance+Gender mid-level groups |

`SHOW_SUMMARY` remains unchanged.

If all three result flags are false, no result pages are shown (equivalent to old `SHOW_CATEGORIES=false`).

## Ordering

Groups are ordered by distance, with tiers within each distance in order: overall → distance → category. Within each tier, groups appear in their original API order.

Example with defaults (`overall=true`, `category=true`, `distance=false`):
1. Long Course (88 miles) — overall
2. Adult Long Course (age 18-44) Female — category
3. Adult Long Course (age 18-44) Male — category
4. Masters Long Course (age 45+) Female — category
5. Masters Long Course (age 45+) Male — category
6. Mid Course (45 miles) — overall
7. Adult Mid Course (age 18-44) Female — category
8. ...and so on

## Totals

No change — summary page totals are still counted from `Overall: true` groups only.

## Frontend

The frontend `showCategories` config key is removed. The backend filtering means the frontend simply renders whatever categories it receives. `buildPageList` always includes category pages from `data.pages` (unless the pages array is empty).

## Files Changed

- `config.py` — remove `show_categories`, add `show_overall_results`, `show_category_results`, `show_distance_results`
- `data_processing.py` — `process_race_data` accepts grouping config, classifies groups, filters by tier, orders by distance
- `app.py` — pass grouping config to `process_race_data`, remove `show_categories` from API response
- `static/dashboard.js` — remove `showCategories` handling from `buildPageList`; always include category pages
- `tests/test_data_processing.py` — update for filtering behavior, add multi-distance filtering tests
- `tests/test_config.py` — update for new config keys
- `tests/test_app.py` — update mock config

## Backward Compatibility

For simple single-distance races (groups have `Category` but no `Distance`): the Overall group is included (has `Overall: true`), category groups are included (have `Category`). Same behavior as today.

## Edge Cases

- Group with only `Gender` and no other fields: classified as `distance` tier
- All three flags false: no result pages shown, only summary
- Race with no `Category`-level groups: only overall and/or distance groups available
- `Gender` value "Female/Male" (non-binary): treated the same as any other gender value
