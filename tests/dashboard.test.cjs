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
  const pauseIndicator = makeElement("div");
  const elements = { dashboard, "toast-container": toastContainer, "pause-indicator": pauseIndicator };
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
    fetch(url, init) {
      return new Promise((resolve, reject) =>
        requests.push({ url, method: (init && init.method) || "GET", resolve, reject }));
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
    pauseIndicator,
    requests,
    // Page timers (display time, scroll pauses) that have not been cleared.
    pageTimers: () => timers.filter((t) => !t.done && t.ms >= 1000000),
    settle,
    async respond(index, payload) {
      requests[index].resolve({ ok: true, json: () => Promise.resolve(payload) });
      await settle();
    },
    async fail(index) {
      requests[index].reject(new Error("network down"));
      await settle();
    },
    // Press a key; returns the index of the newest request.
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

test("P holds the page timer and resumes with the time left", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  assert.equal(d.pageTimers().length, 1);

  await d.press("p");
  assert.equal(d.pageTimers().length, 0);
  assert.match(d.pauseIndicator.className, /visible/);

  await d.press("P"); // caps lock on
  assert.doesNotMatch(d.pauseIndicator.className, /visible/);
  const resumed = d.pageTimers();
  assert.equal(resumed.length, 1);
  assert.ok(resumed[0].ms <= 1998000 && resumed[0].ms > 1990000, `resumes with the time left, got ${resumed[0].ms}`);
});

test("arrow keys still change page while paused, and it stays paused", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  await d.press("p");
  await d.respond(await d.press("ArrowRight"), payload({ finishers: [1, 2] }));
  assert.match(d.dashboard.innerHTML, /Rider 2/);
  assert.equal(d.pageTimers().length, 0);
  assert.match(d.pauseIndicator.className, /visible/);

  await d.press("p");
  assert.equal(d.pageTimers().length, 1);
});

test("R asks the server to poll now, then redraws with the new data", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  const refresh = await d.press("r");
  assert.equal(d.requests[refresh].url, "/api/refresh");
  assert.equal(d.requests[refresh].method, "POST");
  assert.equal(await d.press("r"), refresh, "a second press while refreshing is ignored");

  await d.respond(refresh, { refreshed: true, error: null });
  const data = d.requests.length - 1;
  assert.equal(d.requests[data].url, "/api/data");
  await d.respond(data, payload({ finishers: [1, 2] }));
  assert.match(d.dashboard.innerHTML, /Rider 2/);
  assert.ok(d.toastContainer.children.some((t) => /Results refreshed/.test(t.textContent)));
  assert.ok(d.requests[await d.press("r")].url === "/api/refresh", "R works again once done");
});

test("R during the cooldown says when to retry and does not redraw", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  const refresh = await d.press("r");
  await d.respond(refresh, { refreshed: false, reason: "cooldown", retry_after: 3 });
  assert.equal(d.requests.length, refresh + 1);
  assert.ok(d.toastContainer.children.some((t) => /try again in 3s/.test(t.textContent)));
});

test("R while paused shows new data but stays paused", async () => {
  const d = startDashboard();
  await d.respond(0, payload({ finishers: [1] }));
  await d.press("p");
  const refresh = await d.press("r");
  await d.respond(refresh, { refreshed: true, error: null });
  await d.respond(d.requests.length - 1, payload({ finishers: [1, 2] }));
  assert.match(d.dashboard.innerHTML, /Rider 2/);
  assert.equal(d.pageTimers().length, 0);
  assert.match(d.pauseIndicator.className, /visible/);
});
