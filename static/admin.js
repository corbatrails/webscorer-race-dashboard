// Admin settings page: loads the WebScorer race list for the race picker.
(function () {
  "use strict";

  function init() {
    var source = document.getElementById("field-source");
    var raceId = document.getElementById("field-race_id");
    var picker = document.getElementById("race-picker");
    var list = document.getElementById("race-list");
    var status = document.getElementById("race-status");
    var reload = document.getElementById("race-reload");
    if (!source || !raceId || !picker || !list) return;
    var request = 0;

    function setOptions(placeholder, races) {
      list.textContent = "";
      var first = document.createElement("option");
      first.value = "";
      first.textContent = placeholder;
      list.appendChild(first);
      (races || []).forEach(function (race) {
        var opt = document.createElement("option");
        opt.value = race.id;
        opt.textContent = [race.name, race.date, race.sport].filter(Boolean).join(" \u2014 ") + " (" + race.id + ")";
        if (race.id === raceId.value.trim()) opt.selected = true;
        list.appendChild(opt);
      });
    }

    function load() {
      var mine = ++request;
      picker.hidden = false;
      status.textContent = "";
      setOptions("Loading races...", []);
      fetch("/admin/races?source=" + encodeURIComponent(source.value), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (response) {
          return response.json().catch(function () { return {}; }).then(function (body) {
            return { ok: response.ok, status: response.status, body: body };
          });
        })
        .then(function (result) {
          if (mine !== request) return;
          if (result.ok && result.body.supported === false) {
            picker.hidden = true;
            return;
          }
          if (!result.ok) {
            setOptions("Race list unavailable", []);
            status.textContent = result.status === 401
              ? "Your session expired. Reload the page and log in again."
              : (result.body.error || "Could not load the race list.");
            return;
          }
          var races = result.body.races || [];
          setOptions(races.length ? "Choose a race..." : "No races found", races);
        })
        .catch(function () {
          if (mine !== request) return;
          setOptions("Race list unavailable", []);
          status.textContent = "Could not reach the server.";
        });
    }

    list.addEventListener("change", function () {
      if (list.value) raceId.value = list.value;
    });
    source.addEventListener("change", load);
    if (reload) reload.addEventListener("click", load);
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
