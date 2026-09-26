"""
ORM Models — all seven entities from the project plan.

TEACHER → CLASSROOM → STUDENT → PRACTICE_SESSION → READING_ATTEMPT → ERROR_LOG
TEACHER → DAILY_DIGEST
"""

import uuid
from datetime import datetime, time
from sqlalchemy import (
    String, Text, Float, Boolean, Integer,
    DateTime, Time, ForeignKey, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------
class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name: Mapped[str] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Time-of-day to send daily digest (stored as HH:MM string for portability)
    digest_time: Mapped[str] = mapped_column(String(5), default="16:00")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    classrooms: Mapped[list["Classroom"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )
    daily_digests: Mapped[list["DailyDigest"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Classroom
# ---------------------------------------------------------------------------
class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="hi")
    academic_year: Mapped[str] = mapped_column(String(10), default="2025-26")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    teacher: Mapped["Teacher"] = relationship(back_populates="classrooms")
    students: Mapped[list["Student"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------
class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    classroom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    roll_number: Mapped[str] = mapped_column(String(50), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    # Attention flag: set by digest worker when recent sessions show no improvement
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    attention_reason: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    classroom: Mapped["Classroom"] = relationship(back_populates="students")
    practice_sessions: Mapped[list["PracticeSession"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# PracticeSession  (one per sitting — baseline + optional retest)
# ---------------------------------------------------------------------------
class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    passage_id: Mapped[str] = mapped_column(String(255), nullable=True)
    total_words_read: Mapped[int] = mapped_column(Integer, default=0)
    avg_wcpm: Mapped[float] = mapped_column(Float, default=0.0)
    # Delta summary from the remediation cycle (JSON blob)
    delta_summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Whether this session included a full retest cycle
    completed_retest: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Student"] = relationship(back_populates="practice_sessions")
    reading_attempts: Mapped[list["ReadingAttempt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ReadingAttempt  (baseline or adaptive-generated retest)
# ---------------------------------------------------------------------------
class ReadingAttempt(Base):
    __tablename__ = "reading_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "BASELINE" | "ADAPTIVE_GENERATED"
    passage_type: Mapped[str] = mapped_column(String(30), default="BASELINE")
    passage_text: Mapped[str] = mapped_column(Text, nullable=True)
    transcribed_text: Mapped[str] = mapped_column(Text, nullable=True)
    wcpm: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["PracticeSession"] = relationship(back_populates="reading_attempts")
    error_logs: Mapped[list["ErrorLog"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ErrorLog  (one row per error word, per attempt)
# ---------------------------------------------------------------------------
class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reading_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    spoken_word: Mapped[str] = mapped_column(String(255), nullable=True)
    # MATRA | CONJUNCT | PHONETIC | OMISSION | REPETITION | SUBSTITUTION
    error_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_pattern: Mapped[str] = mapped_column(String(255), nullable=True)
    linguistic_detail: Mapped[str] = mapped_column(Text, nullable=True)
    pedagogical_remedy: Mapped[str] = mapped_column(Text, nullable=True)
    corrected_in_retest: Mapped[bool] = mapped_column(Boolean, default=False)
    in_stumble_cluster: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    attempt: Mapped["ReadingAttempt"] = relationship(back_populates="error_logs")


# ---------------------------------------------------------------------------
# DailyDigest  (one row per teacher per day, stores the rendered HTML + JSON)
# ---------------------------------------------------------------------------
class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    digest_date: Mapped[str] = mapped_column(String(10), nullable=False)  # "YYYY-MM-DD"
    # Structured payload (student cards, class trends)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Rendered HTML email body
    html_body: Mapped[str] = mapped_column(Text, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    teacher: Mapped["Teacher"] = relationship(back_populates="daily_digests")
