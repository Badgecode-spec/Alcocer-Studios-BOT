from datetime import datetime, timezone, timedelta

import config
import db
import emailer
import messaging
from logger import get_logger

log = get_logger(__name__)

CDMX = timezone(timedelta(hours=-6))

# Follow-ups send between 9am and 9pm CDMX — never at night or early morning
_FOLLOWUP_START_HOUR = 9
_FOLLOWUP_END_HOUR = 21


def run_followup_cycle() -> int:
    """
    Send follow-up emails to leads that have been contacted but not replied
    after FOLLOWUP_DAYS days.
    Follow-ups are NOT counted against the daily outreach cap.
    Returns count of follow-ups sent.
    """
    now_cdmx = datetime.now(CDMX)
    if not (_FOLLOWUP_START_HOUR <= now_cdmx.hour < _FOLLOWUP_END_HOUR):
        log.info(
            "followup_cycle skipped — outside send window (now %02d:%02d CDMX)",
            now_cdmx.hour, now_cdmx.minute,
        )
        return 0

    overdue = db.get_leads_due_for_followup(config.FOLLOWUP_DAYS)
    if not overdue:
        log.info("followup_cycle no overdue leads")
        return 0

    log.info("followup_cycle overdue=%d", len(overdue))
    sent = 0

    for lead in overdue:
        email_data = messaging.build_followup_email(lead["name"])
        success = emailer.send_email(
            to_email=lead["email"],
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead["id"],
            send_type="followup",
        )
        if success:
            db.update_lead_followup_sent(lead["id"])
            sent += 1
            log.info("followup_sent lead_id=%d name=%r", lead["id"], lead["name"])
        else:
            log.warning("followup_failed lead_id=%d — will retry next cycle", lead["id"])

    log.info("followup_cycle sent=%d", sent)
    return sent
