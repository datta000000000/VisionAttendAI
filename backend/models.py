import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Organization(Base):
    """
    Organization tenant entity model.
    """
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_name: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    students: Mapped[List["Student"]] = relationship("Student", back_populates="organization", cascade="all, delete-orphan")
    attendance_records: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.organization_name}', code='{self.organization_code}')>"


class User(Base):
    """
    User entity model for Admin / Teacher / Student authentication and access control.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="teacher", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Organization link
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True
    )
    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="users")

    # Student link (for role == "student")
    student_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("students.student_id", ondelete="SET NULL"),
        nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Student(Base):
    """
    Student profile model storing institutional metadata and face registration state.
    """
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    department: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    year: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Organization link
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True
    )
    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="students")

    registered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # One-to-many relationship with attendance records
    attendance_records: Mapped[List["Attendance"]] = relationship(
        "Attendance",
        back_populates="student",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Student(student_id='{self.student_id}', name='{self.name}', dept='{self.department}')>"


class Attendance(Base):
    """
    Attendance record entity storing daily face recognition logs.
    """
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # Format: YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(8), nullable=False)              # Format: HH:MM:SS
    status: Mapped[str] = mapped_column(String(20), default="Present", nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Organization link
    organization_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True
    )
    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="attendance_records")

    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationship linking back to student table
    student: Mapped["Student"] = relationship("Student", back_populates="attendance_records")

    # Composite Index for fast date & student lookup
    __table_args__ = (
        Index("idx_student_date", "student_id", "date", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Attendance(student_id='{self.student_id}', date='{self.date}', status='{self.status}')>"
