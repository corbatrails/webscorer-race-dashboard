# Event Name Header on All Screens — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the race/event name, date, sport, logo, and last-updated timestamp at the top of every dashboard screen (summary, category, waiting).

**Architecture:** Extract the summary-style header into a shared `renderEventHeader(data)` function in `dashboard.js`. Call it from `renderSummary()`, `renderCategory()`, and `renderWaiting()`. No backend or CSS changes needed.

**Tech Stack:** Vanilla JavaScript (ES5, IIFE pattern)

## Global Constraints

- No new dependencies
- Follow existing ES5 style (no arrow functions, no `let`/`const`, no template literals)
- All user-visible strings must be escaped via the existing `escapeHtml()` function
- No backend or CSS changes

---

### Task 1: Extract shared event header and apply to all screens

**Files:**
- Modify: `static/dashboard.js` — lines 149-160 (current `renderSummary` header), lines 187-195 (current `renderCategory` header), lines 138-147 (current `renderWaiting`)

**Step-by-step:**

- [ ] **Step 1: Add `renderEventHeader(data)` function**

Add this function after `renderWaiting()` and before `renderSummary()` (around line 148). It extracts the existing summary header markup:

```javascript
  function renderEventHeader(data) {
    var html = '<div class="summary-header">';
    html += '<img src="/static/logo.png" alt="Logo" onerror="this.style.display=\'none\'">';
    html += "<div>";
    html += '<div class="race-title">' + escapeHtml(data.race_name) + "</div>";
    html += '<div class="race-subtitle">' + escapeHtml(data.race_date) + " \u2022 " + escapeHtml(data.race_sport) + "</div>";
    html += "</div>";
    html += '<div class="summary-meta">Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</div>";
    html += "</div>";
    return html;
  }
```

- [ ] **Step 2: Update `renderSummary()` to use shared header**

Replace the inline header markup in `renderSummary()` with a call to `renderEventHeader(data)`. Change:

```javascript
    html += '<div class="summary-header">';
    html += '<img src="/static/logo.png" alt="Logo" onerror="this.style.display=\'none\'">';
    html += "<div>";
    html += '<div class="race-title">' + escapeHtml(data.race_name) + "</div>";
    html += '<div class="race-subtitle">' + escapeHtml(data.race_date) + " \u2022 " + escapeHtml(data.race_sport) + "</div>";
    html += "</div>";
    html += '<div class="summary-meta">Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</div>";
    html += "</div>";
```

To:

```javascript
    html += renderEventHeader(data);
```

- [ ] **Step 3: Update `renderCategory()` to include event header and remove duplicate "Last updated"**

In `renderCategory()`, add `renderEventHeader(data)` after the opening `<div class="page active">` and remove "Last updated" from `.category-meta`. Change:

```javascript
    var html = '<div class="page active">';

    html += '<div class="category-header">';
    html += '<div class="category-title">' + escapeHtml(category.title) + "</div>";
    html += '<div class="category-meta">';
    html += '<span>Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</span>";
    html += '<span>Category ' + (catIndex + 1) + " of " + categories.length + "</span>";
    html += "</div>";
    html += "</div>";
```

To:

```javascript
    var html = '<div class="page active">';

    html += renderEventHeader(data);

    html += '<div class="category-header">';
    html += '<div class="category-title">' + escapeHtml(category.title) + "</div>";
    html += '<div class="category-meta">';
    html += '<span>Category ' + (catIndex + 1) + " of " + categories.length + "</span>";
    html += "</div>";
    html += "</div>";
```

- [ ] **Step 4: Update `renderWaiting()` to include event header when data is available**

Change `renderWaiting(error)` signature to `renderWaiting(data)` so it can access race name. Update the function and its call site.

Change the function from:

```javascript
  function renderWaiting(error) {
    var html = '<div class="waiting-screen">';
    html += "<h1>No results yet</h1>";
    html += "<p>Waiting for race data\u2026 Dashboard will update automatically.</p>";
    if (error) {
      html += '<p class="error-message">' + escapeHtml(error) + "</p>";
    }
    html += "</div>";
    return html;
  }
```

To:

```javascript
  function renderWaiting(data) {
    var html = "";
    if (data && data.race_name) {
      html += renderEventHeader(data);
    }
    html += '<div class="waiting-screen">';
    html += "<h1>No results yet</h1>";
    html += "<p>Waiting for race data\u2026 Dashboard will update automatically.</p>";
    if (data && data.error) {
      html += '<p class="error-message">' + escapeHtml(data.error) + "</p>";
    }
    html += "</div>";
    return html;
  }
```

Update the call site in `renderCurrentPage()` from:

```javascript
      container.innerHTML = renderWaiting(lastData ? lastData.error : null);
```

To:

```javascript
      container.innerHTML = renderWaiting(lastData);
```

- [ ] **Step 5: Manual verification**

Run the app with `.\start.ps1` and verify:
1. Summary page looks identical to before (header comes from shared function)
2. Category pages show event header above the category name
3. Waiting screen shows event header after first data fetch (but not before)
4. "Last updated" no longer duplicated on category pages

- [ ] **Step 6: Run existing tests**

Run: `pytest tests/ -v`
Expected: All existing tests pass (no backend changes were made)

- [ ] **Step 7: Commit**

```bash
git add static/dashboard.js
git commit -m "feat: show event name header at top of all screens"
```
