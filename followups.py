import config
import db
import emailer
import messaging
from logger import get_logger

log = get_logger(__name__)


def run_followup_cycle() -> int:
    """
    Send follow-up emails to leads that have been contacted but not replied
    after FOLLOWUP_DAYS days.
    Returns count of follow-ups sent.
    """
    overdue = db.get_leads_due_for_followup(config.FOLLOWUP_DAYS)
    if not overdue:
        log.info("followup_cycle no overdue leads")
        return 0

    log.info("followup_cycle overdue=%d", len(overdue))
    sent = 0

    for lead in overdue:
        if not emailer.can_send_today():
            log.info("followup_cycle daily cap reached — stopping")
            break

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
