# Canonical Operator Routes

## Approved intent

Give each staff page one descriptive canonical path. Normal top-navigation
clicks must stay in the current browser tab, including clicks from Admin.

| Destination | Canonical path |
|---|---|
| Race progress | `/progress` |
| Detailed results | `/race-results` |
| Winner announcements | `/announcements` |
| Admin | `/admin` |

## Approaches

The user selected flat paths over a common `/operator/` prefix. Flat paths
fit the existing Flask routes and leave Admin authentication URLs unchanged.
Reusing `/results` for detailed results would change existing announcement
bookmarks, so the user selected `/race-results` instead.

## Navigation and compatibility

- Redirect `/race-control?view=results` to `/race-results`; redirect missing,
  `progress`, or unknown legacy views to `/progress`.
- Redirect legacy `/results` to `/announcements`.
- Use canonical URLs in navigation and documentation. Canonical Progress and
  detailed-results paths determine the view, without a `view` query parameter.
- Keep Progress and detailed results in their existing shared template.
  Switching between them in-page updates the path and active link, retaining
  filters and selection. Keep unrelated query parameters and fragments when
  switching, but remove obsolete `view` parameters.
- Normal navigation to announcements or Admin loads that destination in the
  same tab. Remove automatic new-tab targets from all top links.
- Preserve explicit browser gestures such as Ctrl-click rather than forcing
  them into the in-page switch.

## Unsaved Admin settings

Warn before leaving Admin with unsaved settings, using the browser's standard
leave-page prompt. Compare current named settings controls with their initial
values, including checkbox/select changes and programmatic race selections.
Restoring the original values removes the warning. Saving and explicitly
choosing Discard changes bypass the warning.

## Constraints and verification

Keep Admin authentication and CSRF protection, read-only public staff pages,
the TV dashboard, and API routes unchanged. Add no dependencies or configuration
options. Preserve the user's existing `config.yaml` edits.

Cover redirects, exact active-link mapping, same-tab link attributes, path
synchronization, and unsaved-change behavior with tests. Inspect the running
fixture-backed app in a browser using temporary configuration outside the repo.
