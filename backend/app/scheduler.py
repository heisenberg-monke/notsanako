"""
APScheduler-based background digest worker.

Schedule: every day at 16:00 IST (10:30 UTC).
The job iterates every teacher whose digest_time matches the current
hour:minute (IST), builds the payload, renders the HTML, persists to
daily_digests, and sends the email via Resend.

Designed to run as a FastAPI lifespan task — started on app startup,
stopped on shutdown.
"""

import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import SessionLocal
from app import crud, models
from app.digest import build_digest_payload, render_digest_html
from app.email_service import send_digest_email, EmailDeliveryError

IST = ZoneInfo("Asia/Kolkata")

_scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
_scheduler_started = False


def _run_digests_for_time(hour: int, minute: int) -> None:
    """
    Called by the scheduler every minute.
    Finds teachers whose digest_time == HH:MM and generates their digest.
    """
    time_str = f"{hour:02d}:{minute:02d}"
    print(f"[Digest Worker] Checking for digests at IST {time_str}")

    db = SessionLocal()
    try:
        teachers = (
            db.query(models.Teacher)
            .filter(
                models.Teacher.digest_time == time_str,
                models.Teacher.email_verified == True,
            )
            .all()
        )
        if not teachers:
            return

        digest_date = datetime.now(IST).strftime("%Y-%m-%d")
        print(f"[Digest Worker] Generating digests for {len(teachers)} teacher(s) on {digest_date}")

        for teacher in teachers:
            try:
                payload = build_digest_payload(db, teacher, digest_date)
                html_body = render_digest_html(payload)

                from app.crud import save_daily_digest, mark_digest_sent
                digest = save_daily_digest(db, teacher.id, digest_date, payload, html_body)

                try:
                    sent = send_digest_email(
                        to_email=teacher.email,
                        teacher_name=teacher.name,
                        digest_date=digest_date,
                        html_body=html_body,
                    )
                    if sent:
                        mark_digest_sent(db, digest)
                except EmailDeliveryError as e:
                    print(f"[Digest Worker] Email failed for {teacher.email}: {e}")

            except Exception as exc:
                print(f"[Digest Worker] ERROR for teacher {teacher.id} ({teacher.email}): {exc}")

    finally:
        db.close()


def _job() -> None:
    """Entry point called by APScheduler every minute."""
    now_ist = datetime.now(IST)
    _run_digests_for_time(now_ist.hour, now_ist.minute)


def start_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return

    # Run the digest check every minute so per-teacher digest_time is honoured
    _scheduler.add_job(
        _job,
        trigger=CronTrigger(minute="*/5"),  # every 5 minutes — enough granularity for per-teacher digest times
        id="digest_minutely",
        replace_existing=True,
    )
    _scheduler.start()
    _scheduler_started = True
    print("[Digest Scheduler] Started — checking teacher digest times every 5 minutes (IST).")


def stop_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler_started = False
        print("[Digest Scheduler] Stopped.")


def trigger_digest_now(teacher_id: str) -> dict:
    """
    Manually trigger a digest for a specific teacher (used by the API).
    Returns the payload.
    """
    db = SessionLocal()
    try:
        teacher = crud.get_teacher(db, teacher_id)
        if not teacher:
            return {"error": "Teacher not found"}

        digest_date = datetime.now(IST).strftime("%Y-%m-%d")
        payload = build_digest_payload(db, teacher, digest_date)
        html_body = render_digest_html(payload)

        digest = crud.save_daily_digest(db, teacher.id, digest_date, payload, html_body)

        try:
            sent = send_digest_email(
                to_email=teacher.email,
                teacher_name=teacher.name,
                digest_date=digest_date,
                html_body=html_body,
            )
            if sent:
                crud.mark_digest_sent(db, digest)
        except EmailDeliveryError as e:
            print(f"[Digest] Manual trigger email failed: {e}")

        return {"status": "ok", "digest_date": digest_date, "email_sent": digest.email_sent}
    finally:
        db.close()
