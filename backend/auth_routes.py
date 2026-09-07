import logging
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, Organization, Student
from backend.schemas import UserLogin, UserResponse, Token, UserSignUp, TeacherCreate
from backend.auth import (
    verify_password,
    create_access_token,
    get_current_user,
    hash_password,
    get_current_admin
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login_for_access_token(
    response: Response,
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticate User (Admin / Teacher) via JSON payload and return JWT Token.
    Sets HttpOnly cookie for seamless frontend session management.
    """
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    # Set HttpOnly Session Cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=60 * 60 * 12,  # 12 Hours
        samesite="lax"
    )

    logger.info(f"User '{user.username}' logged in successfully.")
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
def logout(response: Response):
    """
    Logout API: Clears session authentication cookies.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_authenticated_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get profile information of currently authenticated User.
    Protected endpoint requiring valid JWT token / session.
    """
    return UserResponse.model_validate(current_user)


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(
    signup_data: UserSignUp,
    db: Session = Depends(get_db)
):
    """
    Public registration endpoint supporting:
    - Admin / Organization Owner signup (creates new organization if it doesn't exist)
    - Student signup (requires valid existing student_id and organization_code)
    """
    # 1. Validation checks
    if signup_data.password != signup_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )

    # Prevent duplicate username/email
    existing_username = db.query(User).filter(User.username == signup_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )

    existing_email = db.query(User).filter(User.email == signup_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered."
        )

    if signup_data.role not in ["admin", "student"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only admin or student registration is publicly allowed."
        )

    # 2. Process Organization
    org_code = signup_data.organization_code.strip()
    organization = db.query(Organization).filter(Organization.organization_code == org_code).first()

    if signup_data.role == "admin":
        if not organization:
            # Create new organization
            organization = Organization(
                organization_name=signup_data.organization_name,
                organization_code=org_code
            )
            db.add(organization)
            try:
                db.commit()
                db.refresh(organization)
                logger.info(f"New organization '{signup_data.organization_name}' created successfully with code '{org_code}'.")
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization code is already taken."
                )
        else:
            logger.info(f"Adding user as admin to existing organization code '{org_code}'.")
            
    elif signup_data.role == "student":
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization code does not exist. Please contact your administrator."
            )
            
        # Verify student_id exists in that organization
        if not signup_data.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student ID is required for student registration."
            )
            
        student_profile = db.query(Student).filter(
            Student.student_id == signup_data.student_id,
            Student.organization_id == organization.id
        ).first()
        
        if not student_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student ID '{signup_data.student_id}' does not exist in organization '{organization.organization_name}'."
            )
            
        # Verify student_id is not already linked to another User record
        linked_user = db.query(User).filter(User.student_id == signup_data.student_id).first()
        if linked_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user account is already linked to this Student ID."
            )

    # 3. Create User account
    new_user = User(
        username=signup_data.username,
        email=signup_data.email,
        hashed_password=hash_password(signup_data.password),
        role=signup_data.role,
        full_name=signup_data.full_name,
        organization_id=organization.id,
        student_id=signup_data.student_id if signup_data.role == "student" else None,
        is_active=True
    )
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        logger.info(f"User account '{signup_data.username}' created successfully as role '{signup_data.role}'.")
        return new_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user account: {str(e)}"
        )


@router.post("/create-teacher", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    teacher_data: TeacherCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Admin-only endpoint to create/invite a teacher user account within the admin's organization.
    """
    # Prevent duplicate username/email
    existing_username = db.query(User).filter(User.username == teacher_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )

    existing_email = db.query(User).filter(User.email == teacher_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered."
        )

    # Create teacher user
    new_teacher = User(
        username=teacher_data.username,
        email=teacher_data.email,
        hashed_password=hash_password(teacher_data.password),
        role="teacher",
        full_name=teacher_data.full_name,
        organization_id=current_admin.organization_id,
        is_active=True
    )
    
    db.add(new_teacher)
    try:
        db.commit()
        db.refresh(new_teacher)
        logger.info(f"Teacher account '{teacher_data.username}' successfully created by Admin '{current_admin.username}'.")
        return new_teacher
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create teacher account: {str(e)}"
        )
