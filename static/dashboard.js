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
          showSummary: data.show_summary !== false,
          showCategories: data.show_categories !== false
        };
        buildPageList(data);
        renderCurrentPage();
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
      } else if (page.type === "category" && config.showCategories) {
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
      container.innerHTML = renderWaiting(lastData ? lastData.error : null);
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

  function renderWaiting(error) {
    var html = '<div class="waiting-screen">';
    html += "<h1>No results yet</h1>";
    html += "<p>Waiting for race data\u2026 Dashboard will update automatically.</p>";
    if (error) {
      html += '<p class="error-message">' + escapeHtml(error) + "</p>";
    }
    html += "</div>";
    return html;
  }

  function renderSummary(page, data) {
    var d = page.data;
    var html = '<div class="page active">';

    html += '<div class="summary-header">';
    html += '<img src="/static/logo.png" alt="Logo" onerror="this.style.display=\'none\'">';
    html += "<div>";
    html += '<div class="race-title">' + escapeHtml(data.race_name) + "</div>";
    html += '<div class="race-subtitle">' + escapeHtml(data.race_date) + " \u2022 " + escapeHtml(data.race_sport) + "</div>";
    html += "</div>";
    html += '<div class="summary-meta">Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</div>";
    html += "</div>";

    html += '<div class="stats-bar">';
    html += '<div class="stat"><div class="stat-value">' + d.total_finished + '</div><div class="stat-label">Finished</div></div>';
    html += '<div class="stat"><div class="stat-value">' + d.categories.length + '</div><div class="stat-label">Categories</div></div>';
    html += "</div>";

    html += '<div class="leaders-grid">';
    for (var i = 0; i < d.categories.length; i++) {
      var cat = d.categories[i];
      html += '<div class="leader-card">';
      html += "<h3>" + escapeHtml(cat.name) + "</h3>";
      for (var j = 0; j < cat.leaders.length; j++) {
        var r = cat.leaders[j];
        html += '<div class="leader-entry">';
        html += '<span class="leader-place">' + (r.Place || j + 1) + ".</span>";
        html += '<span class="leader-name">' + escapeHtml(r.Name || "") + "</span>";
        html += '<span class="leader-time">' + escapeHtml(r.Time || "") + "</span>";
        html += "</div>";
      }
      if (cat.leaders.length === 0) {
        html += '<div class="leader-entry" style="color:#606080">No results yet</div>';
      }
      html += "</div>";
    }
    html += "</div>";

    html += "</div>";
    return html;
  }

  function renderCategory(category, catIndex, data) {
    var racers = category.racers || [];
    var pinnedCount = Math.min(config.pinnedLeaders, racers.length);
    var pinned = racers.slice(0, pinnedCount);
    var scrolling = racers.slice(pinnedCount);

    var html = '<div class="page active">';

    html += '<div class="category-header">';
    html += '<div class="category-title">' + escapeHtml(category.title) + "</div>";
    html += '<div class="category-meta">';
    html += '<span>Last updated: ' + escapeHtml(data.last_refresh || "\u2014") + "</span>";
    html += '<span>Category ' + (catIndex + 1) + " of " + categories.length + "</span>";
    html += "</div>";
    html += "</div>";

    if (racers.length === 0) {
      html += '<p style="font-size:3vh;color:#606080;text-align:center;margin-top:10vh">No results yet</p>';
      html += "</div>";
      return html;
    }

    // Pinned leaders table
    html += '<table class="results-table pinned-table">';
    html += "<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Time</th></tr></thead>";
    html += "<tbody>";
    for (var i = 0; i < pinned.length; i++) {
      html += renderRacerRow(pinned[i]);
    }
    html += "</tbody></table>";

    // Scrolling results
    if (scrolling.length > 0) {
      html += '<div id="scroll-container" class="scroll-container">';
      html += '<table class="results-table scroll-table">';
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

  // Initial fetch, then poll on refresh interval
  fetchData();
  setInterval(fetchData, 60 * 1000);

  // Retry quickly if still waiting for initial data
  var waitingRetry = setInterval(function () {
    if (lastData && !lastData.waiting) {
      clearInterval(waitingRetry);
      return;
    }
    fetchData();
  }, 3000);
})();
