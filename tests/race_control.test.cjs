"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
globalThis.ResultHelpers = require("../static/result_helpers.js");
const Control = require("../static/race_control.js");

function element(tag) {
  return {
    tagName: tag.toUpperCase(), children: [], dataset: {}, attributes: {}, listeners: {}, style: {},
    hidden: false, disabled: false, value: "", scrollTop: 0, clientHeight: 300, clientWidth: 900, offsetHeight: 32,
    _text: "",
    get firstChild() { return this.children[0]; },
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) { this.children.splice(this.children.indexOf(child), 1); },
    setAttribute(key, value) { this.attributes[key] = String(value); },
    getAttribute(key) { return this.attributes[key]; },
    focus() { this.focused = true; },
    querySelectorAll(selector) {
      return this.children.flatMap(child => [
        ...(child.tagName === selector.toUpperCase() ? [child] : []),
        ...child.querySelectorAll(selector),
      ]);
    },
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
    last_refresh: "10:00:00", refresh_interval: 30, waiting: false, server_time: 1000,
    race_control: {
      race_name: "Race", race_date: "Today",
      groups, progress: { totals: { registered: 1, on_course: 0, finished: 1 }, distances: [] },
      latest_finishers: [], clock_seconds: 3600, sampled_at: 1000,
    }, ...extra,
  };
}

function ui(responses = []) {
  const nodes = {};
  const get = id => nodes[id] ||= element("div");
  const listeners = {}, timers = [], intervals = [], requests = [];
  let now = 1000000;
  const document = {
    body: element("body"), getElementById: get, createElement: element,
    addEventListener(name, fn) { listeners[name] = fn; },
  };
  const env = {
    document, now: () => now,
    getComputedStyle(node) { return { display: node.hidden ? "none" : "table-cell" }; },
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cleared = true; },
    setInterval(fn) { intervals.push(fn); }, addEventListener() {},
    fetch(url, options) {
      requests.push({ url, options });
      const next = responses.shift();
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve(next && "ok" in next ? next : { ok: true, json: async () => next });
    },
  };
  for (let i = 0; i < 7; i++) {
    const heading = element("th");
    if (i === 3) {
      heading.hidden = true;
      nodes["distance-column"] = heading;
    }
    get("result-head").appendChild(heading);
  }
  const page = Control.start(env);
  return {
    page, get, timers, requests, document,
    advance(ms) { now += ms; },
    tick() { intervals.forEach(fn => fn()); },
    press(key, extra = {}) {
      listeners.keydown({ key, target: document.body, preventDefault() {}, ...extra });
    },
    rows: () => get("result-rows").children.filter(row => !row.hidden)
      .map(row => row.children.map(td => td.textContent)),
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

test("unfinished includes only racers on course or not started", () => {
  const racers = [
    racer(0),
    racer(1, { Time: "", Status: "On course" }),
    racer(2, { Time: "", Status: "Not started" }),
    racer(3, { Time: "DNF", Status: "DNF" }),
    racer(4, { Time: "DNS", Status: "DNS" }),
    racer(5, { Time: "DSQ", Status: "DSQ" }),
  ];
  assert.deepEqual(Control.filteredRows(racers, "unfinished"), [racers[1], racers[2]]);
});

test("unfinished button filters rendered rows and reports its pressed state", () => {
  const app = ui();
  app.page.applyData(payload([group("A", "50K", [
    racer(0),
    racer(1, { Time: "", Status: "On course" }),
    racer(2, { Time: "", Status: "Not started" }),
    racer(3, { Time: "DNF", Status: "DNF" }),
  ])]));
  app.page.setView("results");
  app.get("unfinished-filter").dispatch("click");

  assert.deepEqual(app.rows().map(row => row[1]), ["1", "2"]);
  assert.equal(app.get("unfinished-filter").getAttribute("aria-pressed"), "true");
  assert.equal(app.get("all-filter").getAttribute("aria-pressed"), "false");
});

test("All combines Overall racers once and shows their distance-specific places", () => {
  const app = ui();
  const data = payload([
    group("50K Overall", "50K", [racer(0, { Place: "1", LapCount: 2 })]),
    { ...group("10K Category", "10K", [racer(8)]), tier: "gender", title: "F 30-39" },
    group("10K Overall", "10K", [racer(1, { Place: "1", LapCount: 2 })]),
  ]);
  app.page.applyData(data);
  app.page.setView("results");

  assert.equal(app.page.state.distance, "50K");
  assert.equal(app.get("distance-list").children[0].textContent, "All");
  assert.equal(app.get("distance-select").children[0].textContent, "All");
  app.get("distance-list").children[0].dispatch("click");

  assert.equal(app.get("group-list").children.length, 1);
  assert.equal(app.get("group-list").children[0].textContent, "Overall");
  assert.deepEqual(app.rows().map(row => [row[0], row[1], row[3]]), [
    ["1", "0", "50K"],
    ["1", "1", "10K"],
  ]);
  assert.equal(app.get("result-head").children[3].hidden, false);

  app.page.applyData(data);
  assert.equal(app.page.state.allDistances, true);
  assert.equal(app.rows().length, 2);
});

test("All stays distinct from a null distance and excludes category-only distances", () => {
  const app = ui();
  app.page.applyData(payload([
    group("50K Overall", "50K"),
    { ...group("10K Category", "10K", [racer(1)]), tier: "gender" },
    group("Overall", null, [racer(2)]),
  ]));
  app.page.setView("results");

  assert.equal(app.page.state.distance, "50K");
  app.get("distance-list").children[0].dispatch("click");
  assert.equal(app.page.state.allDistances, true);
  assert.deepEqual(app.rows().map(row => row[3]), ["50K", "Overall"]);

  const select = app.get("distance-select");
  select.value = select.children[0].value;
  select.dispatch("change");
  assert.equal(app.page.state.allDistances, true);

  app.page.selectDistance(null);
  assert.equal(app.page.state.allDistances, false);
  assert.equal(app.page.state.distance, null);
  assert.equal(app.rows().length, 1);
  assert.equal(app.rows()[0][1], "2");
});

test("All with no Overall groups stays empty instead of including categories", () => {
  const app = ui();
  app.page.applyData(payload([
    { ...group("10K Category", "10K", [racer(1)]), tier: "gender" },
  ]));
  app.page.setView("results");
  app.get("distance-list").children[0].dispatch("click");
  assert.equal(app.rows().length, 0);
});

test("Distance column is hidden per distance and split details span visible columns", () => {
  const app = ui();
  const data = payload([group("A", "50K", [racer(0, {
    LapSplits: [{ LapNumber: 1, SplitSeconds: 600, ElapsedSeconds: 600 }],
  })])]);
  app.page.applyData(data);
  app.page.setView("results");
  let detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(app.get("result-head").children[3].hidden, true);
  assert.equal(detail.children[1].colSpan, 4);

  app.get("distance-list").children[0].dispatch("click");
  detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(app.get("result-head").children[3].hidden, false);
  assert.equal(detail.children[1].colSpan, 5);
});

test("duration supports multi-day races and time until the start", () => {
  assert.equal(Control.formatDuration(3661), "1:01:01");
  assert.equal(Control.formatDuration(90061), "1d 1:01:01");
  assert.equal(Control.formatDuration(-60), "-0:01:00");
});

test("clock includes cached sample age using server timestamps", () => {
  const app = ui();
  app.page.applyData(payload([group("A")], { server_time: 1037.8 }));
  assert.equal(app.get("race-clock").textContent, "1:00:37");
});

test("clock initialization is independent of the browser clock's starting value", () => {
  const app = ui();
  app.advance(17000000);
  app.page.applyData(payload([group("A")]));
  assert.equal(app.get("race-clock").textContent, "1:00:00");
});

test("clock ticks by elapsed time and catches up after delayed callbacks", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.advance(2500);
  app.tick();
  assert.equal(app.get("race-clock").textContent, "1:00:02");
  app.advance(110000);
  app.tick();
  assert.equal(app.get("race-clock").textContent, "1:01:52");
});

test("results refreshes and distance changes do not reinitialize the clock", () => {
  const app = ui();
  app.page.applyData(payload([group("A"), group("B", "25K")]));
  app.advance(5000);
  const updated = payload([group("A"), group("B", "25K")], { server_time: 1005 });
  updated.race_control.clock_seconds = 7200;
  app.page.applyData(updated);
  app.page.selectDistance("25K");
  assert.equal(app.get("race-clock").textContent, "1:00:05");
});

test("clock keeps ticking through stale provider data while showing its warning", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.advance(5000);
  app.page.applyData(payload([group("A")], { is_stale: true, error: "Provider unavailable" }));
  assert.equal(app.get("race-clock").textContent, "1:00:05");
  assert.match(app.get("control-status").textContent, /out of date.*Provider unavailable/);
  app.advance(2000);
  app.tick();
  assert.equal(app.get("race-clock").textContent, "1:00:07");
});

test("clock keeps ticking when the dashboard server cannot be reached", async () => {
  const app = ui([payload([group("A")]), new Error("offline")]);
  await app.page.poll();
  app.advance(5000);
  await app.page.poll();
  app.tick();
  assert.equal(app.get("race-clock").textContent, "1:00:05");
  assert.match(app.get("control-status").textContent, /Can't reach the dashboard server/);
});

test("clock resets on a race switch and clears when no race is selected", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.advance(5000);
  const next = payload([group("B")], { race_generation: 2, server_time: 1005 });
  next.race_control.clock_seconds = 120;
  next.race_control.sampled_at = 1005;
  app.page.applyData(next);
  assert.equal(app.get("race-clock").textContent, "0:02:00");
  app.advance(2000);
  app.tick();
  assert.equal(app.get("race-clock").textContent, "0:02:02");
  app.page.applyData(payload([], { race_generation: 3, waiting: true, race_control: null }));
  app.tick();
  assert.equal(app.get("race-clock").textContent, "--:--:--");
});

test("clock waits for a valid sample and supports countdowns and multi-day elapsed time", () => {
  const app = ui();
  const data = payload([group("A")]);
  data.race_control.clock_seconds = null;
  app.page.applyData(data);
  assert.equal(app.get("race-clock").textContent, "--:--:--");
  data.race_control.clock_seconds = -1.5;
  app.page.applyData(data);
  assert.equal(app.get("race-clock").textContent, "-0:00:01");
  app.advance(2000);
  app.tick();
  assert.equal(app.get("race-clock").textContent, "0:00:00");
  const next = payload([group("B")], { race_generation: 2, server_time: 1002 });
  next.race_control.clock_seconds = 90000;
  next.race_control.sampled_at = 1002;
  app.page.applyData(next);
  assert.equal(app.get("race-clock").textContent, "1d 1:00:00");
});

test("all result rows render without paging and selections and scroll survive refresh", () => {
  const app = ui();
  const racers = Array.from({ length: 25 }, (_, i) => racer(i));
  app.page.applyData(payload([group("A"), group("B", "25K", racers)]));
  app.page.selectDistance("25K");
  app.page.setView("results");
  assert.equal(app.rows().length, 25);
  app.get("table-wrap").scrollTop = 240;
  app.page.applyData(payload([group("A"), group("B", "25K", racers)], { color_scheme: "light" }));
  assert.equal(app.document.body.dataset.theme, "light");
  assert.equal(app.page.state.groupKey, "B");
  assert.equal(app.page.state.view, "results");
  assert.equal(app.rows().length, 25);
  assert.equal(app.get("table-wrap").scrollTop, 240);
  assert.match(app.get("result-count").textContent, /25 racers/);
});

function splitButtons(app) {
  return app.get("result-rows").children.filter(row => !row.hidden && row.className !== "split-detail")
    .flatMap(row => row.children[2].children.filter(child => child.tagName === "BUTTON"));
}

test("multi-lap racers expand inline with split and ending elapsed; single-lap racers do not", () => {
  const app = ui();
  app.page.applyData(payload([group("A", "50K", [
    racer(0, { LapSplits: [
      { LapNumber: 1, SplitSeconds: 600.125, ElapsedSeconds: 600.125, WallClockSeconds: 29400.125 },
      { LapNumber: 3, SplitSeconds: null, ElapsedSeconds: 1800, WallClockSeconds: 86400 + 3725 },
    ] }),
    racer(1, { LapCount: 1 }),
    racer(2, { LapSplits: [] }),
  ])]));
  app.page.setView("results");
  const buttons = splitButtons(app);
  assert.equal(buttons.length, 2);
  assert.equal(buttons[0].getAttribute("aria-expanded"), "false");
  buttons[0].dispatch("click");
  assert.equal(buttons[0].getAttribute("aria-expanded"), "true");
  const detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(detail.hidden, false);
  assert.equal(detail.id, buttons[0].getAttribute("aria-controls"));
  assert.match(detail.textContent, /Lap.*Split.*Elapsed.*Wall clock.*1.*0:10:00\.125.*0:10:00\.125.*08:10:00/);
  assert.match(detail.textContent, /3.*--:--:--.*0:30:00.*01:02:05 \+1 day/);
  buttons[1].dispatch("click");
  assert.match(app.rows().flat().join(" "), /No lap splits available/);
  assert.equal(buttons[0].getAttribute("aria-expanded"), "true");
  buttons[0].dispatch("click");
  assert.equal(detail.hidden, true);
});

test("expanded racers and focused toggle survive updates and reset on a race switch", () => {
  const app = ui();
  const data = payload([group("A", "50K", [racer(0), racer(1)])]);
  app.page.applyData(data);
  app.page.setView("results");
  const buttons = splitButtons(app);
  assert.equal(buttons.length, 2);
  app.document.activeElement = buttons[0];
  buttons[0].dispatch("click");
  buttons[1].dispatch("click");
  app.get("table-wrap").scrollTop = 144;
  const updated = payload([group("A", "50K", [racer(1), racer(0, { LapSplits: [
    { LapNumber: 1, SplitSeconds: 700, ElapsedSeconds: 700 },
  ] })])]);
  app.page.applyData(updated);
  assert.ok(splitButtons(app).every(button => button.getAttribute("aria-expanded") === "true"));
  assert.equal(splitButtons(app)[1].focused, true);
  assert.match(app.rows().flat().join(" "), /0:11:40/);
  assert.equal(app.get("table-wrap").scrollTop, 144);
  app.page.applyData({ ...updated, race_generation: 2 });
  assert.ok(splitButtons(app).every(button => button.getAttribute("aria-expanded") === "false"));
  assert.equal(app.get("table-wrap").scrollTop, 0);
});

test("arrow keys no longer intercept native navigation in results", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.page.setView("results");
  let prevented = false;
  app.press("ArrowRight", { preventDefault() { prevented = true; } });
  assert.equal(prevented, false);
});

test("split details start at the name column and span only remaining visible columns", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.page.setView("results");
  let detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(detail.children[0].colSpan, 2);
  assert.equal(detail.children[0].textContent, "");
  assert.equal(detail.children[1].colSpan, 4);
  assert.match(detail.children[1].textContent, /No lap splits available/);
  app.get("result-head").children[4].hidden = true;
  app.page.render();
  detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(detail.children[0].colSpan, 2);
  assert.equal(detail.children[1].colSpan, 3);
  app.get("result-head").children[6].hidden = true;
  app.page.render();
  detail = app.get("result-rows").children.find(row => row.className === "split-detail");
  assert.equal(detail.children[0].colSpan, 2);
  assert.equal(detail.children[1].colSpan, 2);
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

test("provider errors retain the successful snapshot's event identity", () => {
  const app = ui();
  app.page.applyData(payload([group("A")]));
  app.page.applyData(payload([group("A")], { race_name: "", race_date: "", error: "Provider unavailable" }));
  assert.equal(app.get("race-name").textContent, "Race");
  assert.equal(app.get("race-date").textContent, "Today");
  assert.match(app.get("control-status").textContent, /Provider unavailable/);
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
