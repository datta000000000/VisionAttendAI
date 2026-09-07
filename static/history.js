// Attendance logs history pagination and filtering
let currentPage = 1;
const pageSize = 15;
let currentSortBy = "date";
let currentSortOrder = "desc";

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.location.pathname.endsWith("history.html")) return;

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

    const filterForm = document.getElementById("filter-form");
    const resetBtn = document.getElementById("reset-btn");
    const refreshBtn = document.getElementById("refresh-btn");
    const prevPageBtn = document.getElementById("prev-page-btn");
    const nextPageBtn = document.getElementById("next-page-btn");

    if (filterForm) {
        filterForm.addEventListener("submit", (e) => {
            e.preventDefault();
            currentPage = 1;
            fetchHistory();
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            filterForm.reset();
            currentPage = 1;
            fetchHistory();
        });
    }

    if (refreshBtn) {
        refreshBtn.addEventListener("click", fetchHistory);
    }

    if (prevPageBtn) {
        prevPageBtn.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage--;
                fetchHistory();
            }
        });
    }

    if (nextPageBtn) {
        nextPageBtn.addEventListener("click", () => {
            currentPage++;
            fetchHistory();
        });
    }

    // Set sorting columns click listeners
    const sortHeaders = document.querySelectorAll("th[data-sort]");
    sortHeaders.forEach(th => {
        th.addEventListener("click", () => {
            const sortField = th.getAttribute("data-sort");
            if (currentSortBy === sortField) {
                currentSortOrder = currentSortOrder === "asc" ? "desc" : "asc";
            } else {
                currentSortBy = sortField;
                currentSortOrder = "desc";
            }

            // Remove existing caret icons
            sortHeaders.forEach(h => {
                const icon = h.querySelector("i");
                if (icon) icon.className = "fas fa-sort text-muted ms-1";
            });

            // Update header class
            const icon = th.querySelector("i");
            if (icon) {
                icon.className = currentSortOrder === "asc" ? "fas fa-sort-up ms-1" : "fas fa-sort-down ms-1";
            }

            fetchHistory();
        });
    });

    // Populate initial listing
    fetchHistory();
});

// 1. Query history data with parameters
async function fetchHistory() {
    const tableBody = document.getElementById("history-table-body");
    const totalCountElem = document.getElementById("total-count");
    const pageNumElem = document.getElementById("page-num");
    const totalPagesElem = document.getElementById("total-pages");
    const prevPageBtn = document.getElementById("prev-page-btn");
    const nextPageBtn = document.getElementById("next-page-btn");

    if (!tableBody) return;

    // Load filter values
    const studentId = document.getElementById("filter-student-id").value.trim();
    const name = document.getElementById("filter-name").value.trim();
    const department = document.getElementById("filter-department").value;
    const date = document.getElementById("filter-date").value;
    const startDate = document.getElementById("filter-start-date").value;
    const endDate = document.getElementById("filter-end-date").value;

    // Validate date format checks locally (FastAPI also validates, but local prevents bad queries)
    if (date && !isValidDateFormat(date)) {
        showToast("Invalid Date", "Date format must be YYYY-MM-DD", "danger");
        return;
    }
    if (startDate && !isValidDateFormat(startDate)) {
        showToast("Invalid Date", "Start Date format must be YYYY-MM-DD", "danger");
        return;
    }
    if (endDate && !isValidDateFormat(endDate)) {
        showToast("Invalid Date", "End Date format must be YYYY-MM-DD", "danger");
        return;
    }

    // Build query URL
    let url = `/api/attendance/history?page=${currentPage}&limit=${pageSize}&sort_by=${currentSortBy}&sort_order=${currentSortOrder}`;
    if (studentId) url += `&student_id=${encodeURIComponent(studentId)}`;
    if (name) url += `&name=${encodeURIComponent(name)}`;
    if (department) url += `&department=${encodeURIComponent(department)}`;
    if (date) url += `&date=${date}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;

    tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4"><span class="spinner-border spinner-border-sm me-2"></span> Loading logs...</td></tr>`;

    try {
        const response = await apiFetch(url);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Query failed");
        }

        const data = await response.json();

        // 2. Populate table
        if (data.records.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No matching logs found.</td></tr>`;
        } else {
            let rowsHTML = "";
            data.records.forEach(row => {
                let badgeClass = "badge-unknown";
                if (row.status === "Present") {
                    badgeClass = "badge-present";
                }
                
                rowsHTML += `
                    <tr>
                        <td class="font-monospace">${escapeHTML(row.student_id)}</td>
                        <td>${escapeHTML(row.name)}</td>
                        <td>${escapeHTML(row.department)}</td>
                        <td>${row.date}</td>
                        <td>${row.time}</td>
                        <td><span class="badge ${badgeClass}">${row.status}</span></td>
                        <td class="font-monospace">${Math.round(row.confidence_score * 100)}%</td>
                    </tr>
                `;
            });
            tableBody.innerHTML = rowsHTML;
        }

        // 3. Update pagination states
        if (totalCountElem) totalCountElem.textContent = data.total;
        if (pageNumElem) pageNumElem.textContent = data.page;
        if (totalPagesElem) totalPagesElem.textContent = data.pages;

        currentPage = data.page;
        if (prevPageBtn) prevPageBtn.disabled = currentPage <= 1;
        if (nextPageBtn) nextPageBtn.disabled = currentPage >= data.pages || data.pages === 0;

    } catch (err) {
        console.error("Fetch history error:", err);
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-4">Failed to load logs from server.</td></tr>`;
        showToast("Query Error", err.message || "Failed to load logs.", "danger");
    }
}

// Simple YYYY-MM-DD regex check
function isValidDateFormat(dateStr) {
    const regex = /^\d{4}-\d{2}-\d{2}$/;
    return regex.test(dateStr);
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
