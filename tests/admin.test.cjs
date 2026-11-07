"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const script = fs.readFileSync(require.resolve("../static/admin.js"), "utf8");

function eventTarget() {
  const listeners = {};
  return {
    addEventListener(type, listener) { (listeners[type] ||= []).push(listener); },
    dispatch(type, extra = {}) {
      const event = { target: this, button: 0, defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; }, ...extra };
      (listeners[type] || []).forEach(listener => listener(event));
      return event;
    },
  };
}

function settingsPage(readyState = "complete", displayedValues = {}) {
  const fields = {
    race_id: { name: "race_id", type: "text", value: "100" },
    refresh_interval: { name: "refresh_interval", type: "number", value: "60" },
    show_summary: { name: "show_summary", type: "checkbox", value: "true", checked: true },
    color_scheme: { name: "color_scheme", type: "select-one", value: "dark" },
  };
  for (const [name, field] of Object.entries(fields)) {
    field.dataset = { savedValue: String(field.type === "checkbox" ? field.checked : field.value) };
    if (Object.hasOwn(displayedValues, name)) {
      if (field.type === "checkbox") field.checked = displayedValues[name];
      else field.value = displayedValues[name];
    }
  }
  const discard = eventTarget();
  const form = Object.assign(eventTarget(), {
    elements: Object.values(fields),
    querySelector(selector) { return selector === "[data-discard-changes]" ? discard : null; },
  });
  const document = Object.assign(eventTarget(), {
    readyState,
    querySelector(selector) { return selector === ".settings-form" ? form : null; },
    getElementById() { return null; },
  });
  const window = eventTarget();
  vm.runInNewContext(script, { document, window });
  return { fields, form, discard, document, unload: () => window.dispatch("beforeunload") };
}

test("clean settings do not warn before leaving", () => {
  const page = settingsPage();
  assert.equal(page.unload().defaultPrevented, false);
  assert.equal(page.unload().returnValue, undefined);
});

for (const [name, change] of [
  ["text", fields => { fields.race_id.value = "200"; }],
  ["number", fields => { fields.refresh_interval.value = "30"; }],
  ["checkbox", fields => { fields.show_summary.checked = false; }],
  ["select", fields => { fields.color_scheme.value = "light"; }],
]) {
  test(`unsaved ${name} settings warn before leaving without race-picker controls`, () => {
    const page = settingsPage();
    change(page.fields);
    const event = page.unload();
    assert.equal(event.defaultPrevented, true);
    assert.equal(event.returnValue, "");
  });
}

test("restoring initial settings removes the warning", () => {
  const page = settingsPage();
  page.fields.color_scheme.value = "light";
  assert.equal(page.unload().defaultPrevented, true);
  page.fields.color_scheme.value = "dark";
  assert.equal(page.unload().defaultPrevented, false);
});

test("programmatic race selections count as unsaved without an input event", () => {
  const page = settingsPage();
  page.fields.race_id.value = "300";
  assert.equal(page.unload().defaultPrevented, true);
});

test("saving changed settings bypasses the leave warning", () => {
  const page = settingsPage();
  page.fields.race_id.value = "300";
  assert.equal(page.unload().defaultPrevented, true);
  page.form.dispatch("submit");
  assert.equal(page.unload().defaultPrevented, false);
});

test("explicitly discarding changed settings bypasses the leave warning", () => {
  const page = settingsPage();
  page.fields.race_id.value = "300";
  assert.equal(page.unload().defaultPrevented, true);
  page.discard.dispatch("click");
  assert.equal(page.unload().defaultPrevented, false);
});

test("opening Discard in another tab keeps the original page protected", () => {
  const page = settingsPage();
  page.fields.race_id.value = "300";
  page.discard.dispatch("click", { ctrlKey: true });
  assert.equal(page.unload().defaultPrevented, true);
});

test("settings protection initializes after DOMContentLoaded", () => {
  const page = settingsPage("loading");
  page.document.dispatch("DOMContentLoaded");
  page.fields.race_id.value = "300";
  assert.equal(page.unload().defaultPrevented, true);
});

for (const [name, value] of [["race_id", "300"], ["show_summary", false], ["color_scheme", "light"]]) {
  test(`retained ${name} edits after a rejected save remain protected`, () => {
    const page = settingsPage("complete", { [name]: value });
    assert.equal(page.unload().defaultPrevented, true);
    const field = page.fields[name];
    if (field.type === "checkbox") field.checked = field.dataset.savedValue === "true";
    else field.value = field.dataset.savedValue;
    assert.equal(page.unload().defaultPrevented, false);
  });
}
