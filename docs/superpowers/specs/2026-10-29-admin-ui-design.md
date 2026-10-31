# Phase 5: Password-Protected Admin UI

## Intent

Give a trusted race-day operator a phone-friendly way to choose the active race
and edit dashboard settings without reaching the terminal or restarting the
dashboard. A saved race or display-setting change should reach the TV by the
next polling cycle.

## Goals

- Add a password-protected `/admin` page using one shared `ADMIN_PASSWORD`
  secret from `.env`. An unset password disables admin access.
- Let the operator choose a WebScorer race and edit every non-secret setting
  from `config.yaml`.
- Apply valid changes to the running dashboard, including `source`, `race_id`,
  and `data_file`; reject invalid changes while retaining the last working race
  and settings.
- Start the server without a configured race and show a waiting state. Offer
  race selection through both `/admin` and the terminal when an interactive
  terminal is available; accept the first valid selection.
- Use `config.yaml` as the sole source of non-secret settings. `.env` and
  process environment variables provide secrets only.
- Make local demos and UI functional checks reproducible using fixture data and
  a temporary configuration file.
- Protect writes with CSRF validation, use security headers, and never expose
  secrets in HTML or API responses.

## Non-goals

- TLS, individual accounts, roles, password reset, or protection against a
  hostile network. The page is for a trusted LAN; the README must state this
  threat model and recommend network isolation.
- Changing the dashboard's existing data model or visual result pages.
- Editing secrets through the admin page.

## Constraints

- Flask, Jinja templates, PyYAML and pytest are already used. Avoid adding
  dependencies unless needed to preserve the existing configuration file.
- `config.py` has a central `OPTIONS` registry and `ConfigWatcher`; `app.py`
  polls through the selected provider and exposes dashboard data through
  `/api/data`.
- The current watcher deliberately holds `source`, `race_id` and `data_file`
  at startup. The current startup path prompts for a race when `race_id` is
  missing.
- Tests and fixture data live under `tests/`; fixture-backed app runs do not
  need live credentials.
- `start.sh` and `start.ps1` must remain behaviorally equivalent if either is
  changed.

## Approaches

1. **Concurrent terminal and UI selection (chosen).** Start the server in a
   waiting state and offer the existing race prompt without blocking the web
   server. Accept the first valid selection from the terminal or admin UI,
   close the terminal prompt, and continue console logging. Preserve live
   switching through the admin UI after startup selection.
2. **UI-only initial selection.** Start in a waiting state and select the race
   through `/admin`. This supports headless startup but removes the terminal
   selection workflow the operator wants to keep.
3. **Treat source/race/file changes as restart-only.** This preserves the
   current watcher contract but does not let the operator switch races from a
   phone while the TV is running.

## Decisions

| Topic | Decision | Rationale |
|---|---|---|
| Startup race state | Resume a valid saved `race_id` from YAML across app restarts. If it is unset for live WebScorer input, start the server and show a waiting message. Offer a terminal race prompt when stdin is interactive, alongside selection through `/admin`. Skip the prompt for a saved race or file-backed input. | Preserves configured startup, terminal operation, and unattended fixture runs without blocking access to the UI. |
| First startup selection | Coordinate CLI and UI selection through one shared, atomic selection/write path. The first valid selection that saves succeeds; reject stale submissions from the other startup selector instead of overwriting the winner. Persist either selection to the active YAML file. After startup selection, allow subsequent UI race changes. | Keeps the two interfaces from racing to select different initial races and keeps YAML authoritative. |
| Terminal prompt lifetime | No clock-based timeout. End the prompt when the CLI selects a race or the UI selects one, then continue normal console logging. Cancel pending terminal input without leaving a blocked reader that could consume later input. On EOF or unavailable stdin, stop prompting and leave the server available in its waiting state. | Matches the requested selection-driven timeout and supports Windows, Linux, and non-interactive launches. |
| Environment configuration | Remove environment overrides for non-secret `OPTIONS`. Resolve non-secret values from `config.yaml`, then built-in defaults. Keep WebScorer credentials and `ADMIN_PASSWORD` in `.env` / process environment. | Makes the settings the operator sees and edits authoritative. |
| Temporary config | Add `--config <path>` to `app.py`; use the same path for initial load, watcher reads and admin writes. Default remains the repository's `config.yaml`. | Keeps fixtures and exploratory edits isolated from the committed configuration. |
| Runtime race changes | Treat `source`, `race_id` and `data_file` as reloadable. Accept a valid configured race ID without a preflight API fetch; immediately clear the previous race's cached data and show a waiting-for-results screen while the poller fetches the new race. If the fetch fails, remain on the selected race in the waiting/error state and retry on the normal polling cadence. | Switching should not be blocked by an extra API request or a temporary outage; clearing the cache prevents old-race results from being shown under the new selection. |
| Race list | Fetch race choices from the provider selected in the form after an authenticated request, including when it differs from the running source. The browser receives only race identifiers and display metadata, never credentials. | Reuses the provider's existing race-list interface without adding an unauthenticated route. |
| No selected WebScorer race | Do not fetch race results; keep the API in a waiting state with empty pages until a race is selected. Allow race-list requests for the terminal selector and authenticated admin UI. | Avoids invalid results requests while supporting both selection interfaces. |
| Provider-specific controls | Expose `source` and `data_file` for both providers; WebScorer supports an offline JSON file and CSV requires a file. Show the race selector for live WebScorer input. Changing the source updates the race control and file guidance. | Preserves the existing offline WebScorer workflow and the full supported configuration surface. |
| CSV/offline mode | Continue to use `source: csv` and `data_file` from YAML. A relative `data_file` path resolves against the process working directory, preserving current behavior. A temporary YAML can point at a checked-in fixture. | Supports offline development and demos without environment overrides or live credentials while preserving existing path semantics. |
| Authentication | Shared password login backed by Flask's signed session cookie and a per-process random signing key. Compare submitted and configured passwords with `hmac.compare_digest`; set `HttpOnly`, `SameSite=Lax`, and no `Secure` attribute because the documented deployment is HTTP on a LAN. | Minimal authentication consistent with the no-TLS deployment; restarting invalidates sessions. |
| CSRF and headers | Require a per-session CSRF token on all state-changing requests. Add at least `X-Content-Type-Options`, `X-Frame-Options`, a restrictive `Content-Security-Policy`, and `Referrer-Policy`; do not set HSTS for HTTP-only deployment. | Protects browser-originated writes and reduces common web attack surfaces without claiming transport security. |
| YAML save behavior | Write atomically to the active config path, preserving unrelated/unknown YAML keys and, if reasonably supported without disproportionate complexity, comments. Validate the complete candidate before replacing the file. | Avoids partial files and unintended deletion of settings; preserves operator edits. |
| Error presentation | Keep invalid form values on the page with field-level validation messages. Do not write invalid values or replace the active config. | Makes correction practical on a phone and keeps the TV stable. |
| Rule updates | Update the `.env.example` rule to include `ADMIN_PASSWORD` among secrets, and change the UI-testing rule from `DATA_FILE` environment injection to a temporary config passed with `--config`. | The implementation introduces a new secret and deliberately removes non-secret environment overrides. |

## Admin behavior

- At startup with no configured live WebScorer race, start the web server and
  show its address before offering the terminal race prompt. Keep the prompt
  readable without hiding errors. Accept valid terminal input until either
  selector saves a race; close the prompt and continue console logging once
  that happens. Do not impose a time limit.
- Use a shared startup selection guard for terminal and UI submissions. A
  losing startup submission must not overwrite the selected race. Show the
  selected race in the UI and discard pending terminal input. Later UI
  changes use the normal runtime switching flow.
- With `ADMIN_PASSWORD` unset, `/admin` is disabled and writes are unavailable.
- With a password configured, unauthenticated visitors see a login form. A
  successful login gets a session; logout clears it.
- The authenticated form exposes every non-secret key in `OPTIONS`, including
  provider, race/file selection, timing, layout, visibility and color options.
  Secret values and secret environment variable names are not returned.
- For WebScorer, the race control offers races from `list_races`. Selecting a
  valid ID updates `race_id` without a preflight fetch. For CSV, the operator
  edits `data_file`; switching to WebScorer enables the race selector.
- Validation is server-side regardless of browser constraints. Unknown YAML
  keys are retained but not presented as editable settings. A save is all or
  nothing.
- On an accepted change to the race/source/file, clear race-specific cached
  results, show waiting state, and wake the poller immediately. If fetching the
  selected race fails, keep the new selection and show the existing error
  information with the waiting state; retry on the configured poll cadence.
  The frontend must reset race-specific finish/toast tracking when the race
  changes so the new race's existing finishers are not announced as new
  finishers.
- The active config and watcher must use the same path, including when started
  with `--config`.

## Testing and local use

- Unit tests cover configuration precedence/removal, validation, atomic writes,
  config-path threading, authentication, constant-time password checking,
  session/logout, CSRF, headers, secret non-disclosure, race-list access,
  failed-save behavior, and runtime switch/cache reset.
- App tests cover startup with and without a saved race, fixture-backed CSV
  polling, CLI-first and UI-first startup selections, concurrent selection
  attempts, prompt cancellation without leftover stdin readers, EOF /
  non-interactive startup, immediate WebScorer race changes and cache clearing,
  and waiting / error behavior while the newly selected race cannot be fetched.
- UI functional verification runs the app with a temporary YAML setting
  `source: csv` and `data_file` to a fixture under `tests/fixtures`, then
  inspects the admin page and dashboard in a browser. It must not overwrite
  committed `config.yaml` or use live credentials when fixtures suffice.
- Tests use temporary config files and fake providers / fixture inputs; they
  do not need a real WebScorer account or network.

## Documentation and affected surfaces

- `config.py`: remove non-secret env names and legacy `.env` overrides/warnings;
  support complete candidate validation and config-path-aware watching.
- `app.py`: parse `--config`; start the server alongside a cancellable terminal
  race prompt; coordinate first-valid startup selection with the admin UI;
  handle no-race waiting state and immediate runtime switches.
- `templates/` and `static/`: add responsive admin/login UI and reset client
  race-specific finish notifications after a race change.
- `config.yaml`: continue listing every non-secret option and its default.
- `README.md`: remove env override/precedence instructions, document
  `ADMIN_PASSWORD`, admin operation, LAN-only threat model and fixture-based
  local testing with `--config`.
- `.env.example`: list only `WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`, and
  `ADMIN_PASSWORD`.
- `.github/instructions/project-rules.instructions.md`: revise the relevant
  secrets-only and fixture-testing rules.
- `tests/`: replace non-secret env override expectations with config-only
  behavior and cover the admin/runtime-switch contract.
- `start.sh` and `start.ps1` are unchanged unless config argument forwarding is
  necessary; if either changes, both remain equivalent.

## Left to the implementation plan

Choose the smallest route and form structure that supports the behaviors above.
Prefer existing Flask/Jinja and browser-side patterns, avoid unnecessary
dependencies, and keep auth and config-write code narrowly scoped. Split
implementation into logical commits: configuration source cleanup and
`--config`, waiting state/live source switching, admin security and form, then
documentation and browser verification.
