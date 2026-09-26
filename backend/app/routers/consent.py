"""
DPDP Act 2023 consent management + anonymised pilot telemetry endpoints.
"""
import hashlib
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import SessionLocal
from app import models

router = APIRouter(prefix="/api", tags=["consent & telemetry"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ─────────────────────────────────────────────────────────────────

class ConsentGrantRequest(BaseModel):
    student_id: str
    given_by: str
    given_by_relation: str = "parent"
    consent_version: str = "1.0"


class TelemetryEventRequest(BaseModel):
    event_type: str
    student_id: Optional[str] = None   # hashed before storage
    classroom_id: Optional[str] = None
    wcpm: Optional[float] = None
    accuracy_pct: Optional[float] = None
    delta_accuracy: Optional[float] = None
    error_type_counts: Optional[dict] = None
    session_duration_s: Optional[float] = None
    stt_provider: Optional[str] = None
    language: Optional[str] = None
    grade_level: Optional[int] = None


# ── Consent endpoints ────────────────────────────────────────────────────────

@router.post("/consent/grant")
def grant_consent(
    req: ConsentGrantRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Record explicit parental/guardian consent for a student.
    DPDP Act 2023 compliant: records who gave consent, when, and for what purpose.
    """
    existing = (
        db.query(models.ConsentRecord)
        .filter(
            models.ConsentRecord.student_id == req.student_id,
            models.ConsentRecord.revoked_at == None,  # noqa: E711
        )
        .first()
    )
    if existing:
        return {
            "status": "already_active",
            "student_id": req.student_id,
            "since": existing.created_at.isoformat(),
        }

    ip = request.client.host if request.client else None
    record = models.ConsentRecord(
        student_id=req.student_id,
        given_by=req.given_by,
        given_by_relation=req.given_by_relation,
        consent_version=req.consent_version,
        ip_address=ip,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "status": "granted",
        "student_id": req.student_id,
        "consent_id": record.id,
        "purpose": record.purpose,
        "granted_at": record.created_at.isoformat(),
    }


@router.post("/consent/revoke/{student_id}")
def revoke_consent(student_id: str, db: Session = Depends(get_db)):
    """Revoke consent for a student (Right to Erasure — DPDP Act 2023)."""
    records = (
        db.query(models.ConsentRecord)
        .filter(
            models.ConsentRecord.student_id == student_id,
            models.ConsentRecord.revoked_at == None,  # noqa: E711
        )
        .all()
    )
    if not records:
        raise HTTPException(
            status_code=404,
            detail="No active consent found for this student.",
        )
    now = datetime.utcnow()
    for r in records:
        r.revoked_at = now
    db.commit()
    return {"status": "revoked", "student_id": student_id, "count": len(records)}


@router.get("/consent/status/{student_id}")
def consent_status(student_id: str, db: Session = Depends(get_db)):
    """Check whether active consent exists for a student."""
    record = (
        db.query(models.ConsentRecord)
        .filter(
            models.ConsentRecord.student_id == student_id,
            models.ConsentRecord.revoked_at == None,  # noqa: E711
        )
        .first()
    )
    return {
        "student_id": student_id,
        "consent_active": record is not None,
        "granted_at": record.created_at.isoformat() if record else None,
        "given_by_relation": record.given_by_relation if record else None,
    }


# ── Telemetry endpoints ──────────────────────────────────────────────────────

@router.post("/telemetry")
def record_telemetry(req: TelemetryEventRequest, db: Session = Depends(get_db)):
    """
    Record anonymised pilot telemetry.
    student_id is one-way hashed with SHA-256 — never stored raw.
    """
    student_hash = None
    if req.student_id:
        salt = os.getenv("TELEMETRY_SALT", "reading-coach-pilot-2026")
        student_hash = hashlib.sha256(
            f"{salt}:{req.student_id}".encode()
        ).hexdigest()[:16]

    event = models.TelemetryEvent(
        event_type=req.event_type,
        student_hash=student_hash,
        classroom_id=req.classroom_id,
        wcpm=req.wcpm,
        accuracy_pct=req.accuracy_pct,
        delta_accuracy=req.delta_accuracy,
        error_type_counts=req.error_type_counts,
        session_duration_s=req.session_duration_s,
        stt_provider=req.stt_provider,
        language=req.language,
        grade_level=req.grade_level,
    )
    db.add(event)
    db.commit()
    return {"status": "recorded", "event_id": event.id}


@router.get("/telemetry/summary")
def telemetry_summary(
    classroom_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Aggregate pilot telemetry — no PII returned."""
    q = db.query(models.TelemetryEvent)
    if classroom_id:
        q = q.filter(models.TelemetryEvent.classroom_id == classroom_id)
    events = q.all()

    if not events:
        return {"total_events": 0, "classroom_id": classroom_id}

    session_events = [e for e in events if e.event_type == "session_complete"]
    retest_events = [e for e in events if e.event_type == "retest_complete"]

    def _avg(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    error_totals: dict = {}
    for e in events:
        if e.error_type_counts:
            for k, v in e.error_type_counts.items():
                error_totals[k] = error_totals.get(k, 0) + v

    return {
        "total_events": len(events),
        "session_count": len(session_events),
        "retest_count": len(retest_events),
        "avg_wcpm": _avg([e.wcpm for e in session_events]),
        "avg_accuracy_pct": _avg([e.accuracy_pct for e in session_events]),
        "avg_delta_accuracy": _avg([e.delta_accuracy for e in retest_events]),
        "error_type_totals": error_totals,
        "classroom_id": classroom_id,
    }


# ── Right to Erasure (DPDP Act 2023) ────────────────────────────────────────

@router.delete("/students/{student_id}/data")
def erase_student_data(student_id: str, db: Session = Depends(get_db)):
    """
    Delete all stored records for a student (Right to Erasure).
    Anonymised telemetry rows are NOT deleted — no PII linkage is possible.
    """
    deleted: dict = {}

    consents = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.student_id == student_id)
        .all()
    )
    for c in consents:
        db.delete(c)
    deleted["consent_records"] = len(consents)

    sessions = (
        db.query(models.PracticeSession)
        .filter(models.PracticeSession.student_id == student_id)
        .all()
    )
    for s in sessions:
        db.delete(s)
    deleted["practice_sessions"] = len(sessions)

    db.commit()
    return {"status": "erased", "student_id": student_id, "deleted": deleted}
