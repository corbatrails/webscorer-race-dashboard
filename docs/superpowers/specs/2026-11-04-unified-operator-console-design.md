# Unified Race-Director Console Design

**Roadmap:** Successor roadmap epic #96, first priority issue #101. Related
issues: #98 (admin observability) and #100 (progress-to-results drill-down).

The [canonical routes design](2026-11-06-canonical-operator-routes-design.md)
supersedes the URLs below. The [Woodland theme design](2026-11-08-woodland-high-contrast-theme-design.md)
defines the shared layouts and four palette choices.

## Intent

Give race directors one connected console for race progress, detailed results,
winner announcements, settings, and observability, with a consistent way to
move between those screens. Keep read-only race views on a staff-restricted
race network or in a staff-only location. Protect Admin and Observability with
the existing password login. The TV dashboard remains separate and
kiosk-first.

## Goals and behavior

- Keep `/race-control` and `/results` read-only and available without login.
  Deploy them only on a race network or at a location restricted to race staff.
- Require the existing `ADMIN_PASSWORD` login for `/admin` and the
  observability screen added by #98.
- Reuse `/admin/login`, the existing session, and the existing password; do
  not introduce accounts, roles, or another credential. After login, return
  the visitor to the requested protected in-app screen when possible. A login
  without a requested destination opens Admin, matching the current behavior.
- Make every director screen reachable through the same horizontal top
  navigation on Progress, Results, Admin, and Observability pages. It must
  distinguish:
  - Race progress and the detailed, categorized results view hosted as two
    views under `/race-control`.
  - The separate `/results` winner-announcement page.
  - Admin settings at `/admin`.
  - Observability, added to the navigation when #98 supplies its page; do not
    show a dead or disabled placeholder before then.
- Keep a visible active state for the current destination. Navigation to the
  two `/race-control` views must select the requested view, including on direct
  load and refresh.
- Show all implemented director destinations in the shared navigation,
  including links to protected pages for logged-out visitors.
- Provide a logout action in the shared navigation when an authenticated
  session exists, using the existing CSRF-protected behavior. After logout,
  Admin and Observability require login again; Progress and Results remain
  available.
- Apply a consistent visual language to console headers, navigation,
  typography, controls, status messages, focus states, and spacing in both
  configured color schemes. Keep each page's data-specific layout and
  interaction intact.
- Keep navigation usable at supported screen sizes. On narrow screens it may
  compact or collapse, but all destinations must remain available to keyboard
  and touch users without clipping or obscuring the page content.
- Preserve existing race data, refresh cadence, result ordering, filters,
  settings behavior, and the read-only status of race-control views.

## Non-goals

- Adding the observability page itself; #98 owns that work. This feature only
  establishes a navigation pattern that #98 can extend.
- Adding navigation, operator controls, or authentication to the TV dashboard
  at `/`. It remains directly accessible for kiosk use.
- Protecting or changing the shared `/api/data` and `/api/refresh` behavior.
  The TV dashboard uses these endpoints, and they expose no admin credentials.
- Editing official timing-system results, changing provider behavior, or
  changing the existing data contracts.
- Redesigning race tables, winner presentation, or the TV dashboard beyond
  what is necessary to apply shared visual primitives consistently.
- Adding new configuration options, dependencies, users, roles, TLS, or
  password-management features.

## Constraints

- The app uses Flask, Jinja templates, vanilla JavaScript, and CSS. Prefer
  these existing tools and the shared theme variables in `static/theme.css`.
- `ADMIN_PASSWORD` is optional. When unset, the app disables Admin and
  Observability while continuing to serve Progress, Results, and the TV
  display at `/`.
- The app does not verify that a person viewing `/race-control` or `/results`
  belongs to race staff. The deployment must restrict those pages to a
  staff-only network or location.
- Admin writes remain authenticated and CSRF-protected. The shared navigation
  must not weaken that boundary.
- `race_control.html` combines progress and detailed results in separate
  views. `/results` is a distinct, read-only winner-announcement page. Keep
  their purposes clear rather than merging their data or behavior.
- `theme.css` already provides dark and light color tokens, but each page has
  its own template and page-specific stylesheet. The console should reuse
  shared primitives without changing kiosk styling accidentally.

## Approaches

1. **Shared horizontal top navigation (chosen).** Put the same compact
   navigation on every director screen and show the logout action when a
   session is authenticated. This fits the small number of destinations,
   matches the existing top-header pattern in Race control, and preserves
   horizontal room for progress grids and result tables. Adapt it for narrow
   screens without hiding destinations from keyboard or touch users.
2. **Persistent left sidebar.** A left rail keeps every destination visible
   and frees vertical space. It reduces the width available to progress grids
   and result tables, and it requires a mobile drawer. The user chose the top
   navigation.

## Decisions

| Topic | Decision | Rationale |
|---|---|---|
| Console access | Keep `/race-control` and `/results` read-only and unauthenticated on a race-staff-restricted network or at a staff-only location. Protect `/admin` and the observability page from #98 with the existing login. | The user chose to rely on staff-only location for read-only pages and use login for settings and observability. |
| Login and session | Reuse `/admin/login`, `ADMIN_PASSWORD`, and the current authenticated session. Return to a safe in-app destination after login; default to Admin when there is no destination. | Preserves the existing credential and redirect behavior. |
| Navigation layout | Use a shared horizontal top navigation on all director pages. Show logout when the visitor has an authenticated session. | The user selected this layout; it provides direct links while preserving table width. |
| Results destinations | Keep Race control's detailed results view separate from `/results`, the winner-announcement page, and label both clearly in navigation. | They serve different workflows and already have distinct content and behavior. |
| Navigation destinations | Show every implemented director destination in the shared navigation, including Admin and Observability links for logged-out visitors. Add Observability when #98 implements its page; do not show a placeholder. | Keeps staff screens reachable from one navigation bar. |
| Protected links | Send a logged-out visitor who selects Admin or Observability to `/admin/login`; return the visitor to that destination after a successful login. | Keeps protected pages visible without weakening their access checks. |
| Staff-only placement | Deploy the unauthenticated read-only Progress and Results pages only where race staff control access. | The user chose to rely on the race-staff-only location for these pages. |
| Observability | Require the existing login when #98 adds the page. | The user chose to keep #101 focused while leaving room for #98 to extend the navigation. |
| TV display | Leave `/` public and kiosk-first with no operator navigation. | The TV display is not a director screen and must remain usable without login. |
| API access | Leave `/api/data` and `/api/refresh` access unchanged. | The TV display depends on these endpoints; the login does not change the shared data API. |
| No password configured | Keep Admin and Observability unavailable, consistent with the existing disabled-admin behavior. Keep Progress and Results available on the staff-only network or location. | Matches the existing optional-admin configuration while retaining the read-only screens. |
| Page-specific UI | Keep existing data views and page interactions; share only the console shell and visual primitives. | Improves consistency without expanding into the separate result-drill-down or TV redesign work. |

## Access and navigation requirements

- Keep `/race-control` and `/results` available without login. Their deployment
  must restrict access to race staff; the app does not enforce that location
  or network boundary.
- When a logged-out user requests `/admin` or Observability, send the user to
  `/admin/login`. Return to the requested destination only when it points
  inside this app; reject external return URLs.
- A successful login without a return destination opens Admin, preserving the
  current behavior. A failed login leaves the visitor unauthenticated and on
  the login screen.
- When `ADMIN_PASSWORD` is unset, return the existing disabled-admin response
  from `/admin/login`, `/admin`, and Observability. Keep Progress, Results,
  and the root TV route available.
- The shared navigation provides distinct destinations for Race progress,
  detailed Race control results, winner announcements, and Admin. The
  Observability destination appears only after #98 provides a real page.
- Show the same navigation on all director pages. A logged-out visitor who
  selects Admin or Observability must pass through the login flow before
  viewing that page.
- A navigation selection for Race progress or detailed results must select
  that view within `/race-control` and remain selected on a direct load or
  refresh. The implementation may use a route or URL state, provided it
  supports direct navigation.
- Show the active destination visually and semantically. Keep every navigation
  link and the logout action keyboard accessible, with visible focus treatment.
- The logout action uses the existing POST endpoint and CSRF token. Logging
  out clears the shared session; later Admin and Observability requests must
  require login. Progress and Results remain available.
- The API endpoints remain outside this screen-level access change. Do not
  imply that `/api/data` or `/api/refresh` is protected by the console login.

## Visual and responsive requirements

- Reuse the configured dark/light theme and existing shared CSS variables.
- Define shared console treatments for navigation, headings, links, buttons,
  form controls, focus, active state, and notices/statuses. Avoid duplicating
  slightly different global styles in each page.
- Keep page-specific data layouts intact: Race control remains optimized for
  live progress and detailed tables; winner announcements retain their
  presentation layout; Admin retains its settings form.
- At narrow widths, the navigation must remain operable and must not force
  horizontal page overflow or hide critical race data. The implementation plan
  may choose the smallest accessible compact-menu or wrapping behavior.
- The shared console shell must not impose its navigation or sizing on the TV
  dashboard.

## Acceptance and verification

- Without login, staff can still open `/race-control` and `/results` from the
  staff-restricted race location. Logged-out requests to `/admin` and
  Observability require login.
- After login, staff can move among Race progress, detailed Race control
  results, winner announcements, Admin, and Observability once #98 provides it.
- After login, return the visitor to the requested protected in-app
  destination. Reject an invalid or external return destination.
- Logging out from any director screen clears the session. Subsequent Admin
  and Observability requests require login, while Progress and Results remain
  available. Existing CSRF checks for login, logout, and settings writes
  continue to pass.
- With no admin password, Admin and Observability remain disabled. Progress,
  Results, and `/` remain available.
- Every authenticated page shows the same navigation and visual system in
  dark and light themes. The TV dashboard has no console navigation.
- Race progress, detailed results, winner announcements, and admin settings
  retain their current page-specific behavior.
- A fixture-backed local run can verify the screens without WebScorer
  credentials. Use a temporary YAML configuration and fixture data; do not
  overwrite `config.yaml`.
- Verify desktop and narrow-screen layouts, visible focus, active navigation
  state, and keyboard/touch access to every destination.

## Affected surfaces

- `admin.py`: reuse the existing authenticated-session and CSRF mechanisms
  for Admin, Observability, and shared logout.
- `app.py`: expose shared navigation on Progress and Results, route protected
  Admin and Observability links through login, and preserve the public TV route
  and shared API.
- `templates/`: add a shared console navigation/layout fragment to all
  director pages; keep the login screen and TV template outside that shell.
- `static/`: add shared console styles while preserving page-specific
  stylesheets and the TV dashboard's kiosk behavior.
- `tests/test_admin.py`, `tests/test_app.py`, and `tests/test_race_control.py`:
  cover route access, login/return behavior, logout, shared navigation, theme,
  and unchanged kiosk/API access.
- `README.md`: identify the staff-only deployment boundary for Progress and
  Results, document the Admin and Observability login requirement, describe
  the shared navigation, and distinguish the public TV display.
- No change to `config.py`, `config.yaml`, `.env.example`, or provider/data
  contracts is expected.

## Left to the implementation plan

Choose the smallest shared Jinja structure and route guard that meet these
requirements. Decide how the two Race control views are represented in URLs
and how the top navigation adapts to narrow screens. Keep implementation
changes focused on the Admin and Observability access boundary, shared
navigation, and shared visual primitives. Document the staff-only deployment
assumption for Progress and Results; do not add the #98 observability page or
alter the TV/API behavior.
