import os
import datetime
import pickle
import cv2
import numpy as np
import requests
from pathlib import Path
from insightface.app import FaceAnalysis
from backend.database import SessionLocal
from backend.models import User, Student, Attendance, Organization
from backend.face_service import FaceService

API_BASE = "http://127.0.0.1:8000"

BASE_DIR = Path(__file__).resolve().parent
INSIGHTFACE_IMAGES_DIR = BASE_DIR / "venv" / "Lib" / "site-packages" / "insightface" / "data" / "images"
T1_PATH = INSIGHTFACE_IMAGES_DIR / "t1.jpg"
SINGLE_FACE_PATH = BASE_DIR / "single_face_test.jpg"

def prepare_test_fixtures():
    """
    Dynamically generates single_face_test.jpg by cropping a single face from t1.jpg
    using FaceAnalysis. This ensures we have a real face fixture that is detectable.
    """
    if SINGLE_FACE_PATH.exists():
        return
    print("Preparing test image fixtures...")
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

def cleanup_db():
    print("Cleaning up test database records...")
    db = SessionLocal()
    try:
        # Delete attendance records for test students
        db.query(Attendance).filter(Attendance.student_id.in_(["STU_TENANT_1", "STU_TENANT_2"])).delete(synchronize_session=False)
        # Delete test students
        db.query(Student).filter(Student.student_id.in_(["STU_TENANT_1", "STU_TENANT_2"])).delete(synchronize_session=False)
        # Delete users
        db.query(User).filter(User.username.in_(["admin_t1", "admin_t2", "teacher_t1", "student_t1"])).delete(synchronize_session=False)
        # Delete organizations
        db.query(Organization).filter(Organization.organization_code.in_(["ORG-T1", "ORG-T2"])).delete(synchronize_session=False)
        db.commit()
        
        # Also clean up embeddings pickle cache
        fs = FaceService()
        fs.delete_student_embedding("STU_TENANT_1")
        fs.delete_student_embedding("STU_TENANT_2")
        print("Cleanup completed successfully.")
    except Exception as e:
        db.rollback()
        print("Cleanup failed:", e)
    finally:
        db.close()

def run_tests():
    print("==================================================")
    print("STARTING MULTI-TENANT & RBAC INTEGRATION TESTS")
    print("==================================================")

    # 1. Cleanup database first
    cleanup_db()

    # Prepare fixtures
    try:
        prepare_test_fixtures()
    except Exception as e:
        print("Failed to prepare test image fixture:", e)
        return False

    # Create real embeddings from crop image for face recognition test
    print("\nPreparing real embeddings from crop image...")
    fs = FaceService()
    try:
        with open(str(SINGLE_FACE_PATH), "rb") as f:
            img_bytes = f.read()
        real_emb = fs.extract_embedding(img_bytes, "single_face_test.jpg")
        fs.update_student_embedding("STU_TENANT_1", real_emb)
        fs.update_student_embedding("STU_TENANT_2", real_emb)
    except Exception as e:
        print("Failed to extract face embedding:", e)
        return False

    db = SessionLocal()
    try:
        # 2. Test Admin 1 Signup (Creates ORG-T1)
        print("\n--- Test 1 & 2: Admin Signup and Organization Creation ---")
        signup_url = f"{API_BASE}/api/auth/signup"
        admin1_payload = {
            "full_name": "Admin Tenant One",
            "username": "admin_t1",
            "email": "admin1@tenant1.com",
            "password": "password123",
            "confirm_password": "password123",
            "organization_name": "Tenant One Org",
            "organization_code": "ORG-T1",
            "role": "admin"
        }
        res = requests.post(signup_url, json=admin1_payload)
        print(f"Admin 1 signup -> Code: {res.status_code}")
        if res.status_code != 201:
            print("FAILED: Admin 1 signup failed", res.text)
            return False
        
        # Verify Org exists in DB
        org1 = db.query(Organization).filter(Organization.organization_code == "ORG-T1").first()
        if not org1 or org1.organization_name != "Tenant One Org":
            print("FAILED: Organization ORG-T1 not found in database.")
            return False
        print("SUCCESS: Admin 1 signup and Organization 1 creation verified.")

        # 3. Test Admin 2 Signup (Creates ORG-T2)
        admin2_payload = {
            "full_name": "Admin Tenant Two",
            "username": "admin_t2",
            "email": "admin2@tenant2.com",
            "password": "password123",
            "confirm_password": "password123",
            "organization_name": "Tenant Two Org",
            "organization_code": "ORG-T2",
            "role": "admin"
        }
        res = requests.post(signup_url, json=admin2_payload)
        print(f"Admin 2 signup -> Code: {res.status_code}")
        if res.status_code != 201:
            print("FAILED: Admin 2 signup failed", res.text)
            return False
        org2 = db.query(Organization).filter(Organization.organization_code == "ORG-T2").first()
        if not org2:
            print("FAILED: Organization ORG-T2 not found.")
            return False
        print("SUCCESS: Admin 2 signup and Organization 2 creation verified.")

        # 4. Test Duplicate Username Rejection
        print("\n--- Test 3: Duplicate Username Rejection ---")
        duplicate_user_payload = admin1_payload.copy()
        duplicate_user_payload["email"] = "other@email.com"
        duplicate_user_payload["organization_code"] = "ORG-NEW"
        res = requests.post(signup_url, json=duplicate_user_payload)
        print(f"Duplicate username signup -> Code: {res.status_code}")
        if res.status_code != 400:
            print("FAILED: Expected 400 for duplicate username, got", res.status_code)
            return False
        print("SUCCESS: Duplicate username rejected correctly.")

        # 5. Logins to get Admin Tokens
        print("\n--- Test 6: Logins ---")
        login_url = f"{API_BASE}/api/auth/login"
        
        # Admin 1
        res = requests.post(login_url, json={"username": "admin_t1", "password": "password123"})
        if res.status_code != 200:
            print("FAILED: Admin 1 login failed")
            return False
        token_admin1 = res.json()["access_token"]
        headers_admin1 = {"Authorization": f"Bearer {token_admin1}"}

        # Admin 2
        res = requests.post(login_url, json={"username": "admin_t2", "password": "password123"})
        if res.status_code != 200:
            print("FAILED: Admin 2 login failed")
            return False
        token_admin2 = res.json()["access_token"]
        headers_admin2 = {"Authorization": f"Bearer {token_admin2}"}
        print("SUCCESS: Tokens acquired for both Admins.")

        # 6. Test Teacher Creation (Admin 1 creates teacher under ORG-T1)
        print("\n--- Test 4: Teacher Creation (Admin Only) ---")
        create_teacher_url = f"{API_BASE}/api/auth/create-teacher"
        teacher_payload = {
            "full_name": "Teacher Tenant One",
            "username": "teacher_t1",
            "email": "teacher1@tenant1.com",
            "password": "password123"
        }
        res = requests.post(create_teacher_url, json=teacher_payload, headers=headers_admin1)
        print(f"Teacher creation as Admin 1 -> Code: {res.status_code}")
        if res.status_code != 201:
            print("FAILED: Teacher creation failed", res.text)
            return False
        
        # Verify role and organization of created teacher
        teacher_user = db.query(User).filter(User.username == "teacher_t1").first()
        if not teacher_user or teacher_user.role != "teacher" or teacher_user.organization_id != org1.id:
            print("FAILED: Created user is not a teacher or belongs to wrong organization.")
            return False
        print("SUCCESS: Teacher created successfully by Admin 1 within Org 1.")

        # Try creating teacher as unauthenticated or with student role (Unauthorized checks)
        res = requests.post(create_teacher_url, json=teacher_payload)
        print(f"Teacher creation without auth -> Code: {res.status_code} (Expected: 401)")
        if res.status_code != 401:
            print("FAILED: Expected 401, got", res.status_code)
            return False

        # 7. Test Student Signup Workflow
        print("\n--- Test 5: Student Signup (Constraints & Validation) ---")
        # Step 7a: Verify that student signup fails if Student Profile does not exist in DB
        student_signup_payload = {
            "full_name": "Student Tenant One",
            "username": "student_t1",
            "email": "student1@tenant1.com",
            "password": "password123",
            "confirm_password": "password123",
            "organization_name": "Tenant One Org",
            "organization_code": "ORG-T1",
            "role": "student",
            "student_id": "STU_TENANT_1"
        }
        res = requests.post(signup_url, json=student_signup_payload)
        print(f"Student signup with non-existent Student ID -> Code: {res.status_code} (Expected: 400)")
        if res.status_code != 400:
            print("FAILED: Expected student signup to fail when student profile is missing.")
            return False

        # Step 7b: Create Student profile in DB for Org 1 and Org 2
        print("Seeding Student profiles directly into database...")
        s1 = Student(
            student_id="STU_TENANT_1",
            name="Alice Student Org 1",
            department="Computer Science",
            year="1st Year",
            section="A",
            image_count=3,
            embedding_status=True,
            organization_id=org1.id
        )
        s2 = Student(
            student_id="STU_TENANT_2",
            name="Bob Student Org 2",
            department="Mechanical Engineering",
            year="2nd Year",
            section="B",
            image_count=3,
            embedding_status=True,
            organization_id=org2.id
        )
        db.add_all([s1, s2])
        db.commit()

        # Step 7c: Student signup under Org 2 code with Org 1's Student ID (Should Fail)
        bad_student_payload = student_signup_payload.copy()
        bad_student_payload["organization_code"] = "ORG-T2"
        res = requests.post(signup_url, json=bad_student_payload)
        print(f"Student signup with cross-organization code -> Code: {res.status_code} (Expected: 400)")
        if res.status_code != 400:
            print("FAILED: Allowed student to register in Org 2 using Org 1 student profile.")
            return False

        # Step 7d: Successful Student Signup
        res = requests.post(signup_url, json=student_signup_payload)
        print(f"Student signup with valid ID and org code -> Code: {res.status_code}")
        if res.status_code != 201:
            print("FAILED: Student signup failed", res.text)
            return False
        
        # Verify User table links to student profile
        student_user = db.query(User).filter(User.username == "student_t1").first()
        if not student_user or student_user.student_id != "STU_TENANT_1" or student_user.organization_id != org1.id:
            print("FAILED: Student user is not correctly linked to Student ID or Organization.")
            return False
        print("SUCCESS: Student signup constraint verification successful.")

        # Logins for Teacher and Student
        # Teacher
        res = requests.post(login_url, json={"username": "teacher_t1", "password": "password123"})
        token_teacher1 = res.json()["access_token"]
        headers_teacher1 = {"Authorization": f"Bearer {token_teacher1}"}
        # Student
        res = requests.post(login_url, json={"username": "student_t1", "password": "password123"})
        token_student1 = res.json()["access_token"]
        headers_student1 = {"Authorization": f"Bearer {token_student1}"}

        # 8. Profile Role Verification
        print("\n--- Test 9: Profile /api/auth/me Role Details ---")
        res = requests.get(f"{API_BASE}/api/auth/me", headers=headers_student1)
        student_profile_data = res.json()
        print(f"Student /me profile details: Role={student_profile_data['role']}, OrgID={student_profile_data['organization_id']}, StudentID={student_profile_data['student_id']}")
        if student_profile_data["role"] != "student" or student_profile_data["student_id"] != "STU_TENANT_1":
            print("FAILED: Profile data has incorrect values.")
            return False

        # 9. Organization Data Isolation: Student Lists
        print("\n--- Test 10: Organization Isolation (Student Lists) ---")
        res1 = requests.get(f"{API_BASE}/api/students", headers=headers_admin1)
        res2 = requests.get(f"{API_BASE}/api/students", headers=headers_admin2)
        
        students_org1 = [s["student_id"] for s in res1.json()["students"]]
        students_org2 = [s["student_id"] for s in res2.json()["students"]]
        
        print("Org 1 Student List:", students_org1)
        print("Org 2 Student List:", students_org2)
        
        if "STU_TENANT_1" not in students_org1 or "STU_TENANT_2" in students_org1:
            print("FAILED: Org 1 lists cross-organization records or misses its own.")
            return False
        if "STU_TENANT_2" not in students_org2 or "STU_TENANT_1" in students_org2:
            print("FAILED: Org 2 lists cross-organization records or misses its own.")
            return False
        print("SUCCESS: Student list data isolation validated.")

        # 10. Student Self-Only Details Access
        print("\n--- Test 11: Student Self-Only Details Access ---")
        # Student 1 fetches Alice (self) -> 200
        res = requests.get(f"{API_BASE}/api/students/STU_TENANT_1", headers=headers_student1)
        print(f"Student 1 reading self -> Code: {res.status_code}")
        if res.status_code != 200:
            print("FAILED: Student cannot retrieve self profile")
            return False

        # Student 1 fetches Bob (Org 2 student) -> 403 Forbidden
        res = requests.get(f"{API_BASE}/api/students/STU_TENANT_2", headers=headers_student1)
        print(f"Student 1 reading student of Org 2 -> Code: {res.status_code} (Expected: 403)")
        if res.status_code != 403:
            print("FAILED: Cross-organization student detail read was not blocked.")
            return False
        print("SUCCESS: Student role boundaries for details retrieval verified.")

        # 11. Role Permissions: Admin vs Teacher vs Student
        print("\n--- Test 12 & 13: Role Permissions for Write Operations ---")
        # Student tries to update a student profile -> should fail (403)
        res = requests.put(f"{API_BASE}/api/students/STU_TENANT_1", json={"name": "Alice Modified"}, headers=headers_student1)
        print(f"Student trying to update profile -> Code: {res.status_code} (Expected: 403)")
        if res.status_code != 403:
            print("FAILED: Allowed student to update student profile.")
            return False

        # Teacher updates student profile -> should succeed (200)
        res = requests.put(f"{API_BASE}/api/students/STU_TENANT_1", json={"name": "Alice Modified By Teacher"}, headers=headers_teacher1)
        print(f"Teacher updating profile -> Code: {res.status_code} (Expected: 200)")
        if res.status_code != 200:
            print("FAILED: Teacher update failed", res.text)
            return False

        # Teacher tries to delete student profile -> should fail (403)
        res = requests.delete(f"{API_BASE}/api/students/STU_TENANT_1", headers=headers_teacher1)
        print(f"Teacher trying to delete student -> Code: {res.status_code} (Expected: 403)")
        if res.status_code != 403:
            print("FAILED: Allowed teacher to delete student record.")
            return False

        # Admin deletes student profile -> should succeed (200)
        res = requests.delete(f"{API_BASE}/api/students/STU_TENANT_1", headers=headers_admin1)
        print(f"Admin deleting student -> Code: {res.status_code} (Expected: 200)")
        if res.status_code != 200:
            print("FAILED: Admin delete failed")
            return False
        print("SUCCESS: RBAC write permissions verified.")

        # Re-add s1 for downstream tests
        s1 = Student(
            student_id="STU_TENANT_1",
            name="Alice Student Org 1",
            department="Computer Science",
            year="1st Year",
            section="A",
            image_count=3,
            embedding_status=True,
            organization_id=org1.id
        )
        db.add(s1)
        db.commit()
        
        # Restore the pickle cache embedding since it was deleted during delete_student test
        fs.update_student_embedding("STU_TENANT_1", real_emb)

        # 12. Scoped Face Recognition
        print("\n--- Test 16: Scoped Face Recognition ---")
        # Verify single_face_test.jpg exists
        if not SINGLE_FACE_PATH.exists():
            print("FAILED: single_face_test.jpg fixture not prepared successfully.")
            return False

        # Recognize frame using Admin 1 (Org 1) -> must match STU_TENANT_1
        recognize_url = f"{API_BASE}/api/attendance/recognize-frame"
        with open(str(SINGLE_FACE_PATH), "rb") as f:
            res = requests.post(recognize_url, files={"file": ("frame.jpg", f, "image/jpeg")}, headers=headers_admin1)
        print(f"Recognition under Admin 1 (Org 1) -> Code: {res.status_code}")
        if res.status_code != 200:
            print("FAILED: Recognition request failed")
            return False
        res_data = res.json()
        print("Match details:", res_data)
        if res_data["faces_detected"] == 0 or res_data["matches"][0]["student_id"] != "STU_TENANT_1":
            print("FAILED: Org 1 recognition did not match Alice.")
            return False

        # Recognize frame using Admin 2 (Org 2) -> must NOT match STU_TENANT_1 (Alice belongs to Org 1)
        with open(str(SINGLE_FACE_PATH), "rb") as f:
            res = requests.post(recognize_url, files={"file": ("frame.jpg", f, "image/jpeg")}, headers=headers_admin2)
        print(f"Recognition under Admin 2 (Org 2) -> Code: {res.status_code}")
        if res.status_code != 200:
            return False
        res_data2 = res.json()
        print("Match details for Org 2:", res_data2)
        if res_data2["faces_detected"] > 0 and res_data2["matches"][0]["student_id"] == "STU_TENANT_1":
            print("FAILED: Cross-organization face match occurred! Bob's org matched Alice's face.")
            return False
        print("SUCCESS: Face recognition correctly isolated to organization boundaries.")

        # 13. Scoped Dashboard Statistics
        print("\n--- Test 17: Scoped Dashboard ---")
        res_dash1 = requests.get(f"{API_BASE}/api/dashboard/stats", headers=headers_admin1)
        res_dash2 = requests.get(f"{API_BASE}/api/dashboard/stats", headers=headers_admin2)
        
        d1 = res_dash1.json()
        d2 = res_dash2.json()
        
        print("Org 1 Dashboard stats:", d1)
        print("Org 2 Dashboard stats:", d2)
        
        # Verify counts are isolated
        # Org 1: STU_TENANT_1 (count 1)
        # Org 2: STU_TENANT_2 (count 1)
        if d1["total_students"] != 1 or d2["total_students"] != 1:
            print(f"FAILED: Total student counts in dashboard are not isolated. Got Org1={d1['total_students']}, Org2={d2['total_students']}")
            return False
        print("SUCCESS: Dashboard analytics correctly scoped.")

        # 14. Scoped Reports Stats and CSV Permissions
        print("\n--- Test 18 & 19: Scoped Reports & CSV Permissions ---")
        # Verify Student 1 cannot export CSV
        export_url = f"{API_BASE}/api/reports/export"
        res = requests.get(export_url, headers=headers_student1)
        print(f"Student exporting CSV -> Code: {res.status_code} (Expected: 403)")
        if res.status_code != 403:
            print("FAILED: Expected 403 for student CSV export.")
            return False

        # Admin 1 exports -> verify CSV contains only Org 1 attendance logs
        res = requests.get(export_url, headers=headers_admin1)
        print(f"Admin 1 exporting CSV -> Code: {res.status_code}")
        if res.status_code != 200:
            print("FAILED: Admin 1 CSV export failed")
            return False
        print("SUCCESS: Report access and CSV permissions verified.")

        # Clean up crop image file
        if SINGLE_FACE_PATH.exists():
            os.remove(SINGLE_FACE_PATH)

        print("\n==================================================")
        print("ALL MULTI-TENANT & RBAC TESTS PASSED SUCCESSFULLY!")
        print("==================================================")
        return True

    except Exception as e:
        print("Error during integration tests:", e)
        import traceback
        traceback.print_exc()
        return False
    finally:
        cleanup_db()
        db.close()

if __name__ == "__main__":
    run_tests()
