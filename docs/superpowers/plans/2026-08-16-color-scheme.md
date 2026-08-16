# Configurable Color Scheme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `COLOR_SCHEME` environment variable that switches the dashboard between dark and light themes.

**Architecture:** Server reads `COLOR_SCHEME` from `.env`, validates it, passes it to the Jinja template which sets `data-theme` on `<body>`. CSS custom properties define all theme colors; selectors resolve based on `data-theme`. JS reads computed styles for chart colors.

**Tech Stack:** Python/Flask, Jinja2, CSS custom properties, Chart.js

## Global Constraints

- `COLOR_SCHEME` accepts only `"dark"` or `"light"`; invalid values default to `"dark"`
- Medal colors (`#ffd700`, `#c0c0c0`, `#cd7f32`) remain hardcoded (semantic, not theme-dependent)
- No structural/layout changes — only color substitutions
- All tests run with `pytest`

---

### Task 1: Config and Template Plumbing

**Files:**
- Modify: `config.py`
- Modify: `app.py`
- Modify: `templates/dashboard.html`
- Modify: `.env`
- Test: `tests/test_config.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `config["color_scheme"]` (string, `"dark"` or `"light"`)
- Produces: `<body data-theme="...">` attribute in rendered HTML

- [ ] **Step 1: Write failing test for config**

Add to `tests/test_config.py`:

```python
@patch("config.load_dotenv")
def test_color_scheme_default(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.delenv("COLOR_SCHEME", raising=False)
    cfg = load_config()
    assert cfg["color_scheme"] == "dark"


@patch("config.load_dotenv")
def test_color_scheme_light(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("COLOR_SCHEME", "light")
    cfg = load_config()
    assert cfg["color_scheme"] == "light"


@patch("config.load_dotenv")
def test_color_scheme_invalid_falls_back_to_dark(mock_dotenv, monkeypatch):
    monkeypatch.setenv("WEBSCORER_API_ID", "123")
    monkeypatch.setenv("WEBSCORER_API_TOKEN", "abc")
    monkeypatch.setenv("COLOR_SCHEME", "neon")
    cfg = load_config()
    assert cfg["color_scheme"] == "dark"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v -k "color_scheme"`
Expected: KeyError on `cfg["color_scheme"]`

- [ ] **Step 3: Implement config change**

In `config.py`, add to the return dict in `load_config()`:

```python
color_scheme_raw = os.environ.get("COLOR_SCHEME", "dark").lower()
```

And in the return dict:

```python
"color_scheme": color_scheme_raw if color_scheme_raw in ("dark", "light") else "dark",
```

- [ ] **Step 4: Run config tests to verify they pass**

Run: `pytest tests/test_config.py -v -k "color_scheme"`
Expected: all 3 PASS

- [ ] **Step 5: Write failing test for template attribute**

Add to `tests/test_app.py`:

```python
def test_index_includes_data_theme(client):
    response = client.get("/")
    assert b'data-theme="dark"' in response.data
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_app.py::test_index_includes_data_theme -v`
Expected: FAIL (attribute not present yet)

- [ ] **Step 7: Implement app.py and template changes**

In `app.py`, update the `index()` route:

```python
@app.route("/")
def index():
    color_scheme = app.config["dashboard"].get("color_scheme", "dark")
    return render_template("dashboard.html", cache_bust=_start_time, color_scheme=color_scheme)
```

In `templates/dashboard.html`, change:

```html
<body data-theme="{{ color_scheme }}">
```

- [ ] **Step 8: Update test fixture to include color_scheme**

In `tests/test_app.py`, add `"color_scheme": "dark"` to the `test_config` dict in the `app` fixture.

- [ ] **Step 9: Run all tests**

Run: `pytest tests/test_config.py tests/test_app.py -v`
Expected: all PASS

- [ ] **Step 10: Add .env comment**

Add to `.env`:

```
# Optional: color scheme (dark or light, default: dark)
# COLOR_SCHEME=dark
```

- [ ] **Step 11: Commit**

```bash
git add config.py app.py templates/dashboard.html .env tests/test_config.py tests/test_app.py
git commit -m "feat(config): add COLOR_SCHEME env var with template plumbing (#39)"
```

---

### Task 2: CSS Variable Definitions and Refactor

**Files:**
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `data-theme` attribute on `<body>` (from Task 1)
- Produces: CSS custom properties available to all elements

- [ ] **Step 1: Add variable definitions at top of style.css**

Insert after the `* { ... }` reset block, before the `body` rule:

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

- [ ] **Step 2: Replace hardcoded colors with variables**

Apply these substitutions throughout `style.css`:

| Find | Replace |
|------|---------|
| `background: #1a1a2e` | `background: var(--bg-primary)` |
| `background: #16213e` | `background: var(--bg-card)` |
| `background: #0f3460` | `background: var(--bg-track)` |
| `color: #ffffff` | `color: var(--text-primary)` |
| `color: #e0e0e0` | `color: var(--text-body)` |
| `color: #a0a0c0` | `color: var(--text-muted)` |
| `color: #606080` | `color: var(--text-dim)` |
| `color: #00d4ff` | `color: var(--accent-primary)` |
| `color: #ff9f43` | `color: var(--accent-secondary)` |
| `color: #ff6b6b` | `color: var(--error-color)` |
| `border-bottom: 2px solid #2a2a4a` | `border-bottom: 2px solid var(--border-color)` |
| `border-bottom: 1px solid #2a2a4a` | `border-bottom: 1px solid var(--border-color)` |
| `border-bottom: 2px solid #00d4ff` | `border-bottom: 2px solid var(--accent-primary)` |
| `background: #2a2a4a` (progress dot) | `background: var(--border-color)` |
| `background: #00d4ff` (active dot) | `background: var(--accent-primary)` |

Do NOT replace: `#ffd700`, `#c0c0c0`, `#cd7f32` (medal colors).

- [ ] **Step 3: Verify dark mode looks identical**

Run the app with `COLOR_SCHEME=dark` (or unset) and visually confirm no changes.

- [ ] **Step 4: Verify light mode renders correctly**

Set `COLOR_SCHEME=light` in `.env` and visually confirm all elements have readable contrast.

- [ ] **Step 5: Commit**

```bash
git add static/style.css
git commit -m "feat(css): define theme variables and replace hardcoded colors (#39)"
```

---

### Task 3: Chart.js Theme Colors

**Files:**
- Modify: `static/dashboard.js`

**Interfaces:**
- Consumes: CSS custom properties on `document.body` (from Task 2)

- [ ] **Step 1: Replace hardcoded colors in chart config**

Near the top of the chart rendering function, read computed styles:

```javascript
var style = getComputedStyle(document.body);
var textMuted = style.getPropertyValue('--text-muted').trim();
```

Replace in the Chart.js options:

```javascript
ticks: { color: textMuted, font: { size: 14 } },
grid: { color: textMuted + "33" },  // 20% opacity via hex alpha
```

- [ ] **Step 2: Replace inline "no results" color**

Change the inline style in the "No results yet" paragraph:

```javascript
html += '<p style="font-size:3vh;color:var(--text-dim);text-align:center;margin-top:10vh">No results yet</p>';
```

- [ ] **Step 3: Verify chart renders in both themes**

Test with `COLOR_SCHEME=dark` and `COLOR_SCHEME=light` — chart axes and grid lines should match the theme.

- [ ] **Step 4: Commit**

```bash
git add static/dashboard.js
git commit -m "feat(chart): use theme variables for chart colors (#39)"
```

---

### Task 4: Final Verification and Cleanup

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS

- [ ] **Step 2: Test both themes end-to-end**

Start app with `COLOR_SCHEME=dark`, verify all pages. Switch to `COLOR_SCHEME=light`, restart, verify all pages.

- [ ] **Step 3: Final commit (if any remaining changes)**

```bash
git status
# If clean, nothing to do. Otherwise commit any missed files.
```
