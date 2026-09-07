import os
from backend.database import init_db, SessionLocal
from backend.models import User, Student, Attendance

def test_database_operations():
    print("Testing Database Schema & Models...")
    
    # 1. Initialize DB tables
    init_db()
    
    db = SessionLocal()
    try:
        # 2. Test User Creation
        test_user = User(
            username="admin_test",
            email="admin@visionattend.ai",
            hashed_password="hashed_pass_placeholder",
            role="admin"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"Created User: {test_user}")
        
        # 3. Test Student Creation
        test_student = Student(
            student_id="STU1001",
            name="John Doe",
            department="Computer Science",
            year="3rd Year",
            section="A",
            image_count=25,
            embedding_status=True
        )
        db.add(test_student)
        db.commit()
        db.refresh(test_student)
        print(f"Created Student: {test_student}")
        
        # 4. Test Attendance Record Creation with FK Relationship
        test_attendance = Attendance(
            student_id=test_student.student_id,
            name=test_student.name,
            department=test_student.department,
            date="2026-08-04",
            time="09:15:00",
            status="Present",
            confidence_score=0.95
        )
        db.add(test_attendance)
        db.commit()
        db.refresh(test_attendance)
        print(f"Created Attendance: {test_attendance}")
        
        # 5. Verify Relationship
        fetched_student = db.query(Student).filter_by(student_id="STU1001").first()
        print(f"Fetched Student Attendance Count: {len(fetched_student.attendance_records)}")
        assert len(fetched_student.attendance_records) == 1
        assert fetched_student.attendance_records[0].confidence_score == 0.95
        
        # Clean up test entries
        db.delete(test_attendance)
        db.delete(test_student)
        db.delete(test_user)
        db.commit()
        print("Database Verification Completed Successfully! (Test data cleaned up)")
        
    except Exception as e:
        db.rollback()
        print("Database Test Error:", e)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    test_database_operations()
