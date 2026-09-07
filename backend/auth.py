import logging
import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.database import get_db
from backend.models import User, Organization
from backend.schemas import Token, UserResponse, UserLogin

logger = logging.getLogger(__name__)

# Cryptographic password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Scheme for bearer token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Generates a JWT access token with an expiration timestamp."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_default_admin(db: Session):
    """
    Creates a default admin user if the database contains no user records.
    Default Credentials: Username: admin | Password: admin123
    """
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            # Get or create DEFAULT-ORG
            default_org = db.query(Organization).filter(Organization.organization_code == "DEFAULT-ORG").first()
            if not default_org:
                default_org = Organization(
                    organization_name="Default Organization",
                    organization_code="DEFAULT-ORG"
                )
                db.add(default_org)
                db.commit()
                db.refresh(default_org)

            default_admin = User(
                username="admin",
                email="admin@visionattend.ai",
                hashed_password=hash_password("admin123"),
                role="admin",
                is_active=True,
                full_name="System Administrator",
                organization_id=default_org.id
            )
            db.add(default_admin)
            db.commit()
            db.refresh(default_admin)
            logger.info("Default Admin account created successfully: admin / admin123")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating default admin user: {e}")


def get_token_from_request(request: Request, token_header: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """
    Retrieves token from Authorization Bearer header or HTTP Cookie ('access_token').
    """
    if token_header and type(token_header).__name__ != 'Depends':
        return token_header
    
    # Manually check Authorization header if token_header is unresolved
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that decodes JWT token and retrieves the authenticated user.
    Raises HTTP 401 Unauthorized if token is missing or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = get_token_from_request(request)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency enforcing admin role permissions.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to perform this action."
        )
    return current_user


def get_current_teacher_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency enforcing admin or teacher role permissions.
    """
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or admin privileges required to perform this action."
        )
    return current_user
