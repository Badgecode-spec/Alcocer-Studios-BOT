import time

import requests

import config
import db
from logger import get_logger

log = get_logger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


def can_send_today() -> bool:
    """Returns True if daily send cap has not been reached."""
    count = db.count_sends_today()
    if count >= config.DAILY_SEND_LIMIT:
        log.info("Daily send limit reached (%d/%d) — skipping", count, config.DAILY_SEND_LIMIT)
        return False
    return True


def send_email(
    to_email: str,
    subject: str,
    body: str,
    lead_id: int,
    send_type: str = "outreach",
) -> bool:
    """
    Send a plain-text email via Resend API.
    Returns True on success, False on any failure (never raises).
    """
    # If multiple addresses, take the first
    to_email = to_email.split(",")[0].strip()

    payload = {
        "from": f"{config.FROM_NAME} <{config.FROM_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(_RESEND_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code in (200, 201):
            db.log_send(lead_id, send_type, True)
            log.info("email_sent lead_id=%d type=%s to=%s", lead_id, send_type, to_email)
            time.sleep(config.EMAIL_SEND_DELAY)
            return True
        else:
            error_msg = resp.text[:200]
            db.log_send(lead_id, send_type, False, error_msg)
            log.error(
                "email_failed lead_id=%d type=%s status=%d body=%s",
                lead_id, send_type, resp.status_code, error_msg,
            )
            return False
    except Exception as exc:
        error_msg = str(exc)[:200]
        db.log_send(lead_id, send_type, False, error_msg)
        log.error("email_exception lead_id=%d type=%s error=%s", lead_id, send_type, error_msg)
        return False
