(function () {
  var currentIndex = 0;
  var categories = [];
  var summaryPage = null;
  var config = {};
  var scrollAnimationId = null;
  var advanceTimer = null;
  var lastData = null;

  function fetchData() {
    fetch("/api/data")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        lastData = data;
        config = {
          summaryDisplayTime: data.summary_display_time,
          scrollSpeed: data.scroll_speed,
          scrollPauseTime: data.scroll_pause_time,
          pinnedLeaders: data.pinned_leaders,
          showSummary: data.show_summary !== false
        };
        var wasEmpty = !summaryPage && categories.length === 0;
        buildPageList(data);
        // Only render on first data arrival; ongoing animations pick up new data on next advance
        if (wasEmpty && (summaryPage || categories.length > 0)) {
          renderCurrentPage();
        }
      })
      .catch(function (err) {
        console.error("Fetch error:", err);
      });
  }

  function buildPageList(data) {
    if (data.waiting && data.pages.length === 0) {
      summaryPage = null;
      categories = [];
      return;
    }

    summaryPage = null;
    categories = [];
    for (var i = 0; i < data.pages.length; i++) {
      var page = data.pages[i];
      if (page.type === "summary" && config.showSummary) {
        summaryPage = page;
      } else if (page.type === "category") {
        categories.push(page);
      }
    }
  }

  function getTotalPages() {
    return (summaryPage ? 1 : 0) + categories.length;
  }

  function renderCurrentPage() {
    stopAnimations();
    var container = document.getElementById("dashboard");

    if (!summaryPage && categories.length === 0) {
      container.innerHTML = renderWaiting(lastData);
      return;
    }

    var totalPages = getTotalPages();
    if (currentIndex >= totalPages) currentIndex = 0;

    var html;
    if (summaryPage && currentIndex === 0) {
      html = renderSummary(summaryPage, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
    } else {
      var catIndex = summaryPage ? currentIndex - 1 : currentIndex;
      var category = categories[catIndex];
      html = renderCategory(category, catIndex, lastData);
      html += renderProgressDots(totalPages, currentIndex);
      container.innerHTML = html;
      startScroll();
    }
  }

  function advance() {
    stopAnimations();
    currentIndex = (currentIndex + 1) % getTotalPages();
    renderCurrentPage();
  }

  function stopAnimations() {
    if (scrollAnimationId) {
      cancelAnimationFrame(scrollAnimationId);
      scrollAnimationId = null;
    }
    if (advanceTimer) {
      clearTimeout(advanceTimer);
      advanceTimer = null;
    }
  }

  function startScroll() {
    var scrollContainer = document.getElementById("scroll-container");
    if (!scrollContainer) {
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
      return;
    }

    var scrollDistance = scrollContainer.scrollHeight - scrollContainer.clientHeight;
    if (scrollDistance <= 0) {
      advanceTimer = setTimeout(advance, config.summaryDisplayTime * 1000);
      return;
    }

    var startTime = null;
    var duration = (scrollDistance / config.scrollSpeed) * 1000;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var elapsed = timestamp - startTime;
      var progress = Math.min(elapsed / duration, 1);
      scrollContainer.scrollTop = progress * scrollDistance;

      if (progress < 1) {
        scrollAnimationId = requestAnimationFrame(step);
      } else {
        advanceTimer = setTimeout(advance, config.scrollPauseTime * 1000);
      }
    }

    // Pause before starting scroll so first rows are visible
    advanceTimer = setTimeout(function () {
      scrollAnimationId = requestAnimationFrame(step);
    }, config.scrollPauseTime * 1000);
  }

  function renderWaiting(data) {
    var html = "";
    if (data && data.race_name) {
      html += renderEventHeader(data);
    }
    html += '<div class="waiting-screen">';
    html += "<h1>No results yet</h1>";
    html += "<p>Waiting for race data\u2026 Dashboard will update automatically.</p>";
    if (data && data.error) {
      html += '<p class="error-message">' + escapeHtml(data.error) + "</p>";
    }
    html += "</div>";
    return html;
  }

  function renderEventHeader(data) {
    var html = '<div class="summary-header">';
    html += '<img src="/static/logo.png" alt="Logo" onerror="this.style.display=\'none\'">';
    html += "<div>";
    html += '<div class="race-title">' + escapeHtml(data.race_name) + "</div>";
    html += '<div class="race-subtitle">' + escapeHtml(data.race_date) + " \u2022 " + escapeHtml(data.race_sport) + "</div>";
    html += "</div>";
    html += '<div class="summary-meta">Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</div>";
    html += "</div>";
    return html;
  }

  function renderSummary(page, data) {
    var d = page.data;
    var html = '<div class="page active summary-page">';

    html += renderEventHeader(data);

    html += '<div class="summary-stats-row">';
    html += '<div class="stat-card stat-card-primary"><div class="stat-value">' + d.total_racers + '</div><div class="stat-label">Total Racers</div></div>';
    html += '<div class="stat-card stat-card-primary"><div class="stat-value">' + d.total_finished + '</div><div class="stat-label">Finishers</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + d.total_dns + '</div><div class="stat-label">DNS</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + d.total_dnf + '</div><div class="stat-label">DNF</div></div>';
    html += '<div class="stat-card stat-card-secondary"><div class="stat-value">' + d.total_dsq + '</div><div class="stat-label">DSQ</div></div>';
    html += "</div>";

    html += '<div class="summary-chart-area">';
    html += '<div class="chart-placeholder">Chart coming soon</div>';
    html += "</div>";

    html += "</div>";
    return html;
  }

  function isFinished(racer) {
    var t = (racer.Time || "").trim().toUpperCase();
    return t && t !== "-" && t !== "DNS" && t !== "DNF" && t !== "DSQ";
  }

  function renderCategory(category, catIndex, data) {
    var racers = category.racers || [];
    var pinnedCount = 0;
    for (var i = 0; i < Math.min(config.pinnedLeaders, racers.length); i++) {
      if (isFinished(racers[i])) pinnedCount++;
      else break;
    }
    var pinned = racers.slice(0, pinnedCount);
    var scrolling = racers.slice(pinnedCount);

    var html = '<div class="page active">';

    html += renderEventHeader(data);

    html += '<div class="category-header">';
    html += '<div class="category-title">' + escapeHtml(category.title) + "</div>";
    html += '<div class="category-meta">';
    html += '<span>Category ' + (catIndex + 1) + " of " + categories.length + "</span>";
    html += "</div>";
    html += "</div>";

    if (racers.length === 0) {
      html += '<p style="font-size:3vh;color:#606080;text-align:center;margin-top:10vh">No results yet</p>';
      html += "</div>";
      return html;
    }

    // Pinned leaders table (only shown when at least one racer has finished)
    if (pinned.length > 0) {
      html += '<table class="results-table pinned-table">';
      html += "<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Team</th><th>Time</th></tr></thead>";
      html += "<tbody>";
      for (var i = 0; i < pinned.length; i++) {
        html += renderRacerRow(pinned[i]);
      }
      html += "</tbody></table>";
    }

    // Scrolling results
    if (scrolling.length > 0) {
      html += '<div id="scroll-container" class="scroll-container">';
      html += '<table class="results-table scroll-table">';
      if (pinned.length === 0) {
        html += "<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Team</th><th>Time</th></tr></thead>";
      }
      html += "<tbody>";
      for (var j = 0; j < scrolling.length; j++) {
        html += renderRacerRow(scrolling[j]);
      }
      html += "</tbody></table>";
      html += "</div>";
    }

    html += "</div>";
    return html;
  }

  function renderRacerRow(r) {
    var placeClass = "";
    var place = parseInt(r.Place) || 0;
    if (place === 1) placeClass = " place-1";
    else if (place === 2) placeClass = " place-2";
    else if (place === 3) placeClass = " place-3";
    var html = "<tr>";
    html += '<td class="' + placeClass + '">' + (r.Place || "") + "</td>";
    html += "<td>" + escapeHtml(r.Bib || "") + "</td>";
    html += "<td>" + escapeHtml(r.Name || "") + "</td>";
    html += "<td>" + escapeHtml(r.TeamName || "") + "</td>";
    html += "<td>" + escapeHtml(r.Time || "") + "</td>";
    html += "</tr>";
    return html;
  }

  function renderProgressDots(total, active) {
    if (total <= 1) return "";
    var html = '<div class="progress-dots">';
    for (var i = 0; i < total; i++) {
      html += '<div class="progress-dot' + (i === active ? " active" : "") + '"></div>';
    }
    html += "</div>";
    return html;
  }

  function escapeHtml(str) {
    if (!str) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // Fast-poll until data arrives, then switch to normal refresh interval
  fetchData();
  var startupPoll = setInterval(function () {
    if (lastData && !lastData.waiting) {
      clearInterval(startupPoll);
      setInterval(fetchData, 60 * 1000);
    } else {
      fetchData();
    }
  }, 5000);
})();
