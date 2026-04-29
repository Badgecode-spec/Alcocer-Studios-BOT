"""
imap_checker.py — Real Zoho IMAP reply detection.

Gracefully no-ops if ZOHO_IMAP_EMAIL or ZOHO_APP_PASSWORD are not set.
"""

import email
import imaplib
from email.header import decode_header

import config
import db
import telegram_bot
from logger import get_logger

log = get_logger(__name__)

# Opt-out keywords (Spanish + common English)
_OPTOUT_KEYWORDS = (
    "no me contactes",
    "no me interesa",
    "dar de baja",
    "quitar de",
    "no molestar",
    "unsubscribe",
    "cancelar",
    "remover",
    "no gracias",
    "no estamos interesados",
    "no queremos",
    "eliminar",
)


def is_optout(body: str) -> bool:
    """Return True if the email body contains an opt-out phrase."""
    body_lower = body.lower()
    return any(keyword in body_lower for keyword in _OPTOUT_KEYWORDS)


def _decode_value(value) -> str:
    """
    Decode an email header or body value that may be bytes or str.
    Returns a decoded string, falling back to empty string on error.
    """
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.decode("latin-1", errors="replace")
    return str(value) if value is not None else ""


def _decode_header_value(raw_header: str) -> str:
    """Decode a possibly encoded email header (e.g. =?UTF-8?...?) to plain text."""
    if not raw_header:
        return ""
    parts = decode_header(raw_header)
    decoded_parts = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(
                part.decode(charset or "utf-8", errors="replace")
            )
        else:
            decoded_parts.append(str(part))
    return "".join(decoded_parts)


def _extract_plain_text(msg: email.message.Message) -> str:
    """Walk a multipart message and return the first text/plain payload."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return _decode_value(payload) if isinstance(payload, bytes) else str(payload or "")
    else:
        payload = msg.get_payload(decode=True)
        return _decode_value(payload) if isinstance(payload, bytes) else str(msg.get_payload() or "")
    return ""


def run_imap_check() -> int:
    """
    Connect to Zoho IMAP, fetch UNSEEN messages, match to leads, and
    update their status.  Marks processed messages as read.

    Returns the count of emails processed (matched or skipped).
    Gracefully no-ops and returns 0 if credentials are not configured.
    """
    if not config.ZOHO_IMAP_EMAIL or not config.ZOHO_APP_PASSWORD:
        log.debug("imap_check skipped — ZOHO_IMAP_EMAIL or ZOHO_APP_PASSWORD not set")
        return 0

    processed = 0

    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    except imaplib.IMAP4.error as exc:
        log.error("imap_check connection failed: %s", exc)
        return 0
    except Exception as exc:
        log.error("imap_check unexpected connection error: %s", exc)
        return 0

    try:
        mail.login(config.ZOHO_IMAP_EMAIL, config.ZOHO_APP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            log.info("imap_check no unseen messages")
            mail.logout()
            return 0

        message_ids = data[0].split()
        log.info("imap_check unseen=%d", len(message_ids))

        for msg_id in message_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract From address
                from_header = msg.get("From", "")
                from_decoded = _decode_header_value(from_header)
                # Parse bare address from "Name <addr@host>" format
                from_addr = from_decoded
                if "<" in from_decoded and ">" in from_decoded:
                    from_addr = from_decoded.split("<")[1].split(">")[0].strip()
                from_addr = from_addr.strip().lower()

                # Extract subject
                subject = _decode_header_value(msg.get("Subject", ""))

                # Extract plain-text body
                body = _extract_plain_text(msg).strip()

                log.info(
                    "imap_check processing msg_id=%s from=%s subject=%r",
                    msg_id.decode(), from_addr, subject[:60],
                )

                # Mark as read regardless of match outcome
                mail.store(msg_id, "+FLAGS", "\\Seen")
                processed += 1

                # Try to match sender to a lead
                lead = db.get_lead_by_email(from_addr)
                if lead is None:
                    log.info("imap_check unknown_sender from=%s — skipping", from_addr)
                    continue

                lead_id = lead["id"]
                lead_name = lead["name"]

                if is_optout(body):
                    notes = f"Opt-out detected: {body[:200]}"
                    db.close_lead(lead_id, notes=notes)
                    log.info(
                        "imap_check opt_out lead_id=%d name=%r", lead_id, lead_name
                    )
                    telegram_bot.send_message(
                        f"🚫 <b>Opt-out recibido</b>\n\n"
                        f"<b>Negocio:</b> {lead_name}\n"
                        f"<b>Email:</b> {from_addr}\n"
                        f"<b>Mensaje:</b> {body[:200]}"
                    )
                else:
                    db.update_lead_replied(lead_id, notes=body[:200])
                    log.info(
                        "imap_check reply lead_id=%d name=%r", lead_id, lead_name
                    )
                    telegram_bot.notify_reply(lead_name, body[:300])

            except imaplib.IMAP4.error as exc:
                log.error("imap_check message processing IMAP error msg_id=%s: %s", msg_id, exc)
            except Exception as exc:
                log.error("imap_check message processing error msg_id=%s: %s", msg_id, exc)

    except imaplib.IMAP4.error as exc:
        log.error("imap_check auth/session error: %s", exc)
    except Exception as exc:
        log.error("imap_check unexpected error: %s", exc)
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    log.info("imap_check complete processed=%d", processed)
    return processed
