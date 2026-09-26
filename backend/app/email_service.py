"""
Email delivery via Resend HTTP API.
Uses a plain httpx.Client (synchronous) since this runs from the scheduler,
not from within a FastAPI request handler.
"""

import os
import httpx
from typing import Optional


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
# Use onboarding@resend.dev as default so unverified custom domains don't fail in development/testing
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")


class EmailDeliveryError(Exception):
    pass


def send_digest_email(
    to_email: str,
    teacher_name: str,
    digest_date: str,
    html_body: str,
) -> bool:
    """
    Send the daily digest HTML email via Resend.
    Returns True on success, False if RESEND_API_KEY is not configured.
    Raises EmailDeliveryError on API failure.
    """
    if not RESEND_API_KEY:
        print(
            f"[Email] RESEND_API_KEY not configured — skipping email to {to_email}. "
            "Set RESEND_API_KEY in backend/.env to enable digest delivery."
        )
        return False

    subject = f"📚 Reading Coach Digest — {digest_date}"

    payload = {
        "from": RESEND_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }

    print(f"[Email] Sending digest to {to_email} via Resend...")

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"[Email] Delivered. Resend ID: {data.get('id')}")
            return True
        else:
            error_msg = f"Resend HTTP {resp.status_code}: {resp.text}"
            print(f"[Email] Delivery failed — {error_msg}")
            raise EmailDeliveryError(error_msg)

    except httpx.RequestError as err:
        msg = f"Network error sending digest email: {err}"
        print(f"[Email] {msg}")
        raise EmailDeliveryError(msg) from err
