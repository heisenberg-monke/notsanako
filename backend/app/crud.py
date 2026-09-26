"""
CRUD operations — all database reads and writes.
Uses synchronous SQLAlchemy sessions (compatible with both SQLite and PostgreSQL).
"""

from __future__ import annotations
from datetime import date, datetime, timedelta
from collections import Counter
from typing import Optional, List, Dict, Any

from sqlalchemy import func, and_, desc, text
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------

def get_teacher_by_email(db: Session, email: str) -> Optional[models.Teacher]:
    return db.query(models.Teacher).filter(models.Teacher.email == email).first()


def get_teacher(db: Session, teacher_id: str) -> Optional[models.Teacher]:
    return db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()


def create_teacher(db: Session, data: schemas.TeacherCreate) -> models.Teacher:
    teacher = models.Teacher(
        email=data.email,
        name=data.name,
        school_name=data.school_name,
        digest_time=data.digest_time,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def update_teacher(db: Session, teacher: models.Teacher, data: schemas.TeacherUpdate) -> models.Teacher:
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(teacher, field, val)
    db.commit()
    db.refresh(teacher)
    return teacher


def verify_teacher_email(db: Session, teacher: models.Teacher) -> models.Teacher:
    teacher.email_verified = True
    db.commit()
    db.refresh(teacher)
    return teacher


# ---------------------------------------------------------------------------
# Classroom
# ---------------------------------------------------------------------------

def get_classrooms(db: Session, teacher_id: str) -> List[models.Classroom]:
    return (
        db.query(models.Classroom)
        .filter(models.Classroom.teacher_id == teacher_id)
        .order_by(models.Classroom.created_at.desc())
        .all()
    )


def get_classroom(db: Session, classroom_id: str) -> Optional[models.Classroom]:
    return db.query(models.Classroom).filter(models.Classroom.id == classroom_id).first()


def create_classroom(
    db: Session, teacher_id: str, data: schemas.ClassroomCreate
) -> models.Classroom:
    classroom = models.Classroom(
        teacher_id=teacher_id,
        name=data.name,
        grade_level=data.grade_level,
        language=data.language,
        academic_year=data.academic_year,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


def update_classroom(
    db: Session, classroom: models.Classroom, data: schemas.ClassroomUpdate
) -> models.Classroom:
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(classroom, field, val)
    db.commit()
    db.refresh(classroom)
    return classroom


def delete_classroom(db: Session, classroom: models.Classroom) -> None:
    db.delete(classroom)
    db.commit()


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------

def get_students(db: Session, classroom_id: str) -> List[models.Student]:
    return (
        db.query(models.Student)
        .filter(models.Student.classroom_id == classroom_id)
        .order_by(models.Student.display_name)
        .all()
    )


def get_student(db: Session, student_id: str) -> Optional[models.Student]:
    return db.query(models.Student).filter(models.Student.id == student_id).first()


def create_student(
    db: Session, classroom_id: str, data: schemas.StudentCreate
) -> models.Student:
    student = models.Student(
        classroom_id=classroom_id,
        display_name=data.display_name,
        roll_number=data.roll_number,
        grade_level=data.grade_level,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def update_student(
    db: Session, student: models.Student, data: schemas.StudentUpdate
) -> models.Student:
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(student, field, val)
    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: models.Student) -> None:
    db.delete(student)
    db.commit()


# ---------------------------------------------------------------------------
# PracticeSession + ReadingAttempt + ErrorLog
# (submitted together as a bundle from the student app)
# ---------------------------------------------------------------------------

def record_session(
    db: Session,
    record: schemas.PracticeSessionRecord,
) -> models.PracticeSession:
    """
    Persist a complete practice session including both reading attempts
    and their structured error logs.
    """
    session = models.PracticeSession(
        student_id=record.student_id,
        passage_id=record.passage_id,
        total_words_read=record.total_words_read,
        avg_wcpm=record.avg_wcpm,
        delta_summary=record.delta_summary,
        completed_retest=record.completed_retest,
        ended_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()  # get session.id before inserting children

    for attempt_data in [record.baseline, record.retest]:
        if not attempt_data:
            continue
        attempt = models.ReadingAttempt(
            session_id=session.id,
            passage_type=attempt_data.passage_type,
            passage_text=attempt_data.passage_text,
            transcribed_text=attempt_data.transcribed_text,
            wcpm=attempt_data.wcpm,
            accuracy_percentage=attempt_data.accuracy_percentage,
            duration_seconds=attempt_data.duration_seconds,
        )
        db.add(attempt)
        db.flush()

        for err in attempt_data.errors:
            db.add(models.ErrorLog(
                attempt_id=attempt.id,
                word=err.word,
                spoken_word=err.spoken_word,
                error_type=err.error_type,
                target_pattern=err.target_pattern,
                linguistic_detail=err.linguistic_detail,
                pedagogical_remedy=err.pedagogical_remedy,
                corrected_in_retest=err.corrected_in_retest,
                in_stumble_cluster=err.in_stumble_cluster,
            ))

    db.commit()
    db.refresh(session)
    return session


def get_student_sessions(
    db: Session, student_id: str, limit: int = 30
) -> List[models.PracticeSession]:
    return (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.student_id == student_id)
        .order_by(desc(models.PracticeSession.started_at))
        .limit(limit)
        .all()
    )


def get_session_detail(
    db: Session, session_id: str
) -> Optional[models.PracticeSession]:
    return (
        db.query(models.PracticeSession)
        .options(
            selectinload(models.PracticeSession.reading_attempts)
            .selectinload(models.ReadingAttempt.error_logs)
        )
        .filter(models.PracticeSession.id == session_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def count_students(db: Session, classroom_id: str) -> int:
    return db.query(func.count(models.Student.id)).filter(
        models.Student.classroom_id == classroom_id
    ).scalar() or 0


def get_active_student_ids_today(db: Session, classroom_id: str) -> List[str]:
    """Return student IDs in classroom who had a session started today (UTC)."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(models.PracticeSession.student_id)
        .join(models.Student, models.PracticeSession.student_id == models.Student.id)
        .filter(
            models.Student.classroom_id == classroom_id,
            models.PracticeSession.started_at >= today_start,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def get_class_error_patterns(
    db: Session, classroom_id: str, days: int = 7
) -> List[Dict[str, Any]]:
    """
    Return error type frequency for the classroom over the last N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(models.ErrorLog.error_type, func.count(models.ErrorLog.id).label("cnt"))
        .join(models.ReadingAttempt, models.ErrorLog.attempt_id == models.ReadingAttempt.id)
        .join(models.PracticeSession, models.ReadingAttempt.session_id == models.PracticeSession.id)
        .join(models.Student, models.PracticeSession.student_id == models.Student.id)
        .filter(
            models.Student.classroom_id == classroom_id,
            models.ErrorLog.created_at >= cutoff,
        )
        .group_by(models.ErrorLog.error_type)
        .order_by(desc("cnt"))
        .all()
    )
    total = sum(r.cnt for r in rows) or 1
    return [
        {"error_type": r.error_type, "count": r.cnt, "percentage": round(r.cnt / total * 100, 1)}
        for r in rows
    ]


def get_top_error_words(
    db: Session, classroom_id: str, error_type: str, limit: int = 5
) -> List[str]:
    """Top N words of a given error type across the classroom."""
    rows = (
        db.query(models.ErrorLog.word, func.count(models.ErrorLog.id).label("cnt"))
        .join(models.ReadingAttempt, models.ErrorLog.attempt_id == models.ReadingAttempt.id)
        .join(models.PracticeSession, models.ReadingAttempt.session_id == models.PracticeSession.id)
        .join(models.Student, models.PracticeSession.student_id == models.Student.id)
        .filter(
            models.Student.classroom_id == classroom_id,
            models.ErrorLog.error_type == error_type,
        )
        .group_by(models.ErrorLog.word)
        .order_by(desc("cnt"))
        .limit(limit)
        .all()
    )
    return [r.word for r in rows]


def get_student_latest_metrics(
    db: Session, student_id: str
) -> Dict[str, Any]:
    """
    Return the most recent WCPM, accuracy, and last-session date for a student.
    Also derive top error types from the last 3 sessions.
    """
    latest_attempt = (
        db.query(models.ReadingAttempt)
        .join(models.PracticeSession)
        .filter(
            models.PracticeSession.student_id == student_id,
            models.ReadingAttempt.passage_type == "BASELINE",
        )
        .order_by(desc(models.ReadingAttempt.created_at))
        .first()
    )

    latest_session = (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.student_id == student_id)
        .order_by(desc(models.PracticeSession.started_at))
        .first()
    )

    # Error types from last 3 sessions
    recent_errors = (
        db.query(models.ErrorLog.error_type)
        .join(models.ReadingAttempt)
        .join(models.PracticeSession)
        .filter(models.PracticeSession.student_id == student_id)
        .order_by(desc(models.PracticeSession.started_at))
        .limit(50)
        .all()
    )
    top_errors = [t for t, _ in Counter(r[0] for r in recent_errors).most_common(3)]

    # Count sessions
    session_count = db.query(func.count(models.PracticeSession.id)).filter(
        models.PracticeSession.student_id == student_id
    ).scalar() or 0

    # Best delta
    best_delta = None
    sessions_with_delta = (
        db.query(models.PracticeSession.delta_summary)
        .filter(
            models.PracticeSession.student_id == student_id,
            models.PracticeSession.delta_summary.isnot(None),
        )
        .all()
    )
    deltas = [s[0].get("delta", 0.0) for s in sessions_with_delta if s[0]]
    if deltas:
        best_delta = max(deltas)

    return {
        "latest_wcpm": latest_attempt.wcpm if latest_attempt else None,
        "latest_accuracy": latest_attempt.accuracy_percentage if latest_attempt else None,
        "last_session_date": (
            latest_session.started_at.strftime("%Y-%m-%d") if latest_session else None
        ),
        "session_count": session_count,
        "best_delta": best_delta,
        "top_error_types": top_errors,
    }


def flag_students_needing_attention(db: Session, classroom_id: str) -> None:
    """
    Update needs_attention flag for all students in a classroom.
    Criteria: 2+ sessions in the last 7 days with accuracy < 70% and no delta > 10%.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)
    students = get_students(db, classroom_id)

    for student in students:
        sessions = (
            db.query(models.PracticeSession)
            .filter(
                models.PracticeSession.student_id == student.id,
                models.PracticeSession.started_at >= cutoff,
            )
            .all()
        )

        if len(sessions) < 2:
            # Not enough data
            student.needs_attention = False
            student.attention_reason = None
            continue

        # Check accuracy and delta
        low_accuracy_sessions = 0
        improved = False
        for s in sessions:
            attempt = (
                db.query(models.ReadingAttempt)
                .filter(
                    models.ReadingAttempt.session_id == s.id,
                    models.ReadingAttempt.passage_type == "BASELINE",
                )
                .first()
            )
            if attempt and attempt.accuracy_percentage < 70.0:
                low_accuracy_sessions += 1
            if s.delta_summary and s.delta_summary.get("delta", 0.0) > 10.0:
                improved = True

        if low_accuracy_sessions >= 2 and not improved:
            student.needs_attention = True
            student.attention_reason = (
                f"Accuracy below 70% in {low_accuracy_sessions} recent sessions "
                "with no measurable improvement after remediation."
            )
        else:
            student.needs_attention = False
            student.attention_reason = None

    db.commit()


# ---------------------------------------------------------------------------
# Daily Digest persistence
# ---------------------------------------------------------------------------

def save_daily_digest(
    db: Session,
    teacher_id: str,
    digest_date: str,
    payload: dict,
    html_body: str,
) -> models.DailyDigest:
    # Upsert: delete existing digest for same teacher+date if any
    existing = (
        db.query(models.DailyDigest)
        .filter(
            models.DailyDigest.teacher_id == teacher_id,
            models.DailyDigest.digest_date == digest_date,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    digest = models.DailyDigest(
        teacher_id=teacher_id,
        digest_date=digest_date,
        payload=payload,
        html_body=html_body,
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)
    return digest


def mark_digest_sent(db: Session, digest: models.DailyDigest) -> models.DailyDigest:
    digest.email_sent = True
    digest.sent_at = datetime.utcnow()
    db.commit()
    db.refresh(digest)
    return digest


def get_latest_digest(
    db: Session, teacher_id: str
) -> Optional[models.DailyDigest]:
    return (
        db.query(models.DailyDigest)
        .filter(models.DailyDigest.teacher_id == teacher_id)
        .order_by(desc(models.DailyDigest.created_at))
        .first()
    )
