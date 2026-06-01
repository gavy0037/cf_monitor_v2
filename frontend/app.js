let document_handle = "";
const API_BASE_URL = ""; // Relative URL since we mount the frontend on FastAPI

document.addEventListener("DOMContentLoaded", () => {
    checkLoginState();
    initNavigation();
    initForms();

    document.getElementById("refresh-btn").addEventListener("click", () => {
        syncData();
    });

    document.getElementById("logout-btn").addEventListener("click", () => {
        logout();
    });

    document.getElementById("login-form").addEventListener("submit", (e) => {
        handleLogin(e);
    });
});

// Check if user is logged in
function checkLoginState() {
    const cachedHandle = localStorage.getItem("cf_handle");
    if (cachedHandle) {
        document_handle = cachedHandle;
        showAppScreen();
        initDashboard();
    } else {
        showLoginScreen();
    }
}

function showLoginScreen() {
    document.getElementById("login-screen").style.display = "flex";
    document.getElementById("app-container").style.display = "none";
}

function showAppScreen() {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app-container").style.display = "flex";
}

// Handle Login Form Submission
function handleLogin(e) {
    e.preventDefault();
    const handleInput = document.getElementById("login-handle-input").value.trim();
    if (!handleInput) return;

    const submitBtn = document.getElementById("login-submit-btn");
    submitBtn.disabled = true;
    submitBtn.innerText = "Verifying Handle...";

    // Step 1: Verify handle via dashboard endpoint
    fetch(`${API_BASE_URL}/api/dashboard?handle=${handleInput}`)
        .then(res => {
            if (!res.ok) throw new Error("Handle not found or API error");
            return res.json();
        })
        .then(dashData => {
            // Step 2: Backfill past 5 days of history
            submitBtn.innerText = "Fetching History...";
            return fetch(`${API_BASE_URL}/api/backfill/${handleInput}`)
                .then(res => res.json())
                .then(() => dashData); // pass dashData along
        })
        .then(dashData => {
            // Save handle to local storage and show app
            localStorage.setItem("cf_handle", handleInput);
            document_handle = handleInput;
            showAppScreen();
            renderDashboard(dashData);
        })
        .catch(err => {
            console.error("Login error:", err);
            alert("Failed to verify handle. Please make sure the Codeforces handle is correct and exists.");
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerText = "Enter Dashboard";
        });
}

// Logout
function logout() {
    localStorage.removeItem("cf_handle");
    document_handle = "";
    showLoginScreen();
    
    // Clear display values
    document.getElementById("cf-handle-display").innerText = "-";
    document.getElementById("stat-rating").innerText = "-";
    document.getElementById("stat-solved-today").innerText = "0";
    document.getElementById("stat-avg-diff").innerText = "0";
    document.getElementById("submissions-list-display").innerHTML = '<li class="empty-list-msg">Sync to view your submissions today.</li>';
}

// Sidebar Navigation
function initNavigation() {
    const menuButtons = document.querySelectorAll(".menu-btn");
    const sections = document.querySelectorAll(".content-section");

    menuButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");

            // Update active state in menu
            menuButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            // Update active section
            sections.forEach(sec => {
                sec.classList.remove("active");
                if (sec.id === targetId) {
                    sec.classList.add("active");
                }
            });

            // Load data specific to the section
            if (targetId === "history-section" && document_handle) {
                loadHistory();
            } else if (targetId === "upsolve-section" && document_handle) {
                loadUpsolveTracker();
            }
        });
    });
}

// Initial dashboard load
function initDashboard() {
    if (!document_handle) return;
    
    fetch(`${API_BASE_URL}/api/dashboard?handle=${document_handle}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to load dashboard data");
            return res.json();
        })
        .then(data => {
            renderDashboard(data);
        })
        .catch(err => {
            console.error("Dashboard error:", err);
        });
}

// Full Sync from Codeforces API
function syncData() {
    if (!document_handle) return;

    const refreshBtn = document.getElementById("refresh-btn");
    refreshBtn.disabled = true;
    refreshBtn.innerText = "Syncing...";

    fetch(`${API_BASE_URL}/api/dashboard?handle=${document_handle}`)
        .then(res => {
            if (!res.ok) throw new Error("Sync failed");
            return res.json();
        })
        .then(data => {
            renderDashboard(data);
            alert("Data synced successfully!");
        })
        .catch(err => {
            console.error("Sync error:", err);
            alert("Failed to sync from Codeforces API. Please try again later.");
        })
        .finally(() => {
            refreshBtn.disabled = false;
            refreshBtn.innerText = "🔄 Sync API Data";
        });
}

// Render dashboard stats and submissions
function renderDashboard(data) {
    document.getElementById("cf-handle-display").innerText = data.cf_handle;
    
    const rankDisplay = document.getElementById("rank-badge-display");
    rankDisplay.innerText = data.rank;
    rankDisplay.className = `rank-badge ${data.rank.toLowerCase().replace(/ /g, "-")}`;

    document.getElementById("stat-rating").innerText = data.rating || "Unrated";
    document.getElementById("stat-solved-today").innerText = data.accepted_today;
    document.getElementById("stat-avg-diff").innerText = data.average_difficulty_today || "0";

    // Render Submissions Today
    const subList = document.getElementById("submissions-list-display");
    subList.innerHTML = "";

    const todayStr = new Date().toISOString().split('T')[0];
    const todaySubs = data.recent_submissions.filter(sub => {
        const subDate = new Date(sub.creationTimeSeconds * 1000).toISOString().split('T')[0];
        return subDate === todayStr;
    });

    // AC / WA counts come directly from the backend dashboard response
    const acCount = data.accepted_today || 0;
    const waCount = data.wa_today || 0;

    const statsBadges = document.getElementById("sub-stats-badges");
    statsBadges.innerHTML = `
        <span class="badge ac-badge">AC: ${acCount}</span>
        <span class="badge wa-badge">WA: ${waCount}</span>
    `;

    if (todaySubs.length === 0) {
        subList.innerHTML = '<li class="empty-list-msg">No submissions detected today yet. Keep working!</li>';
        return;
    }

    todaySubs.forEach(sub => {
        const li = document.createElement("li");
        li.className = "submission-item";

        const prob = sub.problem;
        const verdict = sub.verdict === "OK" ? "ok" : "wa";
        const verdictText = sub.verdict === "OK" ? "AC" : (sub.verdict || "UNKNOWN");
        const probRating = prob.rating ? `[${prob.rating}]` : "";

        li.innerHTML = `
            <div class="sub-left">
                <span class="sub-title">${prob.name} ${probRating}</span>
                <span class="sub-meta">Problem: ${prob.contestId}${prob.index}</span>
            </div>
            <span class="sub-verdict ${verdict}">${verdictText}</span>
        `;
        subList.appendChild(li);
    });
}

// Form Handlers
function initForms() {
    const quickForm = document.getElementById("quick-log-form");
    const fullForm = document.getElementById("full-log-form");

    const handleFormSubmit = (e, prefix) => {
        e.preventDefault();

        const problemId = document.getElementById(`${prefix}-problem-id`).value;
        const problemTitle = document.getElementById(`${prefix}-problem-title`).value;
        const ratingVal = document.getElementById(`${prefix}-rating`).value;
        const status = document.getElementById(`${prefix}-status`).value;
        const mistakeCategory = document.getElementById(`${prefix}-mistake`).value;
        const customNotes = document.getElementById(`${prefix}-notes`).value;
        const solvedDate = new Date().toISOString().split('T')[0];

        const payload = {
            handle: document_handle,
            problem_id: problemId,
            problem_title: problemTitle,
            rating: ratingVal ? parseInt(ratingVal) : null,
            status: status,
            mistake_category: mistakeCategory || null,
            custom_notes: customNotes || null,
            solved_date: solvedDate
        };

        fetch(`${API_BASE_URL}/api/logs`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to save log");
            return res.json();
        })
        .then(data => {
            alert("Reflection log saved successfully!");
            e.target.reset();
            
            // Redirect to dashboard or load history
            if (prefix === "full") {
                document.querySelector('[data-target="dashboard-section"]').click();
            } else {
                syncData(); // Reload stats to count local log
            }
        })
        .catch(err => {
            console.error("Error saving log:", err);
            alert("Failed to save reflection log.");
        });
    };

    quickForm.addEventListener("submit", (e) => handleFormSubmit(e, "log"));
    fullForm.addEventListener("submit", (e) => handleFormSubmit(e, "full"));
}

// History Loader
function loadHistory() {
    const timeline = document.getElementById("history-timeline-list");
    timeline.innerHTML = '<p class="empty-list-msg">Loading history...</p>';

    fetch(`${API_BASE_URL}/api/history?handle=${document_handle}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to load history");
            return res.json();
        })
        .then(data => {
            timeline.innerHTML = "";
            if (data.length === 0) {
                timeline.innerHTML = '<p class="empty-list-msg">No history cached in SQLite yet.</p>';
                return;
            }

            data.forEach((day, index) => {
                const div = document.createElement("div");
                div.className = `timeline-item ${index === 0 ? "active" : ""}`;
                div.dataset.date = day.date;
                div.innerHTML = `
                    <span class="timeline-date">${day.date}</span>
                    <span class="timeline-stats">${day.accepted_count} AC / ${day.wa_count || 0} WA | Avg: ${day.average_difficulty || 0}</span>
                `;

                div.addEventListener("click", () => {
                    document.querySelectorAll(".timeline-item").forEach(item => item.classList.remove("active"));
                    div.classList.add("active");
                    loadDayDetails(day.date);
                });

                timeline.appendChild(div);
            });

            // Load details for first day initially
            loadDayDetails(data[0].date);
        })
        .catch(err => {
            console.error("History loading error:", err);
            timeline.innerHTML = '<p class="empty-list-msg">Failed to load history.</p>';
        });
}

// Load Specific Day Details
function loadDayDetails(date) {
    const detailPanel = document.getElementById("history-detail-content");
    const detailDate = document.getElementById("history-detail-date");
    
    detailDate.innerText = date;
    detailPanel.innerHTML = '<p class="empty-list-msg">Loading day details...</p>';

    fetch(`${API_BASE_URL}/api/history/${date}?handle=${document_handle}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to load day details");
            return res.json();
        })
        .then(data => {
            detailPanel.innerHTML = "";
            const stats = data.stats || { accepted_count: 0, average_difficulty: 0 };
            
            // Stats Row
            const statsRow = document.createElement("div");
            statsRow.className = "detail-stat-row";
            statsRow.innerHTML = `
                <div class="detail-badge"><strong>Solved Count:</strong> ${stats.accepted_count}</div>
                <div class="detail-badge"><strong>Average Difficulty:</strong> ${stats.average_difficulty || "N/A"}</div>
            `;
            detailPanel.appendChild(statsRow);

            // Logged Problems
            const probTitle = document.createElement("h3");
            probTitle.className = "detail-section-title";
            probTitle.innerText = "Reflection & Mistake Logs";
            detailPanel.appendChild(probTitle);

            const logsList = document.createElement("ul");
            logsList.className = "detail-mistakes-list";

            if (data.logs.length === 0) {
                detailPanel.innerHTML += '<p class="empty-list-msg">No manual reflection logs created for this date.</p>';
                return;
            }

            data.logs.forEach(log => {
                const li = document.createElement("li");
                li.className = "detail-mistake-item";
                
                const mistakeName = log.mistake_category ? log.mistake_category.replace(/_/g, " ").toLowerCase() : "none";
                const mistakeClass = log.mistake_category ? log.mistake_category.toLowerCase() : "none";
                const statusBadge = log.status === "AC" ? '<span class="sub-verdict ok">AC</span>' : `<span class="sub-verdict wa">${log.status}</span>`;
                const ratingBadge = log.rating ? `<span class="badge">[${log.rating}]</span>` : "";

                li.innerHTML = `
                    <div class="mistake-header-row">
                        <strong>${log.problem_id} - ${log.problem_title} ${ratingBadge}</strong>
                        ${statusBadge}
                    </div>
                    <div class="mistake-header-row" style="margin-bottom: 12px;">
                        <span class="mistake-badge ${mistakeClass}">${mistakeName}</span>
                    </div>
                    <p class="mistake-notes">"${log.custom_notes || "No custom notes recorded."}"</p>
                `;
                logsList.appendChild(li);
            });

            detailPanel.appendChild(logsList);
        })
        .catch(err => {
            console.error("Day details error:", err);
            detailPanel.innerHTML = '<p class="empty-list-msg">Failed to load day details.</p>';
        });
}

// Load Upsolve Tracker
function loadUpsolveTracker() {
    const container = document.getElementById("upsolve-list-display");
    container.innerHTML = '<p class="empty-list-msg">Loading upsolve tracking...</p>';

    fetch(`${API_BASE_URL}/api/contests/upsolve?handle=${document_handle}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to load upsolve tracker");
            return res.json();
        })
        .then(data => {
            container.innerHTML = "";
            if (data.length === 0) {
                container.innerHTML = '<p class="empty-list-msg">No contest participation detected in recent submissions.</p>';
                return;
            }

            data.forEach(contest => {
                const div = document.createElement("div");
                div.className = "upsolve-item";

                let statusClass = "not-attempted";
                if (contest.c_status === "Solved") statusClass = "solved";
                else if (contest.c_status === "Upsolved") statusClass = "upsolved";
                else if (contest.c_status === "Attempted but Failed") statusClass = "failed";

                div.innerHTML = `
                    <div class="upsolve-left">
                        <span class="upsolve-title">Contest #${contest.contest_id}</span>
                        <span class="upsolve-meta">Your Submitted Problems: ${contest.submitted_problems.join(", ") || "None"}</span>
                    </div>
                    <span class="upsolve-status ${statusClass}">${contest.c_status}</span>
                `;
                container.appendChild(div);
            });
        })
        .catch(err => {
            console.error("Upsolve tracker error:", err);
            container.innerHTML = '<p class="empty-list-msg">Failed to load upsolve tracking data.</p>';
        });
}
