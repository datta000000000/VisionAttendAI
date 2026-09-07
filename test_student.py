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
SINGLE_FACE_PATH = BASE_DIR / "single_face_test.jpg"

API_BASE = "http://127.0.0.1:8000"

def prepare_test_fixtures():
    """
    Dynamically generates single_face_test.jpg by cropping a single face from t1.jpg
    using FaceAnalysis. This ensures we have a real face fixture that is detectable.
    """
    print("Preparing test fixtures...")
    if not T1_PATH.exists():
        raise FileNotFoundError(f"Source image not found at {T1_PATH}")
    
    # Initialize FaceAnalysis to crop face
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
    print("STARTING STUDENT & FACE REGISTRATION INTEGRATION TESTS")
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

    # Define test student parameters
    student_id = "STU_TEST_101"
    student_data = {
        "student_id": student_id,
        "name": "Alice Smith",
        "department": "AI & Robotics",
        "year": "3rd Year",
        "section": "B"
    }

    # Helper function to delete student if exists (cleanup before starting)
    requests.delete(f"{API_BASE}/api/students/{student_id}", headers=headers)

    # 3. Test 1: Successful registration (3 valid images containing exactly one face)
    print("\n--- Test 1: Successful Registration (3 valid images) ---")
    with open(SINGLE_FACE_PATH, "rb") as sf:
        single_face_data = sf.read()
        
    files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face3.jpg", single_face_data, "image/jpeg"))
    ]
    
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data, files=files, headers=headers)
    if res.status_code != 201:
        print(f"FAILED: Expected 201, got {res.status_code}")
        print(f"Response: {res.text}")
        return False
    
    res_json = res.json()
    print("SUCCESS: Student registered successfully!")
    print(f"Database Image Count: {res_json['image_count']} (Expected: 3)")
    print(f"Database Embedding Status: {res_json['embedding_status']} (Expected: True)")
    
    # Verify dataset directory creation and images count
    dataset_path = BASE_DIR / "dataset" / student_id
    if not dataset_path.exists():
        print(f"FAILED: Dataset directory {dataset_path} does not exist.")
        return False
    saved_images = list(dataset_path.glob("*"))
    print(f"Saved images on disk count: {len(saved_images)} (Expected: 3)")
    if len(saved_images) != 3:
        return False

    # Verify student_embeddings.pkl exists and contains the student
    embeddings_pkl = BASE_DIR / "embeddings" / "student_embeddings.pkl"
    if not embeddings_pkl.exists():
        print(f"FAILED: Embeddings pickle file {embeddings_pkl} not found.")
        return False
    with open(embeddings_pkl, "rb") as pf:
        embeddings_cache = pickle.load(pf)
    if student_id not in embeddings_cache:
        print(f"FAILED: Student {student_id} not found in embeddings cache.")
        return False
    print("SUCCESS: Embedding is cached in pickle store.")

    # 4. Test 2: Duplicate ID Registration
    print("\n--- Test 2: Duplicate ID Registration (Should Fail) ---")
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data, files=files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 5. Test 3: Too Few Images (2 images)
    print("\n--- Test 3: Too Few Images (Should Fail) ---")
    too_few_files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg"))
    ]
    student_data_temp = student_data.copy()
    student_data_temp["student_id"] = "STU_TEMP"
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data_temp, files=too_few_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 6. Test 4: Too Many Images (6 images)
    print("\n--- Test 4: Too Many Images (Should Fail) ---")
    too_many_files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face3.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face4.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face5.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face6.jpg", single_face_data, "image/jpeg"))
    ]
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data_temp, files=too_many_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 7. Test 5: Registration with No-Face Image
    print("\n--- Test 5: Registration with No-Face Image (Should Fail) ---")
    with open(NO_FACE_PATH, "rb") as nf:
        no_face_data = nf.read()
    
    no_face_files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("rocket.jpg", no_face_data, "image/jpeg"))
    ]
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data_temp, files=no_face_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 8. Test 6: Registration with Multiple Faces Image
    print("\n--- Test 6: Registration with Multiple Faces Image (Should Fail) ---")
    with open(T1_PATH, "rb") as mf:
        multi_face_data = mf.read()
        
    multi_face_files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("t1.jpg", multi_face_data, "image/jpeg"))
    ]
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data_temp, files=multi_face_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 9. Test 7: Registration with Corrupted/Invalid File
    print("\n--- Test 7: Registration with Invalid File (Should Fail) ---")
    bad_files = [
        ("face_images", ("face1.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("face2.jpg", single_face_data, "image/jpeg")),
        ("face_images", ("random.txt", b"this is random text not an image", "text/plain"))
    ]
    res = requests.post(f"{API_BASE}/api/students/register", data=student_data_temp, files=bad_files, headers=headers)
    print(f"Response code: {res.status_code} (Expected: 400)")
    if res.status_code != 400:
        print(f"FAILED: Expected 400, got {res.status_code}")
        return False
    print(f"Error message: {res.json()['detail']}")

    # 10. Test 8: Student Retrieval (GET)
    print("\n--- Test 8: Retrieve Student Details & List ---")
    # Single student
    res = requests.get(f"{API_BASE}/api/students/{student_id}", headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    retrieved = res.json()
    print(f"Retrieved student name: {retrieved['name']} (Expected: Alice Smith)")
    
    # List students
    res = requests.get(f"{API_BASE}/api/students", headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    student_list = res.json()
    print(f"Total students count: {student_list['total']}")
    student_ids = [s["student_id"] for s in student_list["students"]]
    if student_id not in student_ids:
        print(f"FAILED: Registered student {student_id} not in listed students.")
        return False
    print("SUCCESS: Student retrieved and listed successfully.")

    # 11. Test 9: Update Student Details (PUT)
    print("\n--- Test 9: Update Student Details ---")
    update_payload = {
        "name": "Alice Smith-Johnson",
        "department": "Artificial Intelligence",
        "year": "4th Year",
        "section": "A"
    }
    res = requests.put(f"{API_BASE}/api/students/{student_id}", json=update_payload, headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    updated = res.json()
    print(f"Updated name: {updated['name']} (Expected: Alice Smith-Johnson)")
    print(f"Updated dept: {updated['department']} (Expected: Artificial Intelligence)")
    print(f"Updated year: {updated['year']} (Expected: 4th Year)")
    print(f"Updated section: {updated['section']} (Expected: A)")
    if updated["name"] != "Alice Smith-Johnson" or updated["department"] != "Artificial Intelligence":
        return False

    # 12. Test 10: Delete Student (DELETE)
    print("\n--- Test 10: Delete Student ---")
    res = requests.delete(f"{API_BASE}/api/students/{student_id}", headers=headers)
    if res.status_code != 200:
        print(f"FAILED: Expected 200, got {res.status_code}")
        return False
    print(f"Delete response: {res.json()['message']}")

    # Verify DB delete
    res = requests.get(f"{API_BASE}/api/students/{student_id}", headers=headers)
    if res.status_code != 404:
        print(f"FAILED: Expected 404, got {res.status_code} for deleted student retrieval.")
        return False
    print("Verified: Student removed from database.")

    # Verify files deleted
    if dataset_path.exists():
        print(f"FAILED: Dataset directory {dataset_path} was not deleted.")
        return False
    print("Verified: Dataset folder deleted from disk.")

    # Verify embedding removed from pickle cache
    with open(embeddings_pkl, "rb") as pf:
        embeddings_cache = pickle.load(pf)
    if student_id in embeddings_cache:
        print(f"FAILED: Embedding for {student_id} was not removed from pickle cache.")
        return False
    print("Verified: Embedding removed from pickle store.")

    # Cleanup temporary single face crop
    if SINGLE_FACE_PATH.exists():
        os.remove(SINGLE_FACE_PATH)
        print("Cleaned up temporary crop image.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")
    return True

if __name__ == "__main__":
    run_tests()
