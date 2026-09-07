import os
import re
import shutil
import pickle
import requests
import cv2
import numpy as np
from pathlib import Path
from insightface.app import FaceAnalysis

# Paths
BASE_DIR = Path(__file__).resolve().parent
INSIGHTFACE_IMAGES_DIR = BASE_DIR / "venv" / "Lib" / "site-packages" / "insightface" / "data" / "images"
SKIMAGE_IMAGES_DIR = BASE_DIR / "venv" / "Lib" / "site-packages" / "skimage" / "data"

T1_PATH = INSIGHTFACE_IMAGES_DIR / "t1.jpg"
NO_FACE_PATH = SKIMAGE_IMAGES_DIR / "rocket.jpg"
SINGLE_FACE_PATH = BASE_DIR / "single_face_att_test.jpg"

API_BASE = "http://127.0.0.1:8000"

def prepare_test_fixtures():
    """
    Dynamically generates single_face_att_test.jpg by cropping a single face from t1.jpg
    using FaceAnalysis.
    """
    print("Preparing test fixtures...")
    if not T1_PATH.exists():
        raise FileNotFoundError(f"Source image not found at {T1_PATH}")
    
    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=-1, det_size=(640, 640))
    
    img = cv2.imread(str(T1_PATH))
    faces = app.get(img)
    if not faces:
        raise ValueError("No faces detected in t1.jpg to prepare test fixture")
    
    # Crop the first face with padding
    box = faces[0].bbox.astype(int)
    h, w, c = img.shape
    y1, x1, y2, x2 = max(0, box[1]-40), max(0, box[0]-40), min(h, box[3]+40), min(w, box[2]+40)
    face_crop = img[y1:y2, x1:x2]
    
    cv2.imwrite(str(SINGLE_FACE_PATH), face_crop)
    print(f"Prepared single-face fixture and saved to {SINGLE_FACE_PATH}")

def run_tests():
    print("==================================================")
    print("STARTING ATTENDANCE & FACE RECOGNITION TESTS")
    print("==================================================")
    
    # 1. Login as Admin
    print("\n--- Testing Admin Login ---")
    login_url = f"{API_BASE}/api/auth/login"
    login_payload = {
        "username": "admin",
        "password": "admin123"
    }
    response = requests.post(login_url, json=login_payload)
    if response.status_code != 200:
        print(f"FAILED to login: {response.status_code} {response.text}")
        return False
    
    token = response.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}"
    }
    print("Login successful! Access token obtained.")

    # 2. Check test fixtures exist
    if not SINGLE_FACE_PATH.exists():
        try:
            prepare_test_fixtures()
        except Exception as e:
            print(f"FAILED to prepare test fixtures: {e}")
            return False

    for path, name in [(SINGLE_FACE_PATH, "Single Face"), (T1_PATH, "Multi Face"), (NO_FACE_PATH, "No Face")]:
        if not path.exists():
            print(f"ERROR: Test fixture {name} not found at {path}")
            return False

    student_id = "STU_ATT_TEST_99"
    student_data = {
        "student_id": student_id,
        "name": "Bob Jenkins",
        "department": "Mechanical Engineering",
        "year": "2nd Year",
        "section": "A"
    }

    # Clean up student and any previous attendance record first
    requests.delete(f"{API_BASE}/api/students/{student_id}", headers=headers)

    # 3. Register the student
    print("\n--- Registering test student Bobs Jenkins ---")
    with open(SINGLE_FACE_PATH, "rb") as sf:
        single_face_data = sf.read()
        
    files = [
        ("face_images", ("bob1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("bob2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("bob3.jpg", single_face_data, "image/jpeg"))
    ]
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data, files=files, headers=headers)
    if res.status_code != 201:
        print(f"FAILED to register student: {res.status_code} {res.text}")
        return False
    print("Test student registered successfully.")

    # 4. Test 1: Registered Face Recognized (Webcam Frame POST)
    print("\n--- Test 1: Registered Face Recognized (Webcam Frame) ---")
    frame_files = {"file": ("webcam_frame.jpg", single_face_data, "image/jpeg")}
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=frame_files, headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        print(f"Response: {res.text}")
        return False
    
    res_json = res.json()
    print("SUCCESS: Endpoint processed successfully!")
    print(f"Faces Detected: {res_json['faces_detected']} (Expected: 1)")
    
    match = res_json["matches"][0]
    print(f"Recognized student_id: {match['student_id']} (Expected: {student_id})")
    print(f"Recognized name: {match['student_name']} (Expected: Bob Jenkins)")
    print(f"Similarity score: {match['similarity']:.4f} (Expected: >= 0.60)")
    print(f"Attendance status: {match['attendance_status']} (Expected: Marked Present)")
    
    if match["student_id"] != student_id or match["attendance_status"] != "Marked Present" or match["similarity"] < 0.60:
        print("FAILED: Recognition attributes do not match expected outcomes.")
        return False

    # 5. Test 2: Duplicate Attendance Prevention
    print("\n--- Test 2: Duplicate Attendance Prevention ---")
    frame_files = {"file": ("webcam_frame_dup.jpg", single_face_data, "image/jpeg")}
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=frame_files, headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    
    res_json = res.json()
    match = res_json["matches"][0]
    print(f"Attendance status on duplicate scan: {match['attendance_status']} (Expected: Already Present)")
    if match["attendance_status"] != "Already Present":
        print("FAILED: Duplicate attendance was not prevented.")
        return False

    # 6. Test 3: Unauthenticated Access (Should fail with 401)
    print("\n--- Test 3: Unauthenticated Access Enforcement ---")
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=frame_files)
    print(f"Response code: {res.status_code} (Expected: 401)")
    if res.status_code != 401:
        print(f"FAILED: Expected 401, got {res.status_code}")
        return False
    print("Verified: Endpoint is properly protected.")

    # 7. Test 4: Invalid file format (Should fail with 400)
    print("\n--- Test 4: Invalid File Format Enforcement ---")
    bad_files = {"file": ("test.txt", b"random content", "text/plain")}
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=bad_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 8. Test 5: Dynamic check of rocket.jpg face count and verify behavior
    print("\n--- Test 5: Dynamic Unknown / No-Face Detection (`rocket.jpg`) ---")
    # First, run FaceAnalysis locally to see what InsightFace detects in rocket.jpg
    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=-1, det_size=(640, 640))
    rocket_img = cv2.imread(str(NO_FACE_PATH))
    rocket_faces = app.get(rocket_img)
    rocket_face_count = len(rocket_faces)
    print(f"InsightFace locally detects {rocket_face_count} faces in rocket.jpg.")
    
    with open(NO_FACE_PATH, "rb") as nf:
        no_face_data = nf.read()
    frame_files_rocket = {"file": ("rocket.jpg", no_face_data, "image/jpeg")}
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=frame_files_rocket, headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    
    res_json = res.json()
    print(f"API returned faces_detected: {res_json['faces_detected']}")
    if rocket_face_count == 0:
        if res_json["faces_detected"] != 0:
            print("FAILED: API should have returned 0 faces detected.")
            return False
        print("SUCCESS: 0 faces detected and no matches returned.")
    else:
        # If a face was detected, it must be marked as unknown
        for match in res_json["matches"]:
            print(f"Face Match ID: {match['student_id']}, Status: {match['attendance_status']}")
            if match["student_id"] != "unknown" or match["attendance_status"] != "Unknown Face":
                print("FAILED: Undetected face was incorrectly matched to a registered student.")
                return False
        print("SUCCESS: Non-registered face classified as unknown and attendance rejected.")

    # 9. Test 6: Multiple Faces Processing independently
    print("\n--- Test 6: Multiple Faces Processing (`t1.jpg`) ---")
    with open(T1_PATH, "rb") as mf:
        multi_face_data = mf.read()
    frame_files_multi = {"file": ("t1.jpg", multi_face_data, "image/jpeg")}
    res = requests.post(f"{API_BASE}/api/attendance/recognize-frame", files=frame_files_multi, headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    
    res_json = res.json()
    print(f"API returned faces_detected: {res_json['faces_detected']}")
    if res_json["faces_detected"] < 2:
        print(f"FAILED: Multi-face image should have multiple faces, got {res_json['faces_detected']}")
        return False
        
    print("Match Details for Multi-Face Frame:")
    for idx, match in enumerate(res_json["matches"]):
        print(f"  Face {idx+1} - ID: {match['student_id']}, Status: {match['attendance_status']}, Sim: {match['similarity']:.4f}")
        # One face should be Bob Jenkins because Bob was registered using a face cropped from t1.jpg!
        # The other faces in t1.jpg are not registered, so they must be "unknown".
        if match["student_id"] == student_id:
            # Bob is already present (from Test 1)
            if match["attendance_status"] not in ["Marked Present", "Already Present"]:
                print("FAILED: Bob Jenkins face crop was not correctly matched in the multi-face image.")
                return False
        else:
            # Unregistered face
            if match["student_id"] != "unknown" or match["attendance_status"] != "Unknown Face":
                print("FAILED: Unregistered face in t1.jpg was incorrectly matched or marked present.")
                return False
    print("SUCCESS: Multiple faces processed independently; only matching registered face logged.")

    # 10. CLEANUP: Clear test student and database records
    print("\n--- Cleaning Up Test Records ---")
    # Deleting student automatically purges DB record, dataset directory, and pickle embedding
    res = requests.delete(f"{API_BASE}/api/students/{student_id}", headers=headers)
    if res.status_code == 200:
        print("Student STU_ATT_TEST_99 and embeddings purged.")
    else:
        print(f"WARNING: Failed to cleanup student: {res.text}")
        
    # Cleanup single face cropped file
    if SINGLE_FACE_PATH.exists():
        os.remove(SINGLE_FACE_PATH)
        print("Cleaned up temporary crop image.")

    print("\n==================================================")
    print("ALL ATTENDANCE TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_tests()
