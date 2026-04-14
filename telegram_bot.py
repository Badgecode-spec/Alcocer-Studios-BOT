import threading
import time
from datetime import datetime, timezone, timedelta

import requests

from logger import get_logger

log = get_logger(__name__)

# Mexico City = UTC-6
CDMX = timezone(timedelta(hours=-6))

_paused = False
_last_update_id = 0
_chat_id: str = ""


def _base_url() -> str:
    import config
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def _get_chat_id() -> str:
    global _chat_id
    if _chat_id:
        return _chat_id
    import config
    _chat_id = config.TELEGRAM_CHAT_ID
    return _chat_id


def send_message(text: str) -> None:
    """Send a message to the configured Telegram chat."""
    chat_id = _get_chat_id()
    if not chat_id:
        return
    try:
        requests.post(
            f"{_base_url()}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as exc:
        log.warning("telegram send_message failed: %s", exc)


def notify_reply(lead_name: str, reply_preview: str) -> None:
    """Called when a lead replies — sends instant notification."""
    send_message(
        f"💬 <b>Nueva respuesta de lead</b>\n\n"
        f"<b>Negocio:</b> {lead_name}\n"
        f"<b>Mensaje:</b> {reply_preview[:200]}\n\n"
        f"Revisa tu correo de Zoho para responder."
    )


def notify_outreach_sent(lead_name: str, email: str) -> None:
    """Called when an outreach email is sent."""
    send_message(
        f"📧 <b>Correo enviado</b>\n"
        f"<b>Negocio:</b> {lead_name}\n"
        f"<b>Email:</b> {email}"
    )


def send_daily_summary() -> None:
    """Send a daily stats summary at 9am CDMX."""
    import db
    today_sent = db.count_sends_today()
    new_leads = len(db.get_leads_by_status("new"))
    contacted = len(db.get_leads_by_status("contacted"))
    followup = len(db.get_leads_by_status("followup"))
    replied = len(db.get_leads_by_status("replied"))

    send_message(
        f"📊 <b>Resumen del día — Alcocer Studios BOT</b>\n\n"
        f"📧 Correos enviados hoy: <b>{today_sent}</b>\n"
        f"🆕 Leads nuevos en cola: <b>{new_leads}</b>\n"
        f"📬 Contactados: <b>{contacted}</b>\n"
        f"🔁 En seguimiento: <b>{followup}</b>\n"
        f"✅ Respondieron: <b>{replied}</b>\n\n"
        f"{'⏸ Bot en PAUSA' if _paused else '▶️ Bot activo'}"
    )


def _handle_command(text: str, from_chat_id: str) -> None:
    """Process an incoming command from Telegram."""
    global _paused, _chat_id

    # Auto-register chat_id on first contact
    if not _chat_id:
        _chat_id = str(from_chat_id)
        import config
        log.info("telegram chat_id auto-registered: %s", _chat_id)

    cmd = text.strip().lower().split()[0]

    if cmd == "/start":
        send_message(
            f"👋 <b>Hola Pablo!</b>\n\n"
            f"Soy el bot de Alcocer Studios. Estoy corriendo 24/7.\n\n"
            f"<b>Comandos disponibles:</b>\n"
            f"/stats — Estadísticas de hoy\n"
            f"/leads — Últimos leads encontrados\n"
            f"/replies — Leads que respondieron\n"
            f"/pause — Pausar envío de correos\n"
            f"/resume — Reanudar envío\n"
            f"/status — Ver estado del bot\n\n"
            f"Tu Chat ID: <code>{from_chat_id}</code>"
        )

    elif cmd == "/stats":
        send_daily_summary()

    elif cmd == "/leads":
        import db
        leads = db.get_leads_by_status("new")[-5:]
        if not leads:
            send_message("No hay leads nuevos en cola.")
        else:
            lines = [f"🆕 <b>Últimos {len(leads)} leads nuevos:</b>\n"]
            for l in reversed(leads):
                lines.append(f"• <b>{l['name']}</b>\n  {l['email']}\n  {l['website']}")
            send_message("\n".join(lines))

    elif cmd == "/replies":
        import db
        replied = db.get_leads_by_status("replied")[-5:]
        if not replied:
            send_message("Ningún lead ha respondido aún.")
        else:
            lines = [f"✅ <b>Últimos {len(replied)} que respondieron:</b>\n"]
            for l in reversed(replied):
                lines.append(f"• <b>{l['name']}</b>\n  {l['notes'] or 'Sin notas'}")
            send_message("\n".join(lines))

    elif cmd == "/pause":
        _paused = True
        send_message("⏸ <b>Bot pausado.</b> No se enviarán más correos hasta que uses /resume.")

    elif cmd == "/resume":
        _paused = False
        send_message("▶️ <b>Bot reanudado.</b> Volviendo a enviar correos normalmente.")

    elif cmd == "/status":
        state = "⏸ <b>PAUSADO</b>" if _paused else "▶️ <b>ACTIVO</b>"
        send_message(f"Estado del bot: {state}")

    else:
        send_message("Comando no reconocido. Usa /start para ver los comandos disponibles.")


def _poll_loop() -> None:
    """Long-poll Telegram for incoming messages. Runs in a daemon thread."""
    global _last_update_id
    import config

    if not config.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — polling disabled")
        return

    log.info("telegram polling started")

    while True:
        try:
            resp = requests.get(
                f"{_base_url()}/getUpdates",
                params={"offset": _last_update_id + 1, "timeout": 30},
                timeout=40,
            )
            if resp.status_code != 200:
                time.sleep(5)
                continue

            updates = resp.json().get("result", [])
            for update in updates:
                _last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                from_chat_id = msg.get("chat", {}).get("id", "")
                if text and text.startswith("/"):
                    _handle_command(text, str(from_chat_id))

        except Exception as exc:
            log.warning("telegram poll error: %s", exc)
            time.sleep(10)


def start_polling() -> threading.Thread:
    """Start the Telegram polling thread as a daemon."""
    t = threading.Thread(target=_poll_loop, daemon=True, name="telegram-poll")
    t.start()
    return t


def is_paused() -> bool:
    """Returns True if the bot has been paused via /pause command."""
    return _paused


def check_daily_summary(last_summary_date: str) -> str:
    """
    Call this each cycle. Sends daily summary at 9am CDMX if not already sent today.
    Pass in last_summary_date (YYYY-MM-DD string), returns updated date.
    """
    now = datetime.now(CDMX)
    today = now.strftime("%Y-%m-%d")
    if now.hour == 9 and last_summary_date != today:
        send_daily_summary()
        return today
    return last_summary_date
