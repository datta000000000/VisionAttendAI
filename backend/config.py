import os
from pathlib import Path

# Base Directory Path
BASE_DIR = Path(__file__).resolve().parent.parent

# Core Folder Directory Paths
DATABASE_DIR = BASE_DIR / "database"
DATASET_DIR = BASE_DIR / "dataset"
EMBEDDINGS_DIR = BASE_DIR / "embeddings"
REPORTS_DIR = BASE_DIR / "reports"
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"

# Ensure all application directories are created on initialization
for directory in [DATABASE_DIR, DATASET_DIR, EMBEDDINGS_DIR, REPORTS_DIR, FRONTEND_DIR, STATIC_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Settings
DB_PATH = DATABASE_DIR / "visionattend.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Security & Authentication Settings
SECRET_KEY = os.getenv("SECRET_KEY", "visionattend-ai-production-super-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

# Face Recognition Parameters (InsightFace primary / face_recognition fallback)
TARGET_SAMPLE_COUNT = 25
FACE_MATCH_THRESHOLD = 0.60
EMBEDDINGS_CACHE_FILE = EMBEDDINGS_DIR / "student_embeddings.pkl"

# Application Metadata
APP_NAME = "VisionAttend AI"
APP_VERSION = "1.0.0"
