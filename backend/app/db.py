"""
Database engine & session factory.
Supports PostgreSQL (via DATABASE_URL) with automatic SQLite fallback for local dev.
Uses SQLAlchemy 2.0 synchronous engine wrapped in run_in_executor for async-safe usage.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# -------------------------------------------------------------------
# Connection URL
# -------------------------------------------------------------------
_DEFAULT_DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reading_coach.db"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_FILE}")

# SQLite WAL mode tweak (ignored if PostgreSQL)
_is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False, "timeout": 30.0} if _is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute("PRAGMA busy_timeout=30000")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables that don't yet exist (idempotent) and seed default demo teacher/student if empty."""
    # Import models so their metadata is registered on Base before create_all
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Seed initial classroom/student for immediate out-of-the-box readiness
    with SessionLocal() as db:
        teacher = db.query(models.Teacher).filter(models.Teacher.id == "default-teacher-1").first()
        if not teacher:
            teacher = models.Teacher(
                id="default-teacher-1",
                email="teacher@readingcoach.edu.in",
                name="Sunita Sharma",
                school_name="Kendriya Vidyalaya, Pune",
                email_verified=True,
                digest_time="16:00"
            )
            db.add(teacher)
            db.commit()

        classroom = db.query(models.Classroom).filter(models.Classroom.id == "default-class-1").first()
        if not classroom:
            classroom = models.Classroom(
                id="default-class-1",
                teacher_id="default-teacher-1",
                name="Grade 4-A (हिन्दी)",
                grade_level=4,
                language="hi",
                academic_year="2025-26"
            )
            db.add(classroom)
            db.commit()

        # Seed students if classroom has none
        student_count = db.query(models.Student).filter(models.Student.classroom_id == "default-class-1").count()
        if student_count == 0:
            demo_students = [
                models.Student(id="student-1", classroom_id="default-class-1", display_name="Aarav Sharma", roll_number="101", grade_level=4),
                models.Student(id="student-2", classroom_id="default-class-1", display_name="Priya Patel", roll_number="102", grade_level=4),
                models.Student(id="student-3", classroom_id="default-class-1", display_name="Rohan Verma", roll_number="103", grade_level=4),
                models.Student(id="student-4", classroom_id="default-class-1", display_name="Ananya Singh", roll_number="104", grade_level=4),
            ]
            db.add_all(demo_students)
            db.commit()

