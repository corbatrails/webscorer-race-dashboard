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
