import os
import re
import shutil
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Student
from backend.schemas import StudentResponse, StudentUpdate, StudentListResponse
from backend.auth import get_current_user, get_current_teacher_or_admin
from backend.face_service import FaceService
from backend.config import DATASET_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/students", tags=["Student Management"])

def sanitize_student_id(student_id: str) -> str:
    """Sanitizes student ID to keep only alphanumeric, hyphens, and underscores."""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', student_id)
    if not sanitized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student ID contains only invalid characters. Only alphanumeric, hyphens, and underscores are allowed."
        )
    return sanitized

def sanitize_filename(filename: str) -> str:
    """Sanitizes image filenames to prevent path traversal and ensure clean extension."""
    base, ext = os.path.splitext(filename)
    clean_base = re.sub(r'[^a-zA-Z0-9_-]', '_', base)
    clean_ext = re.sub(r'[^a-zA-Z0-9.]', '', ext).lower()
    if clean_ext not in ['.jpg', '.jpeg', '.png']:
        clean_ext = '.jpg'
    return f"{clean_base}{clean_ext}"


@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def register_student(
    student_id: str = Form(..., description="Unique Student ID"),
    name: str = Form(..., description="Student Full Name"),
    department: str = Form(..., description="Academic Department"),
    year: str = Form(..., description="Academic Year (e.g. 1st Year)"),
    section: str = Form(..., description="Section (e.g. A, B)"),
    face_images: List[UploadFile] = File(..., description="List of 3 to 5 face registration images"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    Registers a new Student and processes their face images.
    - Validates that exactly 3 to 5 images are provided.
    - Ensures each image contains exactly 1 face.
    - Computes and caches an L2-normalized average face embedding.
    - Stores images on disk and metadata in the database.
    """
    sanitized_id = sanitize_student_id(student_id)

    # 1. Enforce 3-5 images limit
    if len(face_images) < 3 or len(face_images) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration requires between 3 and 5 face images. Received {len(face_images)}."
        )

    # 2. Check for duplicate student ID in DB
    existing_student = db.query(Student).filter(Student.student_id == sanitized_id).first()
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student with ID '{sanitized_id}' is already registered."
        )

    face_service = FaceService()
    embeddings = []
    processed_images = []

    # 3. Read and validate images sequentially
    for file in face_images:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format for '{file.filename}'. Only JPG, JPEG, and PNG are allowed."
            )

        try:
            content = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read file '{file.filename}': {str(e)}"
            )

        # Detect face and generate embedding
        try:
            embedding = face_service.extract_embedding(content, file.filename)
            embeddings.append(embedding)
            processed_images.append((file.filename, content))
        except ValueError as val_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err)
            )

    # 4. Save images to dataset directory
    student_dir = DATASET_DIR / sanitized_id
    student_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for filename, content in processed_images:
        clean_name = sanitize_filename(filename)
        file_path = student_dir / clean_name
        
        # Handle filename collisions (e.g. if uploading multiple images with same filename)
        counter = 1
        while file_path.exists():
            parts = os.path.splitext(clean_name)
            file_path = student_dir / f"{parts[0]}_{counter}{parts[1]}"
            counter += 1

        try:
            with open(file_path, "wb") as f:
                f.write(content)
            saved_paths.append(file_path)
        except Exception as e:
            # Clean up saved files and dir
            if student_dir.exists():
                shutil.rmtree(student_dir)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save image '{filename}': {str(e)}"
            )

    # 5. Compute average embedding and save to cache
    try:
        avg_embedding = face_service.compute_average_embedding(embeddings)
        face_service.update_student_embedding(sanitized_id, avg_embedding)
    except Exception as e:
        # Clean up saved files and dir
        if student_dir.exists():
            shutil.rmtree(student_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute or cache student face embedding: {str(e)}"
        )

    # 6. Save to Database
    new_student = Student(
        student_id=sanitized_id,
        name=name,
        department=department,
        year=year,
        section=section,
        image_count=len(processed_images),
        embedding_status=True,
        organization_id=current_user.organization_id
    )
    db.add(new_student)
    try:
        db.commit()
        db.refresh(new_student)
    except Exception as e:
        db.rollback()
        # Clean up embeddings cache and dataset
        face_service.delete_student_embedding(sanitized_id)
        if student_dir.exists():
            shutil.rmtree(student_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database write failed: {str(e)}"
        )

    logger.info(f"Student '{sanitized_id}' registered successfully.")
    return new_student


@router.get("", response_model=StudentListResponse)
def list_students(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    List all registered Students with pagination and optional search/department filter.
    Enforces organization isolation.
    """
    query = db.query(Student).filter(Student.organization_id == current_user.organization_id)
    if search:
        query = query.filter(
            (Student.name.ilike(f"%{search}%")) |
            (Student.student_id.ilike(f"%{search}%"))
        )
    if department:
        query = query.filter(Student.department.ilike(f"%{department}%"))

    total = query.count()
    students = query.offset(skip).limit(limit).all()
    return StudentListResponse(total=total, students=students)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieve metadata of a specific Student by ID.
    Allows:
    - Admin/Teacher to query within their organization.
    - Student to query ONLY their own registered student record.
    """
    sanitized_id = sanitize_student_id(student_id)
    
    if current_user.role == "student" and sanitized_id != current_user.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student accounts can only access their own student profile details."
        )

    student = db.query(Student).filter(
        Student.student_id == sanitized_id,
        Student.organization_id == current_user.organization_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found."
        )
    return student


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: str,
    update_data: StudentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_teacher_or_admin)
):
    """
    Update Student details (excluding ID and registration files).
    Enforces organization isolation.
    """
    sanitized_id = sanitize_student_id(student_id)
    student = db.query(Student).filter(
        Student.student_id == sanitized_id,
        Student.organization_id == current_user.organization_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found."
        )

    if update_data.name is not None:
        student.name = update_data.name
    if update_data.department is not None:
        student.department = update_data.department
    if update_data.year is not None:
        student.year = update_data.year
    if update_data.section is not None:
        student.section = update_data.section

    try:
        db.commit()
        db.refresh(student)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database update failed: {str(e)}"
        )

    logger.info(f"Student '{sanitized_id}' metadata updated.")
    return student


@router.delete("/{student_id}")
def delete_student(
    student_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a Student, purging their DB record, local image dataset, and cached embedding.
    Enforces admin-only permissions and organization isolation.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization administrators can delete student records."
        )

    sanitized_id = sanitize_student_id(student_id)
    student = db.query(Student).filter(
        Student.student_id == sanitized_id,
        Student.organization_id == current_user.organization_id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID '{student_id}' not found."
        )

    # 1. Purge face embedding cache
    FaceService().delete_student_embedding(sanitized_id)

    # 2. Delete local image dataset directory
    student_dir = DATASET_DIR / sanitized_id
    if student_dir.exists():
        try:
            shutil.rmtree(student_dir)
        except Exception as e:
            logger.error(f"Failed to delete dataset directory for student '{sanitized_id}': {e}")

    # 3. Delete database record
    db.delete(student)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database delete transaction failed: {str(e)}"
        )

    logger.info(f"Student '{sanitized_id}' and all associated registration files successfully deleted.")
    return {"message": f"Student with ID '{student_id}' deleted successfully."}
