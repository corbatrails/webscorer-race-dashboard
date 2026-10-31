"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
globalThis.ResultHelpers = require("../static/result_helpers.js");
const Control = require("../static/race_control.js");

function element(tag) {
  return {
    tagName: tag.toUpperCase(), children: [], dataset: {}, attributes: {}, listeners: {}, style: {},
    hidden: false, disabled: false, value: "", clientHeight: 300, clientWidth: 900, offsetHeight: 32,
    _text: "",
    get firstChild() { return this.children[0]; },
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) { this.children.splice(this.children.indexOf(child), 1); },
    setAttribute(key, value) { this.attributes[key] = String(value); },
    getAttribute(key) { return this.attributes[key]; },
    addEventListener(key, fn) { (this.listeners[key] ||= []).push(fn); },
    dispatch(key) { (this.listeners[key] || []).forEach(fn => fn({ target: this })); },
    get textContent() { return this._text + this.children.map(c => c.textContent).join(""); },
    set textContent(value) { this.children = []; this._text = String(value); },
    set innerHTML(_) { throw new Error("Render API values as text, not HTML"); },
  };
}

const racer = (i, extra = {}) => ({
  Place: String(i + 1), Bib: String(i), Name: `Racer ${i}`, Time: "1:00:00",
  Status: "Finished", Laps: 2, LapCount: 2, GapSeconds: i * 60, ...extra,
});
const group = (key, distance = "50K", racers = [racer(0)]) => ({
  key, distance, title: key, tier: "overall", racers,
});
function payload(groups, extra = {}) {
  return {
    race_name: "Race", race_date: "Today", color_scheme: "dark", race_generation: 1,
    last_refresh: "10:00:00", refresh_interval: 30, waiting: false,
    race_control: {
      groups, progress: { totals: { registered: 1, on_course: 0, finished: 1 }, distances: [] },
      latest_finishers: [], clock_seconds: 3600, sampled_at: 1000,
    }, ...extra,
  };
}

function ui(responses = []) {
  const nodes = {};
  const get = id => nodes[id] ||= element("div");
  const listeners = {}, timers = [], requests = [];
  const document = {
    body: element("body"), getElementById: get, createElement: element,
    addEventListener(name, fn) { listeners[name] = fn; },
  };
  const env = {
    document, now: () => 1000000,
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cleared = true; },
    setInterval() {}, addEventListener() {},
    fetch(url, options) {
      requests.push({ url, options });
      const next = responses.shift();
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve(next && "ok" in next ? next : { ok: true, json: async () => next });
    },
  };
  const page = Control.start(env);
  return {
    page, get, timers, requests, document,
    press(key, extra = {}) {
      listeners.keydown({ key, target: document.body, preventDefault() {}, ...extra });
    },
    rows: () => get("result-rows").children.map(row => row.children.map(td => td.textContent)),
  };
}

test("pagination clamps removed pages and never overfills a short viewport", () => {
  assert.deepEqual(Control.paginate([1, 2, 3, 4, 5], 2, 99), {
    items: [5], page: 2, pages: 3, start: 4, total: 5,
  });
  assert.equal(Control.capacity(90, 32, 36), 1);
  assert.equal(Control.capacity(10, 32, 36), 1);
  assert.equal(Control.paginate([], 3, 9).page, 0);
});

test("all racers includes statuses; finished-only excludes every non-finisher", () => {
  const racers = [racer(0), racer(1, { Time: "", Status: "On course" }),
    racer(2, { Time: "DNF", Status: "DNF" }), racer(3, { Time: "DNS", Status: "DNS" })];
  assert.equal(Control.filteredRows(racers, "all").length, 4);
  assert.deepEqual(Control.filteredRows(racers, "finished"), [racers[0]]);
});

test("duration supports multi-day races and time until the start", () => {
  assert.equal(Control.formatDuration(3661), "1:01:01");
  assert.equal(Control.formatDuration(90061), "1d 1:01:01");
  assert.equal(Control.formatDuration(-60), "-0:01:00");
});

test("configured theme applies on every poll, selections and page survive refresh", () => {
  const app = ui();
  const racers = Array.from({ length: 25 }, (_, i) => racer(i));
  app.page.applyData(payload([group("A"), group("B", "25K", racers)]));
  app.page.selectDistance("25K");
  app.page.setView("results");
  app.get("result-next").dispatch("click");
  assert.match(app.get("result-page").textContent, /8-14 of 25/);
  app.page.applyData(payload([group("A"), group("B", "25K", racers)], { color_scheme: "light" }));
  assert.equal(app.document.body.dataset.theme, "light");
  assert.equal(app.page.state.groupKey, "B");
  assert.equal(app.page.state.resultPage, 1);
  assert.equal(app.page.state.view, "results");
  assert.equal(app.rows().length, 7);
});

test("race changes reset state and waiting clears previous rows and event identity", () => {
  const app = ui();
  app.page.applyData(payload([group("A"), group("B", "25K")]));
  app.page.selectDistance("25K");
  app.page.applyData(payload([group("C")], { race_generation: 2 }));
  assert.equal(app.page.state.groupKey, "C");
  app.page.applyData(payload([], {
    race_generation: 3, race_name: "", race_date: "", waiting: true,
    race_selection_required: true, race_control: null,
  }));
  assert.equal(app.get("control-main").hidden, true);
  assert.match(app.get("page-notice").textContent, /No race selected/);
  assert.equal(app.get("race-name").textContent, "Race control");
  assert.equal(app.rows().length, 0);
});

test("fetch failure retains rows, warns explicitly and retries in five seconds", async () => {
  const app = ui([payload([group("A")]), new Error("offline")]);
  await app.page.poll();
  app.page.setView("results");
  const rows = app.rows();
  await app.page.poll();
  assert.deepEqual(app.rows(), rows);
  assert.match(app.get("control-status").textContent, /out of date.*Retrying/);
  assert.equal(app.timers.at(-1).ms, 5000);
});

test("manual refresh reports cooldown and HTTP errors rather than claiming success", async () => {
  const app = ui([
    { ok: false, status: 429, json: async () => ({ reason: "cooldown", retry_after: 4 }) },
    { ok: false, status: 500, json: async () => ({}) },
    { ok: true, json: async () => ({ refreshed: true }) }, payload([group("A")]),
  ]);
  await app.page.refresh();
  assert.match(app.get("last-updated").textContent, /try again in 4s/);
  await app.page.refresh();
  assert.match(app.get("last-updated").textContent, /Refresh failed/);
  assert.equal(app.get("refresh-button").disabled, false);
  await app.page.refresh();
  assert.equal(app.page.state.groupKey, "A");
});

test("navigation lists paginate many groups and preserve the selected key off-page", () => {
  const app = ui();
  app.page.applyData(payload(Array.from({ length: 40 }, (_, i) => group(`Group ${i}`))));
  app.page.setView("results");
  assert.equal(app.get("group-list").children.length, 8);
  app.get("group-rail-next").dispatch("click");
  assert.equal(app.get("group-list").children[0].textContent, "Group 8");
  app.get("group-list").children[2].dispatch("click");
  assert.equal(app.page.state.groupKey, "Group 10");
  app.page.applyData(payload(Array.from({ length: 40 }, (_, i) => group(`Group ${i}`))));
  assert.equal(app.page.state.groupKey, "Group 10");
});

test("unsafe event, grouping, team and racer names remain literal text", () => {
  const app = ui();
  app.page.applyData(payload([group("<img src=x>", "", [racer(0, {
    Name: "<script>alert(1)</script>", TeamName: "<b>Team</b>",
  })])], { race_name: "<img src=x>" }));
  app.page.setView("results");
  assert.equal(app.get("race-name").textContent, "<img src=x>");
  assert.match(app.rows()[0][2], /<script>alert\(1\)<\/script>/);
  assert.match(app.rows()[0][2], /<b>Team<\/b>/);
});

test("shortcuts ignore typing/modifiers and never rotate views automatically", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.press("2", { target: { tagName: "SELECT" } });
  assert.equal(app.page.state.view, "progress");
  app.press("2", { ctrlKey: true });
  assert.equal(app.page.state.view, "progress");
  app.press("2");
  assert.equal(app.page.state.view, "results");
  assert.ok(app.timers.every(t => t.fn === app.page.poll));
});

test("many distances and laps are reachable by paging the progress grid", () => {
  const app = ui();
  const data = payload([]);
  data.race_control.progress.distances = Array.from({ length: 20 }, (_, i) => ({
    distance: `D${i}`, name: `D${i}`, lap_count: 16, started: 10, registered: 10,
    on_course_by_lap: Array(16).fill(1), dnf_by_lap: Array(16).fill(0),
    finished: 2, dns: 1, dnf: 0, dsq: 0,
  }));
  app.page.applyData(data);
  assert.match(app.get("distance-page").textContent, /1 \/ 7/);
  assert.match(app.get("lap-page").textContent, /1-6 \/ 16/);
  app.get("distance-next").dispatch("click");
  assert.match(app.get("lap-grid").textContent, /D3/);
  assert.match(app.get("completion-bars").textContent, /D3/);
  app.get("lap-next").dispatch("click");
  assert.match(app.get("lap-page").textContent, /7-12 \/ 16/);
  app.page.applyData(data);
  assert.equal(app.page.state.distancePage, 1);
  assert.equal(app.page.state.lapPage, 1);
});

test("gaps retain sub-second differences instead of displaying a zero gap", () => {
  assert.equal(Control.formatGap(0.5), "+0:00:00.5");
  assert.equal(Control.formatGap(60.125), "+0:01:00.125");
  assert.equal(Control.formatGap(0), "");
});

test("poll does not arm another timer while a manual source refresh is pending", async () => {
  const app = ui([payload([group("A")]), { refreshed: true }, payload([group("A")])]);
  const envPage = app.page;
  // Start a cache fetch and then refresh before it settles.
  const poll = envPage.poll();
  const refresh = envPage.refresh();
  await poll;
  assert.ok(app.timers.every(timer => timer.cleared));
  await refresh;
});
