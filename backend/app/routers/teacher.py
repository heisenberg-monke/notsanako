"""
Teacher management API router.

Endpoints:
  POST   /api/teacher/register
  GET    /api/teacher/{teacher_id}
  PUT    /api/teacher/{teacher_id}

  GET    /api/teacher/{teacher_id}/classrooms
  POST   /api/teacher/{teacher_id}/classrooms
  PUT    /api/teacher/{teacher_id}/classrooms/{classroom_id}
  DELETE /api/teacher/{teacher_id}/classrooms/{classroom_id}

  GET    /api/teacher/{teacher_id}/classrooms/{classroom_id}/students
  POST   /api/teacher/{teacher_id}/classrooms/{classroom_id}/students
  PUT    /api/teacher/{teacher_id}/classrooms/{classroom_id}/students/{student_id}
  DELETE /api/teacher/{teacher_id}/classrooms/{classroom_id}/students/{student_id}

  GET    /api/teacher/{teacher_id}/classrooms/{classroom_id}/dashboard
  GET    /api/teacher/{teacher_id}/students/{student_id}/sessions
  GET    /api/teacher/{teacher_id}/sessions/{session_id}

  POST   /api/sessions/record   (called by student app at end of each session)

  GET    /api/teacher/{teacher_id}/digest/latest
  POST   /api/teacher/{teacher_id}/digest/trigger
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app import crud, schemas, models
from app.scheduler import trigger_digest_now

router = APIRouter(prefix="/api", tags=["teacher"])


# ── Auth guard ──────────────────────────────────────────────────────────────
def _get_teacher_or_404(teacher_id: str, db: Session) -> models.Teacher:
    teacher = crud.get_teacher(db, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher


def _get_classroom_or_404(classroom_id: str, teacher_id: str, db: Session) -> models.Classroom:
    classroom = crud.get_classroom(db, classroom_id)
    if not classroom or classroom.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Classroom not found")
    return classroom


# ── Teacher registration / profile ─────────────────────────────────────────

@router.post("/teacher/register", response_model=schemas.TeacherOut, status_code=201)
def register_teacher(data: schemas.TeacherCreate, db: Session = Depends(get_db)):
    existing = crud.get_teacher_by_email(db, data.email)
    if existing:
        # Idempotent: return existing teacher
        return existing
    return crud.create_teacher(db, data)


@router.get("/teacher/{teacher_id}", response_model=schemas.TeacherOut)
def get_teacher(teacher_id: str, db: Session = Depends(get_db)):
    return _get_teacher_or_404(teacher_id, db)


@router.put("/teacher/{teacher_id}", response_model=schemas.TeacherOut)
def update_teacher(
    teacher_id: str, data: schemas.TeacherUpdate, db: Session = Depends(get_db)
):
    teacher = _get_teacher_or_404(teacher_id, db)
    return crud.update_teacher(db, teacher, data)


# ── Classrooms ───────────────────────────────────────────────────────────────

@router.get("/teacher/{teacher_id}/classrooms", response_model=List[schemas.ClassroomOut])
def list_classrooms(teacher_id: str, db: Session = Depends(get_db)):
    _get_teacher_or_404(teacher_id, db)
    classrooms = crud.get_classrooms(db, teacher_id)
    result = []
    for cls in classrooms:
        out = schemas.ClassroomOut.model_validate(cls)
        out.student_count = crud.count_students(db, cls.id)
        result.append(out)
    return result


@router.post(
    "/teacher/{teacher_id}/classrooms",
    response_model=schemas.ClassroomOut,
    status_code=201,
)
def create_classroom(
    teacher_id: str, data: schemas.ClassroomCreate, db: Session = Depends(get_db)
):
    _get_teacher_or_404(teacher_id, db)
    cls = crud.create_classroom(db, teacher_id, data)
    out = schemas.ClassroomOut.model_validate(cls)
    out.student_count = 0
    return out


@router.put(
    "/teacher/{teacher_id}/classrooms/{classroom_id}",
    response_model=schemas.ClassroomOut,
)
def update_classroom(
    teacher_id: str,
    classroom_id: str,
    data: schemas.ClassroomUpdate,
    db: Session = Depends(get_db),
):
    cls = _get_classroom_or_404(classroom_id, teacher_id, db)
    cls = crud.update_classroom(db, cls, data)
    out = schemas.ClassroomOut.model_validate(cls)
    out.student_count = crud.count_students(db, cls.id)
    return out


@router.delete("/teacher/{teacher_id}/classrooms/{classroom_id}", status_code=204)
def delete_classroom(
    teacher_id: str, classroom_id: str, db: Session = Depends(get_db)
):
    cls = _get_classroom_or_404(classroom_id, teacher_id, db)
    crud.delete_classroom(db, cls)


# ── Students ─────────────────────────────────────────────────────────────────

@router.get(
    "/teacher/{teacher_id}/classrooms/{classroom_id}/students",
    response_model=List[schemas.StudentWithStats],
)
def list_students(
    teacher_id: str, classroom_id: str, db: Session = Depends(get_db)
):
    _get_classroom_or_404(classroom_id, teacher_id, db)
    students = crud.get_students(db, classroom_id)
    result = []
    for s in students:
        out = schemas.StudentWithStats.model_validate(s)
        metrics = crud.get_student_latest_metrics(db, s.id)
        out.last_session_date = metrics["last_session_date"]
        out.latest_wcpm = metrics["latest_wcpm"]
        out.latest_accuracy = metrics["latest_accuracy"]
        out.session_count = metrics["session_count"]
        out.best_delta = metrics["best_delta"]
        out.top_error_types = metrics["top_error_types"]
        result.append(out)
    return result


@router.post(
    "/teacher/{teacher_id}/classrooms/{classroom_id}/students",
    response_model=schemas.StudentOut,
    status_code=201,
)
def add_student(
    teacher_id: str,
    classroom_id: str,
    data: schemas.StudentCreate,
    db: Session = Depends(get_db),
):
    _get_classroom_or_404(classroom_id, teacher_id, db)
    return crud.create_student(db, classroom_id, data)


@router.put(
    "/teacher/{teacher_id}/classrooms/{classroom_id}/students/{student_id}",
    response_model=schemas.StudentOut,
)
def update_student(
    teacher_id: str,
    classroom_id: str,
    student_id: str,
    data: schemas.StudentUpdate,
    db: Session = Depends(get_db),
):
    _get_classroom_or_404(classroom_id, teacher_id, db)
    student = crud.get_student(db, student_id)
    if not student or student.classroom_id != classroom_id:
        raise HTTPException(status_code=404, detail="Student not found")
    return crud.update_student(db, student, data)


@router.delete(
    "/teacher/{teacher_id}/classrooms/{classroom_id}/students/{student_id}",
    status_code=204,
)
def delete_student(
    teacher_id: str,
    classroom_id: str,
    student_id: str,
    db: Session = Depends(get_db),
):
    _get_classroom_or_404(classroom_id, teacher_id, db)
    student = crud.get_student(db, student_id)
    if not student or student.classroom_id != classroom_id:
        raise HTTPException(status_code=404, detail="Student not found")
    crud.delete_student(db, student)


# ── Dashboard analytics ──────────────────────────────────────────────────────

@router.get(
    "/teacher/{teacher_id}/classrooms/{classroom_id}/dashboard",
    response_model=schemas.ClassDashboard,
)
def classroom_dashboard(
    teacher_id: str, classroom_id: str, db: Session = Depends(get_db)
):
    cls = _get_classroom_or_404(classroom_id, teacher_id, db)
    crud.flag_students_needing_attention(db, classroom_id)

    students = crud.get_students(db, classroom_id)
    active_ids = crud.get_active_student_ids_today(db, classroom_id)
    error_patterns = crud.get_class_error_patterns(db, classroom_id, days=7)

    attention_cards = []
    wcpm_list, acc_list = [], []

    for s in students:
        m = crud.get_student_latest_metrics(db, s.id)
        if m["latest_wcpm"]:
            wcpm_list.append(m["latest_wcpm"])
        if m["latest_accuracy"]:
            acc_list.append(m["latest_accuracy"])
        if s.needs_attention:
            attention_cards.append(
                schemas.StudentAttentionCard(
                    student_id=s.id,
                    display_name=s.display_name,
                    reason=s.attention_reason or "",
                    latest_wcpm=m["latest_wcpm"],
                    latest_accuracy=m["latest_accuracy"],
                    top_errors=m["top_error_types"],
                    sessions_without_improvement=m["session_count"],
                )
            )

    patterns = [
        schemas.ErrorPatternSummary(
            error_type=ep["error_type"],
            count=ep["count"],
            percentage=ep["percentage"],
            example_words=crud.get_top_error_words(db, classroom_id, ep["error_type"], limit=4),
        )
        for ep in error_patterns
    ]

    top_errors = [p.error_type for p in patterns[:3]]
    from app.digest import _suggest_interventions
    interventions = _suggest_interventions(top_errors)

    return schemas.ClassDashboard(
        classroom_id=cls.id,
        classroom_name=cls.name,
        grade_level=cls.grade_level,
        total_students=len(students),
        active_today=len(active_ids),
        needs_attention_count=len(attention_cards),
        avg_wcpm=round(sum(wcpm_list) / len(wcpm_list), 1) if wcpm_list else 0.0,
        avg_accuracy=round(sum(acc_list) / len(acc_list), 1) if acc_list else 0.0,
        error_patterns=patterns,
        attention_students=attention_cards,
        suggested_interventions=interventions,
    )


# ── Session detail & history ─────────────────────────────────────────────────

@router.get(
    "/teacher/{teacher_id}/students/{student_id}/sessions",
    response_model=List[schemas.PracticeSessionOut],
)
def student_session_history(
    teacher_id: str, student_id: str, db: Session = Depends(get_db)
):
    _get_teacher_or_404(teacher_id, db)
    return crud.get_student_sessions(db, student_id)


@router.get("/teacher/{teacher_id}/sessions/{session_id}")
def session_detail(
    teacher_id: str, session_id: str, db: Session = Depends(get_db)
):
    _get_teacher_or_404(teacher_id, db)
    session = crud.get_session_detail(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    attempts = []
    for attempt in session.reading_attempts:
        attempts.append({
            "id": attempt.id,
            "passage_type": attempt.passage_type,
            "wcpm": attempt.wcpm,
            "accuracy_percentage": attempt.accuracy_percentage,
            "duration_seconds": attempt.duration_seconds,
            "errors": [
                {
                    "word": e.word,
                    "spoken_word": e.spoken_word,
                    "error_type": e.error_type,
                    "target_pattern": e.target_pattern,
                    "linguistic_detail": e.linguistic_detail,
                    "corrected_in_retest": e.corrected_in_retest,
                }
                for e in attempt.error_logs
            ],
        })

    return {
        "id": session.id,
        "student_id": session.student_id,
        "passage_id": session.passage_id,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "avg_wcpm": session.avg_wcpm,
        "total_words_read": session.total_words_read,
        "delta_summary": session.delta_summary,
        "completed_retest": session.completed_retest,
        "reading_attempts": attempts,
    }


# ── Session ingestion (called by student app) ────────────────────────────────

@router.post("/sessions/record", response_model=schemas.PracticeSessionOut, status_code=201)
def record_session(
    record: schemas.PracticeSessionRecord, db: Session = Depends(get_db)
):
    """
    Called by the student app at the end of each practice session.
    Persists the full session including both reading attempts and error logs.
    """
    student = crud.get_student(db, record.student_id)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {record.student_id} not found")
    return crud.record_session(db, record)


# ── Digest ───────────────────────────────────────────────────────────────────

@router.get("/teacher/{teacher_id}/digest/latest", response_model=schemas.DigestOut)
def get_latest_digest(teacher_id: str, db: Session = Depends(get_db)):
    _get_teacher_or_404(teacher_id, db)
    digest = crud.get_latest_digest(db, teacher_id)
    if not digest:
        raise HTTPException(status_code=404, detail="No digest generated yet")
    return digest


@router.post("/teacher/{teacher_id}/digest/trigger")
def trigger_digest(teacher_id: str, db: Session = Depends(get_db)):
    """Manually trigger a digest for the teacher (for testing or on-demand)."""
    _get_teacher_or_404(teacher_id, db)
    result = trigger_digest_now(teacher_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
