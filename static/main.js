// Shared JavaScript for VisionAttend UI
const API_BASE = "";

// 1. Session Storage Token Accessors
function getToken() {
    return sessionStorage.getItem("access_token");
}

function setToken(token) {
    sessionStorage.setItem("access_token", token);
}

function clearToken() {
    sessionStorage.removeItem("access_token");
}

// 2. Globally Protect Pages & Verify Token
// 2. Globally Protect Pages & Verify Token
async function checkAuth() {
    const currentPage = window.location.pathname;
    const token = getToken();
    
    const isAuthPage = currentPage === "/" || 
                       currentPage.endsWith("index.html") || 
                       currentPage === "" || 
                       currentPage.endsWith("signup.html");

    if (isAuthPage) {
        // If user already has a token, check if valid and redirect to their dashboard
        if (token) {
            try {
                const res = await fetch(`${API_BASE}/api/auth/me`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });
                if (res.ok) {
                    const user = await res.json();
                    sessionStorage.setItem("user_role", user.role);
                    sessionStorage.setItem("user_fullname", user.full_name || user.username);
                    if (user.role === "admin") {
                        window.location.href = "dashboard.html";
                    } else if (user.role === "teacher") {
                        window.location.href = "teacher_dashboard.html";
                    } else if (user.role === "student") {
                        window.location.href = "student_dashboard.html";
                    }
                }
            } catch (e) {
                // Ignore errors, stay on login page
            }
        }
        return;
    }

    // For all other pages, enforce token presence
    if (!token) {
        window.location.href = "index.html";
        return;
    }

    // Verify token validity and role with backend
    try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) {
            logout();
            return;
        }
        const user = await res.json();
        sessionStorage.setItem("user_role", user.role);
        sessionStorage.setItem("user_fullname", user.full_name || user.username);

        // Role-based route guard
        if (user.role === "student") {
            if (!currentPage.endsWith("student_dashboard.html")) {
                window.location.href = "student_dashboard.html";
            }
        } else if (user.role === "teacher") {
            const allowedPages = ["teacher_dashboard.html", "registration.html", "recognition.html", "history.html", "reports.html"];
            const isAllowed = allowedPages.some(page => currentPage.endsWith(page));
            if (!isAllowed) {
                window.location.href = "teacher_dashboard.html";
            }
        } else if (user.role === "admin") {
            const allowedPages = ["dashboard.html", "registration.html", "recognition.html", "history.html", "reports.html", "teacher_management.html"];
            const isAllowed = allowedPages.some(page => currentPage.endsWith(page));
            if (!isAllowed) {
                window.location.href = "dashboard.html";
            }
        }
    } catch (err) {
        console.error("Auth verify error:", err);
        showToast("Server Connection Failed", "Cannot reach backend services.", "danger");
    }
}

// 3. Logout action
function logout() {
    clearToken();
    sessionStorage.removeItem("user_role");
    sessionStorage.removeItem("user_fullname");
    window.location.href = "index.html";
}

// 4. API Fetch Wrapper carrying bearer tokens
async function apiFetch(url, options = {}) {
    const token = getToken();
    if (token) {
        options.headers = options.headers || {};
        options.headers["Authorization"] = `Bearer ${token}`;
    }
    
    try {
        const response = await fetch(url, options);
        if (response.status === 401) {
            logout();
            throw new Error("Unauthorized");
        }
        return response;
    } catch (err) {
        console.error(`API Fetch Error [${url}]:`, err);
        throw err;
    }
}

// 5. Dynamic Navigation Sidebar & Header Generation
function injectNavbar() {
    const sidebarContainer = document.getElementById("sidebar-container");
    if (!sidebarContainer) return;

    const currentPath = window.location.pathname;
    const isPageActive = (pageName) => currentPath.endsWith(pageName) ? 'active' : '';
    const userRole = sessionStorage.getItem("user_role") || "admin";
    const userFullname = sessionStorage.getItem("user_fullname") || "User";

    let menuItemsHTML = "";

    if (userRole === "admin") {
        menuItemsHTML = `
            <a href="dashboard.html" class="list-group-item list-group-item-action ${isPageActive('dashboard.html')}">
                <i class="fas fa-chart-line"></i>Dashboard
            </a>
            <a href="registration.html" class="list-group-item list-group-item-action ${isPageActive('registration.html')}">
                <i class="fas fa-user-plus"></i>Student Register
            </a>
            <a href="recognition.html" class="list-group-item list-group-item-action ${isPageActive('recognition.html')}">
                <i class="fas fa-video"></i>Live Attendance
            </a>
            <a href="history.html" class="list-group-item list-group-item-action ${isPageActive('history.html')}">
                <i class="fas fa-history"></i>History Log
            </a>
            <a href="reports.html" class="list-group-item list-group-item-action ${isPageActive('reports.html')}">
                <i class="fas fa-file-invoice"></i>CSV & Reports
            </a>
            <a href="teacher_management.html" class="list-group-item list-group-item-action ${isPageActive('teacher_management.html')}">
                <i class="fas fa-user-tie"></i>Teachers
            </a>
        `;
    } else if (userRole === "teacher") {
        menuItemsHTML = `
            <a href="teacher_dashboard.html" class="list-group-item list-group-item-action ${isPageActive('teacher_dashboard.html')}">
                <i class="fas fa-chart-line"></i>Dashboard
            </a>
            <a href="registration.html" class="list-group-item list-group-item-action ${isPageActive('registration.html')}">
                <i class="fas fa-user-plus"></i>Student Register
            </a>
            <a href="recognition.html" class="list-group-item list-group-item-action ${isPageActive('recognition.html')}">
                <i class="fas fa-video"></i>Live Attendance
            </a>
            <a href="history.html" class="list-group-item list-group-item-action ${isPageActive('history.html')}">
                <i class="fas fa-history"></i>History Log
            </a>
            <a href="reports.html" class="list-group-item list-group-item-action ${isPageActive('reports.html')}">
                <i class="fas fa-chart-pie"></i>Reports & Stats
            </a>
        `;
    } else if (userRole === "student") {
        menuItemsHTML = `
            <a href="student_dashboard.html" class="list-group-item list-group-item-action ${isPageActive('student_dashboard.html')}">
                <i class="fas fa-user-graduate"></i>My Portal
            </a>
        `;
    }

    sidebarContainer.innerHTML = `
        <div class="sidebar-heading text-center">
            <i class="fas fa-camera-retro me-2"></i>VisionAttend AI
        </div>
        <div class="sidebar-user text-center py-3 border-bottom border-secondary mb-2">
            <div class="small text-muted mb-1">Role: <span class="badge bg-indigo text-capitalize">${userRole}</span></div>
            <div class="fw-bold text-white">${userFullname}</div>
        </div>
        <div class="list-group list-group-flush mt-2">
            ${menuItemsHTML}
            <a href="#" onclick="logout(); return false;" class="list-group-item list-group-item-action mt-5 text-danger">
                <i class="fas fa-sign-out-alt"></i>Logout
            </a>
        </div>
    `;
}

// 6. Bootstrap Toast Notification Handler
function showToast(title, message, type = "success") {
    let toastContainer = document.getElementById("toast-container-custom");
    if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.id = "toast-container-custom";
        toastContainer.className = "toast-container-custom";
        document.body.appendChild(toastContainer);
    }

    const toastId = `toast-${Date.now()}`;
    const borderClass = `border-${type}`;
    const bgClass = type === "danger" ? "text-danger" : type === "warning" ? "text-warning" : "text-success";

    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center bg-white border ${borderClass} show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <strong class="${bgClass}">${title}</strong><br>
                    <span class="text-secondary">${message}</span>
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close" onclick="document.getElementById('${toastId}').remove()"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML("beforeend", toastHTML);
    
    // Auto-remove toast after 4 seconds
    setTimeout(() => {
        const toastElement = document.getElementById(toastId);
        if (toastElement) {
            toastElement.classList.remove("show");
            setTimeout(() => toastElement.remove(), 500);
        }
    }, 4000);
}

// Run auth check, inject navbar, and bind mobile menu toggles on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    checkAuth();
    injectNavbar();
    
    // Mobile sidebar toggle binding
    const menuToggle = document.getElementById("menu-toggle");
    if (menuToggle) {
        menuToggle.addEventListener("click", (e) => {
            e.preventDefault();
            const wrapper = document.getElementById("wrapper");
            const sidebar = document.getElementById("sidebar-wrapper");
            const pageContent = document.getElementById("page-content-wrapper");
            if (wrapper) wrapper.classList.toggle("toggled");
            if (sidebar) sidebar.classList.toggle("toggled");
            if (pageContent) pageContent.classList.toggle("toggled");
        });
    }
});
