// Sign Up frontend controller
document.addEventListener("DOMContentLoaded", () => {
    const signupForm = document.getElementById("signup-form");
    if (!signupForm) return;

    const roleSelect = document.getElementById("role");
    const orgCreationFields = document.getElementById("org-creation-fields");
    const studentOnlyFields = document.getElementById("student-only-fields");
    const orgNameInput = document.getElementById("org_name");
    const studentIdInput = document.getElementById("student_id");
    const orgCodeHelp = document.getElementById("org-code-help");

    const roleAdminCard = document.getElementById("role-admin-card");
    const roleStudentCard = document.getElementById("role-student-card");

    // Dynamic card selection hookup
    if (roleAdminCard && roleStudentCard && roleSelect) {
        roleAdminCard.addEventListener("click", () => {
            roleAdminCard.classList.add("active");
            roleStudentCard.classList.remove("active");
            roleSelect.value = "admin";
            roleSelect.dispatchEvent(new Event("change"));
        });

        roleStudentCard.addEventListener("click", () => {
            roleStudentCard.classList.add("active");
            roleAdminCard.classList.remove("active");
            roleSelect.value = "student";
            roleSelect.dispatchEvent(new Event("change"));
        });
    }

    // Dynamic field visibility toggling based on selected role
    roleSelect.addEventListener("change", () => {
        const val = roleSelect.value;
        if (val === "admin") {
            orgCreationFields.classList.remove("d-none");
            studentOnlyFields.classList.add("d-none");
            orgNameInput.required = true;
            studentIdInput.required = false;
            orgCodeHelp.textContent = "A unique code used to group your organization accounts.";
        } else if (val === "student") {
            orgCreationFields.classList.add("d-none");
            studentOnlyFields.classList.remove("d-none");
            orgNameInput.required = false;
            studentIdInput.required = true;
            orgCodeHelp.textContent = "Provide the organization code given by your administrator.";
        }
    });

    // Initial trigger
    roleSelect.dispatchEvent(new Event("change"));

    // Form Submission
    signupForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const errorAlert = document.getElementById("error-alert");
        const successAlert = document.getElementById("success-alert");
        const submitBtn = document.getElementById("submit-btn");

        // Reset UI
        errorAlert.classList.add("d-none");
        errorAlert.textContent = "";
        successAlert.classList.add("d-none");
        successAlert.textContent = "";

        const password = document.getElementById("password").value;
        const confirm_password = document.getElementById("confirm_password").value;

        if (password !== confirm_password) {
            errorAlert.textContent = "Passwords do not match.";
            errorAlert.classList.remove("d-none");
            return;
        }

        const payload = {
            role: roleSelect.value,
            full_name: document.getElementById("fullname").value.trim(),
            username: document.getElementById("username").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: password,
            confirm_password: confirm_password,
            organization_name: orgNameInput.value.trim() || "Joined Organization",
            organization_code: document.getElementById("org_code").value.trim(),
            student_id: roleSelect.value === "student" ? studentIdInput.value.trim() : null
        };

        // Disable UI
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creating Account...`;

        try {
            const response = await fetch("/api/auth/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                successAlert.textContent = "Account registered successfully! Redirecting to login page...";
                successAlert.classList.remove("d-none");
                
                // Clear form
                signupForm.reset();
                
                setTimeout(() => {
                    window.location.href = "index.html";
                }, 2000);
            } else {
                errorAlert.textContent = data.detail || "Registration failed. Please check inputs.";
                errorAlert.classList.remove("d-none");
            }
        } catch (err) {
            console.error("Signup failed:", err);
            errorAlert.textContent = "Connection to server failed. Please try again later.";
            errorAlert.classList.remove("d-none");
        } finally {
            if (!successAlert.classList.contains("d-none")) return;
            submitBtn.disabled = false;
            submitBtn.innerHTML = "Register Account";
        }
    });
});
