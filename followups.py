from datetime import datetime, timezone, timedelta

import config
import db
import emailer
import messaging
from logger import get_logger

log = get_logger(__name__)

CDMX = timezone(timedelta(hours=-6))

_FOLLOWUP_START_HOUR = 9
_FOLLOWUP_END_HOUR = 21
_MAX_FOLLOWUPS = 3


def run_followup_cycle() -> int:
    """
    Send the next follow-up to every overdue lead (up to 3 rounds total).
    Follow-ups are NOT counted against the daily outreach cap.
    After the 3rd successful follow-up the lead is auto-closed.
    Only runs between 9am–9pm CDMX.
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
        followup_count = lead["followup_count"]  # 0, 1, or 2 prior follow-ups
        followup_num = followup_count + 1         # which round we're sending now (1, 2, or 3)

        email_data = messaging.build_followup_email(lead["name"], followup_num)
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
            log.info(
                "followup_sent lead_id=%d name=%r round=%d",
                lead["id"], lead["name"], followup_num,
            )
            if followup_num >= _MAX_FOLLOWUPS:
                db.close_lead(lead["id"], notes=f"{_MAX_FOLLOWUPS} follow-ups sent — no reply")
                log.info("followup_closed lead_id=%d — max rounds reached", lead["id"])
        else:
            log.warning("followup_failed lead_id=%d round=%d — will retry", lead["id"], followup_num)

    log.info("followup_cycle sent=%d", sent)
    return sent
