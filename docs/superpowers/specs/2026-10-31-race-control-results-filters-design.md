# Race Control Results Filters Design

## Intent

Make it easier for race operators to identify participants still racing and inspect racers across distances in Race control Results.

## Goals and behavior

- Add an **Unfinished** filter that shows racers with status **On course** or **Not started** only.
- Add **All** as the first choice in the distance rail. It combines each distance's Overall racers without category duplicates and adds a Distance column to the combined table.
- Preserve each racer's place within their own distance; do not imply a cross-distance ranking.
- Keep the existing distance rail and filter-button layout shown in mockup A.

## Non-goals and constraints

- Do not change per-distance results, server data, or the race-control data contract.
- Do not add a combined cross-distance place order.
- Keep the existing initial selection behavior: the first concrete distance remains selected until the operator chooses All.

## Approaches

- **Browser-side aggregation (chosen):** combine existing per-distance Overall groups in the results view. This reuses current data and keeps the backend contract unchanged while preserving per-distance places.
- **Server-side aggregate group:** add a combined group to race-control data. This expands backend behavior and risks presenting a misleading shared place order.

## Remaining implementation decisions

Use the existing test and rendering patterns. Give the All choice a distinct internal key so it cannot collide with an actual distance, and show each source distance for rows in the combined table.
