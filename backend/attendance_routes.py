import os
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user, get_current_teacher_or_admin
from backend.models import Attendance
from backend.schemas import AttendanceHistoryResponse
from backend.report_service import validate_date_format
from backend.attendance_service import AttendanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attendance", tags=["Attendance Management"])

@router.post("/recognize-frame", status_code=status.HTTP_200_OK)
async def recognize_frame(
    file: UploadFile = File(..., description="Webcam frame image file"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    Endpoint that accepts a webcam frame image, detects/recognizes faces,
    and logs attendance if a matching student is found.
    """
    # 1. Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format for '{file.filename}'. Only JPG, JPEG, and PNG are allowed."
        )

    # 2. Read file contents
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file '{file.filename}': {str(e)}"
        )

    # 3. File size protection (limit to 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{file.filename}' exceeds the maximum allowed size of 10MB."
        )

    # 4. Process frame and log attendance
    try:
        results = AttendanceService.process_frame(db, content, current_user.organization_id)
        return results
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.exception("Internal error processing attendance frame")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the frame."
        )


@router.get("/history", response_model=AttendanceHistoryResponse)
def get_attendance_history(
    page: int = 1,
    limit: int = 20,
    student_id: Optional[str] = None,
    name: Optional[str] = None,
    department: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieve paginated, filtered, and sorted attendance history logs.
    Enforces organization isolation.
    """
    # 1. Validate date formats
    validate_date_format(date)
    validate_date_format(start_date)
    validate_date_format(end_date)

    # 2. Whitelist sortable fields to prevent SQL injection
    sort_whitelist = ["student_id", "name", "department", "date", "time", "confidence_score", "timestamp"]
    if sort_by not in sort_whitelist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sorting by '{sort_by}' is not supported. Supported fields: {', '.join(sort_whitelist)}"
        )

    if sort_order.lower() not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sort order must be either 'asc' or 'desc'."
        )

    # 3. Query Construction with organization filter
    query = db.query(Attendance).filter(Attendance.organization_id == current_user.organization_id)

    # Enforce student personal attendance boundary
    if current_user.role == "student":
        student_id = current_user.student_id
        if not student_id:
            return AttendanceHistoryResponse(
                total=0,
                page=page,
                limit=limit,
                pages=0,
                records=[]
            )

    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if name:
        query = query.filter(Attendance.name.ilike(f"%{name}%"))
    if department:
        query = query.filter(Attendance.department == department)
    if date:
        query = query.filter(Attendance.date == date)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    # 4. Apply sorting safely using whitelisted model attributes
    col_attr = getattr(Attendance, sort_by)
    if sort_order.lower() == "desc":
        query = query.order_by(col_attr.desc())
    else:
        query = query.order_by(col_attr.asc())

    # 5. Pagination
    total = query.count()
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20

    pages = (total + limit - 1) // limit if limit > 0 else 0
    offset = (page - 1) * limit
    records = query.offset(offset).limit(limit).all()

    return AttendanceHistoryResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        records=records
    )
