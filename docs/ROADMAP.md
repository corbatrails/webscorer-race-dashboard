# Race Dashboard Feature Roadmap

> Status: **In progress** · Owner: maintainers · Last updated: 2026-11-02
>
> This is the strategic roadmap for the next stage of race-day use. The original
> platform and refactor roadmap is complete; its delivered phases are recorded
> below. This document tracks outcomes and decision gates, not implementation
> tasks. Each feature follows the repository's design-spec and implementation-
> plan workflow before code work begins.

The successor outcomes are tracked in [GitHub epic #96](https://github.com/corbatrails/webscorer-race-dashboard/issues/96)
and its five child issues.

## North Star

Make the race dashboard a dependable race-day tool with one coherent operator
site for progress, results, configuration, and live-data health, alongside a
clear kiosk-first display for spectators. Make deployment simpler without
committing prematurely to a particular container or timing-reader architecture.

## Guiding principles

- **One operator site.** Progress, results, admin, and observability share
  navigation and a consistent visual language.
- **Actionable progress.** A progress count should lead directly to the racers
  represented by that count.
- **Protect official results.** Race-control workflows may navigate and filter;
  they do not edit the timing system's source-of-record results.
- **Local by default.** Operational observability stays on the race network; no
  third-party telemetry is planned.
- **Validate deployment boundaries.** Preserve editable configuration and
  secrets when evaluating containers, and keep the TV display kiosk-first.
- **Discover before committing.** RFID ingestion and product separation depend
  on hardware and operational facts that are not yet known.

## Current foundation

- `app.py` serves the TV dashboard, results, race control, API, and admin from
  one Flask application.
- `race-control` contains lap progress and results views. It is read-only;
  settings and race selection are managed through the password-protected
  `/admin` page.
- `providers/` defines an ingestion boundary that normalizes WebScorer and CSV
  data into a shared `RaceSnapshot`.
- The app exposes refresh, freshness, and error state that can support an
  operator-facing observability view.
- `start.sh` and `start.ps1` support local and kiosk startup. Issue [#60](https://github.com/corbatrails/webscorer-race-dashboard/issues/60)
  remains open for a recommended Pi image and boot-time startup support.
- Direct RFID ingestion is not yet scoped to a specific reader, protocol, or
  SDK.

## Successor roadmap

The sequence below reflects the selected priority order. It is a sequencing
preference; individual specifications should record only genuine technical
dependencies.

### 1. [Unified operator site](https://github.com/corbatrails/webscorer-race-dashboard/issues/101)

**Status: Planned.**

Bring lap progress, results, admin settings, and observability together behind
shared operator navigation and layout conventions. Use consistent theme,
typography, controls, and status treatments throughout the app, including
shared visual primitives in the TV display. Preserve the display's
kiosk-first layout and keep admin writes authenticated and CSRF-protected.

**Exit criteria:** Operators can move among progress, results, and admin
through common navigation. Core layout and interaction patterns are consistent
in supported color schemes and screen sizes. The TV remains legible and usable
in kiosk mode.

### 2. [Progress-to-results drill-down](https://github.com/corbatrails/webscorer-race-dashboard/issues/100)

**Status: Planned.**

Make progress views interactive:

- Clicking a distance label opens all results for that distance.
- Clicking a progress cell opens only the exact status/lap cohort represented
  by its current count.
- Provide a clear way to remove the filter and return to all results.

**Exit criteria:** Each interactive count leads to the correct current cohort.
Empty cohorts, finished/DNF/DNS states, and changing poll data do not produce
misleading results.

### 3. [Admin observability](https://github.com/corbatrails/webscorer-race-dashboard/issues/98)

**Status: Planned.**

Add a local operational dashboard inside the authenticated admin experience.
Reuse current last-refresh, stale/error, source, and race state before adding
new metrics. The feature spec should determine which additional in-process
measures are useful, such as poll duration or consecutive failures. Integrate
the existing manual-refresh path rather than adding a second one.

**Exit criteria:** An operator can distinguish waiting-for-first-data,
healthy, stale, and failing states, and see the selected source/race, last
successful update, data age, and current error when present without inspecting
server logs. No telemetry leaves the device.

### 4. [Docker feasibility and deployment](https://github.com/corbatrails/webscorer-race-dashboard/issues/97)

**Status: Discovery planned.**

**Related issue:** [#60](https://github.com/corbatrails/webscorer-race-dashboard/issues/60)
for the remaining Pi image and boot-time startup work.

Prototype a containerized run of the existing app. Validate image build,
runtime user and port, credentials, writable/persistent configuration,
health-check behavior, fixture-backed operation, and whether Chromium/kiosk
belongs in the container or remains a host responsibility. Use the results to
decide whether to publish a supported Compose example or keep a documented
container workflow.

**Exit criteria:** A fixture-backed run needs no live credentials and
preserves admin configuration edits across container restarts. The deployment
recommendation covers Pi/kiosk and non-kiosk use and accounts for the remaining
scope of [#60](https://github.com/corbatrails/webscorer-race-dashboard/issues/60). Keep #60 open until its Pi image and startup requirements are
resolved; do not create a duplicate issue for them.

### 5. [Direct RFID and product-boundary discovery](https://github.com/corbatrails/webscorer-race-dashboard/issues/99)

**Status: Discovery planned.**

Identify the relevant timing reader and access to its documentation or SDK.
Determine whether it provides complete results, timing events, or raw reads;
whether data is polled or streamed; and what networking, clock, reconnect,
offline, licensing, and security constraints apply. Compare an adapter in the
current provider registry with a separate ingestion process or product.
Assess whether a standalone operator/control binary or a separate display
product solves an evidenced deployment need.

**Exit criteria:** Produce a go/no-go recommendation and, only if suitable
reader details and access are available, a small contract prototype. Do not
commit to full integration, binary packaging, or product separation without
that evidence.

## Tracking and workflow

- A GitHub epic tracks the successor roadmap, with child issues for the five
  outcomes above. Existing issue #60 is related to the Docker/deployment
  outcome; it remains open for its unresolved scope.
- Child issues represent independently deliverable outcomes or bounded
  discovery, not individual coding steps or commits.
- Each feature gets an approved design spec and implementation plan before
  implementation. Small task checklists remain in those plans.
- Update this roadmap as outcomes ship; link each outcome to its tracking
  issue.

## Completed: Platform and refactor roadmap

The previous five-phase roadmap is complete. These changes established the
foundation for the successor work:

1. **Normalize to a single filterable racer list** — shipped in v1.18.0;
   issue #68, PR #74. The flat `RaceSnapshot` and projections live in
   `normalizer.py` and `data_processing.py`.
2. **Config split** — shipped in v1.17.0; issue #69, PR #73. Non-secret
   configuration lives in `config.yaml`; secrets remain in `.env`.
3. **Provider abstraction** — issue #70, PR #77. WebScorer and CSV adapters
   implement the shared provider contract.
4. **Live config hot-reload** — issue #71, PR #76. `ConfigWatcher` applies
   valid configuration changes without restarting.
5. **Password-protected admin UI** — issue #72, PR #81. The admin supports
   authenticated settings edits and race switching.

Issues #14 (lap race support) and #67 (the original platform/refactor epic)
were closed as resolved after their requested phases/features shipped. The
roadmap above focuses on the next product outcomes rather than repeating
completed work.
