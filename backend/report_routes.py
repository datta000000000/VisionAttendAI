import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user, get_current_admin, get_current_teacher_or_admin
from backend.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/export")
def export_attendance_csv(
    student_id: Optional[str] = None,
    name: Optional[str] = None,
    department: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    """
    Generate and stream a downloadable CSV report of attendance records matching filters.
    Enforces Admin-only access and organization isolation.
    """
    try:
        filters = {
            "student_id": student_id,
            "name": name,
            "department": department,
            "date": date,
            "start_date": start_date,
            "end_date": end_date
        }
        csv_buffer = ReportService.generate_csv_report(db, filters, current_user.organization_id)
        
        # Stream the CSV back to the client
        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=attendance_report.csv"}
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception("Error exporting CSV report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while exporting the report."
        )


@router.get("/stats", status_code=status.HTTP_200_OK)
def get_report_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    Retrieve aggregate statistics for reports:
    - department-wise percentages
    - monthly present counts
    - overall metrics
    Enforces organization isolation.
    """
    try:
        stats = ReportService.get_report_stats(db, current_user.organization_id)
        return stats
    except Exception as e:
        logger.exception("Error generating report stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while calculating reports stats."
        )
