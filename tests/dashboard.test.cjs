// Runs static/dashboard.js in a stub DOM. Only Node built-ins: `node --test tests/dashboard.test.cjs`.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SOURCE = fs.readFileSync(path.join(__dirname, "..", "static", "dashboard.js"), "utf8");

function escapeText(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function makeElement(tag) {
  const el = {
    tagName: tag,
    children: [],
    parentNode: null,
    className: "",
    dataset: {},
    style: {},
    offsetHeight: 0,
    scrollHeight: 0,
    clientHeight: 0,
    _text: null,
    _html: "",
    classList: {
      add() {},
      remove() {},
    },
    appendChild(child) {
      child.parentNode = el;
      el.children.push(child);
      return child;
    },
    removeChild(child) {
      el.children = el.children.filter((c) => c !== child);
      child.parentNode = null;
      return child;
    },
    getAttribute() {
      return null;
    },
    get textContent() {
      if (el._text !== null) return el._text;
      return el.children.map((c) => c.textContent).join("");
    },
    set textContent(value) {
      el.children = [];
      el._text = String(value);
    },
    get innerHTML() {
      if (el.children.length) return el.children.map((c) => escapeText(c.textContent)).join("");
      return el._text !== null ? escapeText(el._text) : el._html;
    },
    set innerHTML(value) {
      el.children = [];
      el._text = null;
      el._html = String(value);
    },
  };
  return el;
}

function startDashboard() {
  const dashboard = makeElement("div");
  const toastContainer = makeElement("div");
  const elements = { dashboard, "toast-container": toastContainer };
  const requests = [];
  const timers = [];

  const document = {
    body: makeElement("body"),
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    createElement: makeElement,
    createTextNode: (text) => ({ textContent: String(text), parentNode: null }),
    addEventListener(type, fn) {
      if (type === "keydown") keydown = fn;
    },
  };
  let keydown = null;

  const context = {
    document,
    console: { error() {}, log() {}, warn() {} },
    fetch(url) {
      return new Promise((resolve, reject) => requests.push({ url, resolve, reject }));
    },
    setTimeout(fn, ms) {
      timers.push({ fn, ms, done: false });
      return timers.length;
    },
    clearTimeout(id) {
      if (timers[id - 1]) timers[id - 1].done = true;
    },
    requestAnimationFrame: () => 0,
    cancelAnimationFrame() {},
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    Chart: function Chart() {
      this.destroy = function () {};
    },
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context);

  async function settle() {
    for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r));
  }

  return {
    dashboard,
    toastContainer,
    requests,
    settle,
    pendingTimers: () => timers.filter((t) => !t.done).map((t) => t.ms),
    async respond(index, payload) {
      requests[index].resolve({ ok: true, json: () => Promise.resolve(payload) });
      await settle();
    },
    async fail(index) {
      requests[index].reject(new Error("network down"));
      await settle();
    },
    // Press an arrow key, which re-fetches before changing page.
    async press(key) {
      keydown({ key, preventDefault() {} });
      await settle();
      return requests.length - 1;
    },
    // Fire the pending poll timer, starting the next /api/data request.
    async poll() {
      const timer = timers.find((t) => !t.done && /scheduleNextFetch/.test(String(t.fn)));
      assert.ok(timer, "a poll is scheduled");
      timer.done = true;
      timer.fn();
      await settle();
      return requests.length - 1;
    },
  };
}

function racer(bib, name, place, time) {
  return { Bib: String(bib), Name: name, Place: String(place), Time: time };
}

function payload({ generation = 1, raceName = "Race A", finishers = [], waiting = false, configVersion = 1,
                   selectionRequired = false, adminEnabled = false, error = null } = {}) {
  const racers = finishers.map((bib, i) => racer(bib, `${raceName} Rider ${bib}`, i + 1, `0:${10 + i}:00`));
  return {
    race_name: waiting ? "" : raceName,
    race_date: "2026-10-30",
    race_sport: "Mountain bike",
    last_refresh: "12:00",
    waiting,
    error,
    pages: waiting ? [] : [{ type: "category", tier: "overall", title: `${raceName} Overall`, racers }],
    summary_display_time: 999,
    scroll_speed: 40,
    scroll_pause_time: 999,
    pinned_leaders: 3,
    show_summary: false,
    show_demographics: false,
    show_toasts: true,
    refresh_interval: 11,
    config_version: configVersion,
    race_generation: generation,
    race_selection_required: selectionRequired,
    admin_enabled: adminEnabled,
  };
}

test("race generation change clears old page and toasts", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1, 2] }));
  await d.respond(await d.poll(), payload({ finishers: [1, 2, 3] }));
  assert.ok(d.toastContainer.children.length > 0, "new finisher toasted");
  assert.match(d.dashboard.innerHTML, /Race A/);

  await d.respond(await d.poll(), payload({ generation: 2, waiting: true }));
  assert.equal(d.toastContainer.children.length, 0);
  assert.doesNotMatch(d.dashboard.innerHTML, /Race A/);
});

test("waiting does not seed the finisher baseline", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  await d.respond(await d.poll(), payload({ generation: 2, waiting: true }));
  await d.respond(await d.poll(), payload({ generation: 2, waiting: true, error: "timeout" }));
  await d.respond(await d.poll(), payload({ generation: 2, raceName: "Race B", finishers: [7, 8, 9] }));
  assert.equal(d.toastContainer.children.length, 0, "existing finishers of the new race stay silent");
  assert.match(d.dashboard.innerHTML, /Race B/);

  await d.respond(await d.poll(), payload({ generation: 2, raceName: "Race B", finishers: [7, 8, 9, 10] }));
  assert.equal(d.toastContainer.children.length, 1);
  assert.match(d.toastContainer.children[0].textContent, /1 racer finished/);
});

test("display setting changes keep the same-race baseline", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1, 2] }));
  await d.respond(await d.poll(), payload({ configVersion: 2, finishers: [1, 2, 3] }));
  assert.equal(d.toastContainer.children.length, 1, "finisher after a settings change still toasts");
});

test("overlapping fetches cannot apply an older response after a newer one", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  const older = await d.poll();
  const newer = await d.press("ArrowRight");
  assert.notEqual(older, newer);

  await d.respond(newer, payload({ generation: 2, raceName: "Race B", finishers: [5] }));
  assert.match(d.dashboard.innerHTML, /Race B/);
  await d.respond(older, payload({ finishers: [1, 2] }));
  assert.match(d.dashboard.innerHTML, /Race B/);
  assert.doesNotMatch(d.dashboard.innerHTML, /Race A/);
  assert.equal(d.toastContainer.children.length, 0);
});

test("no race selected points the operator to the admin page when enabled", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ waiting: true, selectionRequired: true, adminEnabled: true }));
  assert.match(d.dashboard.innerHTML, /No race selected/);
  assert.match(d.dashboard.innerHTML, /href="\/admin"/);
});

test("no race selected without admin points to the terminal or config file", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ waiting: true, selectionRequired: true }));
  assert.match(d.dashboard.innerHTML, /No race selected/);
  assert.doesNotMatch(d.dashboard.innerHTML, /\/admin/);
  assert.match(d.dashboard.innerHTML, /config\.yaml/);
});

test("a failed fetch while waiting shows an error and keeps polling", async () => {
  const d = startDashboard();
  await d.fail(0);
  assert.match(d.dashboard.innerHTML, /Can.t reach the dashboard server/);
  await d.respond(await d.poll(), payload({ finishers: [1] }));
  assert.match(d.dashboard.innerHTML, /Race A/);
});

function lapData(name5k = "5K", onLap1 = 1) {
  return {
    totals: { registered: 8, dns: 1, not_started: 1, on_course: onLap1, finished: 3, dnf: 2, dsq: 0, started: 6 },
    distances: [
      { name: "25K", lap_count: 2, registered: 6, dns: 1, not_started: 1, started: 4, on_course: onLap1,
        on_course_by_lap: [onLap1, 0], dnf_by_lap: [0, 1], dnf_without_crossing: 1, finished: 1, dnf: 2, dsq: 0 },
      { name: name5k, lap_count: 1, registered: 2, dns: 0, not_started: 0, started: 2, on_course: 0,
        on_course_by_lap: [0], dnf_by_lap: [0], dnf_without_crossing: 0, finished: 2, dnf: 0, dsq: 0 },
    ],
  };
}

function lapPayload({ show = true, lap = lapData(), ...rest } = {}) {
  const p = payload({ finishers: [1], ...rest });
  if (p.waiting) return { ...p, show_lap_overview: show };
  const summary = { type: "summary", title: "Summary", data: {
    total_racers: 8, total_finished: 3, total_dns: 1, total_dnf: 2, total_dsq: 0, distance_stats: [], categories: [] } };
  return {
    ...p,
    show_summary: true,
    show_lap_overview: show,
    pages: [summary, { type: "lap_overview", title: "Lap Overview", data: lap }, ...p.pages],
  };
}

const dotCount = (html) => (html.match(/progress-dot\b/g) || []).length;

test("lap overview stays out of the rotation when the toggle is off", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload({ show: false }));
  assert.equal(dotCount(d.dashboard.innerHTML), 2);
  for (let i = 0; i < 3; i++) {
    await d.respond(await d.press("ArrowRight"), lapPayload({ show: false }));
    assert.doesNotMatch(d.dashboard.innerHTML, /lap-overview-page/);
  }
});

test("lap overview follows Summary and dwells for summary_display_time", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload());
  assert.equal(dotCount(d.dashboard.innerHTML), 3);
  assert.match(d.dashboard.innerHTML, /summary-page/);

  await d.respond(await d.press("ArrowRight"), lapPayload());
  assert.match(d.dashboard.innerHTML, /lap-overview-page/);
  assert.ok(d.pendingTimers().includes(999 * 1000), "dwell timer uses summary_display_time");

  await d.respond(await d.press("ArrowRight"), lapPayload());
  assert.match(d.dashboard.innerHTML, /Race A Overall/);
});

test("a settings change adds and removes the lap overview at once", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload({ show: false }));
  await d.respond(await d.poll(), lapPayload({ show: true, configVersion: 2 }));
  assert.equal(dotCount(d.dashboard.innerHTML), 3);
  await d.respond(await d.poll(), lapPayload({ show: false, configVersion: 3 }));
  assert.equal(dotCount(d.dashboard.innerHTML), 2);
});

test("a race switch clears the lap overview before the new race renders", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload());
  await d.respond(await d.press("ArrowRight"), lapPayload());
  assert.match(d.dashboard.innerHTML, /lap-overview-page/);

  await d.respond(await d.poll(), lapPayload({ generation: 2, waiting: true }));
  assert.doesNotMatch(d.dashboard.innerHTML, /lap-overview-page|25K/);
});

test("lap overview renders cells, DNF notes, and non-applicable laps", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload());
  await d.respond(await d.press("ArrowRight"), lapPayload());
  const html = d.dashboard.innerHTML;
  assert.equal((html.match(/class="lap-cell-dnf">1 DNF<\/div>/g) || []).length, 2);
  assert.doesNotMatch(html, /last recorded|no crossing recorded|DNF on lap/);
  assert.match(html, /no lap 2/);
  assert.match(html, /Not Started/);
  assert.doesNotMatch(html, /lap-help|Registered =|not GPS|lap-row-meta/);
  assert.match(html, /lap-row-name">25K<\/div><\/div>/);
});

test("lap overview combines DNF notes in the first lap cell", async () => {
  const d = startDashboard();
  const lap = lapData();
  lap.distances[0].dnf_by_lap = [1, 0];
  await d.respond(0, lapPayload({ lap }));
  await d.respond(await d.press("ArrowRight"), lapPayload({ lap }));
  assert.match(d.dashboard.innerHTML, /class="lap-cell-dnf">2 DNF<\/div>/);
  assert.equal((d.dashboard.innerHTML.match(/class="lap-cell-dnf"/g) || []).length, 1);
});

test("lap overview escapes distance names", async () => {
  const d = startDashboard();
  const lap = lapData("<b>5K</b>");
  await d.respond(0, lapPayload({ lap }));
  await d.respond(await d.press("ArrowRight"), lapPayload({ lap }));
  assert.match(d.dashboard.innerHTML, /&lt;b&gt;5K&lt;\/b&gt;/);
  assert.doesNotMatch(d.dashboard.innerHTML, /<b>5K/);
});

test("a poll refreshes the active lap overview without restarting its dwell", async () => {
  const d = startDashboard();
  await d.respond(0, lapPayload());
  await d.respond(await d.press("ArrowRight"), lapPayload());
  const dwellTimers = d.pendingTimers().filter((ms) => ms === 999 * 1000).length;

  await d.respond(await d.poll(), lapPayload({ lap: lapData("5K", 7) }));
  assert.match(d.dashboard.innerHTML, /lap-overview-page/);
  assert.match(d.dashboard.innerHTML, /lap-cell-count">7</);
  assert.equal(d.pendingTimers().filter((ms) => ms === 999 * 1000).length, dwellTimers);
});

test("lap overview shrinks rows to fit many distances instead of hiding them", async () => {
  const d = startDashboard();
  const base = lapData();
  const many = { ...base, distances: Array.from({ length: 12 }, (_, i) => ({ ...base.distances[1], name: `D${i + 1}` })) };
  await d.respond(0, lapPayload({ lap: many }));
  await d.respond(await d.press("ArrowRight"), lapPayload({ lap: many }));
  const html = d.dashboard.innerHTML;
  assert.match(html, /D12/);
  assert.match(html, /--lap-scale:0\.5\b/);

  await d.respond(await d.poll(), lapPayload());
  assert.match(d.dashboard.innerHTML, /--lap-scale:1\b/);
});
