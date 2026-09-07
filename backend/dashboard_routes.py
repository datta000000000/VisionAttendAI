import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user, get_current_teacher_or_admin
from backend.models import Student, Attendance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", status_code=status.HTTP_200_OK)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    Retrieve real-time dashboard analytics:
    - total registered students in organization
    - registered embeddings count in organization
    - today's attendance count in organization
    - today's attendance percentage
    - overall attendance percentage
    - today's date
    - department-wise student counts
    """
    try:
        today_str = datetime.date.today().isoformat()
        org_id = current_user.organization_id

        # 1. Total students and registered embeddings filtered by organization
        total_students = db.query(Student).filter(Student.organization_id == org_id).count()
        registered_embeddings = db.query(Student).filter(
            Student.embedding_status == True,
            Student.organization_id == org_id
        ).count()

        # 2. Today's attendance count filtered by organization
        today_attendance = db.query(Attendance).filter(
            Attendance.date == today_str,
            Attendance.status == "Present",
            Attendance.organization_id == org_id
        ).count()

        # 3. Today's attendance percentage
        today_pct = 0.0
        if total_students > 0:
            today_pct = (today_attendance / total_students) * 100.0

        # 4. Overall attendance percentage filtered by organization
        # Formula: Total Present records / (Total registered students * unique attendance dates) * 100
        unique_dates_query = db.query(Attendance.date).filter(Attendance.organization_id == org_id).distinct().all()
        num_unique_dates = len(unique_dates_query)
        total_present = db.query(Attendance).filter(
            Attendance.status == "Present",
            Attendance.organization_id == org_id
        ).count()

        overall_pct = 0.0
        if total_students > 0 and num_unique_dates > 0:
            overall_pct = (total_present / (total_students * num_unique_dates)) * 100.0

        # 5. Department-wise student counts filtered by organization
        dept_stats = db.query(Student.department, func.count(Student.id)).filter(
            Student.organization_id == org_id
        ).group_by(Student.department).all()
        dept_counts = {dept: count for dept, count in dept_stats}

        return {
            "total_students": total_students,
            "registered_embeddings_count": registered_embeddings,
            "today_attendance_count": today_attendance,
            "attendance_percentage": round(today_pct, 2),
            "overall_attendance_percentage": round(overall_pct, 2),
            "today_date": today_str,
            "department_wise_counts": dept_counts
        }

    except Exception as e:
        logger.exception("Error generating dashboard stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching dashboard statistics."
        )


@router.get("/student/stats", status_code=status.HTTP_200_OK)
def get_student_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieve personal student dashboard statistics:
    - student name, ID, and organization
    - today's check-in status (Present or Absent)
    - overall attendance percentage
    - list of recent attendance records (limit 5)
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts can access this dashboard endpoint."
        )

    student_id = current_user.student_id
    if not student_id:
        return {
            "student_id": "Unlinked",
            "name": current_user.full_name or current_user.username,
            "organization_name": current_user.organization.organization_name if current_user.organization else "None",
            "today_status": "Unregistered",
            "overall_attendance_percentage": 0.0,
            "recent_records": []
        }

    # Query student details
    student = db.query(Student).filter(
        Student.student_id == student_id,
        Student.organization_id == current_user.organization_id
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile mapping is missing."
        )

    # Today's status
    today_str = datetime.date.today().isoformat()
    today_attendance = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.date == today_str,
        Attendance.organization_id == current_user.organization_id
    ).first()
    today_status = "Present" if today_attendance else "Absent"

    # Overall percentage
    unique_dates_query = db.query(Attendance.date).filter(Attendance.organization_id == current_user.organization_id).distinct().all()
    num_unique_dates = len(unique_dates_query)
    student_present_count = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.status == "Present",
        Attendance.organization_id == current_user.organization_id
    ).count()

    overall_pct = 0.0
    if num_unique_dates > 0:
        overall_pct = (student_present_count / num_unique_dates) * 100.0

    # Recent records
    recent_attendance = db.query(Attendance).filter(
        Attendance.student_id == student_id,
        Attendance.organization_id == current_user.organization_id
    ).order_by(Attendance.date.desc(), Attendance.time.desc()).limit(5).all()

    return {
        "student_id": student.student_id,
        "name": student.name,
        "organization_name": current_user.organization.organization_name if current_user.organization else "None",
        "today_status": today_status,
        "overall_attendance_percentage": round(overall_pct, 2),
        "recent_records": [
            {
                "date": r.date,
                "time": r.time,
                "status": r.status,
                "confidence_score": r.confidence_score
            } for r in recent_attendance
        ]
    }
