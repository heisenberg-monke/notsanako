"""
FastAPI Backend for Adaptive Reading Coach.
Complete Adaptive Remediation Cycle:
Baseline -> Diagnose -> Micro-Feedback -> Generate Personalized Story (Gemini 1.5) -> Retest -> Delta Evaluation.

Teacher Ecosystem:
PostgreSQL/SQLite-backed roster management, class dashboard analytics,
automated 4 PM IST daily digest, and Resend email delivery.
"""

import os
import sqlite3
import json
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from app.passages import get_all_passages, get_passage_by_id
from app.alignment import evaluate_reading_attempt_indic
from app.stt_service import (
    stt_service,
    STTNotConfiguredError,
    STTProviderError,
    STTTimeoutError,
    STTEmptyTranscriptionError,
)
# Back-compat alias: earlier code used STTConfigurationError
STTConfigurationError = STTNotConfiguredError
from app.remediation import (
    rank_and_select_target_words,
    generate_remediation_story_gemini,
    calculate_remediation_delta
)
from app.db import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routers.teacher import router as teacher_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB tables + start digest scheduler. Shutdown: stop scheduler."""
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Adaptive Reading Coach API",
    description="Closed-Loop Indic Oral Reading Fluency & Adaptive Remediation Cycle + Teacher Ecosystem",
    version="3.0.0",
    lifespan=lifespan,
)

# Teacher ecosystem routes
app.include_router(teacher_router)


# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "reading_coach.db")


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reading_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            passage_id TEXT,
            accuracy_pct REAL,
            wcpm REAL,
            wpm REAL,
            duration_sec REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS structured_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            expected_word TEXT,
            spoken_word TEXT,
            error_type TEXT,
            target_pattern TEXT,
            linguistic_detail TEXT,
            pedagogical_remedy TEXT,
            pause_before REAL,
            in_stumble_cluster BOOLEAN,
            FOREIGN KEY (session_id) REFERENCES reading_sessions (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS retest_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baseline_session_id INTEGER,
            student_id TEXT,
            target_words TEXT,
            baseline_accuracy REAL,
            retest_accuracy REAL,
            delta REAL,
            mastered_count INTEGER,
            retest_wcpm REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()


def save_session_and_errors(
    student_id: str,
    passage_id: str,
    metrics: Dict[str, Any],
    structured_errors: List[Dict[str, Any]]
) -> int:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reading_sessions (student_id, passage_id, accuracy_pct, wcpm, wpm, duration_sec)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        passage_id,
        metrics.get("accuracy_percentage", 0.0),
        metrics.get("wcpm", 0.0),
        metrics.get("wpm", 0.0),
        metrics.get("duration_seconds", 0.0)
    ))
    session_id = cursor.lastrowid

    for err in structured_errors:
        cursor.execute("""
            INSERT INTO structured_errors (
                session_id, expected_word, spoken_word, error_type,
                target_pattern, linguistic_detail, pedagogical_remedy,
                pause_before, in_stumble_cluster
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            err.get("word"),
            err.get("spoken_word"),
            err.get("error_type"),
            err.get("target_pattern"),
            err.get("linguistic_detail"),
            err.get("pedagogical_remedy"),
            err.get("pause_before", 0.0),
            1 if err.get("in_stumble_cluster") else 0
        ))

    # Commit and close the raw connection BEFORE opening any SQLAlchemy session.
    # SQLite only allows one writer at a time; leaving this connection open while
    # SQLAlchemy also writes causes "database is locked".
    conn.commit()
    conn.close()

    # Dual-write into SQLAlchemy ORM tables for the teacher ecosystem
    try:
        from app.db import SessionLocal
        from app import models
        with SessionLocal() as orm_db:
            # Check or create default student if student_id does not exist
            student = orm_db.query(models.Student).filter(models.Student.id == student_id).first()
            if not student:
                # Assign to default classroom
                first_class = orm_db.query(models.Classroom).first()
                if first_class:
                    student = models.Student(
                        id=student_id,
                        classroom_id=first_class.id,
                        display_name="Student " + student_id,
                        grade_level=first_class.grade_level
                    )
                    orm_db.add(student)
                    orm_db.commit()

            if student:
                orm_session = models.PracticeSession(
                    student_id=student.id,
                    passage_id=passage_id,
                    total_words_read=int(metrics.get("wpm", 0.0) * (metrics.get("duration_seconds", 0.0) / 60.0)),
                    avg_wcpm=metrics.get("wcpm", 0.0),
                    completed_retest=False,
                )
                orm_db.add(orm_session)
                orm_db.flush()

                attempt = models.ReadingAttempt(
                    session_id=orm_session.id,
                    passage_type="BASELINE",
                    wcpm=metrics.get("wcpm", 0.0),
                    accuracy_percentage=metrics.get("accuracy_percentage", 0.0),
                    duration_seconds=metrics.get("duration_seconds", 0.0),
                )
                orm_db.add(attempt)
                orm_db.flush()

                for err in structured_errors:
                    orm_db.add(models.ErrorLog(
                        attempt_id=attempt.id,
                        word=err.get("word", ""),
                        spoken_word=err.get("spoken_word", ""),
                        error_type=err.get("error_type", "SUBSTITUTION"),
                        target_pattern=err.get("target_pattern"),
                        linguistic_detail=err.get("linguistic_detail"),
                        pedagogical_remedy=err.get("pedagogical_remedy"),
                        in_stumble_cluster=bool(err.get("in_stumble_cluster")),
                        corrected_in_retest=False,
                    ))
                orm_db.commit()
    except Exception as exc:
        print(f"[ORM Sync Warning] Failed to dual-write baseline session: {exc}")

    return session_id


def save_retest_delta(
    baseline_session_id: Optional[int],
    student_id: str,
    target_words: List[str],
    delta_data: Dict[str, Any],
    retest_wcpm: float
) -> int:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO retest_sessions (
            baseline_session_id, student_id, target_words,
            baseline_accuracy, retest_accuracy, delta,
            mastered_count, retest_wcpm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        baseline_session_id or 0,
        student_id,
        json.dumps(target_words),
        delta_data.get("baseline_accuracy", 0.0),
        delta_data.get("retest_accuracy", 0.0),
        delta_data.get("delta", 0.0),
        delta_data.get("mastered_words_count", 0),
        retest_wcpm
    ))
    retest_id = cursor.lastrowid

    # Commit and close the raw connection BEFORE opening any SQLAlchemy session.
    # SQLite only allows one writer at a time; leaving this connection open while
    # SQLAlchemy also writes causes "database is locked".
    conn.commit()
    conn.close()

    # Dual-write into SQLAlchemy ORM tables
    try:
        from app.db import SessionLocal
        from app import models
        from sqlalchemy import desc
        with SessionLocal() as orm_db:
            # Find the most recent session for this student
            recent_session = (
                orm_db.query(models.PracticeSession)
                .filter(models.PracticeSession.student_id == student_id)
                .order_by(desc(models.PracticeSession.started_at))
                .first()
            )
            if recent_session:
                recent_session.completed_retest = True
                recent_session.delta_summary = delta_data
                retest_attempt = models.ReadingAttempt(
                    session_id=recent_session.id,
                    passage_type="ADAPTIVE_GENERATED",
                    wcpm=retest_wcpm,
                    accuracy_percentage=delta_data.get("retest_accuracy", 0.0),
                )
                orm_db.add(retest_attempt)
                orm_db.commit()
    except Exception as exc:
        print(f"[ORM Sync Warning] Failed to dual-write retest session: {exc}")

    return retest_id


class RemediationGenerateRequest(BaseModel):
    grade_level: int = 4
    language: str = "hi"
    student_name: str = "Aarav"
    theme: str = "space"
    structured_errors: Optional[List[Dict[str, Any]]] = None
    override_target_words: Optional[List[str]] = None


@app.get("/")
def root():
    return {
        "message": "Adaptive Reading Coach Closed-Loop Remediation API Active",
        "version": "2.5.0",
        "docs": "/docs"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "resend_configured": bool(os.getenv("RESEND_API_KEY")),
        "stt_provider": os.getenv("STT_PROVIDER", "auto"),
        "database_url": os.getenv("DATABASE_URL", "sqlite (default)").split("@")[-1] if "@" in os.getenv("DATABASE_URL", "") else "sqlite (default)",
        "teacher_ecosystem": "enabled",
        "digest_scheduler": "running",
    }


@app.get("/api/passages")
def list_passages(
    grade: Optional[int] = Query(None, description="Filter by grade level (3, 4, 5)"),
    language: Optional[str] = Query(None, description="Filter by language ('en' or 'hi')")
):
    passages = get_all_passages(grade=grade, language=language)
    return {"passages": passages}


@app.get("/api/passages/{passage_id}")
def get_passage(passage_id: str):
    passage = get_passage_by_id(passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")
    return passage


@app.post("/api/analyze-reading")
async def analyze_reading(
    passage_id: str = Form(...),
    duration_seconds: float = Form(...),
    student_id: Optional[str] = Form("student-1"),
    client_transcript: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None)
):
    """
    Step 1 & 2 of the loop: Baseline Reading & Diagnosis
    """
    passage = get_passage_by_id(passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail="Passage not found")

    reference_text = passage["text"]
    language = passage.get("language", "hi" if "hi" in passage_id else "en")

    transcribed_text = ""
    transcribed_words: List[Dict[str, Any]] = []

    if audio is None:
        raise HTTPException(
            status_code=400,
            detail="NO_AUDIO_RECEIVED: No audio file was uploaded from the client."
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="EMPTY_AUDIO_FILE: Uploaded audio file contains zero or insufficient bytes."
        )

    filename = audio.filename or "recording.wav"
    try:
        stt_result = await stt_service.transcribe_audio_with_timestamps(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language,
            estimated_duration=duration_seconds
        )
        transcribed_text = stt_result.get("text", "")
        transcribed_words = stt_result.get("words", [])
    except STTNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except STTProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except STTTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except STTEmptyTranscriptionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not transcribed_text:
        raise HTTPException(
            status_code=422,
            detail="NO_TRANSCRIPTION_PRODUCED: Speech recognition finished without transcribing any words. Please verify that your microphone volume is active and speak clearly."
        )

    evaluation = evaluate_reading_attempt_indic(
        reference_text=reference_text,
        transcribed_words=transcribed_words,
        duration_seconds=duration_seconds,
        target_wcpm=passage.get("target_wcpm", 75)
    )

    session_id = save_session_and_errors(
        student_id=student_id or "student-1",
        passage_id=passage_id,
        metrics=evaluation["metrics"],
        structured_errors=evaluation["structured_errors"]
    )

    # Rank and pre-select top 3-5 priority target words
    ranked_targets = rank_and_select_target_words(
        evaluation["structured_errors"],
        max_targets=5
    )

    return {
        "session_id": session_id,
        "passage_id": passage_id,
        "passage_title": passage["title"],
        "language": language,
        "reference_text": reference_text,
        "transcribed_text": transcribed_text,
        "alignments": evaluation["alignments"],
        "metrics": evaluation["metrics"],
        "error_breakdown": evaluation["error_breakdown"],
        "structured_errors": evaluation["structured_errors"],
        "priority_target_words": ranked_targets,
        "stumble_clusters": evaluation["stumble_clusters"],
        "long_pauses": evaluation["long_pauses"],
        "feedback": evaluation["feedback"]
    }


@app.post("/api/rank-and-generate-remediation")
async def rank_and_generate_remediation(request: RemediationGenerateRequest):
    """
    Step 4: Generates a 60-80 word personalized mini-story based on
    ranked errors and student interest/theme.
    """
    # 1. Determine target words
    if request.override_target_words and len(request.override_target_words) > 0:
        target_words = request.override_target_words[:5]
    elif request.structured_errors:
        ranked_objs = rank_and_select_target_words(request.structured_errors, max_targets=5)
        target_words = [item["word"] for item in ranked_objs]
    else:
        target_words = ["प्रतियोगिता", "परिश्रमी", "बुद्धिमान"] if request.language == "hi" else ["curiosity", "balanced", "sparked"]

    # 2. Call Gemini 1.5 (with strict JSON structure and deterministic fallback)
    story_result = await generate_remediation_story_gemini(
        target_words=target_words,
        grade_level=request.grade_level,
        language=request.language,
        student_name=request.student_name,
        theme=request.theme
    )

    return {
        "target_words": target_words,
        "grade_level": request.grade_level,
        "language": request.language,
        "theme": request.theme,
        "remediation_passage": story_result
    }


@app.post("/api/evaluate-retest")
async def evaluate_retest(
    remediation_passage_text: str = Form(...),
    target_words_json: str = Form(...),
    duration_seconds: float = Form(...),
    baseline_session_id: Optional[int] = Form(None),
    student_id: Optional[str] = Form("student-1"),
    language: Optional[str] = Form("hi"),
    baseline_alignments_json: Optional[str] = Form("[]"),
    client_transcript: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None)
):
    """
    Step 5 & 6: Evaluates the retest reading on the generated story,
    calculates Delta = post-test target-word accuracy - baseline target-word accuracy,
    and returns immediate encouraging feedback on mastered words.
    """
    try:
        target_words = json.loads(target_words_json)
    except Exception:
        target_words = []

    try:
        baseline_alignments = json.loads(baseline_alignments_json or "[]")
    except Exception:
        baseline_alignments = []

    transcribed_text = ""
    transcribed_words: List[Dict[str, Any]] = []

    if audio is None:
        raise HTTPException(
            status_code=400,
            detail="NO_AUDIO_RECEIVED: No audio file was uploaded for the retest attempt."
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="EMPTY_AUDIO_FILE: Uploaded retest audio file contains zero or insufficient bytes."
        )

    filename = audio.filename or "retest_recording.wav"
    try:
        stt_result = await stt_service.transcribe_audio_with_timestamps(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language or "hi",
            estimated_duration=duration_seconds
        )
        transcribed_text = stt_result.get("text", "")
        transcribed_words = stt_result.get("words", [])
    except STTNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except STTProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except STTTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except STTEmptyTranscriptionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not transcribed_text:
        raise HTTPException(
            status_code=422,
            detail="NO_TRANSCRIPTION_PRODUCED: Retest speech recognition returned no transcribed words."
        )

    # 1. Align retest reading against remediation passage text
    retest_evaluation = evaluate_reading_attempt_indic(
        reference_text=remediation_passage_text,
        transcribed_words=transcribed_words,
        duration_seconds=duration_seconds,
        target_wcpm=75
    )

    # 2. Calculate Before vs. After Target Word Mastery Delta
    delta_summary = calculate_remediation_delta(
        target_words=target_words,
        baseline_alignments=baseline_alignments,
        retest_alignments=retest_evaluation["alignments"]
    )

    # 3. Persist retest delta in SQLite
    retest_id = save_retest_delta(
        baseline_session_id=baseline_session_id,
        student_id=student_id or "student-1",
        target_words=target_words,
        delta_data=delta_summary,
        retest_wcpm=retest_evaluation["metrics"].get("wcpm", 0.0)
    )

    return {
        "retest_id": retest_id,
        "transcribed_text": transcribed_text,
        "retest_alignments": retest_evaluation["alignments"],
        "retest_metrics": retest_evaluation["metrics"],
        "delta_summary": delta_summary,
        "positive_reinforcement": delta_summary["positive_reinforcement"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
