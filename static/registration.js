// Student registration camera & form logic
let localStream = null;
let capturedSnapshots = []; // Array of { dataUrl, blob }

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.location.pathname.endsWith("registration.html")) return;

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

    const startCamBtn = document.getElementById("start-cam-btn");
    const captureBtn = document.getElementById("capture-btn");
    const regForm = document.getElementById("registration-form");

    if (startCamBtn) {
        startCamBtn.addEventListener("click", startWebcam);
    }

    if (captureBtn) {
        captureBtn.addEventListener("click", captureSnapshot);
    }

    if (regForm) {
        regForm.addEventListener("submit", submitRegistration);
        
        // Listen to form input edits to check Step 1 completion
        const inputs = regForm.querySelectorAll("input, select");
        inputs.forEach(input => {
            input.addEventListener("input", updateWizardSteps);
            input.addEventListener("change", updateWizardSteps);
        });
    }

    // Auto-start camera when opening registration
    startWebcam();
    updateWizardSteps();
});

// Helper to update Step Wizard active/completed classes dynamically
function updateWizardSteps() {
    const step1 = document.getElementById("step-1-indicator");
    const step2 = document.getElementById("step-2-indicator");
    const step3 = document.getElementById("step-3-indicator");
    const step4 = document.getElementById("step-4-indicator");

    // 1. Info validation
    const studentId = document.getElementById("student_id")?.value.trim();
    const name = document.getElementById("name")?.value.trim();
    const department = document.getElementById("department")?.value;
    const year = document.getElementById("year")?.value;
    const section = document.getElementById("section")?.value.trim();
    const isInfoValid = studentId && name && department && year && section;

    if (step1) {
        if (isInfoValid) {
            step1.className = "step-wizard-item completed";
        } else {
            step1.className = "step-wizard-item active";
        }
    }

    // 2. Camera Status check
    if (step2) {
        if (localStream) {
            step2.className = "step-wizard-item completed";
            const cctvStatus = document.getElementById("cctv-status-badge");
            if (cctvStatus) {
                cctvStatus.textContent = "LIVE FEED";
                cctvStatus.className = "cctv-rec-dot";
            }
        } else {
            step2.className = isInfoValid ? "step-wizard-item active" : "step-wizard-item";
            const cctvStatus = document.getElementById("cctv-status-badge");
            if (cctvStatus) {
                cctvStatus.textContent = "STANDBY";
                cctvStatus.className = "cctv-rec-dot bg-secondary";
            }
        }
    }

    // 3. Captured snapshots count check
    if (step3) {
        if (capturedSnapshots.length >= 3) {
            step3.className = "step-wizard-item completed";
        } else if (capturedSnapshots.length > 0) {
            step3.className = "step-wizard-item active";
        } else {
            step3.className = (localStream && isInfoValid) ? "step-wizard-item active" : "step-wizard-item";
        }
    }

    // 4. Finalize submission readiness
    if (step4) {
        if (capturedSnapshots.length >= 3 && isInfoValid) {
            step4.className = "step-wizard-item active";
        } else {
            step4.className = "step-wizard-item";
        }
    }
}

// 1. Request Webcam Permission and Start Stream
async function startWebcam() {
    const video = document.getElementById("webcam");
    const errorAlert = document.getElementById("cam-error");
    const captureBtn = document.getElementById("capture-btn");

    if (!video) return;

    // Reset error banner
    if (errorAlert) errorAlert.classList.add("d-none");

    try {
        if (localStream) {
            stopWebcam();
        }

        localStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });
        
        video.srcObject = localStream;
        if (captureBtn) captureBtn.disabled = false;
        
    } catch (err) {
        console.error("Camera access error:", err);
        if (errorAlert) {
            errorAlert.textContent = "Camera access denied. Please ensure you have given browser webcam permissions.";
            errorAlert.classList.remove("d-none");
        }
        if (captureBtn) captureBtn.disabled = true;
    }
    updateWizardSteps();
}

// Stop stream helper
function stopWebcam() {
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
    updateWizardSteps();
}

// 2. Capture Frame from Live Video
function captureSnapshot() {
    const video = document.getElementById("webcam");
    const canvas = document.createElement("canvas");

    if (!video || !localStream) return;

    if (capturedSnapshots.length >= 5) {
        showToast("Capture Limit Reached", "You can register a maximum of 5 images.", "warning");
        return;
    }

    // Configure canvas size matching feed
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    
    const ctx = canvas.getContext("2d");
    // Draw mirrored to look natural (webcam mirroring)
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    // Reset scale to avoid side effects
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    
    // Convert to Blob for Multipart upload
    canvas.toBlob((blob) => {
        const id = Date.now();
        capturedSnapshots.push({ id, dataUrl, blob });
        
        updatePreviews();
        updateWizardSteps();
    }, "image/jpeg", 0.9);
}

// Update Snapshot UI list
function updatePreviews() {
    const previewContainer = document.getElementById("snapshot-previews");
    const countElem = document.getElementById("captured-count");
    if (!previewContainer) return;

    previewContainer.innerHTML = "";
    
    capturedSnapshots.forEach((snap, index) => {
        const card = document.createElement("div");
        card.style.position = "relative";
        card.style.width = "100px";
        card.style.height = "75px";
        card.style.borderRadius = "8px";
        card.style.overflow = "hidden";
        card.style.border = "2px solid var(--border-color)";
        
        card.innerHTML = `
            <img src="${snap.dataUrl}" alt="Snapshot ${index+1}" style="width: 100%; height: 100%; object-fit: cover;">
            <button type="button" class="btn btn-danger btn-sm" onclick="deleteSnapshot(${snap.id})" 
                style="position: absolute; top: 2px; right: 2px; line-height: 1; padding: 1px 5px; font-size: 0.75rem; border-radius: 4px;">
                <i class="fas fa-trash"></i>
            </button>
        `;
        previewContainer.appendChild(card);
    });

    if (countElem) {
        countElem.textContent = capturedSnapshots.length;
    }
}

// Delete captured snapshot
window.deleteSnapshot = function(id) {
    capturedSnapshots = capturedSnapshots.filter(snap => snap.id !== id);
    updatePreviews();
    updateWizardSteps();
};

// 3. Submit Multipart Registration to Backend
async function submitRegistration(e) {
    e.preventDefault();

    const submitBtn = document.getElementById("reg-submit-btn");
    const errorAlert = document.getElementById("reg-error");
    const successAlert = document.getElementById("reg-success");
    const step4 = document.getElementById("step-4-indicator");

    // Clear alert flags
    if (errorAlert) errorAlert.classList.add("d-none");
    if (successAlert) successAlert.classList.add("d-none");

    // Validations
    if (capturedSnapshots.length < 3) {
        if (errorAlert) {
            errorAlert.textContent = "Registration requires a minimum of 3 captured face images.";
            errorAlert.classList.remove("d-none");
        }
        return;
    }

    const studentId = document.getElementById("student_id").value.trim();
    const name = document.getElementById("name").value.trim();
    const department = document.getElementById("department").value;
    const year = document.getElementById("year").value;
    const section = document.getElementById("section").value.trim();

    if (!studentId || !name || !department || !year || !section) {
        if (errorAlert) {
            errorAlert.textContent = "All metadata fields must be filled out.";
            errorAlert.classList.remove("d-none");
        }
        return;
    }

    // Populate Multipart Form Data
    const formData = new FormData();
    formData.append("student_id", studentId);
    formData.append("name", name);
    formData.append("department", department);
    formData.append("year", year);
    formData.append("section", section);

    // Append file blobs
    capturedSnapshots.forEach((snap, idx) => {
        formData.append("face_images", snap.blob, `face_${studentId}_${idx}.jpg`);
    });

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Registering...`;
    
    if (step4) step4.className = "step-wizard-item active";

    try {
        const response = await apiFetch("/api/students/register", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            if (successAlert) {
                successAlert.textContent = `Student '${name}' registered successfully!`;
                successAlert.classList.remove("d-none");
            }
            showToast("Registration Success", `${name} is now registered.`, "success");
            
            // Clear Form
            document.getElementById("registration-form").reset();
            capturedSnapshots = [];
            updatePreviews();
            
            if (step4) step4.className = "step-wizard-item completed";
        } else {
            if (errorAlert) {
                errorAlert.textContent = data.detail || "Registration failed. Please try again.";
                errorAlert.classList.remove("d-none");
            }
            showToast("Registration Failed", data.detail || "Error during face validation.", "danger");
        }
    } catch (err) {
        console.error("Registration error:", err);
        if (errorAlert) {
            errorAlert.textContent = "Connection to server failed. Please ensure the backend is running.";
            errorAlert.classList.remove("d-none");
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-save me-2"></i>Register Student';
        updateWizardSteps();
    }
}

// Clean up stream if leaving page
window.addEventListener("beforeunload", stopWebcam);
