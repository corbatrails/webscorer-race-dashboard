// Announcer results page: pick a result grouping and show its top finishers.
(function (root) {
  var DEFAULT_COUNT = 3;
  var RETRY_SECONDS = 5;

  function helpers() {
    return root.ResultHelpers;
  }

  function includeUnfinished(page, data) {
    return page.tier === "overall"
      ? data.display_unfinished_in_overall === true
      : data.display_unfinished_in_category === true;
  }

  // Same result pages the TV dashboard rotates through, each with a stable key.
  function visibleGroups(data) {
    var pages = (data && data.pages) || [];
    if (data.waiting && pages.length === 0) return [];
    var seen = {};
    var groups = [];
    for (var i = 0; i < pages.length; i++) {
      var page = pages[i];
      if (page.type !== "category") continue;
      var racers = page.racers || [];
      var show = includeUnfinished(page, data);
      var visible = racers.some(function (racer) { return helpers().shouldDisplayRacer(racer, show); });
      if (!visible) continue;
      var base = (page.tier || "") + "\u0000" + (page.title || "");
      seen[base] = (seen[base] || 0) + 1;
      groups.push({ key: base + "\u0000" + seen[base], title: page.title || "", page: page });
    }
    return groups;
  }

  function parseCount(value) {
    var text = String(value == null ? "" : value).trim();
    if (!/^\d+$/.test(text)) return null;
    var count = Number(text);
    return count >= 1 ? count : null;
  }

  function placeNumber(racer) {
    var text = String(racer.Place == null ? "" : racer.Place).trim();
    if (!/^\d+$/.test(text)) return null;
    var place = Number(text);
    return place >= 1 ? place : null;
  }

  // Everyone placed at or above the cutoff, so ties at the cutoff all appear. Order is kept as-is.
  function topFinishers(racers, count) {
    return (racers || []).filter(function (racer) {
      var place = placeNumber(racer);
      return helpers().isFinished(racer) && place !== null && place <= count;
    });
  }

  function clear(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function start(env) {
    var document = env.document;
    var fetchFn = env.fetch;
    var setTimeoutFn = env.setTimeout;
    var el = function (id) { return document.getElementById(id); };

    var state = {
      data: null,
      groups: [],
      selectedKey: null,
      raceGeneration: null,
      fetchFailed: false,
      listSignature: null,
    };

    function selectedGroup() {
      for (var i = 0; i < state.groups.length; i++) {
        if (state.groups[i].key === state.selectedKey) return state.groups[i];
      }
      return null;
    }

    function setMessage(id, text) {
      var node = el(id);
      node.textContent = text || "";
      node.hidden = !text;
    }

    function renderList() {
      var list = el("group-list");
      var signature = state.groups.map(function (g) { return g.key; }).join("\u0001");
      if (signature !== state.listSignature) {
        state.listSignature = signature;
        clear(list);
        state.groups.forEach(function (group) {
          var button = document.createElement("button");
          button.type = "button";
          button.className = "group-button";
          button.textContent = group.title;
          button.dataset.key = group.key;
          button.addEventListener("click", function () {
            state.selectedKey = group.key;
            render();
          });
          list.appendChild(button);
        });
      }
      for (var i = 0; i < list.children.length; i++) {
        var button = list.children[i];
        button.setAttribute("aria-pressed", String(button.dataset.key === state.selectedKey));
      }
    }

    function renderRows(finishers) {
      var body = el("results-rows");
      clear(body);
      finishers.forEach(function (racer) {
        var row = document.createElement("tr");
        [["col-place", racer.Place], ["col-bib", racer.Bib], ["col-name", racer.Name], ["col-time", racer.Time]]
          .forEach(function (cell) {
            var td = document.createElement("td");
            td.className = cell[0];
            td.textContent = cell[1] == null ? "" : String(cell[1]).trim();
            row.appendChild(td);
          });
        body.appendChild(row);
      });
    }

    function pageNotice(data) {
      if (state.fetchFailed && !data) return "Loading race data\u2026 Can\u2019t reach the dashboard server. Retrying\u2026";
      if (!data) return "Loading race data\u2026";
      if (data.race_selection_required) return "No race selected. Choose a race on the admin page.";
      if (state.groups.length === 0) {
        return data.waiting ? "Waiting for race data\u2026 This page updates automatically." : "No results yet.";
      }
      return "";
    }

    function statusText(data) {
      var parts = [];
      if (state.fetchFailed) parts.push("Can\u2019t reach the dashboard server; results may be out of date. Retrying\u2026");
      else if (data && data.is_stale) parts.push("Results may be out of date.");
      if (data && data.error) parts.push(String(data.error));
      return parts.join(" ");
    }

    function render() {
      var data = state.data;
      if (data && data.race_name) el("race-name").textContent = data.race_name;
      setMessage("page-notice", pageNotice(data));
      setMessage("results-status", statusText(data));
      el("last-updated").textContent = data && data.last_refresh ? "Updated " + data.last_refresh : "";

      renderList();
      var group = selectedGroup();
      el("results-panel").hidden = !group;
      if (!group) return;

      el("group-title").textContent = group.title;
      var count = parseCount(el("top-count").value);
      if (count === null) {
        setMessage("count-error", "Enter a whole number of 1 or more.");
        el("results-table").hidden = true;
        setMessage("results-empty", "");
        el("results-summary").textContent = "";
        return;
      }
      setMessage("count-error", "");
      var finishers = topFinishers(group.page.racers, count);
      renderRows(finishers);
      el("results-table").hidden = finishers.length === 0;
      setMessage("results-empty", finishers.length === 0 ? "No finishers in places 1\u2013" + count + " yet." : "");
      var summary = finishers.length === 0 ? "" :
        "Showing " + finishers.length + (finishers.length === 1 ? " finisher" : " finishers") + " placed 1\u2013" + count;
      if (finishers.length > count) summary += " (includes ties)";
      el("results-summary").textContent = summary;
    }

    function applyData(data) {
      var raceChanged = state.raceGeneration !== null && data.race_generation !== state.raceGeneration;
      state.raceGeneration = data.race_generation;
      state.data = data;
      state.fetchFailed = false;
      if (data.color_scheme) document.body.dataset.theme = data.color_scheme;
      if (raceChanged) {
        state.selectedKey = null;
        el("race-name").textContent = "";
      }
      state.groups = visibleGroups(data);
      if (!selectedGroup()) state.selectedKey = state.groups.length ? state.groups[0].key : null;
      render();
    }

    function nextDelaySeconds() {
      if (state.fetchFailed || !state.data || state.data.waiting) return RETRY_SECONDS;
      var interval = Number(state.data.refresh_interval);
      return interval > 0 ? interval : 60;
    }

    function poll() {
      return fetchFn("/api/data")
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(applyData)
        .catch(function (err) {
          if (root.console) root.console.error("Results fetch error:", err);
          state.fetchFailed = true;
          render();
        })
        .then(function () {
          setTimeoutFn(poll, nextDelaySeconds() * 1000);
        });
    }

    el("top-count").addEventListener("input", render);
    render();
    return { poll: poll, state: state, render: render };
  }

  var api = {
    DEFAULT_COUNT: DEFAULT_COUNT,
    visibleGroups: visibleGroups,
    parseCount: parseCount,
    topFinishers: topFinishers,
    start: start,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.ResultsPage = api;
    var page = start({ document: root.document, fetch: root.fetch.bind(root), setTimeout: root.setTimeout.bind(root) });
    page.poll();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
