// Teacher Management controller
document.addEventListener("DOMContentLoaded", () => {
    // Only run if we are on the teacher management page
    if (!window.location.pathname.endsWith("teacher_management.html")) return;

    const createForm = document.getElementById("create-teacher-form");
    if (!createForm) return;

    // Fetch user details to display top nav info
    apiFetch("/api/auth/me")
        .then(res => res.json())
        .then(user => {
            const navUserInfo = document.getElementById("nav-user-info");
            const fullName = user.full_name || user.username;
            navUserInfo.innerHTML = `<i class="fas fa-user-circle me-1"></i>${fullName} (${user.role})`;
        })
        .catch(err => console.error("Failed to load user profile in teacher management:", err));

    createForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const errorAlert = document.getElementById("error-alert");
        const successAlert = document.getElementById("success-alert");
        const submitBtn = document.getElementById("submit-btn");

        // Reset UI
        errorAlert.classList.add("d-none");
        errorAlert.textContent = "";
        successAlert.classList.add("d-none");
        successAlert.textContent = "";

        const payload = {
            full_name: document.getElementById("fullname").value.trim(),
            username: document.getElementById("username").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value
        };

        // Disable UI
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Adding Teacher...`;

        try {
            const response = await apiFetch("/api/auth/create-teacher", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                successAlert.textContent = `Teacher account '${payload.username}' successfully created!`;
                successAlert.classList.remove("d-none");
                createForm.reset();
            } else {
                errorAlert.textContent = data.detail || "Failed to create teacher account. Username or email may already be taken.";
                errorAlert.classList.remove("d-none");
            }
        } catch (err) {
            console.error("Create teacher failed:", err);
            errorAlert.textContent = "Error communicating with server.";
            errorAlert.classList.remove("d-none");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<i class="fas fa-user-check me-2"></i>Add Teacher User`;
        }
    });
});
