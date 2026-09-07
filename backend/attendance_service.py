import datetime
import logging
from typing import List, Dict, Any
import numpy as np
import cv2
from sqlalchemy.orm import Session

from backend.models import Student, Attendance
from backend.face_service import FaceService
from backend.config import FACE_MATCH_THRESHOLD

logger = logging.getLogger(__name__)

class AttendanceService:
    @staticmethod
    def process_frame(db: Session, img_bytes: bytes, organization_id: int) -> Dict[str, Any]:
        """
        Decodes a webcam frame image, detects all faces, recognizes them using
        the registered student face embeddings, and logs attendance.
        """
        # 1. Decode image bytes
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Webcam frame image is invalid or corrupted.")

        # 2. Detect all faces
        face_service = FaceService()
        detected_faces = face_service.detect_all_faces(img)
        
        # 3. Load registered student IDs in this organization
        org_students = db.query(Student.student_id).filter(Student.organization_id == organization_id).all()
        org_student_ids = {s.student_id for s in org_students}

        # Load all registered embeddings and filter by organization
        all_embeddings = face_service.load_all_embeddings()
        registered_embeddings = {
            student_id: emb for student_id, emb in all_embeddings.items() if student_id in org_student_ids
        }
        
        results = []
        today_str = datetime.date.today().isoformat()
        current_time_str = datetime.datetime.now().strftime("%H:%M:%S")

        # 4. Process each face independently
        for face in detected_faces:
            bbox = face["bbox"]
            det_embedding = face["embedding"]
            
            best_student_id = None
            best_similarity = 0.0
            
            # Compare with all registered embeddings (L2-normalized cosine similarity via dot product)
            for student_id, reg_embedding in registered_embeddings.items():
                similarity = float(np.dot(det_embedding, reg_embedding))
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_student_id = student_id
            
            # Match only if similarity matches or exceeds threshold
            if best_student_id and best_similarity >= FACE_MATCH_THRESHOLD:
                # Query DB to get student name and department
                student = db.query(Student).filter(
                    Student.student_id == best_student_id,
                    Student.organization_id == organization_id
                ).first()
                
                if student:
                    # Check for duplicate attendance on the same day within the organization
                    existing_attendance = db.query(Attendance).filter(
                        Attendance.student_id == best_student_id,
                        Attendance.date == today_str,
                        Attendance.organization_id == organization_id
                    ).first()
                    
                    if existing_attendance:
                        attendance_status = "Already Present"
                    else:
                        # Log attendance
                        new_attendance = Attendance(
                            student_id=student.student_id,
                            name=student.name,
                            department=student.department,
                            date=today_str,
                            time=current_time_str,
                            status="Present",
                            confidence_score=best_similarity,
                            organization_id=organization_id
                        )
                        db.add(new_attendance)
                        try:
                            db.commit()
                            attendance_status = "Marked Present"
                        except Exception as e:
                            db.rollback()
                            logger.error(f"Error saving attendance for '{best_student_id}': {e}")
                            attendance_status = "Error Logging Attendance"
                    
                    results.append({
                        "student_id": student.student_id,
                        "student_name": student.name,
                        "department": student.department,
                        "similarity": best_similarity,
                        "attendance_status": attendance_status,
                        "bbox": bbox
                    })
                else:
                    # Pickle out of sync with DB
                    results.append({
                        "student_id": "unknown",
                        "similarity": best_similarity,
                        "attendance_status": "Unknown Face",
                        "bbox": bbox
                    })
            else:
                results.append({
                    "student_id": "unknown",
                    "similarity": best_similarity,
                    "attendance_status": "Unknown Face",
                    "bbox": bbox
                })

        return {
            "faces_detected": len(detected_faces),
            "matches": results
        }
