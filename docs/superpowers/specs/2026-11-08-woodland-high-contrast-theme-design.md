# Bootstrap Woodland theme design

## Intent

Use Bootstrap 5.3.8 as the visual foundation for staff pages and rotating TV screens. Give event staff a high-contrast Woodland palette for outdoor viewing while keeping the original Light and Dark palettes available.

## Goals

- Share the same Bootstrap layouts across all four themes on the rotating dashboard, Race Progress, Detailed Results, Winner Announcements, Admin, and Admin login.
- Use Bootstrap components and utilities for shared page structure and common components, while retaining custom CSS for TV-specific layout and sizing.
- Default to Woodland Light when no theme is configured. Keep explicit `light` and `dark` selections on the original palettes.
- Target at least 7:1 for meaningful text in Woodland Light and 4.5:1 in Woodland Dark, including semantic status text. Target at least 3:1 for meaningful dividers and progress indicators in both Woodland palettes. Verify colors against their actual surfaces.
- Keep the chosen top navigation and compact, flat cards. Use warm ivory, cream, forest, and olive for Woodland. Avoid decorative colored edge stripes, pill-shaped controls, and oversized rounded panels. Do not rely on color alone to communicate race status.
- Preserve existing routes, data, page rotation, scrolling, filters, settings, and interactions.

## Non-goals and limits

- Do not change authentication, routing, race-data behavior, or configuration options beyond the choices and default for `color_scheme`.
- Do not use a CDN or add Bootstrap JavaScript. Self-host the Bootstrap CSS so the Admin Content Security Policy remains effective.
- Do not add automatic light sensing or claim that color contrast ratios guarantee sunlight readability.
- Retain custom TV CSS where Bootstrap does not support the fixed viewport, dynamic lap grid, or dashboard-specific controls.
- Do not restore pre-Bootstrap layouts with the classic themes or automatically rewrite saved theme selections.
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
- Set `data-theme` to the configured palette ID and `data-bs-theme` to its Bootstrap mode. The palette sets the app and Bootstrap colors; the mode keeps Bootstrap and native controls in light or dark mode.

### Theme selection

Admin's **Theme** selector sets the existing `color_scheme` option:

| Label | `color_scheme` | Bootstrap mode | Palette |
|---|---|---|---|
| Light | `light` | `light` | Original light |
| Dark | `dark` | `dark` | Original dark |
| Woodland Light | `woodland-light` | `light` | High-contrast Woodland (default) |
| Woodland Dark | `woodland-dark` | `dark` | Dark Woodland |

Saved `light` and `dark` values select the original colors. Select the corresponding Woodland option to keep the earthy colors from the initial Woodland rollout. Choose Woodland when higher contrast matters; the classic palettes do not target Woodland's contrast thresholds.

Admin applies the theme after a successful save, and Admin login uses the active theme when rendered. `/api/data` reports both `color_scheme` and `color_mode`; open operator and TV pages apply both on their next fetch, including switches between palettes with the same mode.

### Woodland palettes

| Token | Woodland Light | Woodland Dark |
|---|---|---|
| Page background | `#F2F0E5` | `#171D18` |
| Card background | `#FFFDF6` | `#252E25` |
| Navigation background | `#E6EADC` | `#202820` |
| Main text | `#20281F` | `#F3F0E5` |
| Muted text | `#424C3E` | `#B0B6A7` |
| Primary forest/sage accent | `#374F2D` | `#9AAF78` |
| Divider | `#7B8474` | `#6B786C` |
| Progress track | `#D0D8C4` | `#3B4637` |

The Woodland Dark divider is lighter than the preview's `#39443A` so meaningful card boundaries reach 3:1. Check text, status colors, table states, and progress fill against the surfaces where each appears.

### TV dashboard constraints

The rotating dashboard builds its markup in `static/dashboard.js` and fills a viewport without scrolling. Keep custom CSS for `vh` typography and spacing, dynamic lap columns and scale, the demographics 2-by-2 grid, fixed-width result columns, chart sizing, waiting state, page dots, finisher toasts, and pause indicator.

Bootstrap class names can collide with existing dashboard styles. Replace or namespace conflicting classes rather than relying on load order. In particular, rename the dashboard's `.toast` and pause-indicator `.visible` state classes when introducing Bootstrap.

### Security and accessibility

The Admin Content Security Policy permits same-origin assets only, so every stylesheet must remain local. Preserve the existing semantic controls, visible keyboard focus, and status text. Give progress widgets appropriate accessible labels and values; do not communicate DNF, DNS, DSQ, or podium status by color alone.

## Acceptance and verification

- All listed pages use the local Bootstrap 5.3.8 stylesheet and the selected palette. The Admin and login pages load without CSP violations or external requests.
- A missing `color_scheme` and the shipped `config.yaml` both use `woodland-light`. All four palette choices persist through Admin and render with the correct Bootstrap mode. Open operator and TV pages follow saves on the next fetch; operator pages retain the current view, filters, and selection.
- Contrast tests or focused assertions verify the Woodland targets above and meaningful component states.
- Existing routes, result content, pagination/rotation, filtering, Admin behavior, and mobile layouts remain unchanged.
- Verify defaults, Admin saves, and live switches with focused tests. Use fixture data and a temporary configuration outside the repository to inspect all four palettes on staff and TV pages at representative viewport sizes.
- Report the physical TV check as outstanding until someone verifies the display under the tent in the actual event conditions.
