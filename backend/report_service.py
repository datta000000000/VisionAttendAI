import io
import csv
import datetime
import logging
from typing import Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.models import Student, Attendance

logger = logging.getLogger(__name__)

def validate_date_format(date_str: str) -> str:
    """Helper to validate date format (YYYY-MM-DD)."""
    if not date_str:
        return date_str
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'."
        )

class ReportService:
    @staticmethod
    def generate_csv_report(db: Session, filters: Dict[str, Any], organization_id: int) -> io.StringIO:
        """
        Queries attendance records based on filters and outputs a CSV string buffer.
        Enforces organization isolation.
        """
        # Validate dates
        validate_date_format(filters.get("date"))
        validate_date_format(filters.get("start_date"))
        validate_date_format(filters.get("end_date"))

        query = db.query(Attendance).filter(Attendance.organization_id == organization_id)

        if filters.get("student_id"):
            query = query.filter(Attendance.student_id == filters["student_id"])
        if filters.get("name"):
            query = query.filter(Attendance.name.ilike(f"%{filters['name']}%"))
        if filters.get("department"):
            query = query.filter(Attendance.department == filters["department"])
        if filters.get("date"):
            query = query.filter(Attendance.date == filters["date"])
        if filters.get("start_date"):
            query = query.filter(Attendance.date >= filters["start_date"])
        if filters.get("end_date"):
            query = query.filter(Attendance.date <= filters["end_date"])

        records = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(["Student ID", "Name", "Department", "Date", "Time", "Status", "Confidence"])
        
        # Write rows
        for record in records:
            writer.writerow([
                record.student_id,
                record.name,
                record.department,
                record.date,
                record.time,
                record.status,
                f"{record.confidence_score:.4f}"
            ])
            
        output.seek(0)
        return output

    @staticmethod
    def get_report_stats(db: Session, organization_id: int) -> Dict[str, Any]:
        """
        Calculates aggregate statistics for reports:
        - department-wise attendance percentages
        - monthly attendance counts
        - total present records
        - overall attendance percentage
        Enforces organization isolation.
        """
        # 1. Total Registered Students & Unique Dates in organization
        total_students = db.query(Student).filter(Student.organization_id == organization_id).count()
        unique_dates_query = db.query(Attendance.date).filter(Attendance.organization_id == organization_id).distinct().all()
        num_unique_dates = len(unique_dates_query)
        total_present = db.query(Attendance).filter(
            Attendance.status == "Present",
            Attendance.organization_id == organization_id
        ).count()

        # Overall percentage
        overall_pct = 0.0
        if total_students > 0 and num_unique_dates > 0:
            overall_pct = (total_present / (total_students * num_unique_dates)) * 100.0

        # 2. Department-wise stats
        # Get list of unique departments within organization
        depts_query = db.query(Student.department).filter(Student.organization_id == organization_id).distinct().all()
        departments = [d[0] for d in depts_query if d[0]]
        
        dept_stats = {}
        for dept in departments:
            dept_students = db.query(Student).filter(
                Student.department == dept,
                Student.organization_id == organization_id
            ).count()
            dept_unique_dates = db.query(Attendance.date).filter(
                Attendance.department == dept,
                Attendance.organization_id == organization_id
            ).distinct().count()
            dept_present = db.query(Attendance).filter(
                Attendance.department == dept,
                Attendance.status == "Present",
                Attendance.organization_id == organization_id
            ).count()
            
            dept_pct = 0.0
            if dept_students > 0 and dept_unique_dates > 0:
                dept_pct = (dept_present / (dept_students * dept_unique_dates)) * 100.0
                
            dept_stats[dept] = {
                "total_students": dept_students,
                "present_count": dept_present,
                "attendance_percentage": round(dept_pct, 2)
            }

        # 3. Monthly stats (Substrings date to YYYY-MM) filtered by organization
        monthly_query = db.query(
            func.substr(Attendance.date, 1, 7).label("month"),
            func.count(Attendance.id)
        ).filter(
            Attendance.status == "Present",
            Attendance.organization_id == organization_id
        ).group_by("month").all()
        
        monthly_counts = {row[0]: row[1] for row in monthly_query if row[0]}

        return {
            "total_present_records": total_present,
            "overall_attendance_percentage": round(overall_pct, 2),
            "department_wise_attendance": dept_stats,
            "monthly_attendance": monthly_counts
        }
