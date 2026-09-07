// Student Dashboard controller
document.addEventListener("DOMContentLoaded", async () => {
    // Only run if we are on the student dashboard
    if (!window.location.pathname.endsWith("student_dashboard.html")) return;

    const welcomeName = document.getElementById("welcome-name");
    const todayStatus = document.getElementById("today-status");
    const todayStatusCard = document.getElementById("today-status-card");
    const todayStatusIcon = document.getElementById("today-status-icon");
    
    const overallPercentage = document.getElementById("overall-percentage");
    const attendanceBody = document.getElementById("attendance-body");
    
    const profileName = document.getElementById("profile-name");
    const profileStudentId = document.getElementById("profile-student-id");
    const profileOrg = document.getElementById("profile-org");
    const navUserInfo = document.getElementById("nav-user-info");

    try {
        const response = await apiFetch("/api/dashboard/student/stats");
        if (response.ok) {
            const data = await response.json();
            
            // Populate profile
            const fullName = data.name;
            welcomeName.textContent = fullName;
            profileName.textContent = fullName;
            profileStudentId.textContent = data.student_id;
            profileOrg.textContent = data.organization_name;
            navUserInfo.innerHTML = `<i class="fas fa-user-graduate me-1"></i>${fullName} (${data.student_id})`;

            // Populate today's check-in status cards
            todayStatus.textContent = data.today_status;
            if (data.today_status === "Present") {
                todayStatusCard.className = "stat-card accent-green";
                todayStatusIcon.className = "text-success fs-1";
                todayStatusIcon.innerHTML = `<i class="fas fa-check-circle"></i>`;
            } else if (data.today_status === "Absent") {
                todayStatusCard.className = "stat-card accent-red";
                todayStatusIcon.className = "text-danger fs-1";
                todayStatusIcon.innerHTML = `<i class="fas fa-times-circle"></i>`;
            } else {
                todayStatusCard.className = "stat-card";
                todayStatusIcon.className = "text-secondary fs-1";
                todayStatusIcon.innerHTML = `<i class="fas fa-minus-circle"></i>`;
            }

            // Populate overall percentage rate
            overallPercentage.textContent = `${data.overall_attendance_percentage}%`;

            // Populate recent logs list
            attendanceBody.innerHTML = "";
            const records = data.recent_records || [];
            
            if (records.length === 0) {
                attendanceBody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary py-3">No attendance logs found for your ID.</td></tr>`;
            } else {
                records.forEach(rec => {
                    const simScorePercent = (rec.confidence_score * 100).toFixed(1);
                    attendanceBody.insertAdjacentHTML("beforeend", `
                        <tr>
                            <td>${rec.date}</td>
                            <td>${rec.time}</td>
                            <td><span class="badge badge-present">Present</span></td>
                            <td><span class="text-secondary">${simScorePercent}% match</span></td>
                        </tr>
                    `);
                });
            }
        } else {
            showToast("Failed to fetch Student Stats", "Dashboard service could not load your data.", "danger");
        }
    } catch (err) {
        console.error("Failed to load student dashboard info:", err);
        showToast("Error", "Error connecting to student dashboard services.", "danger");
    }
});
