import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import SQLALCHEMY_DATABASE_URL

logger = logging.getLogger(__name__)

# Create SQLite database engine with multi-threading support for FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Session factory for generating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding database sessions.
    Automatically closes session after completion of request lifecycle.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initializes database tables by loading all ORM models and applying migrations.
    """
    try:
        import backend.models  # Ensures models are registered with Base.metadata
        from sqlalchemy import inspect
        
        # 1. First, create any tables that don't exist (e.g. organizations table)
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified.")

        # 2. Run manual migrations for existing tables using SQLite ALTER TABLE statements
        inspector = inspect(engine)
        
        # Helper to add column if it doesn't exist
        def add_column_if_not_exists(table_name: str, column_name: str, alter_sql: str):
            columns = [c["name"] for c in inspector.get_columns(table_name)]
            if column_name not in columns:
                logger.info(f"Adding column '{column_name}' to table '{table_name}'...")
                with engine.begin() as conn:
                    conn.execute(text(alter_sql))

        # Alter statements
        add_column_if_not_exists(
            "users", 
            "full_name", 
            "ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"
        )
        add_column_if_not_exists(
            "users", 
            "organization_id", 
            "ALTER TABLE users ADD COLUMN organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL"
        )
        add_column_if_not_exists(
            "users", 
            "student_id", 
            "ALTER TABLE users ADD COLUMN student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE SET NULL"
        )
        add_column_if_not_exists(
            "students", 
            "organization_id", 
            "ALTER TABLE students ADD COLUMN organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL"
        )
        add_column_if_not_exists(
            "attendance", 
            "organization_id", 
            "ALTER TABLE attendance ADD COLUMN organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL"
        )

        # 3. Seed Default Organization and migrate existing records
        from backend.models import Organization
        db = SessionLocal()
        try:
            org_count = db.query(Organization).count()
            if org_count == 0:
                default_org = Organization(
                    organization_name="Default Organization",
                    organization_code="DEFAULT-ORG"
                )
                db.add(default_org)
                db.commit()
                db.refresh(default_org)
                logger.info("Default Organization created: DEFAULT-ORG")

                # Associate all existing records to the default organization
                db.execute(text("UPDATE users SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": default_org.id})
                db.execute(text("UPDATE students SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": default_org.id})
                db.execute(text("UPDATE attendance SET organization_id = :org_id WHERE organization_id IS NULL"), {"org_id": default_org.id})
                db.commit()
                logger.info("Associated existing records to Default Organization.")
        finally:
            db.close()

        logger.info("Database tables (users, students, attendance, organizations) initialized/migrated successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e
