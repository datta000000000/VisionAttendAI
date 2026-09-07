// Teacher Dashboard controller
document.addEventListener("DOMContentLoaded", async () => {
    // Only run if we are on the teacher dashboard
    if (!window.location.pathname.endsWith("teacher_dashboard.html")) return;

    const welcomeName = document.getElementById("welcome-name");
    const lastUpdate = document.getElementById("last-update");
    const totalStudentsVal = document.getElementById("total-students");
    const todayAttendanceVal = document.getElementById("today-attendance");
    const todayPercentageVal = document.getElementById("today-percentage");
    const overallPercentageVal = document.getElementById("overall-percentage");
    
    const profileName = document.getElementById("teacher-profile-name");
    const profileRole = document.getElementById("teacher-profile-role");
    const orgCodeVal = document.getElementById("teacher-org-code");
    const navUserInfo = document.getElementById("nav-user-info");

    // Fetch user details
    try {
        const userRes = await apiFetch("/api/auth/me");
        if (userRes.ok) {
            const user = await userRes.json();
            const fullName = user.full_name || user.username;
            welcomeName.textContent = fullName;
            profileName.textContent = fullName;
            profileRole.textContent = user.role;
            navUserInfo.innerHTML = `<i class="fas fa-user-circle me-1"></i>${fullName} (${user.role})`;
            
            if (user.organization) {
                orgCodeVal.textContent = user.organization.organization_code;
            } else {
                orgCodeVal.textContent = "DEFAULT-ORG";
            }
        }
    } catch (err) {
        console.error("Failed to load teacher profile info:", err);
    }

    fetchTeacherStats();
    fetchRecentActivity();

    // Auto-refresh every 30 seconds
    setInterval(() => {
        fetchTeacherStats();
        fetchRecentActivity();
    }, 30000);

    async function fetchTeacherStats() {
        try {
            const statsRes = await apiFetch("/api/dashboard/stats");
            if (statsRes.ok) {
                const stats = await statsRes.json();
                
                if (totalStudentsVal) totalStudentsVal.textContent = stats.total_students;
                if (todayAttendanceVal) todayAttendanceVal.textContent = stats.today_attendance_count;
                if (todayPercentageVal) todayPercentageVal.textContent = `${stats.attendance_percentage}%`;
                if (overallPercentageVal) overallPercentageVal.textContent = `${stats.overall_attendance_percentage}%`;
                
                // Format update time
                const now = new Date();
                if (lastUpdate) {
                    lastUpdate.textContent = `Status updated at ${now.toLocaleTimeString()} on ${stats.today_date}`;
                }
            } else {
                showToast("Stats Failed", "Could not fetch dashboard analytics.", "danger");
            }
        } catch (err) {
            console.error("Failed to load dashboard stats:", err);
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
});

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
