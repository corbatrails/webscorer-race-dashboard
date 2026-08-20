(function () {
  var currentIndex = 0;
  var categories = [];
  var summaryPage = null;
  var config = {};
  var scrollAnimationId = null;
  var advanceTimer = null;
  var lastData = null;
  var knownFinishedBibs = null;

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
          showSummary: data.show_summary !== false,
          pinnedLeadersOnOverallResults: data.pinned_leaders_on_overall_results === true
        };
        var wasEmpty = !summaryPage && categories.length === 0;
        buildPageList(data);
        detectNewFinishers(data);
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
      if (lastData.finish_chart) {
        renderFinishChart(lastData.finish_chart);
      }
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

    var chartColorCount = (data.finish_chart && data.finish_chart.datasets) ? data.finish_chart.datasets.length : 0;
    html += renderProgressBars(d.distance_stats, chartColorCount);

    html += '<div class="summary-chart-area">';
    if (data.finish_chart && data.finish_chart.labels && data.finish_chart.labels.length > 0) {
      html += '<canvas id="finish-chart"></canvas>';
    } else {
      html += '<div class="chart-placeholder">No finishers yet</div>';
    }
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
    var showPodiumStyling = category.tier !== "overall" || config.pinnedLeadersOnOverallResults;
    var pinnedCount = 0;
    if (showPodiumStyling) {
      for (var i = 0; i < Math.min(config.pinnedLeaders, racers.length); i++) {
        if (isFinished(racers[i])) pinnedCount++;
        else break;
      }
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
      html += '<p style="font-size:3vh;color:var(--text-dim);text-align:center;margin-top:10vh">No results yet</p>';
      html += "</div>";
      return html;
    }

    // Pinned leaders table (only shown when at least one racer has finished)
    if (pinned.length > 0) {
      html += '<table class="results-table pinned-table">';
      html += "<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Team</th><th>Time</th></tr></thead>";
      html += "<tbody>";
      for (var i = 0; i < pinned.length; i++) {
        html += renderRacerRow(pinned[i], showPodiumStyling);
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
        html += renderRacerRow(scrolling[j], showPodiumStyling);
      }
      html += "</tbody></table>";
      html += "</div>";
    }

    html += "</div>";
    return html;
  }

  function renderRacerRow(r, showPodiumStyling) {
    var placeClass = "";
    if (showPodiumStyling) {
      var place = parseInt(r.Place) || 0;
      if (place === 1) placeClass = " place-1";
      else if (place === 2) placeClass = " place-2";
      else if (place === 3) placeClass = " place-3";
    }
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

  function generateChartColors(count) {
    var colors = [];
    for (var i = 0; i < count; i++) {
      var hue = Math.round((360 / count) * i);
      colors.push("hsla(" + hue + ", 70%, 60%, 0.8)");
    }
    return colors;
  }

  function renderProgressBars(distanceStats, colorCount) {
    if (!distanceStats || distanceStats.length === 0) return "";
    var colors = generateChartColors(colorCount || distanceStats.length);
    var html = '<div class="progress-bars-row">';
    for (var i = 0; i < distanceStats.length; i++) {
      var stat = distanceStats[i];
      var pct = stat.total > 0 ? Math.round((stat.finished / stat.total) * 100) : 0;
      html += '<div class="progress-bar-item">';
      html += '<div class="progress-bar-label">' + escapeHtml(stat.name) + '</div>';
      html += '<div class="progress-bar-track">';
      html += '<div class="progress-bar-fill" style="width:' + pct + '%;background:' + colors[i] + '"></div>';
      html += '<div class="progress-bar-count">' + stat.finished + '/' + stat.total + '</div>';
      html += '</div>';
      html += '</div>';
    }
    html += '</div>';
    return html;
  }

  function renderFinishChart(chartData) {
    var canvas = document.getElementById("finish-chart");
    if (!canvas || !chartData) return;

    var style = getComputedStyle(document.body);
    var textMuted = style.getPropertyValue('--text-muted').trim();

    var colors = generateChartColors(chartData.datasets.length);
    var datasets = [];
    for (var i = 0; i < chartData.datasets.length; i++) {
      datasets.push({
        label: chartData.datasets[i].label,
        data: chartData.datasets[i].data,
        backgroundColor: colors[i],
      });
    }

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: chartData.labels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: {
            stacked: true,
            ticks: { color: textMuted, font: { size: 14 } },
            grid: { color: textMuted + "33" },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: { color: textMuted, font: { size: 14 }, stepSize: 1 },
            grid: { color: textMuted + "33" },
          },
        },
        plugins: {
          legend: { display: false },
        },
      },
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  var TOAST_DURATION = 5000;
  var TOAST_FADE = 300;

  function showToasts(toasts) {
    var container = document.getElementById("toast-container");
    if (!container) return;
    for (var i = 0; i < toasts.length; i++) {
      createToast(container, toasts[i]);
    }
  }

  function createToast(container, toast) {
    var el = document.createElement("div");
    el.className = "toast" + (toast.placeClass ? " " + toast.placeClass : "");
    el.textContent = toast.text;
    container.appendChild(el);

    // Trigger reflow then fade in
    el.offsetHeight;
    el.classList.add("toast-visible");

    setTimeout(function () {
      el.classList.remove("toast-visible");
      el.classList.add("toast-exit");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, TOAST_FADE);
    }, TOAST_DURATION);
  }

  function detectNewFinishers(data) {
    if (!data.show_toasts) return;

    var currentFinished = {};
    var pages = data.pages || [];

    // Collect all currently finished bibs and their best category placement
    for (var i = 0; i < pages.length; i++) {
      var page = pages[i];
      if (page.type !== "category") continue;
      var racers = page.racers || [];
      for (var j = 0; j < racers.length; j++) {
        var r = racers[j];
        if (!isFinished(r)) continue;
        var bib = r.Bib;
        if (!bib) continue;

        if (!currentFinished[bib]) {
          currentFinished[bib] = { name: r.Name, bib: bib, catPlace: null, catName: "" };
        }

        // Track best category placement (lowest place on a category-tier page)
        if (page.tier === "category") {
          var place = parseInt(r.Place) || 0;
          if (place >= 1 && place <= 3) {
            var existing = currentFinished[bib].catPlace;
            if (!existing || place < existing) {
              currentFinished[bib].catPlace = place;
              currentFinished[bib].catName = page.title;
            }
          }
        }
      }
    }

    // First poll — establish baseline silently
    if (knownFinishedBibs === null) {
      knownFinishedBibs = {};
      for (var bib in currentFinished) {
        knownFinishedBibs[bib] = true;
      }
      return;
    }

    // Find new finishers
    var podiumToasts = [];
    var otherCount = 0;

    for (var bib in currentFinished) {
      if (knownFinishedBibs[bib]) continue;
      var f = currentFinished[bib];
      if (f.catPlace) {
        var medal = f.catPlace === 1 ? "\uD83E\uDD47" : f.catPlace === 2 ? "\uD83E\uDD48" : "\uD83E\uDD49";
        var ordinal = f.catPlace === 1 ? "1st" : f.catPlace === 2 ? "2nd" : "3rd";
        podiumToasts.push({
          text: medal + " " + f.name + " \u2014 " + ordinal + " " + f.catName,
          placeClass: "toast-place-" + f.catPlace
        });
      } else {
        otherCount++;
      }
    }

    // Build toast list: podium first, then batch
    var toasts = podiumToasts.slice();
    if (otherCount > 0) {
      var word = otherCount === 1 ? "racer" : "racers";
      toasts.push({ text: otherCount + " " + word + " finished since last update", placeClass: "" });
    }

    if (toasts.length > 0) {
      showToasts(toasts);
    }

    // Update known set
    knownFinishedBibs = {};
    for (var bib in currentFinished) {
      knownFinishedBibs[bib] = true;
    }
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
