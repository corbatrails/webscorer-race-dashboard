# Overall Results Layout Design

## Problem

Overall result pages currently use the same five-column table as category result pages:
`Place`, `Bib`, `Name`, `Team`, and `Time`. That layout is useful, but it does not answer
the award-context question spectators and racers often care about while viewing overall
results: "What did this racer place in their category?"

The new layout should make overall results easier to scan by keeping racer recognition and
time near the front of the row, then showing category placement and category context. The
layout must support non-binary registration data without mapping or normalizing gender;
the dashboard should display the API `Gender` value as-is.

## Goals

- Add a configurable detailed layout for Overall-tier result pages.
- Reorder the shared standard result columns to put `Time` before `Team`.
- Preserve category pages as five-column result pages.
- Enrich Overall rows with category placement by joining against category result groups.
- Display API-provided `Gender` values verbatim, including `X`, blank, or future values.
- Keep the implementation compatible with 1080p dashboard display constraints.

## Configuration

Add a new environment-backed setting:

```text
OVERALL_RESULTS_LAYOUT=standard
```

Supported values:

| Value | Behavior |
| --- | --- |
| `standard` | Overall pages use the standard five-column result layout. |
| `detailed` | Overall pages use the detailed Overall result layout with category context. |

The default is `standard`. Unknown values should fall back to `standard` so a typo does
not break dashboard rendering.

Per project convention, `.env` and `.env.example` must contain the same property names.
When this setting is implemented, both files must be updated together.

## Column Layouts

The standard result layout is used by category pages and by Overall pages when
`OVERALL_RESULTS_LAYOUT=standard`:

```text
Place | Bib | Name | Time | Team
```

This intentionally reorders the existing shared columns from `Place | Bib | Name | Team |
Time` so all result tables follow the same scan pattern: placement, racer identity,
performance, then metadata.

The detailed Overall layout is used only for Overall-tier pages when
`OVERALL_RESULTS_LAYOUT=detailed`:

```text
Overall | Bib | Name | Time | Cat Place | Category | Gender | Team
```

`Overall` is the same value currently shown as `Place` on Overall pages. `Cat Place` is
the racer's placement within their category result group. `Category`, `Gender`, and
`Team` are displayed from the API racer row without gender mapping or value conversion.

## Sorting

Result pages should remain sorted by the placement value that defines the current page.
Overall pages are sorted by Overall placement, even when the detailed layout also shows
`Cat Place`. Category pages are sorted by category placement. The detailed Overall layout
adds category context for recognition and award awareness; it must not regroup or reorder
the Overall page by category, gender, team, or category placement.

The implementation should preserve WebScorer's racer order within each result group.
Category-placement enrichment may add `CategoryPlace` to Overall racers, but it must not
sort or otherwise reorder any racer list.

## Data Enrichment

Sample API dumps show that Overall rows already include `Distance`, `Category`, `Gender`,
and `TeamName`. They do not include category placement. Category result groups contain the
same racers with `Place` representing category placement.

During `process_race_data`, build a category-placement lookup from category-tier groups,
then apply it to Overall-tier racers before pages are built.

Recommended lookup key:

```text
Distance + Category + Gender + Bib
```

String fields should be normalized only for matching stability: convert `None` to an empty
string and trim surrounding whitespace. Do not remap gender values. If WebScorer returns
`X`, the row should keep `X`; if it returns an empty value, the row should keep an empty
value.

For each matched Overall racer, add:

```text
CategoryPlace
```

If no category match is found, leave `CategoryPlace` empty or absent and render a blank
cell. Missing category-placement data should not hide the row or break the page.

The join must be distance-aware so a bib used in multiple distances does not receive a
category placement from the wrong race distance.

## Frontend Rendering

Refactor the result table rendering in `static/dashboard.js` from hardcoded five-column
HTML to column definitions. `renderCategory` should choose the columns once per page:

- Use detailed columns when `category.tier === "overall"` and
  `config.overallResultsLayout === "detailed"`.
- Use standard columns for all category pages and for Overall pages in standard mode.

The fixed header table, pinned table, and scrolling table must all use the same column
definition for a given page so headers stay aligned with rows. Existing pinned-leader and
podium-styling rules remain unchanged; the Overall podium toggle still controls whether
Overall leaders are pinned and medal-colored.

## Layout and Fit

The CSS currently assumes five fixed columns. Implementation should add layout-specific
classes or selectors for the standard and detailed result layouts.

Suggested 1080p starting point:

Standard layout:

```text
Place 7% | Bib 8% | Name 35% | Time 20% | Team 30%
```

Detailed Overall layout:

```text
Overall 8% | Bib 7% | Name 24% | Time 14% | Cat Place 9% | Category 22% | Gender 6% | Team 10%
```

Cells should retain the existing ellipsis behavior. Team is the least important detailed
column and may truncate first when space is tight.

## Testing and Verification

Backend tests should cover:

- `OVERALL_RESULTS_LAYOUT` defaults to `standard`.
- `OVERALL_RESULTS_LAYOUT=detailed` is exposed through `/api/data`.
- Unknown `OVERALL_RESULTS_LAYOUT` values fall back to `standard`.
- Overall racers receive `CategoryPlace` from matching category groups.
- Gender value `X` is preserved as-is.
- Blank or missing gender remains blank and does not prevent matching when the API data is
  otherwise consistent.
- Bibs are not cross-matched between distances.
- Missing category matches leave `CategoryPlace` blank or absent without errors.
- Overall racer order is preserved after category-placement enrichment, even when category
  placement order differs from overall placement order.

Manual frontend verification should cover:

- Category pages render `Place | Bib | Name | Time | Team`.
- Overall pages in standard mode render `Place | Bib | Name | Time | Team`.
- Overall pages in detailed mode render `Overall | Bib | Name | Time | Cat Place |
  Category | Gender | Team`.
- Header alignment remains correct for fixed headers, pinned rows, and scrolling rows.
- Detailed Overall pages remain readable at 1080p, with truncation favoring `Team` before
  core placement, identity, time, and category-placement information.

## Scope Boundaries

Included:

- Configuration and API response plumbing for `OVERALL_RESULTS_LAYOUT`.
- Category-placement enrichment in `data_processing.py`.
- Frontend column-definition rendering in `static/dashboard.js`.
- CSS width rules for standard and detailed result table layouts.
- Focused Python tests for configuration, API exposure, and enrichment behavior.

Excluded:

- Gender normalization or mapping.
- Changes to result ordering, time calculation, or status classification.
- Changes to which Overall/category pages are shown.
- Changes to podium toast behavior.
- Adding a JavaScript test framework.