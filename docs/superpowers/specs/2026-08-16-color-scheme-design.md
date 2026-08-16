# Configurable Light/Dark Mode Color Scheme

**Issue:** #39  
**Date:** 2026-08-16

## Overview

Add a `COLOR_SCHEME` environment variable that controls whether the dashboard renders in dark or light mode. The server passes the value to the template, which sets a `data-theme` attribute on `<body>`. CSS custom properties provide all theme-dependent colors.

## Architecture

```
.env (COLOR_SCHEME=dark|light)
  → config.py (reads + validates)
    → app.py (passes to template)
      → dashboard.html (<body data-theme="...">)
        → style.css (CSS vars resolve per theme)
        → dashboard.js (reads computed styles for chart colors)
```

## Changes

### 1. config.py

Add to `load_config()` return dict:

```python
"color_scheme": os.environ.get("COLOR_SCHEME", "dark").lower(),
```

Validate: if value not in `["dark", "light"]`, default to `"dark"`.

### 2. app.py

Pass `color_scheme` to the template render:

```python
return render_template("dashboard.html", cache_bust=_start_time,
                       color_scheme=app.config["dashboard"].get("color_scheme", "dark"))
```

### 3. templates/dashboard.html

```html
<body data-theme="{{ color_scheme }}">
```

### 4. static/style.css

Add variable definitions at the top of the file:

```css
[data-theme="dark"] {
  --bg-primary: #1a1a2e;
  --bg-card: #16213e;
  --bg-track: #0f3460;
  --text-primary: #ffffff;
  --text-body: #e0e0e0;
  --text-muted: #a0a0c0;
  --text-dim: #606080;
  --accent-primary: #00d4ff;
  --accent-secondary: #ff9f43;
  --border-color: #2a2a4a;
  --error-color: #ff6b6b;
  --row-even: #16213e;
}

[data-theme="light"] {
  --bg-primary: #f5f5f5;
  --bg-card: #ffffff;
  --bg-track: #e0e0e0;
  --text-primary: #1a1a2e;
  --text-body: #333333;
  --text-muted: #666666;
  --text-dim: #999999;
  --accent-primary: #0088cc;
  --accent-secondary: #e07000;
  --border-color: #dddddd;
  --error-color: #cc0000;
  --row-even: #f0f0f0;
}
```

Replace all hardcoded color values with corresponding variables:

| Hardcoded | Variable |
|-----------|----------|
| `#1a1a2e` (body bg) | `var(--bg-primary)` |
| `#16213e` (cards, even rows) | `var(--bg-card)` / `var(--row-even)` |
| `#0f3460` (progress track) | `var(--bg-track)` |
| `#ffffff` (titles) | `var(--text-primary)` |
| `#e0e0e0` (body text) | `var(--text-body)` |
| `#a0a0c0` (muted text) | `var(--text-muted)` |
| `#606080` (dim text) | `var(--text-dim)` |
| `#00d4ff` (accent/headers) | `var(--accent-primary)` |
| `#ff9f43` (secondary accent) | `var(--accent-secondary)` |
| `#2a2a4a` (borders) | `var(--border-color)` |
| `#ff6b6b` (errors/stale) | `var(--error-color)` |

Medal colors (`#ffd700`, `#c0c0c0`, `#cd7f32`) stay hardcoded — they are semantic (gold/silver/bronze), not theme-dependent.

### 5. static/dashboard.js

For the three hardcoded colors in JS (chart ticks, grid, "no results" text):

Read computed styles from `document.body`:

```javascript
var style = getComputedStyle(document.body);
var textMuted = style.getPropertyValue('--text-muted').trim();
var textDim = style.getPropertyValue('--text-dim').trim();
```

Use these in chart config and the inline "no results" style.

### 6. .env (documentation)

Add commented example:

```
# Optional: color scheme (dark or light, default: dark)
# COLOR_SCHEME=dark
```

## Testing

- `test_config.py`: Add test that `color_scheme` defaults to `"dark"`, and that invalid values fall back to `"dark"`.
- `test_app.py`: Add test that `data-theme` attribute is rendered in the HTML response with the configured value.
- Manual: visual check both themes render without broken colors.

## Out of Scope

- Browser-side toggle (config-only per user decision)
- Additional themes beyond dark/light
- Persisting preference in localStorage
