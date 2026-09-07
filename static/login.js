// Login logic
document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    if (!loginForm) return;

    // Password Show/Hide Toggle
    const passwordInput = document.getElementById("password");
    const passwordToggle = document.getElementById("password-toggle");
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener("click", () => {
            const isPassword = passwordInput.getAttribute("type") === "password";
            passwordInput.setAttribute("type", isPassword ? "text" : "password");
            
            const icon = passwordToggle.querySelector("i");
            if (icon) {
                icon.className = isPassword ? "fas fa-eye-slash" : "fas fa-eye";
            }
        });
    }

    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const usernameInput = document.getElementById("username");
        const errorAlert = document.getElementById("error-alert");
        const submitBtn = document.getElementById("submit-btn");

        // UI Reset
        errorAlert.classList.add("d-none");
        errorAlert.textContent = "";
        
        const username = usernameInput.value.trim();
        const password = passwordInput.value.trim();

        if (!username || !password) {
            errorAlert.textContent = "Please fill in all fields.";
            errorAlert.classList.remove("d-none");
            return;
        }

        // Disable elements during login request
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Logging in...`;

        try {
            const response = await fetch("/api/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                // Save access token
                setToken(data.access_token);
                // Save role info in sessionStorage
                sessionStorage.setItem("user_role", data.user.role);
                sessionStorage.setItem("user_fullname", data.user.full_name || data.user.username);
                
                // Redirect to role-specific portal
                if (data.user.role === "admin") {
                    window.location.href = "dashboard.html";
                } else if (data.user.role === "teacher") {
                    window.location.href = "teacher_dashboard.html";
                } else if (data.user.role === "student") {
                    window.location.href = "student_dashboard.html";
                } else {
                    window.location.href = "dashboard.html";
                }
            } else {
                errorAlert.textContent = data.detail || "Invalid credentials. Please try again.";
                errorAlert.classList.remove("d-none");
            }
        } catch (err) {
            console.error("Login failure:", err);
            errorAlert.textContent = "Connection to server failed. Please ensure the backend is running.";
            errorAlert.classList.remove("d-none");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = "Sign In";
        }
    });
});
