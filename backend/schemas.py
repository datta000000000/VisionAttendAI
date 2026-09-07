import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, EmailStr


# ==========================================
# User & Authentication Schemas
# ==========================================

class OrganizationResponse(BaseModel):
    id: int
    organization_name: str
    organization_code: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: str = Field(..., description="Valid email address")
    role: str = Field("teacher", description="User role: admin, teacher, or student")
    full_name: Optional[str] = Field(None, max_length=100, description="User's full name")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")


class UserSignUp(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    organization_name: str = Field(..., min_length=2, max_length=100)
    organization_code: str = Field(..., min_length=2, max_length=50)
    role: str = Field(..., description="Role: admin or student")
    student_id: Optional[str] = Field(None, description="Required only if role is student")


class TeacherCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class UserResponse(UserBase):
    id: int
    is_active: bool
    organization_id: Optional[int] = None
    student_id: Optional[str] = None
    organization: Optional[OrganizationResponse] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==========================================
# Student Management Schemas
# ==========================================

class StudentBase(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=50, description="Unique Student ID")
    name: str = Field(..., min_length=2, max_length=100, description="Student Full Name")
    department: str = Field(..., max_length=50, description="Academic Department")
    year: str = Field(..., max_length=20, description="Academic Year (e.g. 1st Year, 2nd Year)")
    section: str = Field(..., max_length=20, description="Section (e.g. A, B)")


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    section: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
    image_count: int
    embedding_status: bool
    registered_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class StudentListResponse(BaseModel):
    total: int
    students: List[StudentResponse]


# ==========================================
# Attendance Schemas
# ==========================================

class AttendanceBase(BaseModel):
    student_id: str = Field(..., description="Student ID")
    name: str = Field(..., description="Student Full Name")
    department: str = Field(..., description="Department Name")
    date: str = Field(..., description="Attendance Date (YYYY-MM-DD)")
    time: str = Field(..., description="Attendance Time (HH:MM:SS)")
    status: str = Field("Present", description="Attendance Status")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Face recognition match confidence")


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceResponse(AttendanceBase):
    id: int
    timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    records: List[AttendanceResponse]


# ==========================================
# Dashboard & Analytics Schemas
# ==========================================

class DashboardStats(BaseModel):
    total_students: int
    registered_embeddings_count: int
    today_attendance_count: int
    attendance_percentage: float
