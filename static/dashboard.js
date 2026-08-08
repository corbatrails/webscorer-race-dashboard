(function () {
    let currentPage = 0;
    let pages = [];
    let rotationInterval = 20;
    let rotationTimer = null;

    function fetchData() {
        fetch("/api/data")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                rotationInterval = data.page_rotation_interval || 20;
                renderDashboard(data);
            })
            .catch(function (err) {
                console.error("Fetch error:", err);
            });
    }

    function renderDashboard(data) {
        var container = document.getElementById("dashboard");

        if (data.waiting && data.pages.length === 0) {
            container.innerHTML = renderWaiting(data.error);
            return;
        }

        pages = data.pages;
        if (currentPage >= pages.length) currentPage = 0;

        var html = "";
        for (var i = 0; i < pages.length; i++) {
            var page = pages[i];
            var active = i === currentPage ? " active" : "";
            if (page.type === "summary") {
                html += renderSummary(page, data, active, i);
            } else {
                html += renderCategory(page, active, i, data);
            }
        }

        html += renderProgressDots(pages.length, currentPage);
        container.innerHTML = html;
    }

    function renderWaiting(error) {
        var html = '<div class="waiting-screen">';
        html += "<h1>Waiting for race data\u2026</h1>";
        html += "<p>Dashboard will update automatically when results are available.</p>";
        if (error) {
            html += '<p class="error-message">' + escapeHtml(error) + "</p>";
        }
        html += "</div>";
        return html;
    }

    function renderSummary(page, data, activeClass, index) {
        var d = page.data;
        var html = '<div class="page' + activeClass + '" data-index="' + index + '">';

        html += '<div class="summary-header">';
        html += '<img src="/static/logo.png" alt="Logo" onerror="this.style.display=\'none\'">';
        html += "<div>";
        html += '<div class="race-title">' + escapeHtml(data.race_name) + "</div>";
        html += '<div class="race-subtitle">' + escapeHtml(data.race_date) + " \u2022 " + escapeHtml(data.race_sport) + "</div>";
        html += "</div></div>";

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

        html += renderFooter(data);
        html += "</div>";
        return html;
    }

    function renderCategory(page, activeClass, index, data) {
        var html = '<div class="page' + activeClass + '" data-index="' + index + '">';

        html += '<div class="category-header">';
        html += '<div class="category-title">' + escapeHtml(page.title) + "</div>";
        if (page.total_pages > 1) {
            html += '<div class="category-page-num">Page ' + page.page_num + " of " + page.total_pages + "</div>";
        }
        html += "</div>";

        if (page.racers.length === 0) {
            html += '<p style="font-size:3vh;color:#606080;text-align:center;margin-top:10vh">No results yet</p>';
        } else {
            html += '<table class="results-table">';
            html += "<thead><tr><th>Place</th><th>Bib</th><th>Name</th><th>Time</th></tr></thead>";
            html += "<tbody>";
            for (var i = 0; i < page.racers.length; i++) {
                var r = page.racers[i];
                var placeClass = "";
                if (r.Place === 1) placeClass = " place-1";
                else if (r.Place === 2) placeClass = " place-2";
                else if (r.Place === 3) placeClass = " place-3";
                html += "<tr>";
                html += '<td class="' + placeClass + '">' + (r.Place || "") + "</td>";
                html += "<td>" + escapeHtml(r.Bib || "") + "</td>";
                html += "<td>" + escapeHtml(r.Name || "") + "</td>";
                html += "<td>" + escapeHtml(r.Time || "") + "</td>";
                html += "</tr>";
            }
            html += "</tbody></table>";
        }

        html += renderFooter(data);
        html += "</div>";
        return html;
    }

    function renderFooter(data) {
        var html = '<div class="page-footer">';
        html += "<span>Last updated: " + escapeHtml(data.last_refresh || "\u2014") + "</span>";
        if (data.is_stale) {
            html += '<span class="stale-indicator">\u26a0 Stale data</span>';
        }
        html += "</div>";
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

    function rotatePage() {
        if (pages.length <= 1) return;
        currentPage = (currentPage + 1) % pages.length;
        var allPages = document.querySelectorAll(".page");
        var allDots = document.querySelectorAll(".progress-dot");
        for (var i = 0; i < allPages.length; i++) {
            allPages[i].classList.toggle("active", i === currentPage);
        }
        for (var j = 0; j < allDots.length; j++) {
            allDots[j].classList.toggle("active", j === currentPage);
        }
    }

    function startRotation() {
        if (rotationTimer) clearInterval(rotationTimer);
        rotationTimer = setInterval(rotatePage, rotationInterval * 1000);
    }

    // Initial fetch, then poll on refresh interval
    fetchData();
    startRotation();
    setInterval(fetchData, 60 * 1000);
})();
