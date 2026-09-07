import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.config import (
    APP_NAME,
    APP_VERSION,
    FRONTEND_DIR,
    STATIC_DIR,
    DATABASE_DIR,
    DATASET_DIR,
    EMBEDDINGS_DIR,
    REPORTS_DIR
)
from backend.database import init_db, SessionLocal
from backend.auth import create_default_admin
from backend.auth_routes import router as auth_router
from backend.student_routes import router as student_router
from backend.attendance_routes import router as attendance_router
from backend.dashboard_routes import router as dashboard_router
from backend.report_routes import router as report_router
from backend.face_service import FaceService

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("visionattend")

# Initialize FastAPI Application Instance
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Real-Time Face Recognition Based Smart Attendance Management System API"
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(attendance_router)
app.include_router(dashboard_router)
app.include_router(report_router)

# Mount Static Files and Frontend Assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.on_event("startup")
def startup_event():
    """Server Startup Lifecycle Event."""
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}...")
    init_db()
    
    # Initialize default admin account if database is empty
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()
        
    # Warm up InsightFace face registration models
    try:
        FaceService().initialize()
    except Exception as e:
        logger.error(f"Failed to initialize FaceService during startup: {e}")
        
    logger.info("Application initialization complete.")


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint verifying backend status."""
    return {
        "status": "online",
        "app": APP_NAME,
        "version": APP_VERSION,
        "message": "VisionAttend AI Backend Service is running smoothly."
    }


@app.get("/api/system/status", tags=["System"])
def system_status():
    """System status endpoint verifying filesystem readiness."""
    return {
        "database_dir_exists": DATABASE_DIR.exists(),
        "dataset_dir_exists": DATASET_DIR.exists(),
        "embeddings_dir_exists": EMBEDDINGS_DIR.exists(),
        "reports_dir_exists": REPORTS_DIR.exists(),
        "status": "ready"
    }


@app.get("/", tags=["System"])
def read_root():
    """Serve index.html or API JSON metadata."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(content={
        "app": APP_NAME,
        "version": APP_VERSION,
        "message": "Welcome to VisionAttend AI API. Access /health for system status."
    })


@app.get("/{page}.html", tags=["System"])
def read_page_html(page: str):
    """Serve specific HTML pages directly from the frontend directory."""
    page_file = FRONTEND_DIR / f"{page}.html"
    if page_file.exists():
        return FileResponse(str(page_file))
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/{page}", tags=["System"])
def read_page(page: str):
    """Serve specific pages directly without the .html extension if they exist."""
    # Ignore core paths to prevent hijacking FastAPIs default routers
    if page in ["api", "health", "docs", "redoc", "openapi.json", "static", "frontend"]:
        raise HTTPException(status_code=404, detail="Page not found")
    page_file = FRONTEND_DIR / f"{page}.html"
    if page_file.exists():
        return FileResponse(str(page_file))
    raise HTTPException(status_code=404, detail="Page not found")
