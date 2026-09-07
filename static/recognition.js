// Real-Time Face Recognition Attendance Loop
let recognitionInterval = null;
let videoStream = null;
let isRecognizing = false;
let isProcessingFrame = false;
let activeBoxes = []; // Cache of bounding boxes to render on canvas
let recognitionLogs = []; // List of recent recognition logs

document.addEventListener("DOMContentLoaded", async () => {
    if (!window.location.pathname.endsWith("recognition.html")) return;

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

    const startBtn = document.getElementById("start-recognition-btn");
    const stopBtn = document.getElementById("stop-recognition-btn");

    if (startBtn) {
        startBtn.addEventListener("click", startRecognition);
    }

    if (stopBtn) {
        stopBtn.addEventListener("click", stopRecognition);
    }

    // Auto-start streaming on page load
    initCamera();
});

// 1. Initialise webcam stream
async function initCamera() {
    const video = document.getElementById("video-feed");
    const errorAlert = document.getElementById("recognition-cam-error");

    if (!video) return;
    if (errorAlert) errorAlert.classList.add("d-none");

    try {
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });
        video.srcObject = videoStream;
        
        // Start Canvas drawing loop
        startCanvasLoop();
    } catch (err) {
        console.error("Failed to access camera:", err);
        if (errorAlert) {
            errorAlert.textContent = "Camera access denied. Please grant webcam permissions to demonstrate face recognition.";
            errorAlert.classList.remove("d-none");
        }
    }
}

// 2. Draw loop: Renders video frame and overlays face bounding boxes on canvas
function startCanvasLoop() {
    const video = document.getElementById("video-feed");
    const canvas = document.getElementById("overlay-canvas");
    if (!video || !canvas) return;

    const ctx = canvas.getContext("2d");

    function renderFrame() {
        if (!videoStream) return;
        
        // Adjust canvas dimensions to match video size
        if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
        }

        // Draw current video frame to canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw video mirrored (for natural webcam view)
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform

        // Draw bounding boxes (Need to mirror box X coordinates because feed is mirrored!)
        ctx.lineWidth = 3;
        ctx.font = "bold 15px sans-serif";
        ctx.textBaseline = "top";

        activeBoxes.forEach(face => {
            const [x1, y1, x2, y2] = face.bbox;
            
            // Calculate mirrored coordinates
            // Original: x1 is distance from left. Mirrored: it's distance from right.
            const w = x2 - x1;
            const h = y2 - y1;
            const mirroredX1 = canvas.width - x2;

            // Border color: Green for present, orange for duplicate, red for unknown
            let color = "#f59e0b"; // Orange default (Duplicate/Already Present)
            if (face.attendance_status === "Marked Present") {
                color = "#10b981"; // Green
            } else if (face.student_id === "unknown") {
                color = "#ef4444"; // Red
            }

            ctx.strokeStyle = color;
            ctx.fillStyle = color;

            // Draw bounding rect
            ctx.strokeRect(mirroredX1, y1, w, h);

            // Draw tag block
            const nameText = face.student_name || "Unknown Face";
            const scoreText = `${Math.round(face.similarity * 100)}%`;
            const label = `${nameText} (${scoreText})`;
            
            const textWidth = ctx.measureText(label).width;
            ctx.fillRect(mirroredX1 - 1.5, y1 - 25, textWidth + 10, 25);
            
            ctx.fillStyle = "#ffffff";
            ctx.fillText(label, mirroredX1 + 3, y1 - 21);
        });

        requestAnimationFrame(renderFrame);
    }

    requestAnimationFrame(renderFrame);
}

// 3. Start periodic recognition request sending
function startRecognition() {
    if (isRecognizing) return;
    
    isRecognizing = true;
    toggleUIState(true);
    
    // Periodically capture frames (every 1000 ms)
    recognitionInterval = setInterval(processFrame, 1000);
    showToast("Recognition Loop Started", "Analyzing webcam frames in real-time...", "success");
}

// Stop recognition
function stopRecognition() {
    if (!isRecognizing) return;
    
    isRecognizing = false;
    clearInterval(recognitionInterval);
    recognitionInterval = null;
    activeBoxes = []; // Clear visual boxes
    
    toggleUIState(false);
    showToast("Recognition Loop Stopped", "Real-time analysis paused.", "warning");
}

// UI State Switcher
function toggleUIState(active) {
    const startBtn = document.getElementById("start-recognition-btn");
    const stopBtn = document.getElementById("stop-recognition-btn");
    const loader = document.getElementById("recognition-loader");
    const cctvBadge = document.getElementById("rec-cctv-badge");
    const scanLine = document.getElementById("rec-scan-line");

    if (startBtn) startBtn.disabled = active;
    if (stopBtn) stopBtn.disabled = !active;
    
    if (loader) {
        if (active) loader.classList.remove("d-none");
        else loader.classList.add("d-none");
    }

    if (cctvBadge) {
        if (active) {
            cctvBadge.textContent = "LIVE SCANNING";
            cctvBadge.className = "cctv-rec-dot";
        } else {
            cctvBadge.textContent = "SCAN STANDBY";
            cctvBadge.className = "cctv-rec-dot bg-secondary";
        }
    }

    if (scanLine) {
        if (active) {
            scanLine.classList.remove("d-none");
        } else {
            scanLine.classList.add("d-none");
        }
    }
}

// 4. Capture Canvas Image and Send to recognize-frame
async function processFrame() {
    if (isProcessingFrame) return; // Prevent overlapping requests
    
    const canvas = document.getElementById("overlay-canvas");
    if (!canvas || !videoStream) return;

    isProcessingFrame = true;
    
    // Extract canvas as Blob
    // We capture the frame from the video element directly using a temporary canvas to get un-mirrored feed for the backend models
    const tempCanvas = document.createElement("canvas");
    const video = document.getElementById("video-feed");
    tempCanvas.width = video.videoWidth || 640;
    tempCanvas.height = video.videoHeight || 480;
    const tempCtx = tempCanvas.getContext("2d");
    tempCtx.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

    tempCanvas.toBlob(async (blob) => {
        if (!blob) {
            isProcessingFrame = false;
            return;
        }

        const formData = new FormData();
        formData.append("file", blob, "frame.jpg");

        try {
            const response = await apiFetch("/api/attendance/recognize-frame", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error("HTTP recognition failure");
            }

            const data = await response.json();
            
            // 5. Update box overlay mapping
            activeBoxes = data.matches || [];

            // Update stats
            const countElem = document.getElementById("faces-count");
            if (countElem) countElem.textContent = data.faces_detected;

            // Log recognition events
            logEvents(data.matches);

        } catch (err) {
            console.error("Frame recognition error:", err);
            // Auto pause loop if connection lost
            stopRecognition();
            showToast("Connection Lost", "Failed to recognize frame. Loop stopped.", "danger");
        } finally {
            isProcessingFrame = false;
        }
    }, "image/jpeg", 0.85);
}

// 6. Log Events Listing in Right panel
function logEvents(matches) {
    const listContainer = document.getElementById("log-list");
    if (!listContainer || !matches) return;

    matches.forEach(match => {
        // Only log recognized student matches or actual unknown face alerts (prevent excessive duplicates in log UI)
        const timestamp = new Date().toLocaleTimeString();
        
        let badgeClass = "badge-unknown";
        let statusText = match.attendance_status;

        if (statusText === "Marked Present") {
            badgeClass = "badge-present";
        } else if (statusText === "Already Present") {
            badgeClass = "badge-duplicate";
        }

        const name = match.student_name || "Unknown Face";
        const studentId = match.student_id === "unknown" ? "" : `(${match.student_id})`;

        // Add to global logs array
        recognitionLogs.unshift({
            timestamp,
            name,
            studentId,
            status: statusText,
            badgeClass,
            score: `${Math.round(match.similarity * 100)}%`
        });
    });

    // Limit log size to 10
    if (recognitionLogs.length > 10) {
        recognitionLogs = recognitionLogs.slice(0, 10);
    }

    // Render list
    let listHTML = "";
    recognitionLogs.forEach(log => {
        listHTML += `
            <li class="list-group-item py-3">
                <div class="d-flex justify-content-between">
                    <strong>${escapeHTML(log.name)} ${escapeHTML(log.studentId)}</strong>
                    <span class="badge ${log.badgeClass}">${log.status}</span>
                </div>
                <small class="text-muted d-flex justify-content-between mt-1">
                    <span>Time: ${log.timestamp}</span>
                    <span>Confidence: ${log.score}</span>
                </small>
            </li>
        `;
    });

    listContainer.innerHTML = listHTML;
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

// Stop streams helper
function stopCamera() {
    stopRecognition();
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
}

// Cleanup streams on navigation
window.addEventListener("beforeunload", stopCamera);
