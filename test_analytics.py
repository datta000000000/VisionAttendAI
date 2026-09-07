import os
import datetime
import pickle
import csv
import io
import requests
from pathlib import Path
from backend.database import SessionLocal
from backend.models import Student, Attendance, Organization

API_BASE = "http://127.0.0.1:8000"

def seed_test_data(db):
    print("Seeding test database with mock records...")
    # Delete any existing test data if remaining from previous runs
    db.query(Attendance).filter(Attendance.student_id.in_(["STU_MOCK_1", "STU_MOCK_2"])).delete(synchronize_session=False)
    db.query(Student).filter(Student.student_id.in_(["STU_MOCK_1", "STU_MOCK_2"])).delete(synchronize_session=False)
    db.commit()

    # Get DEFAULT-ORG organization ID
    default_org = db.query(Organization).filter(Organization.organization_code == "DEFAULT-ORG").first()
    org_id = default_org.id if default_org else 1

    # Create mock students
    student1 = Student(
        student_id="STU_MOCK_1",
        name="Mock Student One",
        department="Computer Science",
        year="1st Year",
        section="A",
        image_count=3,
        embedding_status=True,
        organization_id=org_id
    )
    student2 = Student(
        student_id="STU_MOCK_2",
        name="Mock Student Two",
        department="Electrical Engineering",
        year="2nd Year",
        section="B",
        image_count=3,
        embedding_status=True,
        organization_id=org_id
    )
    db.add(student1)
    db.add(student2)
    db.commit()

    # Create mock attendance records
    today_str = datetime.date.today().isoformat()
    
    # 2 unique dates for attendance: 2026-08-01, 2026-08-02, and today
    att1 = Attendance(
        student_id="STU_MOCK_1",
        name="Mock Student One",
        department="Computer Science",
        date="2026-08-01",
        time="09:00:00",
        status="Present",
        confidence_score=0.85,
        organization_id=org_id
    )
    att2 = Attendance(
        student_id="STU_MOCK_1",
        name="Mock Student One",
        department="Computer Science",
        date="2026-08-02",
        time="09:15:00",
        status="Present",
        confidence_score=0.90,
        organization_id=org_id
    )
    att3 = Attendance(
        student_id="STU_MOCK_2",
        name="Mock Student Two",
        department="Electrical Engineering",
        date="2026-08-02",
        time="09:10:00",
        status="Present",
        confidence_score=0.88,
        organization_id=org_id
    )
    # Log today's present record for student 1
    att4 = Attendance(
        student_id="STU_MOCK_1",
        name="Mock Student One",
        department="Computer Science",
        date=today_str,
        time="09:30:00",
        status="Present",
        confidence_score=0.95,
        organization_id=org_id
    )
    db.add_all([att1, att2, att3, att4])
    db.commit()
    print("Test database seeded successfully.")

def cleanup_test_data(db):
    print("Cleaning up test database records...")
    db.query(Attendance).filter(Attendance.student_id.in_(["STU_MOCK_1", "STU_MOCK_2"])).delete(synchronize_session=False)
    db.query(Student).filter(Student.student_id.in_(["STU_MOCK_1", "STU_MOCK_2"])).delete(synchronize_session=False)
    db.commit()
    print("Test database records purged.")

def run_tests():
    print("==================================================")
    print("STARTING DASHBOARD, HISTORY & REPORTS API TESTS")
    print("==================================================")

    db = SessionLocal()
    try:
        # Seed initial test fixtures in DB
        seed_test_data(db)
        
        # 1. Login as Admin
        print("\n--- Test Login ---")
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
        print("Login successful.")

        # 2. Test Auth Protection (Unauthenticated request should fail with 401)
        print("\n--- Test 1: Authentication Protection ---")
        for endpoint in ["dashboard/stats", "attendance/history", "reports/export", "reports/stats"]:
            res = requests.get(f"{API_BASE}/api/{endpoint}")
            print(f"GET /api/{endpoint} without auth -> Code: {res.status_code} (Expected: 401)")
            if res.status_code != 401:
                print(f"FAILED: Expected 401 for /api/{endpoint}")
                return False

        # 3. Test Dashboard Stats API
        print("\n--- Test 2: Dashboard Statistics ---")
        res = requests.get(f"{API_BASE}/api/dashboard/stats", headers=headers)
        if res.status_code != 200:
            print(f"FAILED: Expected 200, got {res.status_code}")
            return False
        
        stats = res.json()
        print("Dashboard stats response:", stats)
        # Expected:
        # total_students = 2 (seeding two mock students)
        # today_attendance_count = 1 (att4 logged today for STU_MOCK_1)
        # Unique dates count = 3 (2026-08-01, 2026-08-02, and today)
        # Total present count = 4
        # overall_pct = 4 / (2 * 3) * 100 = 66.67%
        if stats["total_students"] < 2:
            print(f"FAILED: Expected >= 2 total students, got {stats['total_students']}")
            return False
        if stats["today_attendance_count"] < 1:
            print(f"FAILED: Expected >= 1 today's attendance, got {stats['today_attendance_count']}")
            return False
        if stats["overall_attendance_percentage"] <= 0.0:
            print(f"FAILED: Expected overall percentage > 0.0")
            return False

        # 4. Test Attendance History (Filtering, Pagination, Sorting)
        print("\n--- Test 3: Attendance History ---")
        
        # Test default listing
        res = requests.get(f"{API_BASE}/api/attendance/history", headers=headers)
        if res.status_code != 200:
            print(f"FAILED: Expected 200, got {res.status_code}")
            return False
        history = res.json()
        print(f"Total history count: {history['total']}")
        
        # Test student_id filter
        res = requests.get(f"{API_BASE}/api/attendance/history?student_id=STU_MOCK_2", headers=headers)
        res_json = res.json()
        print(f"History filtered by student_id=STU_MOCK_2 count: {res_json['total']} (Expected: 1)")
        if res_json["total"] != 1:
            return False
            
        # Test date range filter
        res = requests.get(f"{API_BASE}/api/attendance/history?start_date=2026-08-01&end_date=2026-08-02", headers=headers)
        res_json = res.json()
        print(f"History filtered by date range count: {res_json['total']} (Expected: 3)")
        if res_json["total"] != 3:
            return False

        # Test date validation (Invalid date format YYYY/MM/DD should return HTTP 400)
        res = requests.get(f"{API_BASE}/api/attendance/history?date=2026/08/01", headers=headers)
        print(f"History filtered by invalid date format -> Code: {res.status_code} (Expected: 400)")
        if res.status_code != 400:
            print(f"FAILED: Expected 400, got {res.status_code}")
            return False
            
        # Test sort validation (Invalid sort field should return HTTP 400)
        res = requests.get(f"{API_BASE}/api/attendance/history?sort_by=hashed_password", headers=headers)
        print(f"History filtered by invalid sort field -> Code: {res.status_code} (Expected: 400)")
        if res.status_code != 400:
            print(f"FAILED: Expected 400, got {res.status_code}")
            return False

        # Test pagination (limit=2)
        res = requests.get(f"{API_BASE}/api/attendance/history?limit=2&page=1", headers=headers)
        res_json = res.json()
        print(f"Pagination page 1 records count: {len(res_json['records'])} (Expected: 2)")
        if len(res_json["records"]) != 2 or res_json["pages"] < 2:
            return False

        # Test sorting order (asc vs desc)
        res_desc = requests.get(f"{API_BASE}/api/attendance/history?sort_by=confidence_score&sort_order=desc", headers=headers)
        score_desc = res_desc.json()["records"][0]["confidence_score"]
        res_asc = requests.get(f"{API_BASE}/api/attendance/history?sort_by=confidence_score&sort_order=asc", headers=headers)
        score_asc = res_asc.json()["records"][0]["confidence_score"]
        print(f"Sort desc first score: {score_desc}, Sort asc first score: {score_asc}")
        if score_desc < score_asc:
            print("FAILED: Sorting order assertion failed.")
            return False

        # 5. Test CSV Export API
        print("\n--- Test 4: CSV Export API ---")
        export_url = f"{API_BASE}/api/reports/export?start_date=2026-08-01&end_date=2026-08-02"
        res = requests.get(export_url, headers=headers)
        if res.status_code != 200:
            print(f"FAILED: Expected 200, got {res.status_code}")
            return False
        
        # Verify content type
        content_type = res.headers.get("content-type")
        content_disposition = res.headers.get("content-disposition")
        print(f"Export headers - Content-Type: {content_type}, Content-Disposition: {content_disposition}")
        if "text/csv" not in content_type or "attachment" not in content_disposition:
            return False
            
        # Parse CSV stream
        csv_file = io.StringIO(res.text)
        reader = csv.reader(csv_file)
        rows = list(reader)
        
        print("CSV Headers:", rows[0])
        # Assert headers: Student ID, Name, Department, Date, Time, Status, Confidence
        expected_headers = ["Student ID", "Name", "Department", "Date", "Time", "Status", "Confidence"]
        if rows[0] != expected_headers:
            print(f"FAILED: Expected headers {expected_headers}, got {rows[0]}")
            return False
            
        print(f"CSV exported records count: {len(rows)-1} (Expected: 3)")
        if len(rows) - 1 != 3:
            return False

        # 6. Test Reports Stats API
        print("\n--- Test 5: Report Statistics API ---")
        res = requests.get(f"{API_BASE}/api/reports/stats", headers=headers)
        if res.status_code != 200:
            print(f"FAILED: Expected 200, got {res.status_code}")
            return False
        
        report_stats = res.json()
        print("Report stats response:", report_stats)
        # Assert math parity with dashboard overall percentage
        if report_stats["overall_attendance_percentage"] != stats["overall_attendance_percentage"]:
            print(f"FAILED: Stats mismatch between dashboard ({stats['overall_attendance_percentage']}) and reports ({report_stats['overall_attendance_percentage']})")
            return False
            
        # Verify department breakdown exists
        cs_stats = report_stats["department_wise_attendance"].get("Computer Science")
        print(f"Computer Science stats: {cs_stats}")
        if not cs_stats or cs_stats["total_students"] < 1:
            return False

        print("\n==================================================")
        print("ALL ANALYTICS TESTS PASSED SUCCESSFULLY!")
        print("==================================================")
        return True

    except Exception as e:
        print("Error during integration tests:", e)
        return False
    finally:
        # Perform Database Cleanup
        cleanup_test_data(db)
        db.close()

if __name__ == "__main__":
    run_tests()
