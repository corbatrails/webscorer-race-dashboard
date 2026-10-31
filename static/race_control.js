// Fixed-viewport race director and timing desk.
(function (root) {
  "use strict";
  var CHOICE_HEIGHT = 36;

  function capacity(height, reserved, itemHeight) {
    return Math.max(1, Math.floor((height - reserved) / itemHeight));
  }

  function paginate(items, size, requestedPage) {
    size = Math.max(1, size);
    var pages = Math.max(1, Math.ceil(items.length / size));
    var page = Math.max(0, Math.min(requestedPage, pages - 1));
    var start = page * size;
    return { items: items.slice(start, start + size), page: page, pages: pages, start: start, total: items.length };
  }

  function filteredRows(racers, filter) {
    return (racers || []).filter(function (r) {
      return filter === "all" || (r.Status === "Finished" && root.ResultHelpers.isFinished(r));
    });
  }

  function formatDuration(seconds) {
    if (!Number.isFinite(seconds)) return "--:--:--";
    var sign = seconds < 0 ? "-" : "";
    var total = Math.floor(Math.abs(seconds));
    var days = Math.floor(total / 86400);
    var hours = Math.floor(total % 86400 / 3600);
    return sign + (days ? days + "d " : "") + hours + ":" +
      String(Math.floor(total % 3600 / 60)).padStart(2, "0") + ":" + String(total % 60).padStart(2, "0");
  }

  function formatGap(seconds) {
    if (!(seconds > 0)) return "";
    return "+" + formatSplit(seconds);
  }

  function formatSplit(seconds) {
    if (!Number.isFinite(seconds)) return "--:--:--";
    var rounded = Math.round(seconds * 1000) / 1000;
    var fraction = rounded % 1;
    return formatDuration(rounded) + (fraction ? fraction.toFixed(3).slice(1).replace(/0+$/, "") : "");
  }

  function start(env) {
    var document = env.document;
    var el = function (id) { return document.getElementById(id); };
    var now = env.now || Date.now;
    var pollTimer = null;
    var pendingPoll = null;
    var state = {
      data: null, view: "progress", distance: null, groupKey: null, filter: "all",
      distancePage: 0, lapPage: 0, distRailPage: 0, groupRailPage: 0,
      expandedRacers: new Set(),
      raceGeneration: null, fetchFailed: false, refreshing: false, notice: "",
    };

    function node(tag, text, className) {
      var result = document.createElement(tag);
      if (text !== undefined && text !== null) result.textContent = String(text);
      if (className) result.className = className;
      return result;
    }
    function clear(target) {
      while (target.firstChild) target.removeChild(target.firstChild);
    }
    function message(id, text) {
      el(id).textContent = text;
      el(id).hidden = !text;
    }
    function control() { return state.data && state.data.race_control; }
    function groups() { return control() ? control().groups || [] : []; }
    function distanceChoices() {
      var seen = new Set();
      return groups().filter(function (g) {
        if (seen.has(g.distance)) return false;
        seen.add(g.distance);
        return true;
      }).map(function (g) { return { key: g.distance, title: g.distance || "Overall" }; });
    }
    function currentGroups() { return groups().filter(function (g) { return g.distance === state.distance; }); }
    function selectedGroup() {
      return currentGroups().find(function (g) { return g.key === state.groupKey; }) || null;
    }
    function pager(prefix, page, label) {
      el(prefix + "-prev").disabled = page.page === 0;
      el(prefix + "-next").disabled = page.page === page.pages - 1;
      el(prefix + "-page").textContent = label || (page.page + 1) + " / " + page.pages;
    }
    function resetSelection() {
      state.distance = null;
      state.groupKey = null;
      state.distancePage = state.lapPage = state.distRailPage = state.groupRailPage = 0;
      state.expandedRacers.clear();
      el("table-wrap").scrollTop = 0;
      state.filter = "all";
    }
    function ensureSelection() {
      var choices = distanceChoices();
      if (!choices.some(function (d) { return d.key === state.distance; })) {
        state.distance = choices.length ? choices[0].key : null;
        state.groupKey = null;
        state.groupRailPage = 0;
        el("table-wrap").scrollTop = 0;
      }
      if (!selectedGroup()) {
        var available = currentGroups();
        state.groupKey = available.length ? available[0].key : null;
        el("table-wrap").scrollTop = 0;
      }
    }

    function renderClock() {
      var c = control();
      var seconds = c && c.clock_seconds;
      if (Number.isFinite(seconds) && Number.isFinite(c.sampled_at) &&
          !state.fetchFailed && !state.data.is_stale && !state.data.error) {
        seconds += Math.max(0, now() / 1000 - c.sampled_at);
      }
      el("race-clock").textContent = formatDuration(seconds);
    }

    function renderHeader() {
      var data = state.data;
      var snapshot = control();
      el("race-name").textContent = data && data.race_name || snapshot && snapshot.race_name || "Race control";
      el("race-date").textContent = data && data.race_date || snapshot && snapshot.race_date || "Director & timing desk";
      var warnings = [];
      if (state.fetchFailed) warnings.push("Can't reach the dashboard server; data may be out of date. Retrying...");
      else if (data && data.is_stale) warnings.push("Data may be out of date.");
      if (data && data.error) warnings.push(String(data.error));
      message("control-status", warnings.join(" "));
      el("last-updated").textContent = state.notice || (data && data.last_refresh ? "Updated " + data.last_refresh : "");
      el("last-updated").className = warnings.length ? "stale" : "updated";
      el("refresh-button").disabled = state.refreshing;
      renderClock();
      el("progress-tab").setAttribute("aria-pressed", String(state.view === "progress"));
      el("results-tab").setAttribute("aria-pressed", String(state.view === "results"));
    }

    function renderStats(progress) {
      var box = el("progress-stats");
      clear(box);
      [["registered", "Registered"], ["on_course", "On course"], ["finished", "Finished"],
        ["dns", "DNS"], ["not_started", "Not started"], ["dnf", "DNF"], ["dsq", "DSQ"]]
        .forEach(function (entry) {
          var card = node("div", null, "control-stat stat-" + entry[0]);
          card.appendChild(node("strong", progress.totals[entry[0]] || 0));
          card.appendChild(node("span", entry[1]));
          box.appendChild(card);
        });
    }

    function renderProgress() {
      var c = control();
      var progress = c && c.progress;
      if (!progress) {
        clear(el("progress-stats"));
        clear(el("lap-grid"));
        el("lap-grid").appendChild(node("p", "No overall lap data available.", "empty-message"));
        clear(el("completion-bars"));
        clear(el("latest-finishers"));
        pager("distance", paginate([], 1, 0), "No distances");
        pager("lap", paginate([], 1, 0), "No laps");
        return;
      }
      renderStats(progress);
      var grid = el("lap-grid");
      var rowCapacity = Math.min(6, capacity(grid.clientHeight, 38, 76),
        capacity(el("completion-bars").clientHeight, 12, 34));
      var distancePage = paginate(progress.distances, rowCapacity, state.distancePage);
      state.distancePage = distancePage.page;
      var maxLaps = Math.max.apply(null, [1].concat(progress.distances.map(function (d) { return d.lap_count; })));
      var lapCapacity = Math.max(1, Math.min(6, Math.floor((grid.clientWidth - 230) / 88)));
      var laps = Array.from({ length: maxLaps }, function (_, i) { return i + 1; });
      var lapPage = paginate(laps, lapCapacity, state.lapPage);
      state.lapPage = lapPage.page;
      clear(grid);
      grid.style.gridTemplateColumns = "minmax(100px, 1.3fr) repeat(" + (lapPage.items.length + 1) + ", minmax(0, 1fr))";
      grid.style.gridTemplateRows = "26px repeat(" + distancePage.items.length + ", minmax(0, 1fr))";
      grid.appendChild(node("div", "Distance", "lap-head"));
      lapPage.items.forEach(function (lap) { grid.appendChild(node("div", "Lap " + lap, "lap-head")); });
      grid.appendChild(node("div", "Finished", "lap-head"));
      clear(el("completion-bars"));
      distancePage.items.forEach(function (d) {
        var label = node("div", null, "lap-label");
        label.appendChild(node("strong", d.name));
        label.appendChild(node("small", d.started + " started / " + d.lap_count + (d.lap_count === 1 ? " lap" : " laps")));
        grid.appendChild(label);
        lapPage.items.forEach(function (lap) {
          var cell = node("div", null, "lap-cell");
          if (lap > d.lap_count) {
            cell.className += " lap-na";
            cell.textContent = "No lap " + lap;
          } else {
            var count = d.on_course_by_lap[lap - 1] || 0;
            var share = d.started > 0 ? count / d.started * 100 : 0;
            var dnf = (d.dnf_by_lap[lap - 1] || 0) + (lap === 1 ? d.dnf_without_crossing || 0 : 0);
            cell.className += count ? " lap-active" : "";
            cell.title = count + " racers on lap " + lap + " (" + Math.round(share) + "% of starters)";
            cell.appendChild(node("strong", count));
            var track = node("div", null, "lap-share");
            var fill = node("i");
            fill.style.width = share + "%";
            track.appendChild(fill);
            cell.appendChild(track);
            if (dnf) cell.appendChild(node("small", dnf + " DNF", "lap-dnf"));
          }
          grid.appendChild(cell);
        });
        var finished = node("div", null, "lap-cell lap-finished");
        finished.appendChild(node("strong", d.finished));
        grid.appendChild(finished);
        var resolved = d.finished + d.dns + d.dnf + d.dsq;
        var bar = node("div", null, "completion-item");
        var barLabel = node("div", null, "completion-label");
        barLabel.appendChild(node("span", d.name));
        barLabel.appendChild(node("span", resolved + " / " + d.registered));
        bar.appendChild(barLabel);
        var barTrack = node("div", null, "completion-track");
        var barFill = node("i");
        barFill.style.width = (d.registered > 0 ? resolved / d.registered * 100 : 0) + "%";
        barTrack.appendChild(barFill);
        bar.appendChild(barTrack);
        el("completion-bars").appendChild(bar);
      });
      pager("distance", distancePage, "Distances " + (distancePage.page + 1) + " / " + distancePage.pages);
      pager("lap", lapPage, "Laps " + lapPage.items[0] + "-" + lapPage.items[lapPage.items.length - 1] + " / " + maxLaps);

      var feed = el("latest-finishers");
      clear(feed);
      var feedCapacity = capacity(feed.clientHeight, 12, 50);
      var finishers = (c.latest_finishers || []).slice(0, feedCapacity);
      finishers.forEach(function (r) {
        var li = node("li");
        var finishTime = formatDuration(r.FinishSeconds);
        li.appendChild(node("span", finishTime, "finish-at"));
        var identity = node("span", r.Name, "finisher-name");
        identity.appendChild(node("small", "#" + r.Bib + " / " + r.Distance + " / place " + r.Place));
        li.appendChild(identity);
        li.appendChild(node("span", r.Time, "finish-time"));
        feed.appendChild(li);
      });
      if (!finishers.length) feed.appendChild(node("li", "No timed finishers yet.", "empty-message"));
    }

    function selectDistance(distance) {
      state.distance = distance;
      state.groupKey = null;
      state.groupRailPage = 0;
      el("table-wrap").scrollTop = 0;
      ensureSelection();
      render();
    }
    function selectGroup(key) {
      state.groupKey = key;
      el("table-wrap").scrollTop = 0;
      render();
    }
    function renderChoices(prefix, choices, selected, pageField, onSelect) {
      var list = el(prefix === "dist-rail" ? "distance-list" : "group-list");
      var result = paginate(choices, capacity(list.clientHeight, 0, CHOICE_HEIGHT), state[pageField]);
      state[pageField] = result.page;
      var signature = JSON.stringify(result.items.map(function (item) { return [item.key, item.title]; }));
      if (list.dataset.signature !== signature) {
        list.dataset.signature = signature;
        clear(list);
        result.items.forEach(function (item) {
          var button = node("button", item.title);
          button.type = "button";
          button.dataset.key = item.key;
          button.title = item.title;
          button.addEventListener("click", function () { onSelect(item.key); });
          list.appendChild(button);
        });
      }
      Array.from(list.children).forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.dataset.key === selected));
      });
      pager(prefix, result);
      var select = el(prefix === "dist-rail" ? "distance-select" : "group-select");
      var optionSignature = JSON.stringify(choices.map(function (item) { return [item.key, item.title]; }));
      if (select.dataset.signature !== optionSignature) {
        select.dataset.signature = optionSignature;
        clear(select);
        choices.forEach(function (item) {
          var option = node("option", item.title);
          option.value = item.key;
          select.appendChild(option);
        });
      }
      select.value = selected === null ? "" : selected;
    }

    function renderResults() {
      renderChoices("dist-rail", distanceChoices(), state.distance, "distRailPage", selectDistance);
      renderChoices("group-rail", currentGroups(), state.groupKey, "groupRailPage", selectGroup);
      var group = selectedGroup();
      el("group-title").textContent = group ? (group.distance ? group.distance + " / " : "") + group.title : "Results";
      el("all-filter").setAttribute("aria-pressed", String(state.filter === "all"));
      el("finished-filter").setAttribute("aria-pressed", String(state.filter === "finished"));
      var racers = filteredRows(group && group.racers, state.filter);
      var columnCount = Array.from(el("result-head").querySelectorAll("th")).filter(function (heading) {
        return env.getComputedStyle(heading).display !== "none";
      }).length;
      var scrollTop = el("table-wrap").scrollTop;
      var focusedKey = document.activeElement && document.activeElement.dataset &&
        document.activeElement.dataset.racerKey;
      var focusedButton = null;
      var body = el("result-rows");
      clear(body);
      racers.forEach(function (r, index) {
        var row = node("tr", null, r.Status === "Finished" ? "finished" : "unfinished");
        if (index % 2) row.className += " result-even";
        if (r.Status === "Finished" && Number(r.Place) > 0 && Number(r.Place) <= 3) row.className += " podium";
        var name = node("td", null, "col-name");
        name.appendChild(node("span", r.Name));
        if (r.TeamName) name.appendChild(node("small", r.TeamName, "racer-team"));
        name.title = r.Name + (r.TeamName ? " / " + r.TeamName : "");
        row.appendChild(node("td", r.Place || "-", "col-place"));
        row.appendChild(node("td", r.Bib, "col-bib"));
        row.appendChild(name);
        row.appendChild(node("td", r.Laps + "/" + r.LapCount, "col-laps"));
        var time = node("td", null, "col-time");
        if (r.Status === "Finished") time.textContent = r.Time;
        else time.appendChild(node("span", r.Status, "racer-status status-" + r.Status.toLowerCase().replace(/ /g, "-")));
        row.appendChild(time);
        row.appendChild(node("td", formatGap(r.GapSeconds), "col-gap"));
        body.appendChild(row);
        if (r.LapCount > 1) {
          var key = JSON.stringify([group.key, r.Bib, r.Name]);
          var detail = node("tr", null, "split-detail");
          detail.id = "lap-splits-" + index;
          detail.hidden = !state.expandedRacers.has(key);
          var cell = node("td");
          cell.colSpan = columnCount;
          var toggle = node("button", detail.hidden ? "+" : "-", "split-toggle");
          toggle.type = "button";
          toggle.dataset.racerKey = key;
          toggle.setAttribute("aria-controls", detail.id);
          toggle.setAttribute("aria-expanded", String(!detail.hidden));
          toggle.setAttribute("aria-label", "Lap splits for " + r.Name);
          name.appendChild(toggle);
          if (focusedKey === key) focusedButton = toggle;
          var splits = r.LapSplits || [];
          if (splits.length) {
            var table = node("table", null, "split-table");
            table.setAttribute("aria-label", "Lap splits for " + r.Name);
            var head = node("thead");
            var headings = node("tr");
            ["Lap", "Split", "Elapsed"].forEach(function (label) {
              var heading = node("th", label);
              heading.scope = "col";
              headings.appendChild(heading);
            });
            head.appendChild(headings);
            table.appendChild(head);
            var splitBody = node("tbody");
            splits.forEach(function (split) {
              var splitRow = node("tr");
              splitRow.appendChild(node("td", split.LapNumber));
              splitRow.appendChild(node("td", formatSplit(split.SplitSeconds)));
              splitRow.appendChild(node("td", formatSplit(split.ElapsedSeconds)));
              splitBody.appendChild(splitRow);
            });
            table.appendChild(splitBody);
            cell.appendChild(table);
          } else cell.appendChild(node("p", "No lap splits available.", "empty-message"));
          detail.appendChild(cell);
          body.appendChild(detail);
          toggle.addEventListener("click", function () {
            detail.hidden = !detail.hidden;
            if (detail.hidden) state.expandedRacers.delete(key);
            else state.expandedRacers.add(key);
            toggle.textContent = detail.hidden ? "+" : "-";
            toggle.setAttribute("aria-expanded", String(!detail.hidden));
          });
        }
      });
      if (focusedButton) focusedButton.focus({ preventScroll: true });
      el("table-wrap").scrollTop = scrollTop;
      message("results-empty", racers.length ? "" : state.filter === "finished" ? "No finishers in this grouping yet." : "No racers in this grouping.");
      el("result-count").textContent = racers.length + (racers.length === 1 ? " racer" : " racers");
    }

    function render() {
      renderHeader();
      var data = state.data;
      var notice = !data ? "Loading race data..." : data.race_selection_required ?
        "No race selected. Choose a race on the admin page." : !control() ?
          data.waiting ? "Waiting for race data... This page updates automatically." : "No race data available." : "";
      message("page-notice", notice);
      el("control-main").hidden = Boolean(notice);
      el("progress-view").hidden = state.view !== "progress";
      el("results-view").hidden = state.view !== "results";
      if (notice) {
        clear(el("result-rows"));
        clear(el("lap-grid"));
        clear(el("progress-stats"));
        clear(el("latest-finishers"));
        return;
      }
      if (state.view === "progress") renderProgress();
      else renderResults();
    }

    function setView(view) { state.view = view; render(); }
    function applyData(data) {
      if (state.raceGeneration !== null && state.raceGeneration !== data.race_generation) resetSelection();
      state.raceGeneration = data.race_generation;
      state.data = data;
      state.fetchFailed = false;
      state.notice = "";
      if (data.color_scheme) document.body.dataset.theme = data.color_scheme;
      ensureSelection();
      render();
    }
    function schedulePoll() {
      env.clearTimeout(pollTimer);
      if (state.refreshing) return;
      var seconds = state.fetchFailed || !state.data || state.data.waiting ? 5 : Number(state.data.refresh_interval) || 60;
      pollTimer = env.setTimeout(poll, Math.max(1, seconds) * 1000);
    }
    function poll() {
      if (pendingPoll) return pendingPoll;
      pendingPoll = env.fetch("/api/data")
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(applyData)
        .catch(function (error) {
          if (root.console) root.console.error("Race control fetch error:", error);
          state.fetchFailed = true;
          render();
        })
        .then(function () { pendingPoll = null; schedulePoll(); });
      return pendingPoll;
    }
    function refresh() {
      if (state.refreshing) return Promise.resolve();
      state.refreshing = true;
      state.notice = "Refreshing...";
      renderHeader();
      env.clearTimeout(pollTimer);
      // Wait for an in-flight cache fetch before requesting a new source poll.
      return (pendingPoll || Promise.resolve())
        .then(function () { return env.fetch("/api/refresh", { method: "POST" }); })
        .then(function (response) {
          return response.json().then(function (body) {
            if (response.status === 429 && body.reason === "cooldown") {
              state.notice = "Just refreshed - try again in " + body.retry_after + "s";
              return;
            }
            if (!response.ok || body.refreshed !== true) throw new Error("HTTP " + response.status);
            return poll();
          });
        })
        .catch(function (error) {
          if (root.console) root.console.error("Race control refresh error:", error);
          state.notice = "Refresh failed. Retrying automatically.";
        })
        .then(function () {
          state.refreshing = false;
          renderHeader();
          schedulePoll();
        });
    }

    el("progress-tab").addEventListener("click", function () { setView("progress"); });
    el("results-tab").addEventListener("click", function () { setView("results"); });
    el("refresh-button").addEventListener("click", refresh);
    el("distance-select").addEventListener("change", function () { selectDistance(el("distance-select").value); });
    el("group-select").addEventListener("change", function () { selectGroup(el("group-select").value); });
    [["all-filter", "all"], ["finished-filter", "finished"]].forEach(function (filter) {
      el(filter[0]).addEventListener("click", function () {
        state.filter = filter[1];
        el("table-wrap").scrollTop = 0;
        render();
      });
    });
    [["distance", "distancePage"], ["lap", "lapPage"],
      ["dist-rail", "distRailPage"], ["group-rail", "groupRailPage"]].forEach(function (pair) {
      [-1, 1].forEach(function (step) {
        var button = el(pair[0] + (step < 0 ? "-prev" : "-next"));
        button.addEventListener("click", function () {
          if (button.disabled) return;
          state[pair[1]] += step;
          render();
        });
      });
    });
    document.addEventListener("keydown", function (event) {
      var target = event.target;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat ||
          target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
      var key = event.key.toLowerCase();
      if (["1", "2", "r"].indexOf(key) < 0) return;
      event.preventDefault();
      if (key === "1" || key === "2") setView(key === "1" ? "progress" : "results");
      else if (key === "r") refresh();
    });
    if (env.addEventListener) env.addEventListener("resize", render);
    if (env.ResizeObserver) {
      var observer = new env.ResizeObserver(render);
      ["table-wrap", "lap-grid", "completion-bars", "latest-finishers", "distance-list", "group-list"]
        .forEach(function (id) { observer.observe(el(id)); });
    }
    if (env.setInterval) env.setInterval(renderClock, 1000);
    render();
    return { state: state, poll: poll, refresh: refresh, applyData: applyData, render: render,
      selectDistance: selectDistance, setView: setView };
  }

  var api = { capacity: capacity, paginate: paginate, filteredRows: filteredRows,
    formatDuration: formatDuration, formatGap: formatGap, start: start };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else {
    root.RaceControl = api;
    start({
      document: root.document, fetch: root.fetch.bind(root), setTimeout: root.setTimeout.bind(root),
      getComputedStyle: root.getComputedStyle.bind(root),
      clearTimeout: root.clearTimeout.bind(root), setInterval: root.setInterval.bind(root),
      addEventListener: root.addEventListener.bind(root), ResizeObserver: root.ResizeObserver,
    }).poll();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
