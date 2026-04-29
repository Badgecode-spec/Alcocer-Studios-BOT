import random

import anthropic

import config
import db
import emailer
from logger import get_logger

log = get_logger(__name__)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# --- Reply simulation pools ---

SIMPLE_REPLY_TEMPLATES = [
    "Sí, me interesa",
    "¿Cuánto cuesta?",
    "Mándame más información",
    "¿Cómo funciona?",
    "Okay, ¿cuándo podemos hablar?",
]

COMPLEX_REPLY_TEMPLATES = [
    "Ya tenemos una agencia que nos lleva el sitio, ¿qué nos ofreces diferente?",
    "No tenemos presupuesto ahorita, ¿tienen planes de pago o algo accesible?",
    "¿Pueden mostrarme ejemplos de trabajos anteriores en mi industria?",
    "¿En cuánto tiempo tienen el sitio listo? Tenemos prisa porque se acerca temporada alta.",
]

# --- Simple response template ---

_SIMPLE_RESPONSE = (
    "Hola {name}, gracias por responder. "
    "Con gusto te cuento más. ¿Tienes 15 minutos esta semana para una llamada rápida? "
    "https://alcocerstudios.com"
)

_FALLBACK_COMPLEX_RESPONSE = (
    "Hola {name}, gracias por tu mensaje. "
    "Entiendo tu situación y me gustaría platicar contigo para ver cómo podemos ayudarte. "
    "¿Tienes unos minutos esta semana? https://alcocerstudios.com"
)


def simulate_reply(lead_id: int) -> dict | None:
    """
    Randomly decide if a lead has replied.
    Returns {"lead_id": int, "reply_text": str, "is_complex": bool} or None.
    """
    if random.random() >= config.REPLY_SIMULATION_CHANCE:
        return None

    # 70% simple, 30% complex
    if random.random() < 0.70:
        reply_text = random.choice(SIMPLE_REPLY_TEMPLATES)
        is_complex = False
    else:
        reply_text = random.choice(COMPLEX_REPLY_TEMPLATES)
        is_complex = True

    return {"lead_id": lead_id, "reply_text": reply_text, "is_complex": is_complex}


def classify_reply(reply_text: str) -> bool:
    """
    Returns True if reply is complex (needs Sonnet).
    Heuristic: >15 words OR matches a known complex template.
    """
    if reply_text in COMPLEX_REPLY_TEMPLATES:
        return True
    return len(reply_text.split()) > 15


def generate_complex_response(reply_text: str, lead_name: str) -> str:
    """Call Claude Sonnet to draft a reply. Falls back to template on error."""
    prompt = (
        f"Cliente: {lead_name}. Su respuesta: {reply_text}. "
        "Escribe tu respuesta directa y amable en español."
    )
    try:
        response = _client.messages.create(
            model=config.SONNET_MODEL,
            max_tokens=config.SONNET_MAX_TOKENS,
            system=(
                "Eres un representante de ventas amable de Alcocer Studios, "
                "una agencia de diseño web en México. "
                "Responde en español, máximo 3 oraciones, de forma natural y directa."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        reply = response.content[0].text.strip()
        log.info("sonnet_call lead=%r reply_tokens=%d", lead_name, len(reply.split()))
        return reply
    except Exception as exc:
        log.warning("Sonnet API error for %r: %s — using fallback", lead_name, exc)
        return _FALLBACK_COMPLEX_RESPONSE.format(name=lead_name or "amigo")


def build_reply_email(lead_name: str, reply_text: str) -> dict:
    """
    Returns {"subject": str, "body": str, "used_sonnet": bool}.
    Routes to Sonnet only if reply is classified as complex.
    """
    display_name = lead_name or "amigo"
    is_complex = classify_reply(reply_text)

    if is_complex:
        body = generate_complex_response(reply_text, display_name)
        used_sonnet = True
    else:
        body = _SIMPLE_RESPONSE.format(name=display_name)
        used_sonnet = False

    return {
        "subject": f"Re: Duda para {display_name}",
        "body": body,
        "used_sonnet": used_sonnet,
    }


def run_reply_cycle() -> int:
    """
    Reply simulation — only runs if REPLY_SIMULATION_CHANCE > 0 (testing only).
    In production this should be 0 so no fake emails go out to real leads.
    """
    if config.REPLY_SIMULATION_CHANCE <= 0:
        return 0

    candidates = db.get_leads_by_status("contacted") + db.get_leads_by_status("followup")
    if not candidates:
        log.info("reply_cycle no candidates")
        return 0

    processed = 0

    for lead in candidates:
        simulated = simulate_reply(lead["id"])
        if simulated is None:
            continue

        reply_text = simulated["reply_text"]
        log.info(
            "reply_simulated lead_id=%d is_complex=%s text=%r",
            lead["id"], simulated["is_complex"], reply_text[:60],
        )

        email_data = build_reply_email(lead["name"], reply_text)
        success = emailer.send_email(
            to_email=lead["email"],
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead["id"],
            send_type="reply",
        )
        if success:
            db.update_lead_replied(lead["id"], notes=f"Reply: {reply_text[:100]}")
            processed += 1
            log.info(
                "reply_sent lead_id=%d used_sonnet=%s",
                lead["id"], email_data["used_sonnet"],
            )

    log.info("reply_cycle processed=%d", processed)
    return processed
