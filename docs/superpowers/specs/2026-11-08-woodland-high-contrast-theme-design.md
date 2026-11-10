# Bootstrap Woodland theme design

## Intent

Use Bootstrap 5.3.8 as the visual foundation for the whole race dashboard, with the Paddock Woodland palette across staff pages and rotating TV screens. Make the light palette the default for new installations so event staff can use the dashboard in bright outdoor conditions.

## Goals

- Apply one Woodland design to the rotating dashboard, Race Progress, Detailed Results, Winner Announcements, Admin, and Admin login.
- Use Bootstrap components and utilities for shared page structure and common components, while retaining custom CSS for TV-specific layout and sizing.
- Keep both light and dark schemes. Default new installations to light and preserve an explicit dark selection.
- In the light palette, target at least 7:1 contrast for meaningful text and at least 3:1 for meaningful dividers and progress indicators. Verify colors against their actual surfaces. Maintain WCAG AA contrast for the dark palette and semantic status colors.
- Keep the chosen top navigation, compact flat cards, warm ivory, cream, forest, and olive colors. Avoid decorative colored edge stripes, pill-shaped controls, and oversized rounded panels. Do not rely on color alone to communicate race status.
- Preserve existing routes, data, page rotation, scrolling, filters, settings, and interactions.

## Non-goals and limits

- Do not change authentication, routing, race-data behavior, or configuration options other than changing the default value of `color_scheme`.
- Do not use a CDN or add Bootstrap JavaScript. Self-host the Bootstrap CSS so the Admin Content Security Policy remains effective.
- Do not add automatic light sensing or claim that color contrast ratios guarantee sunlight readability.
- Retain custom TV CSS where Bootstrap does not support the fixed viewport, dynamic lap grid, or dashboard-specific controls.
- Preserve the user's existing uncommitted `config.yaml` changes, including `color_scheme: light`.
- Confirm readability on the installed TV at the venue, from the expected viewing distance and under the actual glare conditions.

## Approaches

1. **Use Bootstrap across all pages, with custom TV layout CSS (selected).** This matches the user's preference for one foundation throughout the app. It gives staff and TV screens common Bootstrap components and theme variables, but the fixed-size TV dashboard still needs custom CSS for its layout and `vh` typography.
2. **Keep the existing CSS foundation and update shared palette tokens.** This is a smaller change and avoids Bootstrap migration work, but does not establish Bootstrap as the foundation across the app.

## Design

### Bootstrap integration

- Pin Bootstrap CSS to version 5.3.8 and store the distributed stylesheet under `static/vendor/`, recording the version and license alongside the existing vendor metadata.
- Load the local stylesheet from every applicable page. Do not request assets from a CDN. Bootstrap JavaScript is not needed for this work.
- Use Bootstrap navigation, cards, tables, progress bars, badges, lists, forms, buttons, grid and spacing utilities where they fit.
- Keep the existing page-specific CSS for layout and behavior that Bootstrap does not provide.
- Keep the configured `color_scheme` and Bootstrap's `data-bs-theme` in sync. The implementation may use one as the source of truth, but the dashboard, staff pages, Admin, and Admin login must all render the same configured mode.

### Woodland palette

Use the approved outdoor-light preview as the starting point:

| Token | Light | Dark |
|---|---|---|
| Page background | `#F2F0E5` | `#171D18` |
| Card background | `#FFFDF6` | `#252E25` |
| Navigation background | `#E6EADC` | `#202820` |
| Main text | `#20281F` | `#F3F0E5` |
| Muted text | `#424C3E` | `#B0B6A7` |
| Primary forest/sage accent | `#374F2D` | `#9AAF78` |
| Divider | `#7B8474` | `#6B786C` |
| Progress track | `#D0D8C4` | `#3B4637` |

These are starting colors, not permission to skip contrast checks. The dark divider was raised from the preview's `#39443A` to `#6B786C` so meaningful card boundaries reach 3:1. Check primary, secondary, warning, error, success, podium, muted text, and table states against the surfaces where each appears. In light mode, preserve the mockup's verified minimums: 7.35:1 for text, 3.18:1 for separators, and 6.17:1 for progress fill against its track. Revise any semantic color that misses its target.

### TV dashboard constraints

The rotating dashboard builds its markup in `static/dashboard.js` and fills a viewport without scrolling. Keep custom CSS for `vh` typography and spacing, dynamic lap columns and scale, the demographics 2-by-2 grid, fixed-width result columns, chart sizing, waiting state, page dots, finisher toasts, and pause indicator.

Bootstrap class names can collide with existing dashboard styles. Replace or namespace conflicting classes rather than relying on load order. In particular, rename the dashboard's `.toast` and pause-indicator `.visible` state classes when introducing Bootstrap.

### Security and accessibility

The Admin Content Security Policy permits same-origin assets only, so every stylesheet must remain local. Preserve the existing semantic controls, visible keyboard focus, and status text. Give progress widgets appropriate accessible labels and values; do not communicate DNF, DNS, DSQ, or podium status by color alone.

## Acceptance and verification

- All listed pages use the local Bootstrap 5.3.8 stylesheet and the Woodland palette. The Admin and login pages load without CSP violations or external requests.
- The new-install `color_scheme` default is light, and explicitly configured dark mode remains available and synchronized across pages. Update `OPTIONS`, the committed default in `config.yaml`, the README options table, config display, and focused tests as required by the repository's configuration rules. Preserve the user's original `config.yaml` changes in the path-scoped stash until all planned commits are complete.
- Contrast tests or focused assertions verify the targets above for both modes and meaningful component states.
- Existing routes, result content, pagination/rotation, filtering, Admin behavior, and mobile layouts remain unchanged.
- Run focused tests, then the suite relevant to configuration and templates. Start the app using a temporary configuration outside the repository and fixture data; inspect every dashboard view and each staff/Admin page in both modes at representative viewport sizes.
- Report the physical TV check as outstanding until someone verifies the display under the tent in the actual event conditions.
