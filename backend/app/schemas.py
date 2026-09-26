"""
Pydantic v2 schemas for request/response serialization.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------
class TeacherCreate(BaseModel):
    email: EmailStr
    name: str
    school_name: Optional[str] = None
    digest_time: str = "16:00"  # HH:MM


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    school_name: Optional[str] = None
    digest_time: Optional[str] = None


class TeacherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    school_name: Optional[str]
    email_verified: bool
    digest_time: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Classroom
# ---------------------------------------------------------------------------
class ClassroomCreate(BaseModel):
    name: str
    grade_level: int = Field(ge=1, le=12)
    language: str = "hi"
    academic_year: str = "2025-26"


class ClassroomUpdate(BaseModel):
    name: Optional[str] = None
    grade_level: Optional[int] = None
    language: Optional[str] = None


class ClassroomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    teacher_id: str
    name: str
    grade_level: int
    language: str
    academic_year: str
    student_count: int = 0
    created_at: datetime


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------
class StudentCreate(BaseModel):
    display_name: str
    roll_number: Optional[str] = None
    grade_level: int = Field(ge=1, le=12)


class StudentUpdate(BaseModel):
    display_name: Optional[str] = None
    roll_number: Optional[str] = None
    needs_attention: Optional[bool] = None
    attention_reason: Optional[str] = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    classroom_id: str
    display_name: str
    roll_number: Optional[str]
    grade_level: int
    needs_attention: bool
    attention_reason: Optional[str]
    created_at: datetime


class StudentWithStats(StudentOut):
    """Extended student card with latest session metrics."""
    last_session_date: Optional[str] = None
    latest_wcpm: Optional[float] = None
    latest_accuracy: Optional[float] = None
    session_count: int = 0
    best_delta: Optional[float] = None
    top_error_types: List[str] = []


# ---------------------------------------------------------------------------
# PracticeSession
# ---------------------------------------------------------------------------
class PracticeSessionCreate(BaseModel):
    student_id: str
    passage_id: Optional[str] = None


class PracticeSessionRecord(BaseModel):
    """Posted by the student app after a completed session."""
    student_id: str
    passage_id: Optional[str] = None
    total_words_read: int = 0
    avg_wcpm: float = 0.0
    delta_summary: Optional[dict] = None
    completed_retest: bool = False
    # Nested attempts and errors submitted together
    baseline: Optional["ReadingAttemptRecord"] = None
    retest: Optional["ReadingAttemptRecord"] = None


class PracticeSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    student_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    passage_id: Optional[str]
    total_words_read: int
    avg_wcpm: float
    delta_summary: Optional[dict]
    completed_retest: bool


# ---------------------------------------------------------------------------
# ReadingAttempt
# ---------------------------------------------------------------------------
class ReadingAttemptRecord(BaseModel):
    passage_type: str = "BASELINE"
    passage_text: Optional[str] = None
    transcribed_text: Optional[str] = None
    wcpm: float = 0.0
    accuracy_percentage: float = 0.0
    duration_seconds: float = 0.0
    errors: List["ErrorRecord"] = []


class ReadingAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    passage_type: str
    wcpm: float
    accuracy_percentage: float
    duration_seconds: float
    created_at: datetime


# ---------------------------------------------------------------------------
# ErrorLog
# ---------------------------------------------------------------------------
class ErrorRecord(BaseModel):
    word: str
    spoken_word: Optional[str] = None
    error_type: str
    target_pattern: Optional[str] = None
    linguistic_detail: Optional[str] = None
    pedagogical_remedy: Optional[str] = None
    corrected_in_retest: bool = False
    in_stumble_cluster: bool = False


class ErrorLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    attempt_id: str
    word: str
    spoken_word: Optional[str]
    error_type: str
    target_pattern: Optional[str]
    linguistic_detail: Optional[str]
    pedagogical_remedy: Optional[str]
    corrected_in_retest: bool
    in_stumble_cluster: bool


# ---------------------------------------------------------------------------
# Dashboard Analytics
# ---------------------------------------------------------------------------
class ErrorPatternSummary(BaseModel):
    error_type: str
    count: int
    percentage: float
    example_words: List[str] = []


class StudentAttentionCard(BaseModel):
    student_id: str
    display_name: str
    reason: str
    latest_wcpm: Optional[float] = None
    latest_accuracy: Optional[float] = None
    top_errors: List[str] = []
    sessions_without_improvement: int = 0


class ClassDashboard(BaseModel):
    classroom_id: str
    classroom_name: str
    grade_level: int
    total_students: int
    active_today: int
    needs_attention_count: int
    avg_wcpm: float
    avg_accuracy: float
    error_patterns: List[ErrorPatternSummary] = []
    attention_students: List[StudentAttentionCard] = []
    suggested_interventions: List[str] = []


# ---------------------------------------------------------------------------
# DailyDigest
# ---------------------------------------------------------------------------
class DigestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    teacher_id: str
    digest_date: str
    payload: Optional[dict]
    email_sent: bool
    sent_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# Auth (simple token-based teacher login — no OAuth for MVP)
# ---------------------------------------------------------------------------
class TeacherLoginRequest(BaseModel):
    email: EmailStr


class TeacherLoginResponse(BaseModel):
    teacher: TeacherOut
    token: str  # Simple UUID-based session token for MVP


# Rebuild models that reference forward refs
PracticeSessionRecord.model_rebuild()
ReadingAttemptRecord.model_rebuild()
