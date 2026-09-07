// Dashboard statistics logic
document.addEventListener("DOMContentLoaded", async () => {
    // Only execute if on dashboard page
    if (!window.location.pathname.endsWith("dashboard.html")) return;

    // Fetch user details for top nav
    try {
        const userRes = await apiFetch("/api/auth/me");
        if (userRes.ok) {
            const user = await userRes.json();
            const fullName = user.full_name || user.username;
            const topUserRole = document.getElementById("top-user-role");
            if (topUserRole) {
                topUserRole.innerHTML = `<i class="fas fa-user-circle me-1"></i>${fullName} (${user.role})`;
            }
        }
    } catch (e) {
        console.error("Error fetching user info:", e);
    }

    fetchDashboardStats();
    fetchRecentActivity();
    
    // Auto-refresh stats every 30 seconds
    setInterval(() => {
        fetchDashboardStats();
        fetchRecentActivity();
    }, 30000);
});

async function fetchDashboardStats() {
    const totalStudentsElem = document.getElementById("total-students");
    const todayAttendanceElem = document.getElementById("today-attendance");
    const todayPercentageElem = document.getElementById("today-percentage");
    const overallPercentageElem = document.getElementById("overall-percentage");
    const registeredEmbeddingsElem = document.getElementById("registered-embeddings");
    const departmentStatsContainer = document.getElementById("department-stats-container");
    const lastUpdateElem = document.getElementById("last-update");

    try {
        const response = await apiFetch("/api/dashboard/stats");
        if (!response.ok) {
            throw new Error(`Failed to fetch stats: ${response.statusText}`);
        }
        
        const data = await response.json();

        // 1. Populate summary stats
        if (totalStudentsElem) totalStudentsElem.textContent = data.total_students;
        if (todayAttendanceElem) todayAttendanceElem.textContent = data.today_attendance_count;
        if (todayPercentageElem) todayPercentageElem.textContent = `${data.attendance_percentage}%`;
        if (overallPercentageElem) overallPercentageElem.textContent = `${data.overall_attendance_percentage}%`;
        if (registeredEmbeddingsElem) registeredEmbeddingsElem.textContent = data.registered_embeddings_count;

        // 2. Populate department-wise listing
        if (departmentStatsContainer) {
            const depts = data.department_wise_counts;
            if (Object.keys(depts).length === 0) {
                departmentStatsContainer.innerHTML = `<li class="list-group-item text-center text-muted py-3">No departments found. Register students first.</li>`;
            } else {
                let listHTML = "";
                for (const [dept, count] of Object.entries(depts)) {
                    listHTML += `
                        <li class="list-group-item d-flex justify-content-between align-items-center py-3">
                            <div>
                                <i class="fas fa-university me-2 text-primary"></i>${escapeHTML(dept)}
                            </div>
                            <span class="badge bg-primary rounded-pill font-monospace">${count} students</span>
                        </li>
                    `;
                }
                departmentStatsContainer.innerHTML = listHTML;
            }
        }

        // Update timestamp
        if (lastUpdateElem) {
            const now = new Date();
            lastUpdateElem.textContent = `Last update: ${now.toLocaleTimeString()}`;
        }

    } catch (err) {
        console.error("Dashboard stats error:", err);
        showToast("Stats Load Failure", "Could not fetch dashboard statistics from the server.", "danger");
    }
}

async function fetchRecentActivity() {
    const recentActivityContainer = document.getElementById("recent-activity-container");
    if (!recentActivityContainer) return;

    try {
        const response = await apiFetch("/api/attendance/history?limit=5");
        if (!response.ok) {
            throw new Error(`Failed to fetch recent history logs: ${response.statusText}`);
        }

        const data = await response.json();
        const records = data.records || [];

        if (records.length === 0) {
            recentActivityContainer.innerHTML = `<li class="list-group-item text-center text-muted py-3"><i class="fas fa-history me-2"></i>No recent attendance logs recorded today.</li>`;
        } else {
            let listHTML = "";
            records.forEach(rec => {
                const confScore = Math.round(rec.confidence_score * 100);
                listHTML += `
                    <li class="list-group-item py-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong class="text-navy">${escapeHTML(rec.name)}</strong> 
                                <span class="text-muted small">(${escapeHTML(rec.student_id)})</span>
                            </div>
                            <span class="badge badge-present">Present</span>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mt-1">
                            <span class="text-secondary small font-monospace"><i class="far fa-clock me-1"></i>${rec.date} ${rec.time}</span>
                            <span class="text-secondary small font-monospace">Confidence: ${confScore}%</span>
                        </div>
                    </li>
                `;
            });
            recentActivityContainer.innerHTML = listHTML;
        }
    } catch (err) {
        console.error("Dashboard recent activity load failure:", err);
        recentActivityContainer.innerHTML = `<li class="list-group-item text-center text-danger py-3">Failed to load recent activity logs.</li>`;
    }
}

// Simple HTML escaping helper to prevent XSS
function escapeHTML(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
