"""
Email delivery via Resend HTTP API.
Uses a plain httpx.Client (synchronous) since this runs from the scheduler,
not from within a FastAPI request handler.
"""

import os
import httpx


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

    NOTE: RESEND_API_KEY and RESEND_FROM are read lazily here (not at import
    time) so that load_dotenv() in main.py always runs first.
    """
    api_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev")

    if not api_key:
        print(
            f"[Email] RESEND_API_KEY not configured — skipping email to {to_email}. "
            "Set RESEND_API_KEY in backend/.env to enable digest delivery."
        )
        return False

    subject = f"📚 Reading Coach Digest — {digest_date}"

    payload = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }

    print(f"[Email] Sending digest to {to_email} via Resend (from: {from_addr})...")

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
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
