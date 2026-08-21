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

The implementation should sort each result group by numeric `Place` before pages are built
because WebScorer API rows can arrive in bib order. Category-placement enrichment may add
`CategoryPlace` to Overall racers, but it must not cause Overall pages to be sorted by
category placement.

## Visual Emphasis

Detailed Overall pages should de-emphasize Overall leaders when the race does not award an
Overall podium. Overall placement remains visible and remains the sort key, but medal icons
and gold/silver/bronze coloring should apply to the `Cat Place` cell for category places
1-3. This makes the award signal match what racers and spectators care about: category
podiums.

The existing `PINNED_LEADERS_ON_OVERALL_RESULTS` setting continues to control whether
Overall pages pin leaders. It must not be required for detailed Overall pages to show
category-placement medal styling. Category pages keep their existing medal treatment on
the `Place` column.

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

Result pages should only enter the rotation when they have at least one displayable row:
a finished time, `DNS`, `DNF`, or `DSQ`. Registered racers with blank time or `-` are in
progress and should not make an Overall or category result page appear. This rule applies
to Overall and category pages in both standard and detailed layouts.

Two optional toggles can include in-progress rows in result pages before racers have a
displayable result:

```text
DISPLAY_UNFINISHED_IN_CATEGORY=false
DISPLAY_UNFINISHED_IN_OVERALL=false
```

Both default to `false`. When `DISPLAY_UNFINISHED_IN_CATEGORY=true`, category pages may
enter the rotation and display racers whose `Time` is blank or `-`. When
`DISPLAY_UNFINISHED_IN_OVERALL=true`, Overall pages may do the same. The toggles are
independent so an event can show unfinished rows for one result-page tier without showing
them for the other.

The summary page is separate from this filtering and remains controlled only by
`SHOW_SUMMARY`. A race with no displayable result rows may still show the summary page
because it contains useful registration and progress information. When a refresh makes a
previously empty result page eligible, the page should join the rotation on the next
natural advance; the current page should not be interrupted just because eligibility
changed.

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
- Overall racer rows are sorted by numeric Overall `Place`, even when API rows arrive in
  bib order and category placement order differs from overall placement order.

Manual frontend verification should cover:

- Category pages render `Place | Bib | Name | Time | Team`.
- Overall pages in standard mode render `Place | Bib | Name | Time | Team`.
- Overall pages in detailed mode render `Overall | Bib | Name | Time | Cat Place |
  Category | Gender | Team`.
- Result pages with only blank or `-` times are skipped while the summary page remains
  governed by `SHOW_SUMMARY`.
- When `DISPLAY_UNFINISHED_IN_CATEGORY` or `DISPLAY_UNFINISHED_IN_OVERALL` is enabled,
  the matching page tier can display unfinished rows and enter rotation before results
  arrive.
- Newly eligible result pages join the rotation after data refresh without interrupting
  the currently displayed page.
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
- Changes to result ordering beyond sorting each result group by its own numeric `Place`.
- Changes to time calculation or status classification.
- Changes to which Overall/category pages are shown.
- Changes to podium toast behavior.
- Adding a JavaScript test framework.