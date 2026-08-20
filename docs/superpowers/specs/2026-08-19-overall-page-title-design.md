# Overall Page Title — Design

## Problem

Overall result pages currently use only the distance name as their title. This
does not make it explicit that the page contains overall results.

## Solution

When `build_pages` creates a page for an overall-tier category, prefix its
existing name with `Overall - `. For example, an overall group named
`Mid Course (45 miles)` becomes `Overall - Mid Course (45 miles)`.

Category-tier page titles remain unchanged. If an overall group has no distance
name and its existing name is `Overall`, the title remains `Overall` rather
than becoming `Overall - Overall`.

## Implementation

The title formatting belongs in `data_processing.py` at the page-building
boundary, where the category tier and name are already available. The frontend
already renders the page `title`, so no frontend changes are required.

## Testing

Add focused `build_pages` assertions covering:

- an overall page with a distance name receives the `Overall - ` prefix;
- an overall page without a distance remains `Overall`;
- category page titles remain unchanged.

Run the data-processing tests and the full test suite after implementation.

## Scope

This change affects display titles only. It does not alter grouping, filtering,
sorting, podium styling, or the summary page.