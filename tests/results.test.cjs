// Tests static/result_helpers.js and static/results.js. Only Node built-ins: `node --test tests/results.test.cjs`.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const ResultHelpers = require(path.join(__dirname, "..", "static", "result_helpers.js"));

test("isFinished accepts real times and rejects statuses and blanks", () => {
  assert.ok(ResultHelpers.isFinished({ Time: "1:02:03.4" }));
  for (const time of ["", "-", " - ", "DNS", "dnf", "DSQ", undefined]) {
    assert.ok(!ResultHelpers.isFinished({ Time: time }), String(time));
  }
});

test("hasResult covers finishers and DNS/DNF/DSQ but not blanks", () => {
  for (const time of ["0:59:00", "DNS", "dnf", "DSQ"]) {
    assert.ok(ResultHelpers.hasResult({ Time: time }), time);
  }
  for (const time of ["", "-", undefined]) {
    assert.ok(!ResultHelpers.hasResult({ Time: time }), String(time));
  }
});

test("isUnfinished is true only for blank or dash times", () => {
  assert.ok(ResultHelpers.isUnfinished({ Time: "" }));
  assert.ok(ResultHelpers.isUnfinished({ Time: " - " }));
  assert.ok(ResultHelpers.isUnfinished({}));
  assert.ok(!ResultHelpers.isUnfinished({ Time: "DNF" }));
  assert.ok(!ResultHelpers.isUnfinished({ Time: "1:00:00" }));
});

test("shouldDisplayRacer only shows unfinished racers when enabled", () => {
  const unfinished = { Time: "-" };
  assert.ok(!ResultHelpers.shouldDisplayRacer(unfinished, false));
  assert.ok(ResultHelpers.shouldDisplayRacer(unfinished, true));
  assert.ok(ResultHelpers.shouldDisplayRacer({ Time: "DNS" }, false));
  assert.ok(ResultHelpers.shouldDisplayRacer({ Time: "1:00:00" }, false));
});

// ---- Results page (static/results.js) ----

globalThis.ResultHelpers = ResultHelpers;
const ResultsPage = require(path.join(__dirname, "..", "static", "results.js"));

function racer(place, name, time, bib = "") {
  return { Place: place, Bib: bib, Name: name, Time: time };
}

function category(title, racers, tier = "category") {
  return { type: "category", tier, title, racers };
}

function payload(pages, extra = {}) {
  return {
    pages,
    waiting: false,
    race_generation: 1,
    refresh_interval: 30,
    color_scheme: "dark",
    race_name: "Trail Fest",
    last_refresh: "09:41:00",
    display_unfinished_in_category: false,
    display_unfinished_in_overall: false,
    ...extra,
  };
}

function fakeElement(tag) {
  const el = {
    tagName: tag,
    children: [],
    dataset: {},
    attributes: {},
    listeners: {},
    hidden: false,
    value: "",
    type: "",
    className: "",
    _text: "",
    get firstChild() { return el.children[0] || null; },
    appendChild(child) { el.children.push(child); return child; },
    removeChild(child) { el.children = el.children.filter((c) => c !== child); return child; },
    setAttribute(name, value) { el.attributes[name] = String(value); },
    getAttribute(name) { return name in el.attributes ? el.attributes[name] : null; },
    addEventListener(type, fn) { (el.listeners[type] ||= []).push(fn); },
    dispatch(type) { (el.listeners[type] || []).forEach((fn) => fn({ target: el })); },
    get textContent() { return el.children.length ? el.children.map((c) => c.textContent).join("|") : el._text; },
    set textContent(value) { el.children = []; el._text = String(value); },
    set innerHTML(_value) { throw new Error("results.js must not use innerHTML"); },
  };
  return el;
}

function startResults(responses, refreshResponses = []) {
  const ids = ["race-name", "last-updated", "page-notice", "results-status", "group-list", "results-panel",
    "group-title", "top-count", "count-error", "results-table", "results-rows", "results-empty", "results-summary"];
  const elements = Object.fromEntries(ids.map((id) => [id, fakeElement("div")]));
  elements["top-count"].value = "3";
  const docListeners = {};
  const document = {
    body: fakeElement("body"),
    getElementById: (id) => elements[id],
    createElement: fakeElement,
    addEventListener(type, fn) { (docListeners[type] ||= []).push(fn); },
  };
  const timers = [];
  const requests = [];
  const queue = [...responses];
  const refreshQueue = [...refreshResponses];
  const respond = (next) => {
    if (next instanceof Error) return Promise.reject(next);
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(next) });
  };
  const page = ResultsPage.start({
    document,
    setTimeout: (fn, ms) => { timers.push({ fn, ms, cleared: false }); return timers.length; },
    clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1].cleared = true; },
    fetch: (url, options = {}) => {
      requests.push({ url, method: options.method || "GET" });
      if (url === "/api/refresh") return respond(refreshQueue.length ? refreshQueue.shift() : { refreshed: true, error: null });
      return respond(queue.shift());
    },
  });
  const el = (id) => elements[id];
  return {
    page,
    document,
    el,
    timers,
    requests,
    queue,
    poll: () => page.poll(),
    // Fire a keydown and wait for any refresh it started to settle.
    async press(key, extra = {}) {
      const event = { key, target: document.body, prevented: false, preventDefault() { this.prevented = true; }, ...extra };
      (docListeners.keydown || []).forEach((fn) => fn(event));
      for (let i = 0; i < 10; i++) await Promise.resolve();
      return event;
    },
    pendingPolls: () => timers.filter((t) => !t.cleared && t.fn === page.poll),
    buttons: () => el("group-list").children,
    titles: () => el("group-list").children.map((b) => b.textContent),
    selected: () => el("group-list").children.filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.textContent),
    rows: () => el("results-rows").children.map((row) => row.children.map((td) => td.textContent)),
    setCount(value) { el("top-count").value = value; el("top-count").dispatch("input"); },
  };
}

test("topFinishers includes everyone tied at the cutoff and keeps order", () => {
  const racers = [racer("1", "A", "1:00"), racer("2", "B", "1:01"), racer("3", "C", "1:02"),
    racer("3", "D", "1:02"), racer("5", "E", "1:05")];
  assert.deepEqual(ResultsPage.topFinishers(racers, 3).map((r) => r.Name), ["A", "B", "C", "D"]);
});

test("topFinishers excludes statuses, unplaced and non-numeric places", () => {
  const racers = [racer("1", "A", "1:00"), racer("", "B", "1:01"), racer("2", "C", "DNF"),
    racer("-", "D", "1:03"), racer("2", "E", "-"), racer("x", "F", "1:04"), racer("0", "G", "1:05"), racer(" 2 ", "H", "1:06")];
  assert.deepEqual(ResultsPage.topFinishers(racers, 3).map((r) => r.Name), ["A", "H"]);
});

test("parseCount accepts positive whole numbers only", () => {
  assert.equal(ResultsPage.parseCount("3"), 3);
  assert.equal(ResultsPage.parseCount(" 10 "), 10);
  for (const bad of ["", "0", "-1", "2.5", "abc", "1e2", null]) {
    assert.equal(ResultsPage.parseCount(bad), null, String(bad));
  }
});

test("visibleGroups matches the dashboard's result pages and visibility toggles", () => {
  const pages = [
    { type: "summary", title: "Summary" },
    category("Overall - 10K", [racer("", "U", "-")], "overall"),
    category("10K Open Female", [racer("", "U", "")]),
    category("10K Open Male", [racer("1", "A", "DNS")]),
    category("Empty", []),
  ];
  assert.deepEqual(ResultsPage.visibleGroups(payload(pages)).map((g) => g.title), ["10K Open Male"]);
  assert.deepEqual(
    ResultsPage.visibleGroups(payload(pages, { display_unfinished_in_overall: true })).map((g) => g.title),
    ["Overall - 10K", "10K Open Male"]);
  assert.deepEqual(
    ResultsPage.visibleGroups(payload(pages, { display_unfinished_in_category: true })).map((g) => g.title),
    ["10K Open Female", "10K Open Male"]);
});

test("visibleGroups gives duplicate titles distinct keys", () => {
  const pages = [category("Same", [racer("1", "A", "1:00")]), category("Same", [racer("1", "B", "1:00")])];
  const keys = ResultsPage.visibleGroups(payload(pages)).map((g) => g.key);
  assert.equal(new Set(keys).size, 2);
});

test("page shows the first grouping's top 3 by default, with ties", async () => {
  const pages = [
    category("Overall - 10K", [racer("1", "A", "1:00", "11"), racer("2", "B", "1:01", "12"), racer("3", "C", "1:02", "13"),
      racer("3", "D", "1:02", "14"), racer("5", "E", "1:05", "15")], "overall"),
    category("10K Open Female", [racer("1", "F", "1:10", "21")]),
  ];
  const ui = startResults([payload(pages)]);
  await ui.poll();
  assert.deepEqual(ui.titles(), ["Overall - 10K", "10K Open Female"]);
  assert.deepEqual(ui.selected(), ["Overall - 10K"]);
  assert.equal(ui.el("group-title").textContent, "Overall - 10K");
  assert.deepEqual(ui.rows(), [["1", "11", "A", "1:00"], ["2", "12", "B", "1:01"], ["3", "13", "C", "1:02"], ["3", "14", "D", "1:02"]]);
  assert.match(ui.el("results-summary").textContent, /4 finishers placed 1.3 \(includes ties\)/);
  assert.equal(ui.el("race-name").textContent, "Trail Fest");
  assert.equal(ui.el("last-updated").textContent, "Updated 09:41:00");
  assert.equal(ui.el("page-notice").hidden, true);
  assert.equal(ui.timers.at(-1).ms, 30000);
});

test("selecting a grouping and editing the count update the winners", async () => {
  const pages = [
    category("A group", [racer("1", "A1", "1:00")]),
    category("B group", [racer("1", "B1", "1:00"), racer("2", "B2", "1:01"), racer("3", "B3", "1:02")]),
  ];
  const ui = startResults([payload(pages)]);
  await ui.poll();
  ui.buttons()[1].dispatch("click");
  assert.deepEqual(ui.selected(), ["B group"]);
  ui.setCount("2");
  assert.deepEqual(ui.rows().map((r) => r[2]), ["B1", "B2"]);
  ui.setCount("0");
  assert.equal(ui.el("count-error").hidden, false);
  assert.equal(ui.el("results-table").hidden, true);
  assert.equal(ui.el("results-summary").textContent, "");
  ui.setCount("10");
  assert.equal(ui.el("count-error").hidden, true);
  assert.deepEqual(ui.rows().map((r) => r[2]), ["B1", "B2", "B3"]);
});

test("selection and count survive refreshes; duplicate titles select independently", async () => {
  const first = [category("Same", [racer("1", "X", "1:00")]), category("Same", [racer("1", "Y", "1:00")])];
  const second = [category("Same", [racer("1", "X", "1:00")]), category("Same", [racer("1", "Y", "1:00"), racer("2", "Z", "1:01")])];
  const ui = startResults([payload(first), payload(second)]);
  await ui.poll();
  ui.buttons()[1].dispatch("click");
  ui.setCount("5");
  assert.deepEqual(ui.rows().map((r) => r[2]), ["Y"]);
  await ui.poll();
  assert.equal(ui.el("top-count").value, "5");
  assert.equal(ui.buttons()[1].getAttribute("aria-pressed"), "true");
  assert.equal(ui.buttons()[0].getAttribute("aria-pressed"), "false");
  assert.deepEqual(ui.rows().map((r) => r[2]), ["Y", "Z"]);
});

test("a removed grouping or new race falls back to the first grouping", async () => {
  const a = category("A", [racer("1", "A1", "1:00")]);
  const b = category("B", [racer("1", "B1", "1:00")]);
  const ui = startResults([payload([a, b]), payload([a]), payload([a, b]), payload([a, b], { race_generation: 2, race_name: "Other" })]);
  await ui.poll();
  ui.buttons()[1].dispatch("click");
  await ui.poll();
  assert.deepEqual(ui.selected(), ["A"]);
  await ui.poll();
  ui.buttons()[1].dispatch("click");
  assert.deepEqual(ui.selected(), ["B"]);
  await ui.poll();
  assert.deepEqual(ui.selected(), ["A"]);
  assert.equal(ui.el("race-name").textContent, "Other");
});

test("empty, waiting and no-race states clear old winners", async () => {
  const ui = startResults([
    payload([category("A", [racer("1", "A1", "1:00")])]),
    payload([], { waiting: true, race_generation: 2, race_name: "" }),
    payload([], { race_selection_required: true, race_generation: 3 }),
    payload([category("A", [racer("", "A1", "-")])], { race_generation: 3 }),
  ]);
  assert.match(ui.el("page-notice").textContent, /Loading/);
  await ui.poll();
  await ui.poll();
  assert.equal(ui.el("results-panel").hidden, true);
  assert.equal(ui.el("race-name").textContent, "");
  assert.match(ui.el("page-notice").textContent, /Waiting for race data/);
  assert.equal(ui.timers.at(-1).ms, 5000);
  await ui.poll();
  assert.match(ui.el("page-notice").textContent, /No race selected/);
  await ui.poll();
  assert.match(ui.el("page-notice").textContent, /No results yet/);
  assert.equal(ui.titles().length, 0);
});

test("a grouping without placed finishers says so", async () => {
  const ui = startResults([payload([category("A", [racer("", "A1", "DNF")])])]);
  await ui.poll();
  assert.equal(ui.el("results-table").hidden, true);
  assert.match(ui.el("results-empty").textContent, /No finishers in places 1.3 yet/);
});

test("fetch failures keep results but mark them stale and retry", async () => {
  const ui = startResults([payload([category("A", [racer("1", "A1", "1:00")])]), new Error("offline"),
    payload([category("A", [racer("1", "A1", "1:00")])], { is_stale: true, error: "API <b>down</b>" })]);
  await ui.poll();
  await ui.poll();
  assert.deepEqual(ui.rows().map((r) => r[2]), ["A1"]);
  assert.equal(ui.el("results-status").hidden, false);
  assert.match(ui.el("results-status").textContent, /out of date/);
  assert.equal(ui.timers.at(-1).ms, 5000);
  await ui.poll();
  assert.equal(ui.el("results-status").textContent, "Results may be out of date. API <b>down</b>");
  assert.equal(ui.timers.at(-1).ms, 30000);
});

test("theme follows config and names render as text", async () => {
  const ui = startResults([payload([category("<i>A</i>", [racer("1", "<img src=x onerror=alert(1)>", "1:00")])], { color_scheme: "light" })]);
  await ui.poll();
  assert.equal(ui.document.body.dataset.theme, "light");
  assert.equal(ui.titles()[0], "<i>A</i>");
  assert.equal(ui.rows()[0][2], "<img src=x onerror=alert(1)>");
});

test("R refreshes the source, then redraws immediately and restarts the poll timer", async () => {
  const ui = startResults([payload([category("A", [racer("1", "A1", "1:00")])]),
    payload([category("A", [racer("1", "A1", "1:00"), racer("2", "A2", "1:01")])], { last_refresh: "09:42:00" })]);
  await ui.poll();
  ui.setCount("5");
  const event = await ui.press("r");
  assert.equal(event.prevented, true);
  assert.deepEqual(ui.requests.slice(1).map((r) => `${r.method} ${r.url}`), ["POST /api/refresh", "GET /api/data"]);
  assert.deepEqual(ui.rows().map((r) => r[2]), ["A1", "A2"]);
  assert.equal(ui.el("last-updated").textContent, "Updated 09:42:00");
  assert.equal(ui.pendingPolls().length, 1, "the old poll timer is replaced, not doubled");
  assert.equal(ui.el("top-count").value, "5");
});

test("R is ignored with modifiers, on key repeat, and while typing in a text field", async () => {
  const ui = startResults([payload([category("A", [racer("1", "A1", "1:00")])])]);
  await ui.poll();
  await ui.press("r", { ctrlKey: true });
  await ui.press("r", { repeat: true });
  await ui.press("r", { target: { tagName: "TEXTAREA" } });
  await ui.press("r", { target: { tagName: "INPUT", type: "text" } });
  await ui.press("x");
  assert.equal(ui.requests.length, 1);
  await ui.press("R", { target: { tagName: "INPUT", type: "number" } });
  assert.equal(ui.requests[1].url, "/api/refresh", "R still works from the Show top field");
});

test("R during the cooldown says so without re-polling", async () => {
  const ui = startResults([payload([category("A", [racer("1", "A1", "1:00")])])],
    [{ refreshed: false, reason: "cooldown", retry_after: 4 }]);
  await ui.poll();
  await ui.press("r");
  assert.equal(ui.requests.length, 2);
  assert.equal(ui.el("last-updated").textContent, "Just refreshed \u2014 try again in 4s");
  const clearNotice = ui.timers.at(-1);
  clearNotice.fn();
  assert.equal(ui.el("last-updated").textContent, "Updated 09:41:00");
});

test("a failed refresh request is reported and R works again afterwards", async () => {
  const ui = startResults([payload([category("A", [racer("1", "A1", "1:00")])]), payload([category("A", [racer("1", "A1", "1:00")])])],
    [new Error("offline")]);
  await ui.poll();
  const originalError = console.error;
  console.error = () => {};
  try { await ui.press("r"); } finally { console.error = originalError; }
  assert.equal(ui.el("last-updated").textContent, "Refresh failed");
  await ui.press("r");
  assert.deepEqual(ui.requests.slice(2).map((r) => r.url), ["/api/refresh", "/api/data"]);
});
