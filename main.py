import time
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

CDMX = timezone(timedelta(hours=-6))

load_dotenv()  # Must run before any config import

import config  # noqa: E402
import db  # noqa: E402
import emailer  # noqa: E402
import followups  # noqa: E402
import imap_checker  # noqa: E402
import leads  # noqa: E402
import messaging  # noqa: E402
import replies  # noqa: E402
import telegram_bot  # noqa: E402
from logger import get_logger, setup_logging  # noqa: E402


def run_outreach_cycle() -> int:
    """
    Send initial outreach emails to all 'new' leads.
    Returns count sent.
    """
    log = get_logger(__name__)

    # Only send outreach 7am–9pm CDMX, every day of the week
    now_cdmx = datetime.now(CDMX)
    if not (7 <= now_cdmx.hour < 21):
        log.info("outreach_cycle skipped — outside send window (now %02d:%02d CDMX)", now_cdmx.hour, now_cdmx.minute)
        return 0

    new_leads = db.get_leads_by_status("new")
    if not new_leads:
        log.info("outreach_cycle no new leads")
        return 0

    log.info("outreach_cycle candidates=%d", len(new_leads))
    sent = 0

    for lead in new_leads:
        if telegram_bot.is_paused():
            log.info("outreach_cycle paused via Telegram — stopping")
            break

        if not emailer.can_send_today():
            log.info("outreach_cycle daily cap reached — stopping")
            break

        email_data = messaging.build_outreach_email(
            name=lead["name"],
            website=lead["website"],
            category=lead["category"] or "",
        )
        success = emailer.send_email(
            to_email=lead["email"],
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead["id"],
            send_type="outreach",
        )
        if success:
            db.update_lead_outreach_sent(lead["id"], email_data["ai_line"])
            sent += 1
            log.info("outreach_sent lead_id=%d name=%r", lead["id"], lead["name"])
        else:
            log.warning("outreach_failed lead_id=%d — will retry next cycle", lead["id"])

    log.info("outreach_cycle sent=%d", sent)
    if sent > 0:
        telegram_bot.notify_outreach_batch(sent, db.count_sends_today())
    return sent


def run_cycle(fetch_leads: bool = False) -> None:
    """One full work cycle. Each step is isolated so a failure in one doesn't stop others."""
    log = get_logger(__name__)

    if telegram_bot.is_paused():
        log.info("cycle skipped — bot paused via Telegram")
        return

    log.info("=== cycle start (fetch_leads=%s) ===", fetch_leads)

    if fetch_leads:
        try:
            new_leads = leads.run_lead_fetch()
            log.info("cycle step=lead_fetch new=%d", new_leads)
        except Exception as exc:
            log.error("cycle step=lead_fetch FAILED: %s", exc)
    else:
        log.info("cycle step=lead_fetch skipped (already ran today)")

    try:
        outreach_sent = run_outreach_cycle()
        log.info("cycle step=outreach sent=%d", outreach_sent)
    except Exception as exc:
        log.error("cycle step=outreach FAILED: %s", exc)

    try:
        followups_sent = followups.run_followup_cycle()
        log.info("cycle step=followup sent=%d", followups_sent)
    except Exception as exc:
        log.error("cycle step=followup FAILED: %s", exc)

    try:
        replies_processed = replies.run_reply_cycle()
        log.info("cycle step=replies processed=%d", replies_processed)
    except Exception as exc:
        log.error("cycle step=replies FAILED: %s", exc)

    try:
        replies_from_inbox = imap_checker.run_imap_check()
        log.info("cycle step=imap_check processed=%d", replies_from_inbox)
    except Exception as exc:
        log.error("cycle step=imap_check FAILED: %s", exc)

    log.info("=== cycle end ===")


def main() -> None:
    setup_logging(config.LOG_FILE)
    log = get_logger(__name__)

    db.init_db()

    # Start Telegram polling in background thread
    telegram_bot.start_polling()

    log.info("=== Alcocer Studios BOT starting ===")
    log.info(
        "DB=%s | interval=%ds | daily_limit=%d | followup_days=%d | reply_sim=%.0f%%",
        config.DB_PATH,
        config.LOOP_INTERVAL_SECONDS,
        config.DAILY_SEND_LIMIT,
        config.FOLLOWUP_DAYS,
        config.REPLY_SIMULATION_CHANCE * 100,
    )

    telegram_bot.send_message(
        "🤖 <b>Alcocer Studios BOT iniciado</b>\n"
        f"Enviando hasta {config.DAILY_SEND_LIMIT} correos/día\n"
        "Usa /start para ver los comandos disponibles."
    )

    try:
        while True:
            # Use CDMX calendar date so "today" matches Mexico City, not UTC
            today = datetime.now(CDMX).strftime("%Y-%m-%d")

            telegram_bot.check_daily_summary()

            # Read fetch date from DB so it survives bot restarts/redeploys
            last_lead_fetch_date = db.get_state("last_lead_fetch_date")
            should_fetch = last_lead_fetch_date != today
            run_cycle(fetch_leads=should_fetch)

            if should_fetch:
                db.set_state("last_lead_fetch_date", today)

            log.info("sleeping %ds until next cycle", config.LOOP_INTERVAL_SECONDS)
            time.sleep(config.LOOP_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log.info("=== BOT stopped by user ===")
        telegram_bot.send_message("⚠️ Bot detenido manualmente.")


if __name__ == "__main__":
    main()
