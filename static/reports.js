// Report charts generation & CSV exports
let departmentChart = null;
let monthlyChart = null;

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.location.pathname.endsWith("reports.html")) return;

    // Fetch user details for top nav and role-based interface tweaks
    try {
        const userRes = await apiFetch("/api/auth/me");
        if (userRes.ok) {
            const user = await userRes.json();
            const fullName = user.full_name || user.username;
            const topUserRole = document.getElementById("top-user-role");
            if (topUserRole) {
                topUserRole.innerHTML = `<i class="fas fa-user-circle me-1"></i>${fullName} (${user.role})`;
            }

            // Hide CSV export card for teachers
            if (user.role === "teacher") {
                const exportCard = document.getElementById("export-card-container");
                if (exportCard) {
                    exportCard.style.display = "none";
                }
            }
        }
    } catch (e) {
        console.error("Error fetching user info in reports page:", e);
    }

    const exportBtn = document.getElementById("export-csv-btn");
    const filterForm = document.getElementById("report-filter-form");

    if (exportBtn) {
        exportBtn.addEventListener("click", exportCSV);
    }

    if (filterForm) {
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            // Just triggers CSV export or updates chart?
            // The prompt says "Export CSV button with current filters if practical".
            exportCSV();
        });
    }

    // Populate stats and charts
    fetchReportStats();
});

// 1. Fetch aggregate stats for displays and charts
async function fetchReportStats() {
    const totalPresentsElem = document.getElementById("total-presents");
    const overallPercentageElem = document.getElementById("overall-percentage");

    try {
        const response = await apiFetch("/api/reports/stats");
        if (!response.ok) {
            throw new Error(`Failed to load stats: ${response.statusText}`);
        }

        const data = await response.json();

        // Populate text metrics
        if (totalPresentsElem) totalPresentsElem.textContent = data.total_present_records;
        if (overallPercentageElem) overallPercentageElem.textContent = `${data.overall_attendance_percentage}%`;

        // Render Charts using Chart.js
        renderDepartmentChart(data.department_wise_attendance);
        renderMonthlyChart(data.monthly_attendance);

    } catch (err) {
        console.error("Report stats failure:", err);
        showToast("Stats Load Mismatch", "Could not fetch report metrics.", "danger");
    }
}

// 2. Render Department Stats Bar Chart
function renderDepartmentChart(deptData) {
    const ctx = document.getElementById("department-chart");
    if (!ctx) return;

    const labels = Object.keys(deptData);
    const percentages = Object.values(deptData).map(d => d.attendance_percentage);

    if (departmentChart) {
        departmentChart.destroy();
    }

    departmentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Attendance Percentage (%)',
                data: percentages,
                backgroundColor: 'rgba(63, 81, 181, 0.7)',
                borderColor: 'rgba(63, 81, 181, 1)',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: 'Percentage (%)' }
                }
            }
        }
    });
}

// 3. Render Monthly Stats Line Chart
function renderMonthlyChart(monthlyData) {
    const ctx = document.getElementById("monthly-chart");
    if (!ctx) return;

    const labels = Object.keys(monthlyData).sort(); // Sort chronological
    const counts = labels.map(m => monthlyData[m]);

    if (monthlyChart) {
        monthlyChart.destroy();
    }

    monthlyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Present Logs',
                data: counts,
                fill: true,
                backgroundColor: 'rgba(245, 0, 87, 0.1)',
                borderColor: 'rgba(245, 0, 87, 1)',
                borderWidth: 2,
                tension: 0.3,
                pointBackgroundColor: 'rgba(245, 0, 87, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 },
                    title: { display: true, text: 'Presents Count' }
                }
            }
        }
    });
}

// 4. Download CSV via Fetch carrying headers
async function exportCSV() {
    const exportBtn = document.getElementById("export-csv-btn");
    
    // Read filter values from reports page form
    const studentId = document.getElementById("filter-student-id").value.trim();
    const name = document.getElementById("filter-name").value.trim();
    const department = document.getElementById("filter-department").value;
    const date = document.getElementById("filter-date").value;
    const startDate = document.getElementById("filter-start-date").value;
    const endDate = document.getElementById("filter-end-date").value;

    let exportUrl = `/api/reports/export?`;
    if (studentId) exportUrl += `&student_id=${encodeURIComponent(studentId)}`;
    if (name) exportUrl += `&name=${encodeURIComponent(name)}`;
    if (department) exportUrl += `&department=${encodeURIComponent(department)}`;
    if (date) exportUrl += `&date=${date}`;
    if (startDate) exportUrl += `&start_date=${startDate}`;
    if (endDate) exportUrl += `&end_date=${endDate}`;

    if (exportBtn) {
        exportBtn.disabled = true;
        exportBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Exporting...`;
    }

    try {
        const response = await apiFetch(exportUrl);
        if (!response.ok) {
            throw new Error(`CSV export failed: ${response.statusText}`);
        }

        const blob = await response.blob();
        
        // Dynamic file download link trigger
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `attendance_report_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);

        showToast("CSV Exported", "Report downloaded successfully.", "success");

    } catch (err) {
        console.error("CSV export failure:", err);
        showToast("Export Failed", "Could not download CSV report file.", "danger");
    } finally {
        if (exportBtn) {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<i class="fas fa-file-csv me-2"></i>Export CSV';
        }
    }
}
