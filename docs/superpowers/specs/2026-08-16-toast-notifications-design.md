# Toast Notifications When Racers Finish

## Problem

During a live race with 200-550 racers, spectators viewing the dashboard on a TV/projector have no real-time indication when new finishers cross the line between 60-second poll intervals.

## Solution

Show toast notifications at the bottom-center of the screen when new finishers are detected between polls. Category podium finishers (1st/2nd/3rd) always get individual toasts with medal accents. All other finishers are summarized in a single count toast.

## Behavior

- Compare previous finisher set vs current on each 60s poll
- Category podium finishers (Place 1/2/3 on a `tier: "category"` page) always get individual toasts
- Non-podium finishers get a single batch toast (e.g. "11 racers finished since last update")
- First poll after page load: silently establish baseline, no toasts
- Toasts auto-dismiss after 5 seconds
- Max ~4 toasts visible simultaneously (podium toasts stack, batch toast below)

## Toast Format

**Individual podium toast (compact one-liner):**
```
🥇 Jane Doe — 1st Women 40-49 (25K)
🥈 John Smith — 2nd Men 30-39 (50K)
🥉 Alex Chen — 3rd Open (25K)
```

**Batch summary toast:**
```
11 racers finished since last update
```

## Visual Design

- Position: fixed bottom-center, above progress dots
- Container: `flex-direction: column-reverse` so podium toasts appear above batch
- Toast style: semi-transparent dark background, rounded corners, ~2.5vh font
- Podium accents: left border in gold/silver/bronze for places 1/2/3
- Animation: CSS fade-in on appear, fade-out before removal
- `pointer-events: none` so toasts don't block interaction

## Data Flow

**Backend (minimal change):**
- Add `tier` field (`"overall"` or `"category"`) to each page in `build_pages()`
- Add `show_toasts` config option (default `true`), passed through `/api/data`

**Frontend (all detection logic):**
1. Maintain a `Set` of previously-seen finished Bib numbers
2. On each poll, scan all pages' racers → collect currently finished Bibs
3. Diff against the known set → new finisher Bibs
4. First poll: populate the set silently, no toasts
5. For each new finisher, scan `tier: "category"` pages to find if Place is 1/2/3
6. Show individual toasts for podium finishers; single count toast for the rest
7. Update known set

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SHOW_TOASTS` | `true` | Enable/disable finish notifications |

## Scope

- No sound/audio
- No persistent notification history
- No user interaction with toasts (dismiss, click-through)
